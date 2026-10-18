"""Tutorial 5b — andar até ficar a 80 mm de uma parede, desacelerando.

Use o simulador da Maze (tem paredes por todo lado) com o robô de frente para uma parede:
    python simulador.py --programa CAMINHO/05_distancia/para_na_parede.py
"""
import time

from motores import Motores
from placaControleMotor import PlacaControleMotor
from portas import Portas
from vl53 import VL53L0X

ALVO = 80     # mm

motores = Motores(False)
motores.direcao_motor(2, Motores.INVERTIDO)
barramento = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
placas = [PlacaControleMotor(barramento, 8), PlacaControleMotor(barramento, 51)]
placas[1].direcao_motor(PlacaControleMotor.INVERTIDO)
frente = VL53L0X(Portas.I2C5)


def anda(ve, vd):
    motores.velocidade_motores(int(ve), int(vd))
    motores.atualiza_motores()
    placas[0].velocidade_motor(int(ve))
    placas[1].velocidade_motor(int(vd))


try:
    frente.solicita_leitura()
    while True:
        time.sleep(0.035)
        d = frente.leitura_mm()       # resultado da medida pedida na volta anterior
        frente.solicita_leitura()     # já pede a próxima: o laço não fica esperando
        falta = d - ALVO
        if falta <= 0:
            break
        vel = max(12, min(50, falta * 0.3))
        anda(vel, vel)
    anda(0, 0)
    time.sleep(0.5)
    print('parei a', frente.read_range_single_millimeters(), 'mm da parede')
finally:
    anda(0, 0)
