"""Substituto do `luma.oled` (tela OLED SSD1306 128x64 do brick) ligado ao simulador.

A lib tela.py do Mariola roda sem mudar: ela desenha com o Pillow (ImageDraw) dentro de
`canvas(device)` e, ao sair do `with`, a imagem vai para a tela do simulador.

Requer o Pillow (pip install pillow), como no robô.
"""

import os

from . import cliente

# ------------------------------------------------------------------ luma.core.error
class Error(Exception):
    pass


class DeviceNotFoundError(Error):
    pass


class DevicePermissionError(Error):
    pass


class DeviceAddressError(Error):
    pass


class DeviceDisplayModeError(Error):
    pass


def _cfg_tela():
    c = cliente.config.get('tela')
    if c is True:
        c = {}
    if not isinstance(c, dict):
        return None
    return {'barramento': int(c.get('barramento', 0)), 'endereco': int(c.get('endereco', 0x3C))}


# ------------------------------------------------------------------ luma.core.interface.serial
class i2c:
    """Interface I2C da tela. Só existe a tela configurada no robo.json (barramento e endereço)."""

    def __init__(self, bus=None, port=1, address=0x3C, **kwargs):
        cfg = _cfg_tela()
        if cfg is None:
            raise DeviceNotFoundError('I2C device not found: este robô não tem tela (sem "tela" no robo.json)')
        if int(port) != cfg['barramento']:
            raise DeviceNotFoundError(f'I2C device not found on bus {port} (a tela está no barramento '
                                      f'{cfg["barramento"]})')
        if int(address) != cfg['endereco']:
            raise DeviceAddressError(f'I2C device not found on address: 0x{int(address):02X}')
        self._port = int(port)
        self._addr = int(address)

    def command(self, *cmd):
        pass

    def data(self, data):
        pass

    def cleanup(self):
        pass


def spi(*a, **k):
    raise DeviceNotFoundError('no simulador só existe a tela I2C')


# ------------------------------------------------------------------ luma.oled.device
class ssd1306:
    """SSD1306 128x64 (ou 128x32). display(imagem) manda a imagem para o simulador."""

    def __init__(self, serial_interface=None, width=128, height=64, rotate=0, **kwargs):
        self._serial = serial_interface or i2c(port=(_cfg_tela() or {}).get('barramento', 0))
        self.width = int(width)
        self.height = int(height)
        self.rotate = int(rotate) % 4
        if self.rotate % 2:
            self.width, self.height = self.height, self.width
        self.size = (self.width, self.height)
        self.bounding_box = (0, 0, self.width - 1, self.height - 1)
        self.mode = '1'
        self.persist = False
        self._ligada = True
        self._contraste = 0xCF
        self._ultima = None
        self.clear()

    def _envia(self, bits):
        try:
            cliente.conexao.chamar('oled', b=bits.hex() if bits is not None else None,
                                   w=self._larg_fisica, h=self._alt_fisica)
        except Exception:
            pass

    @property
    def _larg_fisica(self):
        return self.height if self.rotate % 2 else self.width

    @property
    def _alt_fisica(self):
        return self.width if self.rotate % 2 else self.height

    def display(self, image):
        img = image
        if img.mode != '1':
            img = img.convert('1')
        if img.size != self.size:
            raise DeviceDisplayModeError(f'Invalid image size: {img.size} (a tela é {self.size})')
        if self.rotate:
            img = img.rotate(-90 * self.rotate, expand=True)
        bits = img.tobytes()          # 1 bit por pixel, linha a linha, bit mais significativo primeiro
        self._ultima = bits
        if self._ligada:
            self._envia(bits)

    def clear(self):
        from PIL import Image
        self.display(Image.new('1', self.size))

    def show(self):
        self._ligada = True
        self._envia(self._ultima)

    def hide(self):
        self._ligada = False
        self._envia(None)

    def contrast(self, level):
        self._contraste = int(level)

    def command(self, *cmd):
        pass

    def cleanup(self):
        if not self.persist:
            self.hide()
            self.clear()


sh1106 = ssd1306
ssd1309 = ssd1306


# ------------------------------------------------------------------ luma.core.render
class canvas:
    """with canvas(device) as draw: ...  -> ao sair, device.display(imagem)."""

    def __init__(self, device, background=None, dither=False):
        from PIL import Image
        self.device = device
        self.image = background.copy() if background is not None else Image.new(device.mode, device.size)
        self.dither = dither

    def __enter__(self):
        from PIL import ImageDraw
        self.draw = ImageDraw.Draw(self.image)
        return self.draw

    def __exit__(self, tipo, valor, tb):
        if tipo is None:
            self.device.display(self.image)
        del self.draw
        return False


# ------------------------------------------------------------------ fontes
_PASTA_FONTES = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'fontes')


def instala_fontes():
    """No robô as libs abrem /usr/share/fonts/truetype/dejavu/DejaVuSans.ttf. No Windows esse
    arquivo não existe: procura a mesma fonte na pasta fake_hw/fontes do simulador."""
    try:
        from PIL import ImageFont
    except ImportError:
        return
    original = ImageFont.truetype
    if getattr(original, '_simulador', False):
        return

    def truetype(font=None, size=10, *a, **k):
        try:
            return original(font, size, *a, **k)
        except OSError:
            if isinstance(font, str):
                alt = os.path.join(_PASTA_FONTES, os.path.basename(font))
                if os.path.exists(alt):
                    return original(alt, size, *a, **k)
            raise

    truetype._simulador = True
    ImageFont.truetype = truetype


def modulos():
    import types
    mods = {}

    def mod(nome, **attrs):
        m = types.ModuleType(nome)
        m.__dict__.update(attrs)
        m.__path__ = []
        mods[nome] = m
        return m

    erro = mod('luma.core.error', Error=Error, DeviceNotFoundError=DeviceNotFoundError,
               DevicePermissionError=DevicePermissionError, DeviceAddressError=DeviceAddressError,
               DeviceDisplayModeError=DeviceDisplayModeError)
    serial = mod('luma.core.interface.serial', i2c=i2c, spi=spi)
    interface = mod('luma.core.interface', serial=serial)
    render = mod('luma.core.render', canvas=canvas)
    core = mod('luma.core', error=erro, interface=interface, render=render)
    device = mod('luma.oled.device', ssd1306=ssd1306, sh1106=sh1106, ssd1309=ssd1309)
    oled = mod('luma.oled', device=device)
    mod('luma', core=core, oled=oled)
    return mods
