import gpiod
from gpiod.line import Direction, Value


class Botoes:
    P1 = 267
    P2 = 266
    P3 = 265
    P4 = 234
    BOTAO1 = None
    BOTAO2 = None
    BOTAO3 = None
    BOTAO4 = None
    LIBERADO = Value.ACTIVE
    APERTADO = Value.INACTIVE
    chip = None

    def __init__(self):
        chip_name = '/dev/gpiochip0'
        self.chip = gpiod.Chip(chip_name)
        self.BOTAO1 = gpiod.request_lines(
            chip_name,
            config={
                self.P1: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self.BOTAO2 = gpiod.request_lines(
            chip_name,
            config={
                self.P2: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self.BOTAO3 = gpiod.request_lines(
            chip_name,
            config={
                self.P3: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self.BOTAO4 = gpiod.request_lines(
            chip_name,
            config={
                self.P4: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )

    def le_botao(self, pin):
        if pin not in {self.P1, self.P2, self.P3, self.P4}:
            raise ValueError('Porta Inválida')
        # de acordo com o pino escolhido, retorna o valor do botão
        if pin == self.P1:
            if self.BOTAO1.get_value(self.P1) == self.LIBERADO:
                return self.LIBERADO
            else:
                return self.APERTADO
        if pin == self.P2:
            if self.BOTAO2.get_value(self.P2) == self.LIBERADO:
                return self.LIBERADO
            else:
                return self.APERTADO
        if pin == self.P3:
            if self.BOTAO3.get_value(self.P3) == self.LIBERADO:
                return self.LIBERADO
            else:
                return self.APERTADO
        if pin == self.P4:
            if self.BOTAO4.get_value(self.P4) == self.LIBERADO:
                return self.LIBERADO
            else:
                return self.APERTADO

    def botao_pressionado(self, pin):
        """Verifica se um botão está pressionado."""
        return self.le_botao(pin) == self.APERTADO
