"""Placa de motor externa (ATtiny1616) no emulador: protocolo de 6 bytes, resposta de 8."""
from emu import *

ID = 0x21
MODO_PID, MODO_PWM, SET_FREIO, RESET, CALIBRACAO, ATUALIZA_P, GET_CALIB = 0, 1, 2, 3, 4, 9, 10
W_NL_PLACA = 130 / 60 * 17 * 34 * 4      # contagens/s (o firmware conta as 4 bordas do encoder)


def pacote(modo, b2=0, b3=0, b4=0, ident=ID):
    p = [ident, modo, b2 & 0xFF, b3 & 0xFF, b4 & 0xFF]
    crc = 0
    for b in p:
        crc ^= b
    return bytes(p + [crc])


class Placa(Emu):
    def __init__(self, qual, eeprom=None):
        super().__init__(*firmware('placa', qual), tipo=1)
        dll.emu_motor_param(W_NL_PLACA, 0.06, W_NL_PLACA / 0.06 * 0.07)
        dll.emu_tiny_pinos(5, 4, 12, 13)             # PA5 = PWM frente, PA4 = PWM trás, PB4/PB5 = encoder
        if eeprom is not None:
            dll.emu_eeprom(bytes(eeprom), len(eeprom), 1)
        self.qual = qual

    def cmd(self, modo, b2=0, b3=0, b4=0, limite=0.01):
        """manda um comando e devolve (modo, estado, contador) ou None se a placa não respondeu"""
        r = self.comando(pacote(modo, b2, b3, b4), 8, limite)
        if len(r) != 8:
            return None
        crc = 0
        for b in r[:7]:
            crc ^= b
        if crc != r[7] or r[0] != ID:
            return None
        return r[1], r[2], struct.unpack('>i', r[3:7])[0]

    def anda(self, dur, vel, modo=MODO_PID, periodo=0.02):
        fim = self.t + dur
        ult = None
        while self.t < fim:
            prox = self.t + periodo
            ult = self.cmd(modo, vel)
            if self.t < prox:
                self.ate(min(prox, fim))
        return ult

    @property
    def resets(self):
        return dll.emu_resets()
