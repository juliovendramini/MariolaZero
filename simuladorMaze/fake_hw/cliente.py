"""Conexão com o simulador e relógio virtual do processo do aluno.

O relógio virtual substitui time.time/monotonic/perf_counter/sleep para que o
programa siga a velocidade escolhida no simulador (1x, 2x, pausa...).
"""

import _thread
import os
import socket
import sys
import threading
import time as _time

_real_sleep = _time.sleep
_real_perf = _time.perf_counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.protocolo import envia, recebe  # noqa: E402
sys.path.pop(0)


class Conexao:
    def __init__(self, porta):
        self.sock = socket.create_connection(('127.0.0.1', porta))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.lock = threading.Lock()

    def chamar(self, op, **kw):
        kw['op'] = op
        with self.lock:
            envia(self.sock, kw)
            r = recebe(self.sock)
        if 'erro' in r:
            raise RuntimeError('[simulador] ' + r['erro'])
        return r


class Relogio:
    def __init__(self, conn, ola):
        self.conn = conn
        self.epoca = ola['epoca']
        self._t_ref = ola['t']
        self._real_ref = _real_perf()
        self.fator = ola['f']
        self._ultimo = self._t_ref
        self._lock = threading.Lock()
        self.parar = False
        threading.Thread(target=self._sincroniza, daemon=True).start()

    def _sincroniza(self):
        while True:
            try:
                r = self.conn.chamar('relogio')
            except Exception:
                os._exit(3)      # simulador fechou
            with self._lock:
                self._t_ref = r['t']
                self._real_ref = _real_perf()
                self.fator = r['f']
            if r.get('parar') and not self.parar:
                self.parar = True
                _thread.interrupt_main()
            _real_sleep(0.01)

    def agora(self):
        with self._lock:
            t = self._t_ref + (_real_perf() - self._real_ref) * self.fator
            if t < self._ultimo:
                t = self._ultimo
            self._ultimo = t
            return t

    def dorme(self, s):
        if s is None or s <= 0:
            _real_sleep(0)
            return
        alvo = self.agora() + s
        while True:
            resto = alvo - self.agora()
            if resto <= 0:
                return
            f = self.fator
            if f <= 0:
                _real_sleep(0.01)
            else:
                _real_sleep(min(resto / f, 0.02))

    def instala(self):
        """Troca as funções do módulo time pelas versões virtuais."""
        _time.time = lambda: self.epoca + self.agora()
        _time.time_ns = lambda: int((self.epoca + self.agora()) * 1e9)
        _time.monotonic = self.agora
        _time.monotonic_ns = lambda: int(self.agora() * 1e9)
        _time.perf_counter = self.agora
        _time.perf_counter_ns = lambda: int(self.agora() * 1e9)
        _time.sleep = self.dorme


conexao = None
relogio = None
config = None


def conectar():
    global conexao, relogio, config
    porta = int(os.environ.get('SIM_PORTA', '0'))
    if not porta:
        raise RuntimeError('SIM_PORTA não definida: rode o programa pelo simulador (simulador.py)')
    conexao = Conexao(porta)
    ola = conexao.chamar('ola')
    config = ola['cfg']
    relogio = Relogio(conexao, ola)
    return conexao, relogio, config
