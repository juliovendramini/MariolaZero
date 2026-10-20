"""Firmware das placas de motor, emulado a partir do código real:

* placaBrickVendra.ino  (ATmega328PB do Mariola)  -> FirmwareMariola
* placaControleMotor.ino (ATtiny1616 one-wire)    -> FirmwarePlaca

O cliente (processo do aluno) só junta os bytes do pacote; quem decide a
resposta, os tempos e os efeitos nos motores é este módulo, porque o firmware
também age sem receber nada (PID a 40 Hz, parada por ângulo, timeouts).
"""

import struct

TIMEOUT_MARIOLA = 5.0        # TIMEOUT 1250 com millis() 4x mais lento
TIMEOUT_PLACA = 5.0          # TIMEOUT_COMUNICACAO
WATCHDOG_PLACA = 12.0        # 10 s sem comunicação + watchdog de 2 s -> placa reinicia
NUM_LEDS = 10                # LEDStrip numLeds


def _s8(b):
    return b - 256 if b > 127 else b


def _s16(v):
    v &= 0xFFFF
    return v - 65536 if v > 32767 else v


def _xor(buf):
    c = 0
    for b in buf:
        c ^= b
    return c & 0xFF


class FirmwareMariola:
    def __init__(self, mundo):
        self.w = mundo
        self.ultimo = 0.0
        self.desativado = False
        self.ocupado_ate = -1.0
        self.velocidades = [0, 0, 0, 0]
        self.leds_porta4 = None      # porta 4 como fita de LEDs (None = servo); não aparece na tela
        self.ventoinha = None        # PWM da ventoinha (0-255) depois do primeiro ATIVA_VENTOINHA

    def motor(self, canal):
        return self.w.por_mariola.get(canal)

    def _estado(self):
        e = 0
        m1, m2 = self.motor(1), self.motor(2)
        if m1:
            e |= m1.estado() & 0b11
        if m2:
            e |= (m2.estado() & 0b11) << 2
        return e

    def _resposta(self, hdr, t):
        c = []
        for canal in (1, 2):
            m = self.motor(canal)
            c.append(m.le_contagem(t) if m else 0)
        return bytes([hdr]) + struct.pack('>ii', c[0], c[1]) + bytes([self._estado()])

    def quadro(self, f, t):
        """Recebe um pacote de 10 bytes. Devolve (resposta, atraso) ou None."""
        if t < self.ocupado_ate:          # calibrando: não atende a serial
            return None
        cmd = f[0]
        if cmd < 0xF0 or cmd > 0xFD:
            return None
        self.ultimo = t
        if self.desativado:
            self.desativado = False
            for m in self.w.por_mariola.values():
                m.desligado = False
        if cmd == 0xFD:                                      # ENVIA_SERVOS
            self.w.servos = {str(i): f[i] for i in range(1, 5)}
            if f[4] <= 180:                                  # ângulo no servo 4: a porta volta a ser servo
                self.leds_porta4 = None
            if self.ventoinha is not None and min(f[1:5]) <= 180:
                self.ventoinha = 0                           # o servo religa o Timer2 e o PWM do pino 11 para
            return (b'\xFD', 0.0002)
        if cmd in (0xFC, 0xF8):                              # ENVIA_MOTORES / 4X4 (PID)
            modo4x4 = cmd == 0xF8
            v = [_s8(f[1]), _s8(f[2]), _s8(f[3]), _s8(f[4])]
            if modo4x4:
                v[2], v[3] = v[0], v[1]
            freio = f[9] == 1
            giros = [_s16((f[5] << 8) | f[6]), _s16((f[7] << 8) | f[8])]   # int16 no firmware!
            for i, canal in enumerate((1, 2)):
                m = self.motor(canal)
                self.velocidades[i] = v[i]
                if m is None:
                    continue
                m.travado = freio
                m.modo = 'pid'
                m.setpoint = m.mapa(v[i])
                if giros[i] != 0:
                    m.alvo = m.contagem + giros[i] if m.setpoint >= 0 else m.contagem - giros[i]
                if v[i] == 0:
                    m.alvo = None
            for i, canal in ((2, 3), (3, 4)):                 # motores sem encoder
                m = self.motor(canal)
                self.velocidades[i] = v[i]
                if m is None:
                    continue
                m.travado = freio
                if modo4x4:                                  # seguem o PID do 1 e do 2
                    src = self.motor(canal - 2)
                    m.modo = 'pid'
                    m.setpoint = m.mapa(v[i]) if src is None else src.setpoint
                    m.alvo = None
                else:
                    m.modo = 'pwm'
                    m.pwm = v[i]
            return (self._resposta(0xFC, t), 0.0004)
        if cmd in (0xFA, 0xF7):                              # ENVIA_MOTORES_POTENCIA / 4X4
            v = [_s8(f[1]), _s8(f[2]), _s8(f[3]), _s8(f[4])]
            if cmd == 0xF7:
                v[2], v[3] = v[0], v[1]
            freio = f[9] == 1
            for i, canal in enumerate((1, 2, 3, 4)):
                m = self.motor(canal)
                self.velocidades[i] = v[i]
                if m is None:
                    continue
                m.travado = freio
                m.alvo = None
                if v[i] == 0 and canal <= 2:
                    m.modo = 'pid'
                    m.setpoint = 0
                else:
                    m.modo = 'pwm'
                    m.pwm = v[i]
            return (self._resposta(0xFC, t), 0.0004)
        if cmd == 0xFB:                                      # ATUALIZA_MOTORES
            return (self._resposta(0xFB, t), 0.0004)
        if cmd == 0xF9:                                      # ENVIA_PID
            return (b'\xF9', 0.003)
        if cmd == 0xF6:                                      # LED_RGB_ALL
            self.w.leds = [(f[1], f[2], f[3])] * NUM_LEDS
            return (b'\xF6', 0.0005)
        if cmd == 0xF5:                                      # LED_RGB_ONE
            if f[4] < NUM_LEDS:
                leds = list(self.w.leds)
                leds[f[4]] = (f[1], f[2], f[3])
                self.w.leds = leds
            return (b'\xF5', 0.0005)
        if cmd in (0xF1, 0xF0):                              # LED_RGB_ALL_PORTA4 / LED_RGB_ONE_PORTA4
            if self.leds_porta4 is None:                     # ativaPorta4ComoLed: desliga o servo 4, apaga
                self.leds_porta4 = [(0, 0, 0)] * NUM_LEDS
                self.w.servos = dict(self.w.servos, **{'4': 200})
            if cmd == 0xF1:
                self.leds_porta4 = [(f[1], f[2], f[3])] * NUM_LEDS
            elif f[4] < NUM_LEDS:
                self.leds_porta4[f[4]] = (f[1], f[2], f[3])
            return (bytes([cmd]), 0.0005)
        if cmd == 0xF4:                                     # OBTEM_CALIBRACAO_MOTORES
            m1, m2 = self.motor(1), self.motor(2)
            c1 = m1.cal[0] if m1 else 0
            c2 = m2.cal[0] if m2 else 0
            return (b'\xF4' + struct.pack('>ii', c1, c2) + bytes([self._estado()]), 0.0004)
        if cmd == 0xF3:                                      # CALIBRA_MOTORES (bloqueia ~26 s)
            self.ocupado_ate = t + 26.0
            return (b'\xF3', 0.0002)
        if cmd == 0xF2:                                      # ATIVA_VENTOINHA
            if self.ventoinha is None:                       # configuraTimer2PWMVentoinha: desliga os servos
                self.w.servos = {str(i): 200 for i in range(1, 5)}
            self.ventoinha = f[1]                            # o timeout de 5 s não desliga a ventoinha
            return (b'\xF2', 0.0002)
        return None

    def passo(self, t):
        if not self.desativado and t - self.ultimo > TIMEOUT_MARIOLA:
            self.desativado = True
            for m in self.w.por_mariola.values():
                m.setpoint = 0
                m.pwm = 0
                m.alvo = None
                m.desligado = True
            self.w.leds = [(0, 0, 0)] * NUM_LEDS       # sem comando os LEDs também apagam
            if self.leds_porta4 is not None:
                self.leds_porta4 = [(0, 0, 0)] * NUM_LEDS


class FirmwarePlaca:
    MODO_PID, MODO_PWM, SET_FREIO, RESET, CALIBRACAO = 0, 1, 2, 3, 4
    SET_KP, SET_KI, SET_KD, SET_CAL, ATUALIZA, GET_CAL = 5, 6, 7, 8, 9, 10
    SET_KP_FREIO, SET_KD_FREIO, SET_DELTA_FREIO = 11, 12, 13

    def __init__(self, mundo, motor, id_placa):
        self.w = mundo
        self.m = motor
        self.id = id_placa
        self.ultimo = 0.0
        self.modo_atual = 0
        self.ocupado_ate = -1.0

    def _resp(self, b2, payload4, modo=None):
        p = bytes([self.id, self.modo_atual if modo is None else modo, b2 & 0xFF]) + payload4
        return p + bytes([_xor(p)])

    def _padrao(self, t):
        return self._resp(self.m.estado(), struct.pack('>i', self.m.le_contagem(t)))

    def quadro(self, f, t):
        """Pacote de 6 bytes já com CRC conferido e ID desta placa."""
        if t < self.ocupado_ate:
            return None
        m = self.m
        modo = f[1]
        self.ultimo = t
        m.desligado = False
        h, ah = struct.pack('>h', _s16(m.cal[0])), struct.pack('>h', _s16(m.cal[1]))
        if modo == self.RESET:
            m.reset()
            self.modo_atual = self.MODO_PID
            return (self._padrao(t), 0.0008)
        if modo == self.CALIBRACAO:
            self.modo_atual = self.CALIBRACAO
            self.ocupado_ate = t + 14.0
            m.para()
            m.contagem = 0.0
            c = int(0.8 * m.vlivre / 40.0)
            m.cal = [c, -c]
            h, ah = struct.pack('>h', c), struct.pack('>h', -c)
            return (self._resp(0, h + ah, self.CALIBRACAO), 14.0)
        if modo == self.GET_CAL:
            return (self._resp(1 if m.cal[0] != 0 else 0, h + ah, self.GET_CAL), 0.0008)
        if modo == self.SET_CAL:
            d = f[2]
            m.cal[0 if d == 0 else 1] = _s16((f[3] << 8) | f[4])
            h, ah = struct.pack('>h', _s16(m.cal[0])), struct.pack('>h', _s16(m.cal[1]))
            return (self._resp(d, h + ah, self.SET_CAL), 0.0008)
        if modo in (self.SET_KP, self.SET_KI, self.SET_KD, self.SET_KP_FREIO,
                    self.SET_KD_FREIO, self.SET_DELTA_FREIO):
            return (self._resp(0, bytes([f[2], f[3], 0, 0]), modo), 0.0008)
        if modo == self.SET_FREIO:
            m.travado = f[2] == 1
            return (self._padrao(t), 0.0008)
        if modo == self.ATUALIZA:
            return (self._padrao(t), 0.0008)
        if modo in (self.MODO_PID, self.MODO_PWM):
            self.modo_atual = modo
            v = _s8(f[2])
            giro = (f[3] << 8) | f[4]                       # uint16 nesta placa
            if modo == self.MODO_PID:
                if m.cal[0] != 0:
                    m.modo = 'pid'
                    m.setpoint = m.mapa(v)
                else:                                        # sem calibração: PWM direto
                    m.modo = 'pwm'
                    m.pwm = v
                if giro > 0 and m.modo == 'pid':
                    m.alvo = m.contagem + giro if m.setpoint >= 0 else m.contagem - giro
                else:
                    m.alvo = None                            # giro 0 cancela (diferente do Mariola)
            else:
                m.alvo = None
                if v == 0:
                    m.modo = 'pid'
                    m.setpoint = 0
                else:
                    m.modo = 'pwm'
                    m.pwm = v
            if v == 0:
                m.alvo = None
            est = 1 if v > 0 else 2 if v < 0 else 0
            return (self._resp(est, struct.pack('>i', m.le_contagem(t))), 0.0008)
        return (self._padrao(t), 0.0008)

    def passo(self, t):
        ocioso = t - self.ultimo
        if ocioso > WATCHDOG_PLACA:            # watchdog reinicia a placa: contagem volta a 0
            self.m.reset()
            self.modo_atual = self.MODO_PID
            self.ultimo = t
        elif ocioso > TIMEOUT_PLACA and not self.m.desligado:
            self.m.setpoint = 0
            self.m.pwm = 0
            self.m.alvo = None
            self.m.desligado = True


def placa_pacote(fws, f, t):
    """Barramento one-wire: entrega o pacote à placa com aquele ID (se o CRC bater)."""
    if len(f) != 6 or _xor(f[:5]) != f[5]:
        return None
    fw = fws.get(f[0])
    if fw is None:
        return None
    return fw.quadro(f, t)
