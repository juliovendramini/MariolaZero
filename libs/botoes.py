import gpiod
from gpiod.line import Direction, Value


class Botoes:
    P1 = 259
    P2 = 260
    P3 = 71
    P4 = 234
    P5 = 228
    P6 = 265
    P7 = 266
    P8 = 267
    BOTAO1 = None
    BOTAO2 = None
    BOTAO3 = None
    BOTAO4 = None
    BOTAO5 = None
    BOTAO6 = None
    BOTAO7 = None
    BOTAO8 = None
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
        self.BOTAO5 = gpiod.request_lines(
            chip_name,
            config={
                self.P5: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self.BOTAO6 = gpiod.request_lines(
            chip_name,
            config={
                self.P6: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self.BOTAO7 = gpiod.request_lines(  
            chip_name,
            config={
                self.P7: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self.BOTAO8 = gpiod.request_lines(
            chip_name,
            config={
                self.P8: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )


    def le_botao(self, pin):
        if pin not in {self.P1, self.P2, self.P3, self.P4, self.P5, self.P6, self.P7, self.P8}:
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
        if pin == self.P5:
            if self.BOTAO5.get_value(self.P5) == self.LIBERADO:
                return self.LIBERADO
            else:
                return self.APERTADO
        if pin == self.P6:
            if self.BOTAO6.get_value(self.P6) == self.LIBERADO:
                return self.LIBERADO
            else:
                return self.APERTADO
        if pin == self.P7:
            if self.BOTAO7.get_value(self.P7) == self.LIBERADO:
                return self.LIBERADO
            else:
                return self.APERTADO
        if pin == self.P8:
            if self.BOTAO8.get_value(self.P8) == self.LIBERADO:
                return self.LIBERADO
            else:
                return self.APERTADO

    def botao_pressionado(self, pin):
        """Verifica se um botão está pressionado."""
        return self.le_botao(pin) == self.APERTADO
