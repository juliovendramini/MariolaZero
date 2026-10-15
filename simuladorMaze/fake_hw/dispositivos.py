"""Emulação do firmware das placas, byte a byte, como o robô real responderia.

Cada dispositivo serial implementa recebe(dados) -> lista de (bytes_resposta, atraso_s).
Os dispositivos I2C implementam escrita/leitura de registradores.
"""

import struct

from . import cliente


def _s8(b):
    return b - 256 if b > 127 else b


def _i16(v):
    v = int(v)
    return ((v + 32768) % 65536) - 32768


def _xor(buf):
    c = 0
    for b in buf:
        c ^= b
    return c & 0xFF


# =========================================================================== serial
class Mariola:
    """ATmega328PB do brick Mariola (lib motores.py). Pacotes de 10 bytes a 250000 bps."""
    CMDS = {0xFC: 'pid', 0xF8: 'pid4x4', 0xFA: 'pwm', 0xF7: 'pwm4x4', 0xFB: 'estado'}

    def __init__(self, nome):
        self.buf = bytearray()
        self.leds = [(0, 0, 0)] * 11
        cal = int(cliente.config['motor_padrao'].get('calibracao', 208))
        self.cal = [cal, cal]

    def recebe(self, dados):
        self.buf += dados
        out = []
        while len(self.buf) >= 10:
            if self.buf[0] < 0xF3 or self.buf[0] > 0xFD:
                del self.buf[0]          # perdeu o sincronismo: descarta byte
                continue
            f = bytes(self.buf[:10])
            del self.buf[:10]
            out.extend(self._quadro(f))
        return out

    def _quadro(self, f):
        cmd = f[0]
        con = cliente.conexao
        if cmd in self.CMDS:
            r = con.chamar('mariola', tipo=self.CMDS[cmd], vals=[_s8(x) for x in f[1:5]],
                           alvos=[(f[5] << 8) | f[6], (f[7] << 8) | f[8]], freio=f[9])
            est = (r['e'][0] & 0b11) | ((r['e'][1] & 0b11) << 2)
            hdr = 0xFB if cmd == 0xFB else 0xFC
            return [(bytes([hdr]) + struct.pack('>ii', r['c'][0], r['c'][1]) + bytes([est]), 0.0004)]
        if cmd == 0xFD:   # servos
            con.chamar('servo', v={str(i): f[i] for i in range(1, 7)})
            return [(b'\xFD', 0.0002)]
        if cmd == 0xF9:   # PID
            return [(b'\xF9', 0.02)]
        if cmd in (0xF6, 0xF5):   # LEDs RGB
            cor = (f[1], f[2], f[3])
            if cmd == 0xF6:
                self.leds = [cor] * 11
            else:
                self.leds[min(max(f[4], 0), 10)] = cor
            con.chamar('led', leds=[list(c) for c in self.leds])
            return [(bytes([cmd]), 0.0002)]
        if cmd == 0xF4:
            return [(b'\xF4' + struct.pack('>ii', self.cal[0], self.cal[1]) + b'\x00', 0.0004)]
        if cmd == 0xF3:
            return [(b'\xF3', 0.0002)]
        return []


class BarramentoMotores:
    """Barramento one-wire half-duplex das placas de controle de motor (placaControleMotor.py).
    O host ouve o eco do que envia (6 bytes) e depois a resposta de 8 bytes."""

    def __init__(self, nome):
        self.nome = nome
        self.buf = bytearray()
        cal = int(cliente.config['motor_padrao'].get('calibracao', 208))
        self.cal = {}
        self.cal_padrao = cal

    def recebe(self, dados):
        self.buf += dados
        out = []
        while len(self.buf) >= 6:
            f = bytes(self.buf[:6])
            if _xor(f[:5]) != f[5]:
                out.append((bytes(self.buf[:1]), 0.0))   # eco do lixo
                del self.buf[0]
                continue
            del self.buf[:6]
            out.append((f, 0.0001))                       # eco
            r = self._trata(f)
            if r:
                out.append(r)
        return out

    def _resp(self, idm, modo, b2, payload4):
        p = bytes([idm, modo, b2 & 0xFF]) + payload4
        return p + bytes([_xor(p)])

    def _trata(self, f):
        idm, modo, b2, b3, b4 = f[0], f[1], f[2], f[3], f[4]
        con = cliente.conexao
        cal = self.cal.setdefault(idm, [self.cal_padrao, -self.cal_padrao])
        if modo == 0:
            r = con.chamar('placa', porta=self.nome, id=idm, modo='pid', valor=_s8(b2), giro=(b3 << 8) | b4)
        elif modo == 1:
            r = con.chamar('placa', porta=self.nome, id=idm, modo='pwm', valor=_s8(b2))
        elif modo == 2:
            r = con.chamar('placa', porta=self.nome, id=idm, modo='freio', valor=b2)
        elif modo == 3:
            r = con.chamar('placa', porta=self.nome, id=idm, modo='reset')
        else:
            r = con.chamar('placa', porta=self.nome, id=idm, modo='atualiza')
        if r.get('ausente'):
            return None
        if modo == 4:          # calibração automática (bloqueante no firmware)
            return (self._resp(idm, modo, 0, struct.pack('>hh', cal[0], cal[1])), 2.0)
        if modo == 8:
            cal[b2 & 1] = _i16((b3 << 8) | b4)
            return (self._resp(idm, modo, 0, struct.pack('>hh', cal[0], cal[1])), 0.0008)
        if modo == 10:
            return (self._resp(idm, modo, 1, struct.pack('>hh', cal[0], cal[1])), 0.0008)
        return (self._resp(idm, modo, r['e'], struct.pack('>i', r['c'])), 0.0008)


class Giroscopio:
    """Placa do giroscópio (giroscopio.py): recebe o modo (1 byte) e responde 8 bytes.
    Trocar entre GYRO e GYRO2 zera o eixo Z; o modo GYRO_CAL calibra e responde 1 byte."""

    def __init__(self, nome):
        self.ultimo = None

    def recebe(self, dados):
        out = []
        con = cliente.conexao
        for b in dados:
            if b in (0, 1):
                if self.ultimo in (0, 1) and b != self.ultimo:
                    con.chamar('giro_reset')
                self.ultimo = b
                v = con.chamar('giro')['v']
                out.append((struct.pack('>hhh', *[_i16(x) for x in v]) + b'\x00\x00', 0.0006))
            elif b == 2:
                con.chamar('giro_reset')
                self.ultimo = None
                t = float(cliente.config['giroscopio'].get('tempo_calibracao_s', 2.0))
                out.append((b'\x01', t))
        return out


class CorReflexaoV2:
    """Sensor de linha Pro1616 (ATtiny1616): 0x61 -> 16 bytes; 0x62/0x63 calibram e respondem 0x01."""

    def __init__(self, nome):
        pass

    def recebe(self, dados):
        out = []
        for b in dados:
            if b == 0x61:
                v = cliente.conexao.chamar('cor')['v']
                out.append((bytes(v), 0.0012))
            elif b in (0x62, 0x63):
                t = float(cliente.config['cor_reflexao'].get('tempo_calibracao_s', 1.5))
                out.append((b'\x01', t))
        return out


class MuxVl53Serial:
    """PlacaMuxVl53l0x: modo 0 -> 4 distâncias (int16) + 4 botões (int16)."""

    def __init__(self, nome):
        c = cliente.config.get('mux_vl53_serial', {})
        nomes = [s['nome'] for s in cliente.config['vl53']]
        self.idx = [nomes.index(n) if n in nomes else None for n in c.get('vl53', [])][:4]
        self.idx += [None] * (4 - len(self.idx))
        from .pinos import pino_num
        self.botoes = [pino_num(p) for p in c.get('botoes', [])][:4]

    def recebe(self, dados):
        out = []
        con = cliente.conexao
        for b in dados:
            if b == 0:
                vals = []
                for i in self.idx:
                    vals.append(con.chamar('vl53', idx=i)['d'] if i is not None else 8190)
                bots = []
                for k in range(4):
                    if k < len(self.botoes):
                        bots.append(1 if con.chamar('gpio_le', pino=self.botoes[k])['v'] == 0 else 0)
                    else:
                        bots.append(0)
                out.append((struct.pack('>8h', *[_i16(v) for v in vals + bots]), 0.002))
        return out


TIPOS_SERIAL = {
    'mariola': Mariola,
    'barramento_motores': BarramentoMotores,
    'giroscopio': Giroscopio,
    'cor_reflexao_v2': CorReflexaoV2,
    'mux_vl53_serial': MuxVl53Serial,
}


def cria_serial(nome_porta):
    tipo = cliente.config.get('portas_serial', {}).get(nome_porta)
    if tipo is None:
        return None
    return TIPOS_SERIAL[tipo](nome_porta)


# =========================================================================== I2C
class Mux:
    """TCA9548A em 0x70."""
    def __init__(self):
        self.mascara = 0

    def escreve(self, dados):
        if dados:
            self.mascara = dados[-1]

    def le(self, n):
        return [self.mascara] * n


class PCF8574:
    """Teclado do brick (teclado.py): 4 botões nos bits 0..3 (0 = apertado), LEDs nos bits 4..7."""
    def __init__(self):
        self.estado = 0xFF

    def escreve(self, dados):
        if dados:
            self.estado = dados[-1]

    def le(self, n):
        v = cliente.conexao.chamar('teclado')['v']
        return [((self.estado & 0xF0) | (v & 0x0F))] * n


class VL53L0X:
    """VL53L0X no nível de registradores, suficiente para a lib vl53.py rodar inalterada."""
    PADRAO = {0x91: 0x3C, 0x92: 0x2C, 0x84: 0x01, 0x01: 0xFF, 0x50: 0x06, 0x70: 0x04, 0xC0: 0xEE,
              0xB0: 0xFF, 0xB1: 0xFF, 0xB2: 0xFF, 0xB3: 0xFF, 0xB4: 0xFF, 0xB5: 0xFF}

    def __init__(self, canal):
        self.canal = canal
        self.addr = 0x29
        self.banco = 0
        self.regs = {}
        self.ponteiro = 0
        self.sysrange = 0
        self.continuo = False
        self.pronto_em = None
        self.medida = None
        self.budget = float(cliente.config['vl53_params'].get('tempo_medida_ms', 33)) / 1000.0

    def _agora(self):
        return cliente.relogio.agora()

    def _inicia(self):
        self.pronto_em = self._agora() + self.budget
        self.medida = None

    def _w(self, reg, v):
        if reg == 0xFF:
            self.banco = v
            return
        if self.banco == 0:
            if reg == 0x8A:
                self.addr = v & 0x7F
                return
            if reg == 0x00:
                if self.continuo and v == 0x01:     # stop_continuous
                    self.continuo = False
                    self.pronto_em = None
                    self.sysrange = 0
                    return
                self.sysrange = v
                if v & 0x06:
                    self.continuo = True
                    self._inicia()
                elif v & 0x01:
                    self.continuo = False
                    self._inicia()
                return
            if reg == 0x0B:
                if self.continuo:
                    self._inicia()
                else:
                    self.pronto_em = None
                return
        self.regs[(self.banco, reg)] = v

    def _r(self, reg):
        if reg == 0x83:
            v = self.regs.get((self.banco, 0x83), 0)
            return v if v else 0x10
        if self.banco == 0:
            if reg == 0x00:
                return self.sysrange & 0xFE
            if reg == 0x13:
                return 0x07 if (self.pronto_em is not None and self._agora() >= self.pronto_em) else 0x00
            if reg in (0x1E, 0x1F):
                if self.medida is None:
                    d = cliente.conexao.chamar('vl53', canal=self.canal)['d']
                    self.medida = 8190 if d is None else max(0, min(65535, int(d)))
                return (self.medida >> 8) & 0xFF if reg == 0x1E else self.medida & 0xFF
            if reg == 0x8A:
                return self.addr
        return self.regs.get((self.banco, reg), self.PADRAO.get(reg, 0))

    def escreve(self, dados):
        if not dados:
            return
        self.ponteiro = dados[0]
        for i, v in enumerate(dados[1:]):
            self._w((self.ponteiro + i) & 0xFF, v & 0xFF)

    def le(self, n):
        out = [self._r((self.ponteiro + i) & 0xFF) for i in range(n)]
        return out


class BarramentoI2C:
    def __init__(self, num):
        self.num = num
        self.acima = {}       # dispositivos antes do mux
        self.canais = {}      # canal -> [dispositivos]
        self.mux = None
        if num == 1:
            self.mux = Mux()
            self.acima[0x70] = self.mux
            if cliente.config.get('teclado'):
                self.acima[0x38] = PCF8574()
            from . import pinos as sim_pinos
            for s in cliente.config['vl53']:
                ch = sim_pinos.canal_mux(s['mux'])
                self.canais.setdefault(ch, []).append(VL53L0X(ch))

    def acha(self, addr):
        if addr in self.acima:
            return self.acima[addr]
        if self.mux is not None:
            for ch, devs in self.canais.items():
                if self.mux.mascara & (1 << ch):
                    for d in devs:
                        if d.addr == addr:
                            return d
        raise OSError(121, 'Remote I/O error')


_barramentos = {}


def barramento(num):
    if num not in _barramentos:
        _barramentos[num] = BarramentoI2C(num)
    return _barramentos[num]
