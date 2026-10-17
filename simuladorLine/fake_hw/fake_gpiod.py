"""Substituto do libgpiod v2 (`gpiod` e `gpiod.line`) ligado aos pinos do simulador.
Entrada: o simulador devolve o nível (para-choque e botão de início aparecem como BAIXO quando apertados).
Saída: o nível escrito vai para o simulador (pode ser o LED de vítima, se configurado)."""

import enum
import types

from . import cliente


class Direction(enum.Enum):
    AS_IS = 1
    INPUT = 2
    OUTPUT = 3


class Value(enum.Enum):
    INACTIVE = 0
    ACTIVE = 1

    def __bool__(self):
        return self is Value.ACTIVE


class Bias(enum.Enum):
    AS_IS = 1
    UNKNOWN = 2
    DISABLED = 3
    PULL_UP = 4
    PULL_DOWN = 5


class Drive(enum.Enum):
    PUSH_PULL = 1
    OPEN_DRAIN = 2
    OPEN_SOURCE = 3


class Edge(enum.Enum):
    NONE = 1
    RISING = 2
    FALLING = 3
    BOTH = 4


class Clock(enum.Enum):
    MONOTONIC = 1
    REALTIME = 2
    HTE = 3


line = types.ModuleType('gpiod.line')
line.Direction = Direction
line.Value = Value
line.Bias = Bias
line.Drive = Drive
line.Edge = Edge
line.Clock = Clock


class LineSettings:
    def __init__(self, direction=Direction.AS_IS, edge_detection=Edge.NONE, bias=Bias.AS_IS,
                 drive=Drive.PUSH_PULL, active_low=False, debounce_period=None,
                 event_clock=Clock.MONOTONIC, output_value=Value.INACTIVE):
        self.direction = direction
        self.edge_detection = edge_detection
        self.bias = bias
        self.drive = drive
        self.active_low = active_low
        self.debounce_period = debounce_period
        self.event_clock = event_clock
        self.output_value = output_value


class Chip:
    def __init__(self, path):
        self.path = path

    def close(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def request_lines(self, config, consumer=None, output_values=None, **kw):
        return request_lines(self.path, config=config, consumer=consumer, output_values=output_values)


def _offsets(chave):
    if isinstance(chave, (tuple, list, set, frozenset)):
        return list(chave)
    return [chave]


class LineRequest:
    def __init__(self, config, output_values=None):
        self.cfg = {}
        self._aplica(config, output_values)

    def _aplica(self, config, output_values=None):
        for chave, ls in (config or {}).items():
            ls = ls or LineSettings()
            for off in _offsets(chave):
                self.cfg[off] = ls
                if ls.direction == Direction.OUTPUT:
                    v = ls.output_value
                    if output_values and off in output_values:
                        v = output_values[off]
                    self._escreve(off, v)
                else:
                    cliente.conexao.chamar('gpio_escreve', pino=off, v=None)

    def _escreve(self, off, v):
        nivel = 1 if v in (Value.ACTIVE, 1, True) else 0
        if self.cfg[off].active_low:
            nivel ^= 1
        cliente.conexao.chamar('gpio_escreve', pino=off, v=nivel)

    @property
    def offsets(self):
        return list(self.cfg)

    def get_value(self, offset):
        nivel = cliente.conexao.chamar('gpio_le', pino=offset)['v']
        ls = self.cfg.get(offset)
        if ls is not None and ls.active_low:
            nivel ^= 1
        return Value.ACTIVE if nivel else Value.INACTIVE

    def get_values(self, offsets=None):
        return [self.get_value(o) for o in (offsets or self.offsets)]

    def set_value(self, offset, value):
        self._escreve(offset, value)

    def set_values(self, values):
        for o, v in values.items():
            self._escreve(o, v)

    def reconfigure_lines(self, config):
        self._aplica(config)

    def release(self):
        for off, ls in self.cfg.items():
            if ls.direction == Direction.OUTPUT:
                try:
                    cliente.conexao.chamar('gpio_escreve', pino=off, v=None)
                except Exception:
                    pass
        self.cfg = {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.release()


def request_lines(path, config=None, consumer=None, output_values=None, **kw):
    return LineRequest(config, output_values)


def is_gpiochip_device(path):
    return True


api_version = '2.1 (simulador)'
