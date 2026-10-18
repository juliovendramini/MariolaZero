"""Controle da simulação: thread de física, relógio virtual, processo do aluno, LoP."""

import collections
import json
import os
import subprocess
import sys
import threading
import time

from . import mapa as M
from .fisica import Mundo, pino_num
from .juiz import Juiz
from .servidor import Servidor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Simulacao:
    def __init__(self, mapa, cfg, programa=None, porta=0, semente=None):
        self.cfg = cfg
        self.programa = os.path.abspath(programa) if programa else None
        self.mundo = Mundo(mapa, cfg, semente)
        self.juiz = Juiz(self.mundo)
        self.juiz.on_lop = self._lop
        self.juiz.on_fim = self._fim
        self.fator = 1.0
        self.pausado = False
        self.pedido_parar = False
        self.epoca = time.time()
        self.proc = None
        self.saida = collections.deque(maxlen=300)
        self.modo_lop = 'reiniciar'          # 'reiniciar' (desliga/liga) ou 'botao' (só aperta o botão)
        self.auto_botao = True              # aperta o botão de início sozinho ao iniciar o programa
        self.em_lop = False
        self.servidor = Servidor(self, porta)
        self._t_ref = 0.0
        self._real_ref = time.perf_counter()
        self.passos_por_seg = 0
        self.rodando = True
        self.th = threading.Thread(target=self._loop_fisica, daemon=True)
        self.th.start()

    # ------------------------------------------------------------------ relógio
    def fator_efetivo(self):
        return 0.0 if self.pausado else self.fator

    def _rebase(self):
        self._t_ref = self.mundo.t
        self._real_ref = time.perf_counter()

    def set_fator(self, f):
        with self.mundo.lock:
            self._rebase()
            self.fator = f

    def set_pausa(self, p):
        with self.mundo.lock:
            self._rebase()
            self.pausado = p

    def _loop_fisica(self):
        dt = Mundo.DT
        cont = 0
        t_cont = time.perf_counter()
        while self.rodando:
            agora = time.perf_counter()
            alvo = self._t_ref + (agora - self._real_ref) * self.fator_efetivo()
            n = 0
            if alvo - self.mundo.t > 0.25:      # não dá conta: desacelera o relógio
                with self.mundo.lock:
                    self._t_ref = self.mundo.t
                    self._real_ref = agora
                    alvo = self.mundo.t + dt
            while self.mundo.t + dt <= alvo and n < 64:
                with self.mundo.lock:
                    self.mundo.passo(dt)
                    if not self.em_lop:
                        self.juiz.atualiza(dt)
                n += 1
            cont += n
            if agora - t_cont > 1.0:
                self.passos_por_seg = cont / (agora - t_cont)
                cont = 0
                t_cont = agora
            time.sleep(0.001 if n == 0 else 0)

    # ------------------------------------------------------------------ programa
    def programa_rodando(self):
        return self.proc is not None and self.proc.poll() is None

    def iniciar_programa(self):
        if not self.programa or self.programa_rodando():
            return
        self.pedido_parar = False
        self.mundo.oled = None              # ligar o robô: tela apagada, teclado com os LEDs no estado inicial
        self.mundo.teclado_leds = 0x0F
        env = dict(os.environ)
        env['SIM_PORTA'] = str(self.servidor.porta)
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        cmd = [sys.executable, '-u', os.path.join(RAIZ, 'rodar.py'), self.programa]
        kw = {}
        if os.name == 'nt':
            kw['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        self.proc = subprocess.Popen(cmd, env=env, cwd=os.path.dirname(self.programa),
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, **kw)
        self._log('---- programa iniciado ----')
        threading.Thread(target=self._le_saida, args=(self.proc,), daemon=True).start()
        if self.auto_botao:
            threading.Timer(1.5, self.apertar_botao).start()

    def _le_saida(self, proc):
        for linha in iter(proc.stdout.readline, b''):
            self._log(linha.decode('utf-8', 'replace').rstrip('\n'))
        proc.wait()
        self._log(f'---- programa terminou (código {proc.returncode}) ----')

    def _log(self, s):
        self.saida.append(s)
        try:
            print('[robô] ' + s, flush=True)
        except Exception:
            pass

    def parar_programa(self, espera=2.0):
        if not self.programa_rodando():
            return
        self.pedido_parar = True          # o processo recebe KeyboardInterrupt
        t0 = time.time()
        while self.programa_rodando() and time.time() - t0 < espera:
            time.sleep(0.05)
        if self.programa_rodando():
            self.proc.kill()
            self.proc.wait()
        self.pedido_parar = False
        with self.mundo.lock:
            self.mundo.para_tudo()

    def reiniciar_programa(self):
        self.parar_programa()
        self.iniciar_programa()

    def apertar_botao(self, dur=0.4):
        bi = self.cfg.get('botao_inicio')
        if not bi:
            return
        p = pino_num(bi['pino'])
        self.mundo.botoes_gui.add(p)
        threading.Timer(dur / max(self.fator, 0.1), lambda: self.mundo.botoes_gui.discard(p)).start()

    # ------------------------------------------------------------------ rodada
    def nova_rodada(self):
        """Para o programa, volta o robô para o início e zera o placar."""
        self.parar_programa()
        with self.mundo.lock:
            m = self.mundo.mapa
            x, y = m.centro(*m.inicio)
            self.mundo.posicionar(x, y, M.ANGULO_DIR[m.inicio_dir])
            self.mundo.reset_rodada()
            self.juiz.reset()
        if self.programa:
            pasta = os.path.dirname(self.programa)
            for nome in self.cfg.get('arquivos_rodada', []):
                try:
                    os.remove(os.path.join(pasta, nome))
                    self._log(f'(apagado {nome} para a nova rodada)')
                except FileNotFoundError:
                    pass

    def iniciar_rodada(self):
        with self.mundo.lock:
            self.juiz.iniciar()
            self.mundo.giro_reset_z()
        self.iniciar_programa()

    def _fim(self, motivo):
        threading.Thread(target=self.parar_programa, daemon=True).start()

    def _lop(self, motivo):
        """Chamado pelo juiz (dentro da trava do mundo)."""
        if self.em_lop:
            return
        self.em_lop = True
        threading.Thread(target=self._executa_lop, daemon=True).start()

    def _executa_lop(self):
        reinicia = self.modo_lop == 'reiniciar'
        if reinicia:
            self.parar_programa(espera=0.5)
        with self.mundo.lock:
            self.mundo.para_tudo()
            l, c = self.juiz.ultimo_cp
            x, y = self.mundo.mapa.centro(l, c)
            self.mundo.posicionar(x, y, self.juiz.dir_cp)
            self.juiz.reposicionado()
            self.em_lop = False
        if reinicia:
            self.iniciar_programa()
        else:
            threading.Timer(0.8, self.apertar_botao).start()

    def lop_manual(self):
        with self.mundo.lock:
            if self.juiz.ativo and not self.juiz.fim:
                self.juiz.falta_progresso('declarado pelo capitão')
            else:
                self._lop('manual')

    def encerrar(self):
        self.parar_programa(espera=1.0)
        self.rodando = False
        self.servidor.rodando = False
        try:
            self.servidor.sock.close()
        except OSError:
            pass


def carregar_cfg(caminho):
    with open(caminho, 'r', encoding='utf-8') as f:
        return json.load(f)
