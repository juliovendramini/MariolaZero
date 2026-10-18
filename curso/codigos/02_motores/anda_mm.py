"""Tutorial 2a — andar uma distância certa usando o encoder.

Robô de esteira (só os 2 motores do Mariola):
    python simulador.py --robo robo_esteira.json --programa CAMINHO/02_motores/anda_mm.py
"""
import math
import time

from motores import Motores

DIAMETRO = 40.0                      # mm: roda (ou polia da esteira). MEÇA no seu robô!
CONTAGENS_POR_VOLTA = 17 * 34 * 2    # pulsos do encoder x redução x 2 (o Mariola conta as 2 bordas)
MM_POR_CONTAGEM = math.pi * DIAMETRO / CONTAGENS_POR_VOLTA

motores = Motores(False)             # False: eu decido quando mandar (atualiza_motores)
motores.direcao_motor(2, Motores.INVERTIDO)


def andado_mm():
    return (motores.angulo_motor(1) + motores.angulo_motor(2)) / 2 * MM_POR_CONTAGEM


def anda_mm(distancia, vel_max=50):
    motores.estado()                 # pega a contagem atual antes de zerar
    motores.reseta_angulo_motor(1)
    motores.reseta_angulo_motor(2)
    sentido = 1 if distancia > 0 else -1
    while True:
        falta = abs(distancia) - abs(andado_mm())
        if falta <= 2:
            break
        # perto do fim vai mais devagar (controle proporcional simples)
        vel = max(15, min(vel_max, falta * 0.5))
        motores.velocidade_motores(sentido * vel, sentido * vel)
        motores.atualiza_motores()   # envia E lê os encoders
        time.sleep(0.01)
    motores.velocidade_motores(0, 0)
    motores.atualiza_motores()


try:
    anda_mm(300)
    time.sleep(0.5)
    motores.estado()
    print(f'pedi 300 mm, andou {andado_mm():.0f} mm')
    anda_mm(-150)
    time.sleep(0.5)
    motores.estado()
    print(f'pedi -150 mm, andou {andado_mm():.0f} mm')
finally:
    motores.velocidade_motores(0, 0)
    motores.atualiza_motores()
