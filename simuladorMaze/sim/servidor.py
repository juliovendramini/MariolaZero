"""Servidor que atende o processo do programa do aluno.

O processo do aluno emula os protocolos das placas (bytes da serial, registradores
I2C, GPIO) e pede aqui só as grandezas físicas: contagem de encoder, distância,
ângulos, cor do piso etc. Os motores também são comandados por aqui.
"""

import math
import socket
import threading

from . import firmware as FW
from . import mapa as M
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
            # programa morreu: como no robô, os motores seguem o último comando até o
            # timeout de 5 s do firmware (Mariola e placas de motor)

    # ------------------------------------------------------------------ operações
    def trata(self, r):
        op = r['op']
        sim = self.sim
        w = sim.mundo
        if op == 'relogio':
            return {'t': w.t, 'f': sim.fator_efetivo(), 'parar': sim.pedido_parar}
        if op == 'ola':
            return {'cfg': w.cfg, 't': w.t, 'f': sim.fator_efetivo(), 'epoca': sim.epoca}
        with w.lock:
            if op == 'mariola_quadro':
                res = w.fw_mariola.quadro(bytes(r['f']), w.t)
                return {'r': list(res[0]), 'd': res[1]} if res else {'r': None}
            if op == 'placa_quadro':
                res = FW.placa_pacote(w.fw_placas.get(r['porta'], {}), bytes(r['f']), w.t)
                return {'r': list(res[0]), 'd': res[1]} if res else {'r': None}
            if op == 'giro':
                return {'v': w.giro()}
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
            if op == 'vitimas':
                return {'v': self._vitimas(w, r.get('camera'))}
            if op == 'kit':
                return {'n': w.deposita_kit(r['qtd'], r['lado']), 'restantes': w.kits_restantes}
            if op == 'kits_restantes':
                return {'n': w.kits_restantes}
            if op == 'debug':
                self._debug(w, r)
                return {}
        return {'erro': f'operação desconhecida {op}'}

    def _vitimas(self, w, camera):
        dc = w.cfg.get('deteccao', {})
        rng = w.rng
        res = []
        for dist, cam, idx, v in w.vitimas_visiveis(camera):
            st = M.status_vitima(v)
            if st is None:
                if rng.random() < float(dc.get('vitimas_falsas_enganam', 0)):
                    st = rng.choice(['ferida', 'estavel', 'ilesa'])
                else:
                    continue
            elif rng.random() < float(dc.get('falso_negativo', 0)):
                continue
            item = {'camera': cam, 'tipo': v['tipo'], 'status': st, 'kits': M.KITS_STATUS[st],
                    'distancia_mm': int(dist)}
            if v['tipo'] == 'letra':
                item['letra'] = v['letra'] if v['letra'] in M.STATUS_LETRA else {'ferida': 'H', 'estavel': 'S', 'ilesa': 'U'}[st]
            res.append(item)
        if not res and rng.random() < float(dc.get('falso_positivo', 0)):
            cams = [c['nome'] for c in w.cfg['cameras'] if camera in (None, c['nome'])]
            if cams:
                st = rng.choice(['ferida', 'estavel', 'ilesa'])
                res.append({'camera': rng.choice(cams), 'tipo': 'letra', 'status': st,
                            'kits': M.KITS_STATUS[st], 'letra': {'ferida': 'H', 'estavel': 'S', 'ilesa': 'U'}[st],
                            'distancia_mm': 100})
        return res

    def _debug(self, w, r):
        """Converte coordenadas do referencial do aluno (início da rodada) para o mundo."""
        m = w.mapa
        x0, y0 = m.centro(*m.inicio)
        a0 = M.ANGULO_DIR[m.inicio_dir]

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
