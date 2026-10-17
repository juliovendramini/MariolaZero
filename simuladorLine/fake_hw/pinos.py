"""Nomes dos pinos (Botoes/PinosDigitais) e canais do mux I2C (Portas) do Mariola."""

PINOS = {'P1': 259, 'P2': 260, 'P3': 71, 'P4': 234, 'P5': 228, 'P6': 265, 'P7': 266, 'P8': 267}
CANAIS_I2C = {'I2C1': 0, 'I2C2': 1, 'I2C3': 7, 'I2C4': 2, 'I2C5': 3, 'I2C6': 6, 'I2C7': 5, 'I2C8': 4}


def pino_num(p):
    return p if isinstance(p, int) else PINOS[p]


def canal_mux(m):
    return m if isinstance(m, int) else CANAIS_I2C[m]
