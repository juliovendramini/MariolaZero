"""Servidor que atende o processo do programa do aluno.

O processo do aluno emula os protocolos das placas (bytes da serial, registradores
I2C, GPIO) e pede aqui só as grandezas físicas: contagem de encoder, distância,
ângulos, leitura do sensor de linha etc. Os motores também são comandados por aqui.
"""

import math
import socket
import threading

from . import firmware as FW
from .fisica import canal_mux as pino_canal
from .protocolo import envia, recebe


class Servidor:
    def __init__(self, sim, porta=0):
        self.sim = sim
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind(('127.0.0.1', porta))
        self.sock.listen(8)
        self.porta = self.sock.getsockname()[1]
        self.clientes = 0
        self.rodando = True
        threading.Thread(target=self._aceita, daemon=True).start()

    def _aceita(self):
        while self.rodando:
            try:
                c, _ = self.sock.accept()
            except OSError:
                return
            c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            threading.Thread(target=self._atende, args=(c,), daemon=True).start()

    def _atende(self, c):
        self.clientes += 1
        try:
            while True:
                try:
                    req = recebe(c)
                except (ConnectionError, OSError):
                    break
                try:
                    resp = self.trata(req)
                except Exception as e:  # erro do simulador não pode derrubar o aluno sem aviso
                    resp = {'erro': f'{type(e).__name__}: {e}'}
                try:
                    envia(c, resp)
                except OSError:
                    break
        finally:
            self.clientes -= 1
            c.close()
            if getattr(self, '_sinc_con', None) == threading.get_ident():
                self._sinc_con = None
                self.sim.sinc_fim()     # programa saiu: a física volta a andar sozinha
            # programa morreu: como no robô, os motores seguem o último comando até o
            # timeout de 5 s do firmware (Mariola e placas de motor)

    # ------------------------------------------------------------------ operações
    def trata(self, r):
        op = r['op']
        sim = self.sim
        w = sim.mundo
        if op == 'relogio':
            return {'t': sim.t_virtual, 'f': sim.fator_efetivo(), 'parar': sim.pedido_parar}
        if op == 'ola':
            return {'cfg': w.cfg, 't': sim.t_virtual, 'f': sim.fator_efetivo(), 'epoca': sim.epoca,
                    'sinc': sim.sincronizado}
        if op == 'sinc_inicio':
            self._sinc_con = threading.get_ident()
            sim.sinc_inicio()
            return {'t': sim.t_virtual}
        if op == 'avanca':
            t = sim.avanca_sinc(r.get('ate'), bool(r.get('livre')))
            return {'t': t, 'parar': sim.pedido_parar}
        if sim._lop_ate is not None:
            # LoP: o programa antigo está sendo encerrado e não pode mexer no robô nem gastar
            # o ruído dos sensores (senão a rodada deixa de se repetir igual)
            with sim._cv:
                while sim._lop_ate is not None and sim.rodando:
                    sim._cv.wait(0.05)
            return {'erro': 'programa encerrado pelo LoP'}
        with w.lock:
            if op == 'mariola_quadro':
                res = w.fw_mariola.quadro(bytes(r['f']), w.t)
                return {'r': list(res[0]), 'd': res[1]} if res else {'r': None}
            if op == 'placa_quadro':
                res = FW.placa_pacote(w.fw_placas.get(r['porta'], {}), bytes(r['f']), w.t)
                return {'r': list(res[0]), 'd': res[1]} if res else {'r': None}
            if op == 'giro':
                return {'v': w.giro()}
            if op == 'imu':
                return {'v': w.imu()}
            if op == 'motor_dc':
                m = w.por_dc.get(r['porta'])
                if m is not None:
                    m.dc_estado(r.get('frente', 0), r.get('re', 0), r.get('ll', 1), r.get('hh', 0))
                return {}
            if op == 'leds':
                cores = [tuple(int(x) for x in c[:3]) for c in r.get('v', [])][:10]
                w.leds = cores + [(0, 0, 0)] * (10 - len(cores))
                return {}
            if op == 'giro_reset':
                w.giro_reset_z()
                return {}
            if op == 'cor':
                return {'v': w.cor_firmware()}
            if op == 'vl53':
                idx = r.get('idx')
                if idx is None:
                    idx = w.vl53_por_canal(r['canal'])
                if idx is None:
                    return {'d': None}
                return {'d': w.vl53(idx)}
            if op == 'tcs':
                idx = r.get('idx')
                if idx is None:
                    idx = next((i for i, sc in enumerate(w.cfg.get('tcs_i2c', []))
                                if pino_canal(sc['mux']) == r['canal']), None)
                if idx is None:
                    return {'v': None}
                return {'v': w.resgate.tcs(idx)}
            if op == 'visao':
                return {'v': w.resgate.camera(r.get('tipo', 'vitimas'))}
            if op == 'gpio_le':
                return {'v': w.gpio_nivel(int(r['pino']))}
            if op == 'gpio_escreve':
                p = int(r['pino'])
                if r.get('v') is None:
                    w.gpio_saida.pop(p, None)
                else:
                    w.gpio_saida[p] = 1 if r['v'] else 0
                return {}
            if op == 'servo':
                w.servos = r.get('v', {})
                return {}
            if op == 'teclado':
                v = 0x0F
                for k in w.teclas_teclado:
                    v &= ~(1 << (k - 1))
                return {'v': v}
            if op == 'teclado_leds':
                w.teclado_leds = int(r['v']) & 0x0F
                return {}
            if op == 'oled':
                w.oled = bytes.fromhex(r['b']) if r.get('b') else None
                w.oled_tam = (int(r.get('w', 128)), int(r.get('h', 64)))
                return {}
            if op == 'debug':
                self._debug(w, r)
                return {}
        return {'erro': f'operação desconhecida {op}'}

    def _debug(self, w, r):
        """Converte coordenadas do referencial do aluno (pose de início) para o mundo."""
        x0, y0, a0, _ = w.pose_inicio()

        def mundo(x, y):
            return (x0 + x * math.cos(a0) - y * math.sin(a0), y0 + x * math.sin(a0) + y * math.cos(a0))

        if 'pose' in r:
            x, y, th = r['pose']
            wx, wy = mundo(x, y)
            w.debug['pose'] = (wx, wy, a0 + math.radians(th))
        if 'texto' in r:
            w.debug['texto'] = str(r['texto'])[:400]
        if 'marca' in r:
            x, y, cor = r['marca']
            w.debug['marcas'].append((*mundo(x, y), cor))
            w.debug['marcas'] = w.debug['marcas'][-400:]
        if r.get('limpa'):
            w.debug['marcas'] = []
