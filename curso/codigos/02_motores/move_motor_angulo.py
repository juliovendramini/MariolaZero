"""Tutorial 2b — girar as rodas um número exato de contagens (move_motores) e esperar terminar.

    python simulador.py --robo robo_esteira.json --programa CAMINHO/02_motores/move_motor_angulo.py
"""
import time

from motores import Motores

motores = Motores(True)
motores.direcao_motor(2, Motores.INVERTIDO)

try:
    motores.reseta_angulo_motor(1)
    motores.reseta_angulo_motor(2)
    # motor 1 e motor 2: velocidade 40, 1156 contagens (= 1 volta da roda neste robô)
    motores.move_motores(40, 1156, 40, 1156)
    # espera os dois pararem. estado() só LÊ: não reenvia a velocidade
    time.sleep(0.1)
    while True:
        motores.estado()
        if (motores.estado_motor(1) == Motores.PARADO and
                motores.estado_motor(2) == Motores.PARADO):
            break
        time.sleep(0.02)
    print('chegou:', motores.angulo_motor(1), motores.angulo_motor(2))
    # IMPORTANTE: a velocidade 40 continua guardada na placa. Zere antes de mandar
    # qualquer outro comando de motor, senão eles voltam a girar sem parar.
    motores.velocidade_motores(0, 0)
    time.sleep(0.5)
    motores.estado()
    print('depois de zerar:', motores.angulo_motor(1), motores.angulo_motor(2))
finally:
    motores.para_motores()
