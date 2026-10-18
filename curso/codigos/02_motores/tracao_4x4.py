"""Tutorial 2c — robô 4x4: 2 motores no Mariola + 2 placas de controle de motor na SERIAL1.

    python simulador.py --robo robo_4x4.json --programa CAMINHO/02_motores/tracao_4x4.py
"""
import time

from motores import Motores
from placaControleMotor import PlacaControleMotor
from portas import Portas

motores = Motores(False)
motores.direcao_motor(2, Motores.INVERTIDO)

# as placas de motor dividem a mesma porta serial: abra UMA vez e passe para todas
barramento = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
frente_esq = PlacaControleMotor(barramento, 8)     # ID gravado na placa
frente_dir = PlacaControleMotor(barramento, 51)
frente_esq.reset()
frente_dir.reset()
frente_dir.direcao_motor(PlacaControleMotor.INVERTIDO)


def anda(ve, vd):
    """Mesma velocidade (-100..100) nas duas rodas de cada lado."""
    motores.velocidade_motores(ve, vd)
    motores.atualiza_motores()
    frente_esq.velocidade_motor(ve)
    frente_dir.velocidade_motor(vd)


try:
    frente_esq.reseta_angulo_motor()
    motores.reseta_angulo_motor(1)
    fim = time.time() + 1.5
    while time.time() < fim:
        anda(40, 40)               # reenviar sempre: as placas param após 5 s sem comando
        time.sleep(0.02)
    anda(0, 0)
    time.sleep(0.3)
    motores.estado()
    # a placa conta em quadratura (x4): o dobro de contagens do Mariola para a mesma roda
    print('Mariola (traseira esq.):', motores.angulo_motor(1))
    print('Placa   (dianteira esq.):', frente_esq.angulo_motor())
    fim = time.time() + 1.2
    while time.time() < fim:
        anda(-35, 35)              # gira no lugar para a esquerda
        time.sleep(0.02)
finally:
    anda(0, 0)
