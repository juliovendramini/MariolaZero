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


class RelogioSinc:
    """Relógio sincronizado com a física (padrão).

    O tempo do programa só anda quando TODAS as threads dele estão esperando (time.sleep,
    leitura da serial esperando resposta, etc.): aí o simulador avança a física até o primeiro
    despertar e devolve o tempo novo. O tempo que o PC gasta calculando e conversando com o
    simulador não conta, então o programa se comporta igual em 0,25x, 1x ou 4x (e igual com o
    PC mais lento ou mais rápido). As esperas (serial, I2C, sleep) contam como no robô.

    Se alguma thread fica calculando sem esperar (laço sem sleep, thread presa em Lock/Event),
    o tempo passa como tempo real x velocidade, como no modo antigo."""

    LIVRE_APOS = 1.0         # s reais sem todas as threads esperando -> tempo anda pelo relógio real

    def __init__(self, porta, ola):
        self.conn = Conexao(porta)           # conexão só do relógio
        self.epoca = ola['epoca']
        self.T = float(ola['t'])
        self.fator = ola['f']
        self.cond = threading.Condition()
        self.esperando = {}                  # ident da thread -> tempo em que ela acorda
        self.ja_esperou = False
        self.internos = set()
        self.parar = False
        self.conn.chamar('sinc_inicio')
        for alvo in (self._coordena, self._vigia_parar):
            th = threading.Thread(target=alvo, daemon=True)
            th.start()
            self.internos.add(th.ident)

    def agora(self):
        return self.T

    def dorme(self, s):
        if s is None or s <= 0:
            _real_sleep(0)
            return
        tid = threading.get_ident()
        with self.cond:
            self.ja_esperou = True       # (antes disso o programa está só importando/iniciando)
            acorda = self.T + s
            self.esperando[tid] = acorda
            self.cond.notify_all()
            try:
                while self.T < acorda - 1e-9:
                    self.cond.wait(0.05)
            finally:
                self.esperando.pop(tid, None)

    def _participantes(self):
        return [t.ident for t in threading.enumerate() if t.ident not in self.internos and t.is_alive()]

    def _coordena(self):
        todos_em = _real_perf()      # última vez em que todas as threads estavam esperando
        livre_em = 0.0
        while True:
            with self.cond:
                self.cond.wait(0.002)
                parts = self._participantes()
                todos = bool(parts) and all(p in self.esperando for p in parts)
                alvo = min(self.esperando.values()) if self.esperando else None
            agora = _real_perf()
            try:
                if todos and alvo is not None:
                    todos_em = agora
                    r = self.conn.chamar('avanca', ate=alvo)
                elif self.ja_esperou and agora - todos_em > self.LIVRE_APOS and agora - livre_em > 0.01:
                    livre_em = agora
                    r = self.conn.chamar('avanca', livre=True)
                else:
                    continue
            except Exception:
                os._exit(3)      # simulador fechou
            with self.cond:
                if r['t'] > self.T:
                    self.T = r['t']
                self.cond.notify_all()

    def _vigia_parar(self):
        conn = Conexao(self.conn.sock.getpeername()[1])
        while True:
            try:
                r = conn.chamar('relogio')
            except Exception:
                os._exit(3)
            self.fator = r['f']
            if r.get('parar') and not self.parar:
                self.parar = True
                _thread.interrupt_main()
            _real_sleep(0.03)

    def instala(self):
        Relogio.instala(self)


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
    if ola.get('sinc'):
        relogio = RelogioSinc(porta, ola)
    else:
        relogio = Relogio(conexao, ola)
    return conexao, relogio, config
