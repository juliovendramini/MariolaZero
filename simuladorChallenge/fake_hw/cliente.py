"""Conexão com o simulador e relógio virtual do processo do aluno.

O relógio virtual substitui time.time/monotonic/perf_counter/sleep para que o
programa siga a velocidade escolhida no simulador (1x, 2x, pausa...).
"""

import _thread
import contextlib
import math
import os
import signal
import socket
import sys
import threading
import time as _time

_real_sleep = _time.sleep
_real_perf = _time.perf_counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.protocolo import envia, recebe  # noqa: E402
sys.path.pop(0)


class _Interrupcao:
    """O fim da rodada chega como KeyboardInterrupt na thread principal (_thread.interrupt_main).
    Se ele caísse no meio de um Conexao.chamar(), entre o pedido e a resposta, a resposta ficava no
    socket e a próxima thread a usar a conexão lia a resposta errada (KeyError: 'v' no giroscópio):
    o log ganhava um Traceback e o avalia.py marcava "erro no programa" numa rodada que terminou bem.
    Com a thread principal conversando com o simulador, a interrupção fica guardada e é levantada
    logo depois da resposta."""
    principal = threading.main_thread()
    conversas = 0           # chamar() em andamento na thread principal
    pendente = False

    @classmethod
    def instala(cls):
        try:
            signal.signal(signal.SIGINT, cls._tratador)
        except ValueError:
            pass            # conectar() fora da thread principal: fica o tratador padrão

    @classmethod
    def _tratador(cls, signum, frame):
        if cls.conversas:
            cls.pendente = True
            return
        raise KeyboardInterrupt


class Conexao:
    def __init__(self, porta):
        self.sock = socket.create_connection(('127.0.0.1', porta))
        self.sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.lock = threading.Lock()

    def chamar(self, op, **kw):
        kw['op'] = op
        principal = threading.current_thread() is _Interrupcao.principal
        if principal:
            _Interrupcao.conversas += 1
        try:
            with self.lock:
                envia(self.sock, kw)
                r = recebe(self.sock)
        finally:
            if principal:
                _Interrupcao.conversas -= 1
                if not _Interrupcao.conversas and _Interrupcao.pendente:
                    _Interrupcao.pendente = False
                    raise KeyboardInterrupt
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

    @contextlib.contextmanager
    def espera_externa(self):
        """A thread fica parada esperando algo de fora do programa (o Enter do input()). Conta como
        esperando, sem hora para acordar: o tempo anda pelo relógio real, na velocidade escolhida,
        como no robô parado no input() (as outras threads e o timeout de 5 s dos motores seguem)."""
        tid = threading.get_ident()
        with self.cond:
            self.ja_esperou = True
            self.esperando[tid] = math.inf
            self.cond.notify_all()
        try:
            yield
        finally:
            with self.cond:
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
                if todos and alvo == math.inf:
                    # só esperas sem hora para acabar (input()): o tempo anda pelo relógio real
                    todos_em = agora
                    if agora - livre_em < 0.01:
                        continue
                    livre_em = agora
                    r = self.conn.chamar('avanca', livre=True)
                elif todos and alvo is not None:
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
        # Travas criadas pelo programa (threading.Lock/RLock, e as Condition/Event feitas com elas):
        # a thread parada esperando uma trava conta como esperando. Sem isso, uma thread presa no
        # lock enquanto a dona dele dorme (ex.: o I2C_LOCK, com o VL53 medindo) impedia o tempo de
        # andar, e depois de LIVRE_APOS ele ia pelo relógio real: a partida mudava com a velocidade.
        # (O Condition.wait(timeout) e o Event.wait(timeout) continuam no relógio real: o "garçom"
        # deles é um lock interno do threading.)
        threading.Lock = _FabricaTrava(_TravaVigiada, self)
        threading.RLock = _FabricaTrava(_TravaVigiadaR, self)


class _FabricaTrava:
    """O threading.Lock/RLock trocado. Um objeto com __call__ e não um lambda: biblioteca que guarda
    threading.Lock num atributo de classe e chama self.atributo() (o werkzeug do Flask:
    Map.lock_class) receberia o self como argumento se fosse uma função (TypeError)."""

    def __init__(self, classe, relogio):
        self.classe, self.relogio = classe, relogio

    def __call__(self, *a, **k):
        return self.classe(self.relogio)


class _TravaVigiada:
    """Lock do programa do aluno. Esperando por ele, a thread conta como esperando (sem hora para
    acordar, ou até o timeout, em tempo simulado).

    O estado fica no cond do relógio. Quem solta passa a trava direto para a primeira da fila e já
    a tira da lista de espera: entre soltar a trava e a outra thread voltar a rodar, o relógio não
    pode andar (na primeira versão, de 31/10, ele andava nesse intervalo, e quanto andava dependia
    do PC: a rodada da Maze mudava com a velocidade)."""

    def __init__(self, relogio):
        self._rel = relogio
        self._dono = None        # ident da thread que tem a trava (None = livre)
        self._fila = []          # threads esperando, por ordem de chegada
        self._passada = None     # thread da fila que acabou de receber a trava

    def acquire(self, blocking=True, timeout=-1):
        rel = self._rel
        tid = threading.get_ident()
        with rel.cond:
            if self._dono is None and not self._fila:
                self._dono = tid
                return True
            if not blocking:
                return False
            ate = math.inf if timeout is None or timeout < 0 else rel.T + timeout
            self._fila.append(tid)
            rel.ja_esperou = True
            rel.esperando[tid] = ate
            rel.cond.notify_all()
            try:
                while self._passada != tid:
                    if rel.T >= ate - 1e-9:
                        self._fila.remove(tid)
                        rel.esperando.pop(tid, None)
                        return False
                    rel.cond.wait(0.05)
            except BaseException:
                # KeyboardInterrupt (fim da rodada) no meio da espera: sai da fila e, se a trava já
                # tinha chegado, passa adiante (senão ninguém mais a pegaria)
                rel.esperando.pop(tid, None)
                if self._passada == tid:
                    self._passada = None
                    _TravaVigiada.release(self)
                else:
                    self._fila.remove(tid)
                raise
            self._passada = None
            return True

    def release(self):
        rel = self._rel
        with rel.cond:
            if self._dono is None:
                raise RuntimeError('release unlocked lock')
            if self._fila:
                prox = self._fila.pop(0)
                self._dono = self._passada = prox
                rel.esperando.pop(prox, None)
                rel.cond.notify_all()
            else:
                self._dono = None

    def locked(self):
        return self._dono is not None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *a):
        self.release()


class _TravaVigiadaR(_TravaVigiada):
    """RLock do programa do aluno (a Condition usa os métodos _is_owned, _release_save e
    _acquire_restore)."""

    def __init__(self, relogio):
        super().__init__(relogio)
        self._conta = 0

    def acquire(self, blocking=True, timeout=-1):
        if self._dono == threading.get_ident():
            self._conta += 1
            return True
        ok = super().acquire(blocking, timeout)
        if ok:
            self._conta = 1
        return ok

    def release(self):
        if self._dono != threading.get_ident():
            raise RuntimeError('cannot release un-acquired lock')
        self._conta -= 1
        if self._conta == 0:
            super().release()

    def _is_owned(self):
        return self._dono == threading.get_ident()

    def _release_save(self):
        conta = self._conta
        self._conta = 1
        self.release()
        return conta

    def _acquire_restore(self, conta):
        self.acquire()
        self._conta = conta


conexao = None
relogio = None
config = None


def entrada(prompt=''):
    """input() do programa. No robô, rodando pelo ssh, ele espera o Enter do terminal (a equipe usa
    como pausa); aqui espera o Enter da janela do simulador (sem janela, responde na hora)."""
    sys.stdout.write(f'{prompt}\n')
    sys.stdout.flush()
    r = conexao.chamar('entrada', prompt=str(prompt))
    if not r['pronto']:
        espera = getattr(relogio, 'espera_externa', None)
        with espera() if espera else contextlib.nullcontext():
            while not r['pronto']:
                _real_sleep(0.05)
                r = conexao.chamar('entrada_estado')
    return r['texto']


def conectar():
    global conexao, relogio, config
    porta = int(os.environ.get('SIM_PORTA', '0'))
    if not porta:
        raise RuntimeError('SIM_PORTA não definida: rode o programa pelo simulador (simulador.py)')
    _Interrupcao.instala()
    conexao = Conexao(porta)
    ola = conexao.chamar('ola')
    config = ola['cfg']
    if ola.get('sinc'):
        relogio = RelogioSinc(porta, ola)
    else:
        relogio = Relogio(conexao, ola)
    return conexao, relogio, config
