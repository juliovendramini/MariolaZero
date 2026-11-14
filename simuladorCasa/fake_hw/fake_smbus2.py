"""Substituto do `smbus2` ligado aos dispositivos I2C emulados (mux TCA9548A, VL53L0X, PCF8574)."""

from . import dispositivos


class i2c_msg:
    def __init__(self, addr, leitura, dados):
        self.addr = addr
        self.leitura = leitura
        self.flags = 1 if leitura else 0
        self.buf = list(dados)
        self.len = len(self.buf)

    @staticmethod
    def read(address, length):
        return i2c_msg(address, True, [0] * length)

    @staticmethod
    def write(address, buf):
        if isinstance(buf, str):
            buf = buf.encode()
        return i2c_msg(address, False, list(buf))

    def __iter__(self):
        return iter(self.buf)

    def __len__(self):
        return self.len

    def __bytes__(self):
        return bytes(self.buf)


class SMBus:
    def __init__(self, bus=None, force=False):
        self.fd = None
        self.bus = None
        if bus is not None:
            self.open(bus)

    def open(self, bus):
        self.bus = dispositivos.barramento(int(bus))
        self.fd = 1

    def close(self):
        self.fd = None

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()

    def _dev(self, addr):
        return self.bus.acha(addr)

    # comandos SMBus
    def write_quick(self, i2c_addr, force=None):
        self._dev(i2c_addr)

    def read_byte(self, i2c_addr, force=None):
        return self._dev(i2c_addr).le(1)[0]

    def write_byte(self, i2c_addr, value, force=None):
        self._dev(i2c_addr).escreve([value & 0xFF])

    def read_byte_data(self, i2c_addr, register, force=None):
        d = self._dev(i2c_addr)
        d.escreve([register & 0xFF])
        return d.le(1)[0]

    def write_byte_data(self, i2c_addr, register, value, force=None):
        self._dev(i2c_addr).escreve([register & 0xFF, value & 0xFF])

    def read_word_data(self, i2c_addr, register, force=None):
        d = self._dev(i2c_addr)
        d.escreve([register & 0xFF])
        lo, hi = d.le(2)
        return lo | (hi << 8)

    def write_word_data(self, i2c_addr, register, value, force=None):
        self._dev(i2c_addr).escreve([register & 0xFF, value & 0xFF, (value >> 8) & 0xFF])

    def read_i2c_block_data(self, i2c_addr, register, length, force=None):
        d = self._dev(i2c_addr)
        d.escreve([register & 0xFF])
        return list(d.le(length))

    def write_i2c_block_data(self, i2c_addr, register, data, force=None):
        self._dev(i2c_addr).escreve([register & 0xFF] + [x & 0xFF for x in data])

    def read_block_data(self, i2c_addr, register, force=None):
        return self.read_i2c_block_data(i2c_addr, register, 32)

    def write_block_data(self, i2c_addr, register, data, force=None):
        self.write_i2c_block_data(i2c_addr, register, data)

    def i2c_rdwr(self, *msgs):
        for m in msgs:
            d = self._dev(m.addr)
            if m.leitura:
                m.buf = list(d.le(m.len))
            else:
                d.escreve(m.buf)
