"""Tutorial 7b — mover os servos da garra e esperar cada movimento terminar.

Robô 4x4 do simulador da Line:
    python simulador.py --mapa mapas/resgate.json --programa CAMINHO/07_servos/testa_garra.py
"""
import time

from placaControleServo import PlacaControleServo
from portas import Portas

# IDs e posições (leitura do potenciômetro, 0..1023) — CALIBRE no seu robô
BRACO, DEDO_ESQ, DEDO_DIR = 70, 71, 72
BRACO_BAIXO, BRACO_ALTO = 820, 270
ESQ_ABERTO, ESQ_FECHADO = 380, 680
DIR_ABERTO, DIR_FECHADO = 640, 340

braco = PlacaControleServo(Portas.SERIAL1, BRACO)
dedo_esq = PlacaControleServo(Portas.SERIAL1, DEDO_ESQ)
dedo_dir = PlacaControleServo(Portas.SERIAL1, DEDO_DIR)


def espera_chegar(servo, alvo, tolerancia=25, tempo_max=2.0):
    """Lê a posição SEM desligar o motor (consulta_posicao) até chegar perto do alvo."""
    inicio = time.time()
    while time.time() - inicio < tempo_max:
        pos = servo.consulta_posicao()
        if pos is not None and abs(pos - alvo) <= tolerancia:
            return True
        time.sleep(0.02)
    return False


def move_e_espera(servo, alvo, potencia=255):
    servo.move_servo(alvo, potencia)
    ok = espera_chegar(servo, alvo)
    print(f'servo {servo.id_equipamento}: alvo {alvo}, está em {servo.consulta_posicao()}',
          '' if ok else '(NÃO chegou: travou ou demorou)')


try:
    move_e_espera(braco, BRACO_ALTO)
    move_e_espera(dedo_esq, ESQ_ABERTO)
    move_e_espera(dedo_dir, DIR_ABERTO)
    move_e_espera(braco, BRACO_BAIXO, potencia=180)   # descer mais devagar
    # fecha os dois dedos juntos: manda os dois e só depois espera
    dedo_esq.move_servo(ESQ_FECHADO)
    dedo_dir.move_servo(DIR_FECHADO)
    espera_chegar(dedo_esq, ESQ_FECHADO)
    espera_chegar(dedo_dir, DIR_FECHADO)
    move_e_espera(braco, BRACO_ALTO)
    # mantendo a posição: o servo desliga após 5 s sem nenhum pacote, então reenvie o comando
    for _ in range(10):
        braco.move_servo(BRACO_ALTO)
        time.sleep(0.5)
    print('braço ainda em', braco.consulta_posicao())
finally:
    for s in (braco, dedo_esq, dedo_dir):
        s.para_servo()            # potência 0 (o braço cai se não estiver todo levantado)
