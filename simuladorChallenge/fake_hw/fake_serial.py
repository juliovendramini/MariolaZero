"""Substituto do pyserial (módulo `serial`) ligado aos dispositivos emulados."""

import collections

from . import cliente
from . import dispositivos


class SerialException(IOError):
    pass


class SerialTimeoutException(SerialException):
    pass


PARITY_NONE, PARITY_EVEN, PARITY_ODD = 'N', 'E', 'O'
STOPBITS_ONE, STOPBITS_TWO = 1, 2
EIGHTBITS = 8


class Serial:
    def __init__(self, port=None, baudrate=9600, bytesize=8, parity='N', stopbits=1,
                 timeout=None, xonxoff=False, rtscts=False, write_timeout=None, dsrdtr=False, **kw):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.write_timeout = write_timeout
        self.is_open = False
        self._rx = collections.deque()    # (t_disponivel, bytearray)
        self._dev = None
        if port is not None:
            self.open()

    # ------------------------------------------------------------- abertura
    def open(self):
        nome = str(self.port)
        if nome.startswith('sim://'):
            nome = nome[6:]
        dev = dispositivos.cria_serial(nome)
        if dev is None:
            raise SerialException(
                f"[Errno 2] could not open port {self.port}: nada ligado em {nome} no robo.json (portas_serial)")
        self._dev = dev
        self._lat = float(cliente.config.get('latencia_serial_ms', 1.0)) / 1000.0
        self.is_open = True

    def close(self):
        self.is_open = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def __del__(self):
        self.is_open = False

    # ------------------------------------------------------------- escrita
    def write(self, dados):
        if not self.is_open:
            raise SerialException('Attempting to use a port that is not open')
        dados = bytes(dados)
        agora = cliente.relogio.agora()
        # tempo de transmissão dos bytes no fio
        t_tx = len(dados) * 10.0 / max(self.baudrate, 1)
        for resp, atraso in self._dev.recebe(dados):
            if resp:
                t = agora + t_tx + self._lat + atraso + len(resp) * 10.0 / max(self.baudrate, 1)
                self._rx.append((t, bytearray(resp)))
        return len(dados)

    def flush(self):
        pass

    def reset_output_buffer(self):
        pass

    def flushOutput(self):
        pass

    # ------------------------------------------------------------- leitura
    def _disponiveis(self, agora):
        n = 0
        for t, b in self._rx:
            if t > agora:
                break
            n += len(b)
        return n

    @property
    def in_waiting(self):
        return self._disponiveis(cliente.relogio.agora())

    def inWaiting(self):
        return self.in_waiting

    def reset_input_buffer(self):
        agora = cliente.relogio.agora()
        while self._rx and self._rx[0][0] <= agora:
            self._rx.popleft()

    def flushInput(self):
        self.reset_input_buffer()

    def read(self, size=1):
        if not self.is_open:
            raise SerialException('Attempting to use a port that is not open')
        rel = cliente.relogio
        fim = None if self.timeout is None else rel.agora() + self.timeout
        out = bytearray()
        while True:
            agora = rel.agora()
            while self._rx and self._rx[0][0] <= agora and len(out) < size:
                t, b = self._rx[0]
                falta = size - len(out)
                out += b[:falta]
                del b[:falta]
                if not b:
                    self._rx.popleft()
            if len(out) >= size or self.timeout == 0:
                break
            if fim is not None and agora >= fim:
                break
            prox = self._rx[0][0] if self._rx else None
            espera = 0.0005
            if prox is not None:
                espera = max(0.0, prox - agora)
            if fim is not None:
                espera = min(espera, max(0.0, fim - agora))
            rel.dorme(max(espera, 0.0001))
        return bytes(out)

    def read_all(self):
        return self.read(self.in_waiting)

    def readline(self, size=-1):
        out = bytearray()
        while True:
            c = self.read(1)
            if not c:
                break
            out += c
            if c == b'\n' or (size > 0 and len(out) >= size):
                break
        return bytes(out)


def serial_for_url(url, *a, **kw):
    return Serial(url, *a, **kw)
