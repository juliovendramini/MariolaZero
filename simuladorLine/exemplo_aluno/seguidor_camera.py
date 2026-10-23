"""Seguidor de linha só com a câmera de linha (OpenCV), sem o sensor de reflexão.

A câmera fica embaixo do robô, olhando reto para o chão; a frente do robô fica no topo da imagem
e as rodas da frente aparecem nas bordas da esquerda e da direita (por isso as bordas são cortadas).

Ponto de partida, não a solução:
* linha: PD na posição da linha na metade de cima da imagem (a parte à frente da câmera)
* gap (linha sumiu): segue reto
* verde: quadrado verde com a linha preta logo acima dele (antes da interseção) marca o lado;
  quando ele passa da metade da imagem, anda até a interseção e gira 90° (os dois = meia-volta)
* vermelho (chegada): para
Não trata obstáculo, rampa nem área de resgate.

No simulador: robô robo_4x4_camera.json (o 4x4 com a câmera no lugar do sensor de linha) e
botão Programa > exemplo_aluno/seguidor_camera.py.
No robô: a câmera de linha é a /dev/video_usb2 (regra 99-cameras.rules, porta USB 2).
"""

import time

import cv2
import numpy as np

try:
    import simdebug                      # no robô, copie robo_real/simdebug.py (não faz nada)
except ImportError:
    simdebug = None

from robo import Robo

CAMERA = '/dev/video_usb2'
LARGURA, ALTURA = 320, 240
MM_POR_PX = 0.52      # na altura da câmera (106 mm, 76 graus): 320 px = 165 mm
X_CAMERA_MM = 50      # a câmera fica 50 mm à frente do centro do robô
CORTE_RODAS = 40      # px cortados em cada borda (as rodas aparecem ali)
LIMIAR_PRETO = 90     # cinza abaixo disso = linha
MIN_PIXELS = 300      # menos pixels pretos que isso = sem linha
MIN_VERDE = 600       # px de um quadrado verde (inteiro, 25 x 25 mm, dá uns 2300)
MIN_VERMELHO = 3000

VEL = 35
KP = 0.9
KD = 5.0
TEMPO = 480           # s


def abre_camera():
    cam = cv2.VideoCapture(CAMERA)
    if not cam.isOpened():
        raise RuntimeError(f'não abriu a câmera {CAMERA}')
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, LARGURA)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTURA)
    return cam


def mascaras(img):
    """Máscaras (0/255) de preto, verde e vermelho, sem as bordas das rodas."""
    cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    _, preto = cv2.threshold(cinza, LIMIAR_PRETO, 255, cv2.THRESH_BINARY_INV)
    verde = cv2.inRange(hsv, (40, 90, 50), (90, 255, 255))
    vermelho = cv2.inRange(hsv, (0, 120, 60), (10, 255, 255)) | cv2.inRange(hsv, (170, 120, 60), (180, 255, 255))
    for m in (preto, verde, vermelho):
        m[:, :CORTE_RODAS] = 0
        m[:, -CORTE_RODAS:] = 0
    return preto, verde, vermelho


def posicao_linha(preto):
    """mm da linha em relação ao centro da imagem (+ = esquerda), na metade de cima.
    Devolve None se não tem linha."""
    m = cv2.moments(preto[:ALTURA // 2], binaryImage=True)
    if m['m00'] < MIN_PIXELS:
        return None
    return (LARGURA / 2 - m['m10'] / m['m00']) * MM_POR_PX


def marcadores(preto, verde):
    """Quadrados verdes que valem (linha preta logo acima = antes da interseção).
    Devolve lista de (lado, linha_da_imagem do centro), lado 'esq' ou 'dir'."""
    n, _, stats, centros = cv2.connectedComponentsWithStats(verde)
    out = []
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if area < MIN_VERDE:
            continue
        cx, cy = centros[i]
        acima = preto[max(0, y - 30):y, x:x + w]          # faixa logo acima do quadrado
        if y < 5 or acima.size == 0 or cv2.countNonZero(acima) < 0.3 * acima.size:
            continue
        linha = preto[int(cy), :]                         # onde está a linha nessa altura
        cols = np.nonzero(linha)[0]
        if len(cols) == 0:
            continue
        out.append(('esq' if cx < cols.mean() else 'dir', cy))
    return out


def main():
    r = Robo()
    cam = abre_camera()
    r.espera_botao()
    erro_ant = 0.0
    quadros = 0
    verde_visto = set()        # lados com verde valendo na interseção que vem
    t0 = time.time()
    try:
        while time.time() - t0 < TEMPO:
            ok, img = cam.read()
            if not ok:
                print('falha lendo a câmera')
                break
            quadros += 1
            preto, verde, vermelho = mascaras(img)

            if cv2.countNonZero(vermelho) > MIN_VERMELHO:
                r.para()
                print('chegada (vermelho): parando')
                time.sleep(7)
                break

            marcas = marcadores(preto, verde)
            for lado, cy in marcas:
                # só vale o verde que aparece lá na frente (chegando): depois de uma curva, o
                # verde da mesma interseção aparece embaixo da imagem e não pode contar de novo
                if verde_visto or cy < ALTURA * 0.45:
                    verde_visto.add(lado)
            if not verde_visto:
                marcas = []
            # o verde passou da metade da imagem: a interseção está logo à frente do centro do robô
            if verde_visto and (not marcas or max(cy for _, cy in marcas) > ALTURA * 0.62):
                lados = verde_visto
                verde_visto = set()
                r.anda_mm(X_CAMERA_MM + 15, vel=30)
                if lados == {'esq', 'dir'}:
                    print('verde dos dois lados: meia-volta')
                    r.gira(180)
                else:
                    print('verde:', ', '.join(lados))
                    r.gira(90 if 'esq' in lados else -90)
                erro_ant = 0.0
                continue

            erro = posicao_linha(preto)
            if erro is None:                     # gap: reto
                r.anda(VEL, VEL)
                txt = 'sem linha: reto'
            else:
                corr = KP * erro + KD * (erro - erro_ant)
                erro_ant = erro
                r.anda(VEL - corr, VEL + corr)
                txt = f'linha {erro:+.0f} mm'
            if simdebug and quadros % 10 == 0:
                fps = quadros / max(1e-6, time.time() - t0)
                simdebug.texto(f'{txt}   verde {sorted(verde_visto)}   {fps:.0f} quadros/s')
    finally:
        r.para()
        cam.release()


if __name__ == '__main__':
    main()
