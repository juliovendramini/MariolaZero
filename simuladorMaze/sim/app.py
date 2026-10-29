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
        self._auto_pendente = False
        # input() do programa: no robô ele espera o Enter do terminal (ssh); aqui, o da janela
        self.entrada = None                 # texto do input() que está esperando (None = nenhum)
        self._resposta_entrada = None
        self.enter_automatico = False       # sem janela: responde o input() na hora
        self.servidor = Servidor(self, porta)
        self._t_ref = 0.0
        self._real_ref = time.perf_counter()
        self.passos_por_seg = 0
        # relógio: t_virtual é o tempo que o programa do aluno vê; a física (mundo.t) anda em
        # passos de DT e fica sempre em [t_virtual - DT, t_virtual]
        self.t_virtual = 0.0
        self.sincronizado = True     # programa e física andam juntos (mesmo resultado em 1x e 4x)
        self.sinc_ativo = False      # há um programa conectado no modo sincronizado
        self._alvo_sinc = 0.0
        self._cv = threading.Condition()
        self._agenda = []            # (t_virtual, função): eventos no tempo simulado
        self._espera_conexao = None  # programa iniciado e ainda não conectou (física parada)
        self._lop_ate = None         # LoP: relógio parado até o programa reiniciado conectar
        self.vel_real = 0.0
        self.rodando = True
        self.th = threading.Thread(target=self._loop_fisica, daemon=True)
        self.th.start()

    # ------------------------------------------------------------------ relógio
    def fator_efetivo(self):
        return 0.0 if self.pausado else self.fator

    def _rebase(self):
        self._t_ref = self.t_virtual
        self._real_ref = time.perf_counter()

    def set_fator(self, f):
        with self._cv:
            self._rebase()
            self.fator = f

    def set_pausa(self, p):
        with self._cv:
            self._rebase()
            self.pausado = p
            self._cv.notify_all()

    def _permitido(self, agora):
        """Até onde o relógio pode ir agora sem passar da velocidade escolhida (1x, 4x...)."""
        return self._t_ref + (agora - self._real_ref) * self.fator_efetivo()

    def avanca_sinc(self, ate=None, livre=False):
        """Pedido do programa do aluno (modo sincronizado): avança o relógio até 'ate' (todas
        as threads dele estão dormindo) ou, com livre=True, o quanto o tempo real permitir
        (alguma thread está calculando). Volta quando a física chegou lá."""
        with self._cv:
            if livre:
                alvo = max(self.t_virtual, min(self._permitido(time.perf_counter()), self.t_virtual + 0.05))
            else:
                alvo = float(ate)
            self._alvo_sinc = max(self._alvo_sinc, alvo)
            self._cv.notify_all()
            dt = Mundo.DT
            while self.rodando and self.sinc_ativo and (
                    self.t_virtual < alvo - 1e-9 or self.mundo.t + dt <= self.t_virtual + 1e-9):
                self._cv.wait(0.05)
            return self.t_virtual

    def agenda(self, atraso, fn):
        """Executa fn depois de 'atraso' segundos de tempo simulado."""
        with self._cv:
            self._agenda.append((self.mundo.t + atraso, fn))

    def _roda_agenda(self):
        with self._cv:
            t = self.mundo.t + 1e-9
            prontos = [e for e in self._agenda if e[0] <= t]
            self._agenda = [e for e in self._agenda if e[0] > t]
        for _, fn in sorted(prontos, key=lambda e: e[0]):
            try:
                fn()
            except Exception as e:
                self._log(f'[simulador] erro na agenda: {e}')

    def sinc_inicio(self):
        with self._cv:
            self.sinc_ativo = True
            self._espera_conexao = None
            self._lop_ate = None
            self._alvo_sinc = self.t_virtual
            self._rebase()
            self._cv.notify_all()
        if self.auto_botao and self._auto_pendente:
            self._auto_pendente = False
            self.agenda(1.5, self.apertar_botao)

    def sinc_fim(self):
        with self._cv:
            self.sinc_ativo = False
            self._espera_conexao = None
            self._rebase()
            self._cv.notify_all()

    def _loop_fisica(self):
        dt = Mundo.DT
        cont = 0
        t_cont = time.perf_counter()
        while self.rodando:
            agora = time.perf_counter()
            with self._cv:
                if self._lop_ate is not None and agora > self._lop_ate:
                    self._lop_ate = None             # o programa não voltou depois do LoP
                    self._rebase()
                if self._espera_conexao is not None and agora > self._espera_conexao:
                    self.sinc_ativo = False          # o programa não conectou (erro antes de importar as libs)
                    self._espera_conexao = None
                    self._rebase()
                permitido = self._permitido(agora)
                if self._lop_ate is not None:
                    # LoP com reinício do programa: relógio parado até o programa novo conectar
                    self._t_ref = self.t_virtual
                    self._real_ref = agora
                    alvo = self.t_virtual
                elif self.sinc_ativo:
                    # sem burst depois de o programa ficar calculando: no máximo 50 ms de folga
                    if permitido > self.t_virtual + 0.05:
                        self._t_ref = self.t_virtual + 0.05
                        self._real_ref = agora
                        permitido = self.t_virtual + 0.05
                    alvo = min(self._alvo_sinc, permitido)
                else:
                    if permitido - self.t_virtual > 0.25:      # não dá conta: desacelera o relógio
                        self._t_ref = self.t_virtual
                        self._real_ref = agora
                        permitido = self.t_virtual
                    alvo = permitido
                if alvo > self.t_virtual:
                    self.t_virtual = alvo
                tv = self.t_virtual
            n = 0
            with self._cv:
                prox = min((e[0] for e in self._agenda), default=None)
            while n < 64:
                w = self.mundo
                with w.lock:
                    if w is not self.mundo or w.t + dt > tv + 1e-9:
                        break
                    w.passo(dt)
                    if not self.em_lop:
                        self.juiz.atualiza(dt)
                n += 1
                if self._lop_ate is not None:
                    break                       # LoP com reinício: relógio parou aqui
                if prox is not None and w.t >= prox - 1e-9:
                    break                       # agenda roda exatamente neste passo
            if self._agenda:
                self._roda_agenda()             # botão etc. no tempo simulado certo
            with self._cv:
                if self.sinc_ativo and (n < 64 or prox is not None):
                    self._cv.notify_all()       # quem pediu avanca_sinc vê o tempo novo
            cont += n
            if agora - t_cont > 1.0:
                self.passos_por_seg = cont / (agora - t_cont)
                # velocidade que o PC está conseguindo de fato (tempo simulado / tempo real)
                self.vel_real = max(0.0, cont * dt / (agora - t_cont))
                cont = 0
                t_cont = agora
            if n == 0:
                with self._cv:
                    if (self.sinc_ativo or self._lop_ate is not None) and self._alvo_sinc <= self.t_virtual:
                        self._cv.wait(0.002)    # nada pedido: espera o programa
                        continue
                time.sleep(0.0005 if self.sinc_ativo else 0.001)

    # ------------------------------------------------------------------ programa
    def programa_rodando(self):
        return self.proc is not None and self.proc.poll() is None

    def iniciar_programa(self):
        if not self.programa or self.programa_rodando():
            return
        self.pedido_parar = False
        self.entrada = None
        self.mundo.oled = None              # ligar o robô: tela apagada, teclado com os LEDs no estado inicial
        self.mundo.teclado_leds = 0x0F
        env = dict(os.environ)
        env['SIM_PORTA'] = str(self.servidor.porta)
        env['PYTHONUNBUFFERED'] = '1'
        env['PYTHONIOENCODING'] = 'utf-8'
        if self.sincronizado:
            # o robô "liga" sem gastar tempo simulado: a física espera o programa conectar
            with self._cv:
                self.sinc_ativo = True
                self._alvo_sinc = self.t_virtual
                self._espera_conexao = time.perf_counter() + 15.0
            self._auto_pendente = True
        cmd = [sys.executable, '-u', os.path.join(RAIZ, 'rodar.py'), self.programa]
        kw = {}
        if os.name == 'nt':
            kw['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        self.proc = subprocess.Popen(cmd, env=env, cwd=os.path.dirname(self.programa),
                                     stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                     stdin=subprocess.DEVNULL, **kw)
        self._log('---- programa iniciado ----')
        threading.Thread(target=self._le_saida, args=(self.proc,), daemon=True).start()
        if not self.sincronizado and self.auto_botao:
            threading.Timer(1.5, self.apertar_botao).start()

    def _le_saida(self, proc):
        for linha in iter(proc.stdout.readline, b''):
            # no Windows o print do programa termina em \r\n (o \r virava um quadradinho no console);
            # um \r no meio (barra de progresso) deixa só o que foi escrito por último
            self._log(linha.decode('utf-8', 'replace').rstrip('\r\n').split('\r')[-1])
        proc.wait()
        if self.proc is proc:
            self.entrada = None
        self._log(f'---- programa terminou (código {proc.returncode}) ----')
        if self.proc is proc or self.proc is None or self.proc.poll() is not None:
            self.sinc_fim()

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

    def pede_entrada(self, prompt):
        """O programa chamou input(prompt). Devolve a resposta se já houver (sem janela)."""
        if self.enter_automatico:
            self._log(f'[simulador] input({prompt!r}): Enter automático (sem janela)')
            return ''
        self._resposta_entrada = None
        self.entrada = prompt
        return None

    def responde_entrada(self, texto=''):
        """Enter na janela: libera o input() que está esperando."""
        if self.entrada is None:
            return
        self._resposta_entrada = texto
        self.entrada = None

    def le_resposta_entrada(self):
        r, self._resposta_entrada = self._resposta_entrada, None
        return r

    def reiniciar_programa(self):
        self.parar_programa()
        self.iniciar_programa()

    def apertar_botao(self, dur=0.4):
        bi = self.cfg.get('botao_inicio')
        if not bi:
            return
        p = pino_num(bi['pino'])
        self.mundo.botoes_gui.add(p)
        mundo = self.mundo
        self.agenda(dur, lambda: mundo.botoes_gui.discard(p))

    # ------------------------------------------------------------------ rodada
    def nova_rodada(self):
        """Para o programa, volta o robô para o início e zera o placar."""
        self.parar_programa()
        with self.mundo.lock:
            with self._cv:
                # rodada nova começa no tempo 0: mesma semente + mesmo programa = mesma rodada
                self._agenda = []
                self.mundo.t = 0.0
                self.t_virtual = 0.0
                self._alvo_sinc = 0.0
                self._rebase()
                if self.sincronizado:
                    # relógio parado até o programa subir (ou 3 s reais, se ninguém iniciar)
                    self.sinc_ativo = True
                    self._espera_conexao = time.perf_counter() + 3.0
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
        reinicia = self.modo_lop == 'reiniciar' and self.programa_rodando()
        if self.sincronizado:
            # no modo sincronizado o robô volta ao checkpoint na hora (tempo simulado exato)
            if reinicia:
                with self._cv:
                    # relógio para exatamente neste passo (ninguém viu o tempo além dele ainda)
                    self._lop_ate = time.perf_counter() + 15.0
                    self.t_virtual = self._alvo_sinc = self.mundo.t
                    self._rebase()
            self._reposiciona_lop()
            if reinicia:
                threading.Thread(target=self._reinicia_lop, daemon=True).start()
            else:
                self.agenda(0.8, self.apertar_botao)
            return
        threading.Thread(target=self._executa_lop, daemon=True).start()

    def _reposiciona_lop(self):
        w = self.mundo
        w.para_tudo()
        l, c = self.juiz.ultimo_cp
        x, y = w.mapa.centro(l, c)
        w.posicionar(x, y, self.juiz.dir_cp)
        self.juiz.reposicionado()
        self.em_lop = False

    def _reinicia_lop(self):
        self.parar_programa(espera=0.5)
        with self.mundo.lock:
            self.mundo.para_tudo()
        self.iniciar_programa()

    def _executa_lop(self):
        reinicia = self.modo_lop == 'reiniciar'
        if reinicia:
            self.parar_programa(espera=0.5)
        with self.mundo.lock:
            self._reposiciona_lop()
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

    def troca_programa(self, caminho):
        """Troca o programa do aluno sem fechar o simulador: para o que estiver rodando e prepara
        uma rodada nova (o próximo 'Iniciar rodada' já roda o programa escolhido)."""
        self.parar_programa()
        self.programa = os.path.abspath(caminho)
        self.nova_rodada()

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
