"""Teste rápido do robô de casa no simulador: mexe a garra e a câmera, anda, gira, lê os sensores e
tira fotos. Serve para conferir que tudo responde (no simulador e no robô de verdade).

    python simulador.py --programa exemplo_casa/teste_basico.py --sem-janela --velocidade 4

Com a variável CASA_FOTOS apontando para uma pasta, grava ali as fotos da câmera.
"""

import os
import time

import cv2

from robo import Robo, BARRAS_CHAO, BARRAS_DESCANSO, BARRAS_CAIXA, ABERTA

PASTA = os.environ.get('CASA_FOTOS')


def foto(r, nome):
    img = r.foto()
    if img is None:
        print(f'foto {nome}: a câmera não respondeu')
        return
    b, g, rr = (int(v) for v in img.reshape(-1, 3).mean(axis=0))
    print(f'foto {nome}: {img.shape[1]}x{img.shape[0]}, cor média BGR ({b}, {g}, {rr})')
    if PASTA:
        cv2.imwrite(os.path.join(PASTA, f'{nome}.png'), img)


def main():
    r = Robo()
    r.espera_botao()
    t0 = time.time()
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=35, espera=1.0)
    foto(r, '1_descanso_35')
    print('distâncias:', {k: r.distancia(k) for k in r.vl})
    r.garra(inclinacao=-40, espera=0.8)
    foto(r, '2_olhando_para_cima')
    r.garra(inclinacao=15, espera=0.8)
    foto(r, '3_procurando_15')
    r.anda(300)
    print('andou 300 mm; giro', round(r.z(), 1))
    r.gira(90)
    print('girou 90 para a esquerda; giro', round(r.z(), 1))
    r.garra(barras=BARRAS_CHAO, abertura=ABERTA, inclinacao=70, espera=1.0)
    foto(r, '4_garra_no_chao_70')
    r.garra(barras=BARRAS_CAIXA, abertura=40, inclinacao=40, espera=1.2)
    foto(r, '5_garra_no_alto_40')
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=35, espera=1.0)
    r.gira(-90)
    print('distâncias:', {k: r.distancia(k) for k in r.vl})
    print(f'fim do teste em {time.time() - t0:.1f} s')
    r.para()


if __name__ == '__main__':
    main()
