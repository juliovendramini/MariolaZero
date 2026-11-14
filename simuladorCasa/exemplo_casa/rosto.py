"""As carinhas do robô, para a tela do rosto (OLED de 128 x 64, uma cor só).

Cada carinha é desenhada por código (olhos de cantos redondos, pálpebras, boca e enfeites), então dá
para mexer nos números e para animar: piscar, mexer os olhos, abrir e fechar a boca ao falar.

    from rosto import quadro, CARINHAS
    img = quadro('feliz')              # imagem do Pillow, 128 x 64, modo '1' (branco = pixel aceso)
    img = quadro('falando', t=0.3)     # t em segundos: as carinhas animadas mudam com o tempo

    python exemplo_casa/rosto.py folha.png      grava uma folha com todas, para olhar e escolher

A classe Rosto (no fim) escolhe a carinha da vez e manda para a tela do brick (no simulador, a do
painel "brick: tela + teclado"). Estilo aprovado pelo Julio em 12/11/2026.
"""

import math
import os
import sys

from PIL import Image, ImageDraw

L, A = 128, 64
OLHO_E, OLHO_D = 38, 90          # centro de cada olho (x); a esquerda é a esquerda de quem olha a tela
OLHO_Y = 27
OLHO_W, OLHO_H, RAIO = 30, 34, 9


class _Tela:
    """Atalhos de desenho em cima do Pillow. Branco = aceso."""

    def __init__(self):
        self.img = Image.new('1', (L, A), 0)
        self.d = ImageDraw.Draw(self.img)

    def olho(self, cx, cy=OLHO_Y, w=OLHO_W, h=OLHO_H, raio=RAIO):
        h = max(2, h)
        self.d.rounded_rectangle([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], radius=min(raio, h / 2, w / 2), fill=1)

    def palpebra(self, cx, cy=OLHO_Y, w=OLHO_W, h=OLHO_H, dentro=0, fora=0):
        """Pálpebra de cima: tapa 'dentro' pixels do lado do nariz e 'fora' do lado da orelha (uma reta
        inclinada entre os dois). dentro > fora = bravo; fora > dentro = triste."""
        esq = cx < L / 2
        y0 = cy - h / 2 - 2
        ya = y0 + 2 + (fora if esq else dentro)        # lado esquerdo do olho
        yb = y0 + 2 + (dentro if esq else fora)        # lado direito do olho
        self.d.polygon([(cx - w / 2 - 2, y0), (cx + w / 2 + 2, y0), (cx + w / 2 + 2, yb), (cx - w / 2 - 2, ya)], fill=0)

    def bochecha(self, cx, cy=OLHO_Y, w=OLHO_W, h=OLHO_H, sobe=12):
        """Pálpebra de baixo arredondada: o olho vira um arco, de quem sorri."""
        self.d.ellipse([cx - w / 2 - 4, cy + h / 2 - sobe, cx + w / 2 + 4, cy + h / 2 + sobe + 8], fill=0)

    def arco(self, cx, cy, w, h, inicio, fim, esp=3):
        self.d.arc([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], inicio, fim, fill=1, width=esp)

    def sorriso(self, cx=64, cy=52, w=26, h=14, esp=3):
        self.arco(cx, cy - h / 2, w, h, 20, 160, esp)

    def triste(self, cx=64, cy=51, w=22, h=12, esp=3):
        self.arco(cx, cy + h / 2, w, h, 200, 340, esp)

    def boca_o(self, cx=64, cy=55, w=10, h=10):
        self.d.ellipse([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], outline=1, width=2)

    def boca_aberta(self, cx=64, cy=50, w=22, h=12):
        self.d.chord([cx - w / 2, cy - h, cx + w / 2, cy + h], 0, 180, fill=1)

    def reta(self, x0, y0, x1, y1, esp=3):
        self.d.line([x0, y0, x1, y1], fill=1, width=esp)

    def coracao(self, cx, cy, s):
        r = s / 2
        self.d.ellipse([cx - s, cy - r, cx, cy + r], fill=1)
        self.d.ellipse([cx, cy - r, cx + s, cy + r], fill=1)
        self.d.polygon([(cx - s, cy + r * 0.25), (cx + s, cy + r * 0.25), (cx, cy + s * 1.15)], fill=1)

    def texto(self, x, y, s, tam=1):
        """Letras grossas feitas de retas, para os enfeites (Z, ?, !)."""
        t = 6 * tam
        for ch in s:
            if ch == 'Z':
                self.d.line([x, y, x + t, y, x, y + t, x + t, y + t], fill=1, width=2)
            elif ch == '?':
                self.d.arc([x, y, x + t, y + t * 0.9], 180, 90, fill=1, width=2)
                self.d.line([x + t / 2, y + t * 0.8, x + t / 2, y + t * 1.1], fill=1, width=2)
                self.d.rectangle([x + t / 2 - 1, y + t * 1.4, x + t / 2 + 1, y + t * 1.4 + 2], fill=1)
            elif ch == '!':
                self.d.line([x + t / 2, y, x + t / 2, y + t], fill=1, width=3)
                self.d.rectangle([x + t / 2 - 1, y + t * 1.3, x + t / 2 + 1, y + t * 1.3 + 2], fill=1)
            x += t + 3

    def gota(self, cx, cy, s=5):
        self.d.polygon([(cx, cy - s), (cx - s * 0.7, cy + s * 0.4), (cx + s * 0.7, cy + s * 0.4)], fill=1)
        self.d.ellipse([cx - s * 0.7, cy - s * 0.2, cx + s * 0.7, cy + s], fill=1)

    def estrela(self, cx, cy, s=4):
        self.d.line([cx - s, cy, cx + s, cy], fill=1, width=1)
        self.d.line([cx, cy - s, cx, cy + s], fill=1, width=1)
        self.d.point([(cx - 1, cy - 1), (cx + 1, cy + 1), (cx - 1, cy + 1), (cx + 1, cy - 1)], fill=1)


def _pisca(t):
    """Fração de olho aberto: fecha por um instante a cada 4 segundos."""
    f = t % 4.0
    return 0.12 if 3.8 < f < 3.95 else 1.0


# ---------------------------------------------------------------- as carinhas: nome -> função(tela, t)
def _neutro(s, t):
    h = OLHO_H * _pisca(t)
    s.olho(OLHO_E, h=h)
    s.olho(OLHO_D, h=h)


def _feliz(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, h=30)
        s.bochecha(x, h=30)


def _muito_feliz(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, OLHO_Y - 4, h=28)
        s.bochecha(x, OLHO_Y - 4, h=28, sobe=14)
    s.boca_aberta()


def _triste(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, OLHO_Y + 2, h=28)
        s.palpebra(x, OLHO_Y + 2, h=28, dentro=2, fora=14)
    s.triste()


def _chorando(s, t):
    _triste(s, t)
    dy = (t * 14) % 14
    s.gota(OLHO_E - 12, 44 + dy, 4)
    s.gota(OLHO_D + 12, 44 + (dy + 7) % 14, 4)


def _bravo(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, OLHO_Y + 2, h=28)
        s.palpebra(x, OLHO_Y + 2, h=28, dentro=15, fora=1)
    s.reta(54, 58, 74, 58)


def _surpreso(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, OLHO_Y - 2, w=32, h=40, raio=16)
    s.boca_o()


def _assustado(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, OLHO_Y, w=22, h=24, raio=11)
    s.boca_o(w=14, h=8)
    s.texto(112, 6, '!', 2)


def _desconfiado(s, t):
    s.olho(OLHO_E, h=14)
    s.olho(OLHO_D, h=30)
    s.palpebra(OLHO_D, h=30, dentro=10, fora=4)
    s.reta(56, 57, 76, 55)


def _zoeiro(s, t):
    """Olhar de malandro: pálpebras a meio pau, uma sobrancelha levantada e sorriso de canto."""
    s.olho(OLHO_E, OLHO_Y + 3, h=22)
    s.palpebra(OLHO_E, OLHO_Y + 3, h=22, dentro=9, fora=5)
    s.olho(OLHO_D, OLHO_Y, h=28)
    s.palpebra(OLHO_D, OLHO_Y, h=28, dentro=8, fora=3)
    s.arco(70, 50, 30, 16, 10, 110, 3)


def _piscadela(s, t):
    s.olho(OLHO_E, h=30)
    s.arco(OLHO_D, OLHO_Y + 6, 28, 18, 200, 340, 4)
    s.sorriso(w=22, h=10)


def _sonolento(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, OLHO_Y + 6, h=14, raio=6)
        s.palpebra(x, OLHO_Y + 6, h=14, dentro=4, fora=4)


def _dormindo(s, t):
    for x in (OLHO_E, OLHO_D):
        s.arco(x, OLHO_Y + 2, 28, 14, 20, 160, 3)
    k = int(t * 1.5) % 3
    for i in range(k + 1):
        s.texto(100 + i * 8, 12 - i * 5, 'Z', 1)


def _apaixonado(s, t):
    p = 1.0 + 0.12 * math.sin(t * 6)
    s.coracao(OLHO_E, OLHO_Y - 4, 13 * p)
    s.coracao(OLHO_D, OLHO_Y - 4, 13 * p)
    s.sorriso()


def _pensando(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x + 6, OLHO_Y - 6, w=24, h=24, raio=8)
    k = int(t * 2) % 4
    for i in range(k):
        s.d.ellipse([54 + i * 9, 54, 59 + i * 9, 59], fill=1)


def _ouvindo(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, w=30, h=38, raio=12)
    k = 1 + int(t * 3) % 3
    for i in range(k):                         # ondas de som dos dois lados
        s.arco(4, 30, 10 + i * 8, 16 + i * 10, 300, 60, 2)
        s.arco(124, 30, 10 + i * 8, 16 + i * 10, 120, 240, 2)


def _falando(s, t):
    h = OLHO_H * _pisca(t)
    s.olho(OLHO_E, OLHO_Y - 3, h=h)
    s.olho(OLHO_D, OLHO_Y - 3, h=h)
    abre = (2, 10, 5, 12, 3, 8)[int(t * 8) % 6]
    s.d.ellipse([64 - 11, 55 - abre / 2, 64 + 11, 55 + abre / 2], fill=1)


def _confuso(s, t):
    s.olho(OLHO_E, w=24, h=22, raio=8)
    s.olho(OLHO_D, OLHO_Y - 2, w=32, h=38, raio=12)
    s.reta(52, 57, 60, 54, 2)
    s.reta(60, 54, 68, 58, 2)
    s.reta(68, 58, 76, 55, 2)
    s.texto(110, 2, '?', 2)


def _envergonhado(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x - 5, OLHO_Y + 6, w=24, h=20, raio=8)
    for x0 in (14, 96):                        # risquinhos de bochecha corada
        for i in range(4):
            s.reta(x0 + i * 5, 58, x0 + i * 5 + 3, 52, 1)
    s.reta(58, 58, 70, 58, 2)


def _orgulhoso(s, t):
    for x in (OLHO_E, OLHO_D):
        s.arco(x, OLHO_Y + 8, 28, 22, 200, 340, 4)
    s.sorriso(w=30, h=16)
    s.estrela(112, 10, 5)
    s.estrela(12, 16, 3)


def _cansado(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, OLHO_Y + 4, h=20)
        s.palpebra(x, OLHO_Y + 4, h=20, dentro=3, fora=9)
    s.gota(116, 14 + (t * 8) % 10, 5)
    s.boca_o(w=12, h=6)


def _tonto(s, t):
    for x in (OLHO_E, OLHO_D):
        a = t * 6
        pts = [(x + (2 + i * 0.9) * math.cos(a + i * 0.7), OLHO_Y + (2 + i * 0.9) * math.sin(a + i * 0.7)) for i in range(18)]
        s.d.line(pts, fill=1, width=2)
    s.reta(52, 57, 60, 54, 2)
    s.reta(60, 54, 68, 58, 2)
    s.reta(68, 58, 76, 55, 2)


def _erro(s, t):
    for x in (OLHO_E, OLHO_D):
        s.reta(x - 11, OLHO_Y - 11, x + 11, OLHO_Y + 11, 4)
        s.reta(x - 11, OLHO_Y + 11, x + 11, OLHO_Y - 11, 4)
    s.triste(w=18, h=8)


def _nao(s, t):
    """Olhos apertados de quem diz 'não' ou faz força: > <"""
    s.reta(OLHO_E - 12, OLHO_Y - 10, OLHO_E + 10, OLHO_Y, 4)
    s.reta(OLHO_E + 10, OLHO_Y, OLHO_E - 12, OLHO_Y + 10, 4)
    s.reta(OLHO_D + 12, OLHO_Y - 10, OLHO_D - 10, OLHO_Y, 4)
    s.reta(OLHO_D - 10, OLHO_Y, OLHO_D + 12, OLHO_Y + 10, 4)
    s.reta(56, 57, 72, 57)


def _procurando(s, t):
    dx = 9 * math.sin(t * 2.5)
    for x in (OLHO_E, OLHO_D):
        s.olho(x + dx, w=26, h=30)


def _comemorando(s, t):
    _muito_feliz(s, t)
    k = int(t * 4) % 2
    for (x, y) in ((8, 8), (118, 12), (14, 48), (114, 44), (64, 4)):
        s.estrela(x, y + k * 2, 3 + k)


def _olhando_cima(s, t):
    for x in (OLHO_E, OLHO_D):
        s.olho(x, OLHO_Y - 8, w=28, h=30, raio=10)
    s.sorriso(w=18, h=8, cy=56)


def _carregando_objeto(s, t):
    """Fazendo força: olhos apertados para baixo e língua de fora."""
    for x in (OLHO_E, OLHO_D):
        s.olho(x, OLHO_Y + 4, h=16)
        s.palpebra(x, OLHO_Y + 4, h=16, dentro=8, fora=0)
    s.reta(54, 54, 74, 54)
    s.d.chord([60, 48, 72, 62], 0, 180, fill=1)


CARINHAS = {
    'neutro': _neutro, 'feliz': _feliz, 'muito_feliz': _muito_feliz, 'comemorando': _comemorando,
    'zoeiro': _zoeiro, 'piscadela': _piscadela, 'orgulhoso': _orgulhoso, 'apaixonado': _apaixonado,
    'triste': _triste, 'chorando': _chorando, 'bravo': _bravo, 'nao': _nao,
    'surpreso': _surpreso, 'assustado': _assustado, 'confuso': _confuso, 'desconfiado': _desconfiado,
    'envergonhado': _envergonhado, 'cansado': _cansado, 'fazendo_forca': _carregando_objeto, 'tonto': _tonto,
    'ouvindo': _ouvindo, 'pensando': _pensando, 'falando': _falando, 'procurando': _procurando,
    'olhando_para_cima': _olhando_cima, 'sonolento': _sonolento, 'dormindo': _dormindo, 'erro': _erro,
}


def quadro(nome, t=0.0):
    """A carinha 'nome' no instante t (segundos): imagem do Pillow de 128 x 64, modo '1'."""
    s = _Tela()
    CARINHAS.get(nome, _neutro)(s, t)
    return s.img


def folha(caminho, colunas=4, escala=3, t=1.3):
    """Grava uma imagem com todas as carinhas e os nomes, para olhar e escolher."""
    nomes = list(CARINHAS)
    linhas = math.ceil(len(nomes) / colunas)
    cw, ch = L * escala + 16, A * escala + 34
    img = Image.new('RGB', (colunas * cw + 16, linhas * ch + 16), (24, 26, 32))
    d = ImageDraw.Draw(img)
    for i, nome in enumerate(nomes):
        x, y = 16 + (i % colunas) * cw, 16 + (i // colunas) * ch
        q = quadro(nome, t).convert('L').resize((L * escala, A * escala), Image.NEAREST)
        azul = Image.new('RGB', q.size, (120, 220, 255))            # a cor do OLED azul-claro
        img.paste(Image.new('RGB', q.size, (0, 0, 0)), (x, y))
        img.paste(azul, (x, y), q)
        d.rectangle([x - 1, y - 1, x + L * escala, y + A * escala], outline=(70, 74, 84))
        d.text((x + 2, y + A * escala + 6), f'{i + 1}. {nome}', fill=(230, 232, 238))
    img.save(caminho)
    return caminho


# ====================================================================== a tela e o rosto vivo
# A tela do rosto é a do próprio brick: o Julio vai trocar a OLED pequena (SSD1306 de 0,96") pela de 2,42"
# (SSD1309, também 128 x 64) no mesmo conector TELA: barramento I2C 0, endereço 0x3C, como na lib tela.py.
ROSTO_BARRAMENTO = 0
ROSTO_ENDERECO = 0x3C
ROSTO_GIRA = int(os.environ.get('ROSTO_GIRA', '0'))      # 0 a 3 (x 90°), se a tela ficar montada girada
# carinhas que o cérebro pode escolher para mostrar o que sente (as outras são estados: ouvindo, pensando...)
HUMORES = ['neutro', 'feliz', 'muito_feliz', 'comemorando', 'zoeiro', 'piscadela', 'orgulhoso', 'apaixonado',
           'triste', 'chorando', 'bravo', 'nao', 'surpreso', 'assustado', 'confuso', 'desconfiado',
           'envergonhado', 'cansado', 'tonto', 'sonolento']


def abre_tela():
    """A tela do rosto, que é a tela do brick (luma.oled, a mesma lib da tela.py). No simulador é a tela do
    painel "brick: tela + teclado" da janela. None se não há tela (o rosto vira faz de conta e o programa
    segue)."""
    try:
        from luma.core.interface.serial import i2c
        from luma.oled.device import ssd1309
        return ssd1309(i2c(port=ROSTO_BARRAMENTO, address=ROSTO_ENDERECO), rotate=ROSTO_GIRA)
    except Exception as e:
        print(f'[rosto] sem a tela do rosto ({type(e).__name__}: {e})')
        return None


class Rosto:
    """O rosto vivo: escolhe a carinha da vez e redesenha a tela.

    Três camadas, da mais forte para a mais fraca:
      * momento(nome, segundos): uma reação rápida (comemorando por 3 s depois de guardar);
      * estado(nome): o que o robô está fazendo agora (ouvindo, pensando, falando, procurando);
        estado(None) quando acaba;
      * humor(nome): como ele está; fica até mudar (volta a 'neutro' sozinho depois de um tempo).

    passo() redesenha, no máximo QUADROS_S vezes por segundo. Não há thread: o Robo.move() chama passo()
    a cada volta dos laços do robô (basta pôr o Rosto em robo.rosto)."""

    QUADROS_S = 8
    HUMOR_DURA_S = 25

    def __init__(self, tela=None):
        import time
        self._time = time
        self.tela = tela if tela is not None else abre_tela()
        self._humor, self._humor_ate = 'neutro', None
        self._estado = None
        self._momento, self._momento_ate = None, 0.0
        self._ultimo_t = -1.0
        self._ultima = None
        self.parado_desde = time.time()      # para dormir quando ninguém fala com ele
        self.falando = False                 # True enquanto o robô fala: a boca mexe, com a carinha que for

    def humor(self, nome):
        if nome in CARINHAS:
            self._humor = nome
            self._humor_ate = None if nome == 'neutro' else self._time.time() + self.HUMOR_DURA_S
            self.passo(True)

    def estado(self, nome):
        self._estado = nome if nome in CARINHAS else None
        self.parado_desde = self._time.time()
        self.passo(True)

    def momento(self, nome, segundos=3.0):
        if nome in CARINHAS:
            self._momento, self._momento_ate = nome, self._time.time() + segundos
            self.passo(True)

    def fala(self, sim):
        """Liga ou desliga a boca que mexe (o robô está falando)."""
        self.falando = bool(sim)
        self.parado_desde = self._time.time()
        self.passo(True)

    def atual(self):
        """O nome da carinha que vale agora."""
        agora = self._time.time()
        if self._momento and agora < self._momento_ate:
            return self._momento
        self._momento = None
        if self._estado:
            return self._estado
        if self._humor_ate is not None and agora > self._humor_ate:
            self._humor, self._humor_ate = 'neutro', None
        if self._humor == 'neutro':
            parado = agora - self.parado_desde
            if parado > 180:
                return 'dormindo'
            if parado > 60:
                return 'sonolento'
        return self._humor

    def passo(self, ja=False):
        agora = self._time.time()
        if not ja and agora - self._ultimo_t < 1.0 / self.QUADROS_S:
            return
        self._ultimo_t = agora
        if self.tela is None:
            return
        img = quadro(self.atual(), agora)
        if self.falando:
            d = ImageDraw.Draw(img)                    # apaga a boca da carinha e põe a que mexe
            d.rectangle([44, 46, 84, 63], fill=0)
            abre = (2, 10, 5, 12, 3, 8)[int(agora * 8) % 6]
            d.ellipse([64 - 11, 55 - abre / 2, 64 + 11, 55 + abre / 2], fill=1)
        bits = img.tobytes()
        if bits != self._ultima:
            self._ultima = bits
            try:
                self.tela.display(img)
            except Exception as e:                 # a tela soltou: o robô não para por isso
                print(f'[rosto] a tela do rosto falhou ({type(e).__name__}: {e})')
                self.tela = None


if __name__ == '__main__':
    print('gravei', folha(sys.argv[1] if len(sys.argv) > 1 else 'carinhas.png'))
