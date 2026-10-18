"""Tutorial 7a — descobrir quais servos inteligentes estão no barramento (e seus IDs).

Robô 4x4 do simulador da Line (4 servos na SERIAL1, IDs 70 a 73):
    python simulador.py --programa CAMINHO/07_servos/busca_servos.py
"""
from placaControleServo import PlacaControleServo
from portas import Portas

encontrados = PlacaControleServo.buscar_servos(Portas.SERIAL1)
for s in encontrados:
    print(f"ID {s['id']:3d}  potenciômetro em {s['posicao']}")
