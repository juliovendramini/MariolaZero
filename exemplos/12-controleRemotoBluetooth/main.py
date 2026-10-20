from time import sleep
from portas import Portas
from controleRemotoBluetooth import ControleRemotoBluetooth

ctrl = ControleRemotoBluetooth(Portas.SERIAL3)
ctrl.DEBUG = False

print("Aguardando dados do controle... (Ctrl+C para sair)\n")

try:
    while True:
        e = ctrl.estado()
        #print(f"frente_tras={e['frente_tras']:+4d}  esquerda_direita={e['esquerda_direita']:+4d}")
        velocidade_base = e['frente_tras']
        ajuste_direcao = e['esquerda_direita']
        print(f"Velocidade base: {velocidade_base:+4d}  Ajuste direção: {ajuste_direcao:+4d}")
        potencia_motor1 = velocidade_base + ajuste_direcao
        potencia_motor2 = velocidade_base - ajuste_direcao
        print(potencia_motor1, potencia_motor2)
        sleep(0.1)
except KeyboardInterrupt:
    print("\nEncerrando...")
    ctrl.parar()
