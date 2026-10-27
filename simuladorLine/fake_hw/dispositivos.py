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
    """ATmega328PB do brick Mariola (placaBrickVendra.ino): pacotes de 10 bytes a 250000 bps.
    A lógica do firmware fica no simulador (sim/firmware.py); aqui só se junta o pacote."""

    def __init__(self, nome):
        self.buf = bytearray()

    def recebe(self, dados):
        self.buf += dados
        out = []
        while len(self.buf) >= 10:
            if self.buf[0] < 0xEC or self.buf[0] > 0xFD:     # 0xEC-0xEF: buzzer (firmware de 26/10/2026)
                del self.buf[0]          # firmware: byte desconhecido é descartado um a um
                continue
            f = bytes(self.buf[:10])
            self.buf.clear()             # firmware: depois de tratar, descarta o resto do buffer
            r = cliente.conexao.chamar('mariola_quadro', f=list(f))
            if r['r'] is not None:
                out.append((bytes(r['r']), r['d']))
        return out


class BarramentoMotores:
    """Barramento one-wire half-duplex das placas de controle de motor (placaControleMotor.ino).
    O host ouve o eco do que envia (6 bytes) e depois a resposta de 8 bytes da placa com aquele ID."""

    def __init__(self, nome):
        self.nome = nome
        self.buf = bytearray()

    def recebe(self, dados):
        out = [(bytes(dados), 0.0)]       # eco: o TX e o RX estão no mesmo fio
        self.buf += dados
        while len(self.buf) >= 6:
            f = bytes(self.buf[:6])
            del self.buf[:6]
            r = cliente.conexao.chamar('placa_quadro', porta=self.nome, f=list(f))
            if r['r'] is not None:
                out.append((bytes(r['r']), r['d']))
        return out


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
    """Sensor de linha Pro1616 (sensorLinhaPro1616.ino): lê todos os bytes que chegaram e usa o
    último. 0x61 -> 16 bytes; 0x62 calibra o branco (~7 s) e 0x63 o preto (~2 s), respondendo 1."""

    def __init__(self, nome):
        pass

    def recebe(self, dados):
        validos = [b for b in dados if 0x61 <= b <= 0x63]
        if not validos:
            return []
        b = validos[-1]
        if b == 0x61:
            v = cliente.conexao.chamar('cor')['v']
            return [(bytes(v), 0.0005)]
        cc = cliente.config['cor_reflexao']
        t = float(cc.get('tempo_calibra_branco_s', 7.0) if b == 0x62 else cc.get('tempo_calibra_preto_s', 2.2))
        return [(b'\x01', t)]


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
    """Teclado do brick (teclado.py): 4 botões nos bits 0..3 (0 = apertado), LEDs nos bits 4..7.

    Botões da esquerda para a direita: Voltar, Baixo, Cima, Enter (bits 0..3).
    LEDs da esquerda para a direita: branco, vermelho, laranja, verde (bits 4..7).

    Na placa, é um ATtiny1616 emulando um PCF8574A (firmware tecladoMariola.ino): bit 1 = pino
    em INPUT_PULLUP, bit 0 = pino em OUTPUT LOW; a leitura devolve o nível real dos pinos.
    Os pinos dos LEDs vão à base de um NPN (LED entre o VCC e o coletor): o LED acende com 1
    (o pull-up liga o transistor) e apaga com 0;
    ao ligar, os 4 ficam acesos. E um botão cujo bit foi escrito com 0 lê sempre 0 ("apertado")."""
    def __init__(self):
        self.estado = 0xFF
        self._leds = None

    def escreve(self, dados):
        if dados:
            self.estado = dados[-1]
            leds = (self.estado >> 4) & 0x0F
            if leds != self._leds:
                self._leds = leds
                cliente.conexao.chamar('teclado_leds', v=leds)

    def le(self, n):
        v = cliente.conexao.chamar('teclado')['v']
        return [((self.estado & 0xF0) | (v & self.estado & 0x0F))] * n


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


class TCS34725:
    """TCS34725 (0x29) no nível de registradores (lib tcs34725.py do Mariola).
    O simulador devolve a luz como fração do branco a ~1 cm; aqui vira contagem do ADC
    conforme o tempo de integração (ATIME) e o ganho (CONTROL), como no sensor."""
    ESCALA = 9000.0          # contagem do clear no branco, ganho 4x, ATIME 0xC0 (64 ciclos)
    GANHOS = {0: 1.0, 1: 4.0, 2: 16.0, 3: 60.0}

    def __init__(self, canal):
        self.canal = canal
        self.addr = 0x29
        self.regs = {0x00: 0x00, 0x01: 0xFF, 0x0F: 0x00, 0x12: 0x44}
        self.ponteiro = 0
        self.dados = [0, 0, 0, 0]       # c, r, g, b
        self.t_dados = -1.0
        self.ligado_em = None

    def _ciclos(self):
        return 256 - self.regs.get(0x01, 0xFF)

    def _amostra(self):
        agora = cliente.relogio.agora()
        if self.regs.get(0x00, 0) & 0x03 != 0x03:
            return
        integ = 0.0024 * self._ciclos()
        if self.t_dados >= 0 and agora - self.t_dados < integ:
            return
        v = cliente.conexao.chamar('tcs', canal=self.canal)['v']
        if v is None:
            return
        r, g, b, c = v
        k = self.ESCALA * self.GANHOS[self.regs.get(0x0F, 0) & 3] / 4.0 * self._ciclos() / 64.0
        cheio = min(65535, 1024 * self._ciclos())
        self.dados = [min(cheio, int(round(x * k))) for x in (c, r, g, b)]
        self.t_dados = agora

    def _r(self, reg):
        if reg == 0x13:                  # STATUS: AVALID
            return 0x01 if self.t_dados >= 0 else 0x00
        if 0x14 <= reg <= 0x1B:
            if reg == 0x14:
                self._amostra()
            i = (reg - 0x14) // 2
            v = self.dados[i]
            return v & 0xFF if (reg - 0x14) % 2 == 0 else (v >> 8) & 0xFF
        return self.regs.get(reg, 0)

    def escreve(self, dados):
        if not dados:
            return
        self.ponteiro = dados[0] & 0x1F          # bit 7 = comando, bits 5-6 = tipo de acesso
        for i, v in enumerate(dados[1:]):
            self.regs[(self.ponteiro + i) & 0x1F] = v & 0xFF
            if (self.ponteiro + i) & 0x1F == 0x00 and v & 0x03 == 0x03:
                self.t_dados = -1.0

    def le(self, n):
        return [self._r((self.ponteiro + i) & 0x1F) for i in range(n)]


class BarramentoI2C:
    def __init__(self, num):
        self.num = num
        self.acima = {}       # dispositivos antes do mux
        self.canais = {}      # canal -> [dispositivos]
        self.mux = None
        # teclado (PCF8574 em 0x38): no brick atual ele fica na mesma placa da tela, no conector
        # TELA (barramento 0). "teclado": true no robo.json = placa antiga, no barramento 1.
        tec = cliente.config.get('teclado')
        if tec:
            bus_tec = 1 if tec is True else int(tec.get('barramento', 0))
            if bus_tec == num:
                self.acima[int(tec.get('endereco', 0x38)) if isinstance(tec, dict) else 0x38] = PCF8574()
        if num == 1:
            self.mux = Mux()
            self.acima[0x70] = self.mux
            from . import pinos as sim_pinos
            for s in cliente.config['vl53']:
                ch = sim_pinos.canal_mux(s['mux'])
                self.canais.setdefault(ch, []).append(VL53L0X(ch))
            for s in cliente.config.get('tcs_i2c', []):
                ch = sim_pinos.canal_mux(s['mux'])
                self.canais.setdefault(ch, []).append(TCS34725(ch))

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
