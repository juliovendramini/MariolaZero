"""Tutorial 5a — vários VL53L0X no mux I2C, do jeito simples e do jeito rápido.

    python simulador.py --programa CAMINHO/05_distancia/le_distancias.py
"""
import time

from portas import Portas
from vl53 import VL53L0X

sensores = {
    'esquerda': VL53L0X(Portas.I2C1),
    'direita': VL53L0X(Portas.I2C3),
    'frente': VL53L0X(Portas.I2C5),
}

# 1) jeito simples: uma medida de cada vez (cada uma espera ~33 ms)
inicio = time.time()
for nome, s in sensores.items():
    print(nome, s.read_range_single_millimeters(), 'mm')
print(f'simples: {(time.time() - inicio) * 1000:.0f} ms para os 3')

# 2) jeito rápido: pede a medida em todos, espera UMA vez e lê todos
inicio = time.time()
for s in sensores.values():
    s.solicita_leitura()
time.sleep(0.034)
leituras = {nome: s.leitura_mm() for nome, s in sensores.items()}
print(leituras, f'rápido: {(time.time() - inicio) * 1000:.0f} ms para os 3')
# 8190 (ou mais) = nada à vista dentro do alcance
