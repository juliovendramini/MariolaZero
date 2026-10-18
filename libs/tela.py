from luma.core.interface.serial import i2c
from luma.core.render import canvas
from luma.oled.device import ssd1306
from PIL import ImageFont


class Tela:
    width = 128
    height = 64
    TAMANHO_TELA = 4
    TAMANHO_FONTE = 12
    serial = None
    display = None
    linhas = []

    def __init__(self, i2c_bus=0, i2c_address=0x3C):
        self.serial = i2c(port=i2c_bus, address=i2c_address)
        self.display = ssd1306(self.serial, width=self.width, height=self.height, rotate=0)
        self.font = ImageFont.truetype(
            '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
            self.TAMANHO_FONTE,
        )
        with canvas(self.display) as draw:
            draw.rectangle(self.display.bounding_box, outline='black', fill='black')
        self.linhas = ['', '', '', '']

    def escreve(self, texto, linha=0):
        self.linhas[linha] = texto
        self._desenha()

    def limpa(self, linha=-1):
        if linha == -1:
            self.linhas = ['', '', '', '']
        else:
            self.linhas[linha] = ''
        self._desenha()

    def apaga(self, linha):
        if linha < 0 or linha >= self.TAMANHO_TELA:
            raise ValueError('Linha inválida. Deve ser entre 0 e 3.')
        self.linhas[linha] = ''
        self._desenha()

    def _desenha(self):
        """Desenha o conteúdo na tela."""
        with canvas(self.display) as draw:
            for i, linha in enumerate(self.linhas):
                draw.text((0, i * 15), linha, font=self.font, fill="white")
