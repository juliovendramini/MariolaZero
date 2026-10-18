"""Tutorial 4a — ver o que o sensor de linha Pro1616 enxerga.

Ande com o robô (ou arraste no simulador, com o programa rodando) sobre branco, preto, verde e prata.
    python simulador.py --programa CAMINHO/04_linha/le_sensor.py
"""
import time

from portas import Portas
from sensorCorReflexao import CorReflexao

sensor = CorReflexao(Portas.SERIAL6)
sensor.usa_cores(['branco', 'preto', 'verde', 'vermelho', 'prata'])   # cores da Rescue Line

for _ in range(20):
    ir = sensor.le_reflexao()           # 4 canais: 0 = preto, ~100 = branco (prata ~80: quem vê o prata é o TCS)
    rgbc = [sensor.le_rgbc(s) for s in (1, 2, 3)]
    print('IR', ir, '| TCS', rgbc, '| cores', sensor.cores())
    time.sleep(0.5)
