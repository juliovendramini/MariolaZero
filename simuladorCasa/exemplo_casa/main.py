"""Exemplo do robô de casa: procura um objeto colorido pela câmera, pega, acha a caixa (roxa) e guarda.

    python simulador.py                       (janela; este é o programa padrão)
    python simulador.py --sem-janela --velocidade 4

É um exemplo simples, sem mapa: gira até ver um objeto, vai reto até ele, pega, gira até ver a caixa,
vai até ela e solta. Se um móvel fica no caminho ou a caixa não aparece, recua, sai de lado ou anda um
pouco e tenta de novo; se nada dá certo, deixa o objeto no chão e para. Serve para conferir o simulador
e como ponto de partida: o robô não sabe onde está, e é isso que o "cérebro" vai ter de resolver.

O ciclo:
  1. descanso/procura: barras na horizontal, câmera 15° para baixo; gira até ver um objeto;
  2. aproxima centralizando o objeto na imagem, até uns 35 cm;
  3. baixa a garra aberta e avança até o VL53 da frente ver o objeto entre os dedos;
  4. fecha, levanta e confere pelo VL53 (o objeto saiu da frente dele = está na garra);
  5. gira até ver a caixa, chega perto, sobe a garra por cima da borda, avança e abre.
"""

import random
import time

import cv2
import numpy as np

from robo import Robo, BARRAS_CHAO, BARRAS_DESCANSO, BARRAS_CAIXA, ABERTA, LARGURA, ALTURA

SAT_MIN, VAL_MIN = 145, 70        # o que conta como "colorido" (objetos e caixa): cor viva. Piso, parede e
                                  # móveis são mais pálidos (a madeira da mesa de centro chega a 136)
CAIXA_H = (125, 160)              # matiz (H do OpenCV, 0-179) da caixa roxa
AREA_MIN = 25                     # pixels
CAIXA_PERTO = 0.45                # de perto a caixa ocupa pelo menos isso da largura da imagem
TENTATIVAS_CAIXA = 6

sorteio = random.Random(1)


def manchas(img):
    """(objeto, caixa): a maior mancha colorida que não é roxa e a maior roxa, cada uma como
    (cx, cy, x, y, w, h, area) ou None."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    colorido = (hsv[:, :, 1] > SAT_MIN) & (hsv[:, :, 2] > VAL_MIN)
    roxo = colorido & (hsv[:, :, 0] >= CAIXA_H[0]) & (hsv[:, :, 0] <= CAIXA_H[1])
    res = []
    for m in (colorido & ~roxo, roxo):
        n, _, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8), connectivity=8)
        melhor = None
        for i in range(1, n):
            x, y, w, h, a = st[i]
            if a >= AREA_MIN and (melhor is None or a > melhor[6]):
                melhor = (cen[i][0], cen[i][1], x, y, w, h, a)
        res.append(melhor)
    return res


def ve(r, qual):
    img = r.foto()
    if img is None:
        return None
    return manchas(img)[qual]


def procura(r, qual, nome):
    """Gira para a esquerda até a mancha aparecer bem dentro da imagem. False se deu uma volta e não achou."""
    z0 = r.z()
    while abs(r.z() - z0) < 370:
        m = ve(r, qual)
        if m is not None and LARGURA * 0.2 < m[0] < LARGURA * 0.8:
            r.para()
            return True
        r.move(0, 0, 22)
    r.para()
    print(f'não achei {nome} em volta')
    return False


def aproxima(r, qual, para_quando, tempo=25, desiste=None):
    """Vai até a mancha, centralizando-a na imagem. para_quando(mancha, distância da frente) -> True para
    parar (chegou). desiste(mancha, distância) -> True para parar sem ter chegado (algo no caminho).
    qual = 0 (objeto), 1 (caixa) ou uma função que recebe o robô e devolve a mancha a seguir."""
    t0 = time.time()
    perdido = 0
    while time.time() - t0 < tempo:
        m = qual(r) if callable(qual) else ve(r, qual)
        d = r.distancia('frente')
        if m is None:
            perdido += 1
            if perdido > 8:
                r.para()
                return False
            r.move(12, 0, 0)
            continue
        perdido = 0
        if para_quando(m, d):
            r.para()
            return True
        if desiste is not None and desiste(m, d):
            r.para()
            return False
        erro = (m[0] - LARGURA / 2) / (LARGURA / 2)          # -1 (esquerda) a 1 (direita)
        r.move(28 if abs(erro) < 0.25 else 10, 0, -30 * erro)
    r.para()
    return False


def pega(r):
    """Com o objeto uns 35 cm à frente: baixa a garra aberta, avança até ele ficar entre os dedos e fecha."""
    r.garra(barras=BARRAS_CHAO, abertura=ABERTA, inclinacao=45, espera=0.9)
    r.zera_encoder()
    while True:
        m = ve(r, 0)
        d = r.distancia('frente')
        if d <= 100:                       # o VL53 da frente fica 95 mm atrás do meio dos dedos
            break
        if r.deslocamento()[0] > 420:
            r.para()
            return False
        erro = 0.0 if m is None else (m[0] - LARGURA / 2) / (LARGURA / 2)
        r.move(14, 0, -22 * erro)
    r.para()
    r.garra(abertura=0, espera=0.9)
    r.garra(barras=BARRAS_DESCANSO, inclinacao=15, espera=0.9)
    return r.distancia('frente') > 250     # o objeto subiu com a garra: o VL53 não o vê mais


def guarda(r):
    """Com a caixa à vista: chega perto, sobe a garra por cima da borda, avança e solta. False se não
    chegou (um móvel no caminho, a caixa sumiu de vista ou o tempo acabou): o objeto continua na garra."""
    def perto(m, d):
        return d <= 210 and m[4] >= LARGURA * CAIXA_PERTO

    def movel(m, d):
        # algo a menos de 23 cm que não é a caixa (de perto ela enche a imagem): móvel ou parede
        return d <= 230 and m[4] < LARGURA * CAIXA_PERTO

    if not aproxima(r, 1, perto, desiste=movel):
        return False
    r.garra(barras=BARRAS_CAIXA, inclinacao=60, espera=1.2)
    t0 = time.time()
    while r.distancia('frente') > 45 and time.time() - t0 < 6:
        r.move(12, 0, 0)
    r.para()
    r.garra(abertura=ABERTA, espera=0.8)
    r.anda(-220)
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=15, espera=0.9)
    return True


def sai_de_lado(r):
    """Algo no caminho: recua e anda de lado para o lado mais livre."""
    r.anda(-150)
    lado = 1 if r.distancia('esquerda') >= r.distancia('direita') else -1
    r.desliza(lado * 300)


def passeia(r):
    """A caixa não aparece daqui: vira para um lado livre e anda até 70 cm."""
    r.gira(sorteio.choice((-135, -90, -45, 45, 90, 135)))
    for _ in range(8):
        if r.distancia('frente') > 600:
            break
        r.gira(45)
    r.zera_encoder()
    t0 = time.time()
    while r.deslocamento()[0] < 700 and r.distancia('frente') > 260 and time.time() - t0 < 12:
        r.move(28, 0, 0)
    r.para()


def leva_para_a_caixa(r):
    """Com um objeto na garra: procura a caixa e guarda, tentando de novo de outro lugar se não der."""
    for _ in range(TENTATIVAS_CAIXA):
        if not procura(r, 1, 'a caixa'):
            passeia(r)
        elif guarda(r):
            return True
        else:
            print('não cheguei na caixa: tento por outro lado')
            sai_de_lado(r)
    return False


def main():
    r = Robo()
    r.espera_botao()
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=15, espera=1.0)
    guardados = 0
    falhas = 0
    while falhas < 4:
        if not procura(r, 0, 'nenhum objeto'):
            break
        if not aproxima(r, 0, lambda m, d: m[3] + m[5] > ALTURA * 0.80 or d < 330):
            print('perdi o objeto de vista')
            falhas += 1
            r.gira(40)
            continue
        if not pega(r):
            print('não consegui pegar: tento de novo')
            falhas += 1
            r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=15, espera=0.8)
            r.anda(-150)
            continue
        falhas = 0
        print('peguei um objeto')
        if not leva_para_a_caixa(r):
            print('não achei o caminho até a caixa: deixo o objeto aqui')
            r.garra(barras=BARRAS_CHAO, espera=0.9)
            r.garra(abertura=ABERTA, espera=0.8)
            r.anda(-150)
            r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=15, espera=0.9)
            break
        guardados += 1
        print(f'guardei ({guardados})')
        r.gira(150)               # vira de costas para a caixa antes de procurar o próximo
    print(f'fim: {guardados} objeto(s) guardado(s)')
    r.para()


if __name__ == '__main__':
    main()
