"""Tutorial 1 — Olá, Mariola!

Acende os LEDs, anda para frente 1,5 s, para e mostra quanto cada encoder contou.
Roda igual no robô e no simulador:
    python simulador.py --robo robo_esteira.json --programa CAMINHO/01_ola_mariola/main.py
"""
import time

from motores import Motores

motores = Motores(True)                       # True = cada comando já vai para a placa
motores.direcao_motor(2, Motores.INVERTIDO)   # o motor 2 está espelhado no robô

try:
    motores.set_led_rgb_all(0, 80, 0)         # tudo verde: o programa começou
    motores.reseta_angulo_motor(1)
    motores.reseta_angulo_motor(2)

    motores.velocidade_motores(40, 40)        # -100..100 (PID de velocidade)
    inicio = time.time()
    while time.time() - inicio < 1.5:
        motores.estado()                      # lê os encoders sem mudar nada
        print('encoders:', motores.angulo_motor(1), motores.angulo_motor(2))
        time.sleep(0.25)

    motores.velocidade_motores(0, 0)
    time.sleep(0.3)
    motores.estado()
    print('andou (contagens):', motores.angulo_motor(1), motores.angulo_motor(2))
    motores.set_led_rgb_all(0, 0, 80)         # azul: terminou
    time.sleep(0.5)
except KeyboardInterrupt:
    print('Interrompido pelo usuário')
finally:
    # acontece SEMPRE: no fim normal, no Ctrl+C e se der erro no meio
    motores.para_motores()
    motores.set_led_rgb_all(0, 0, 0)
    print('Motores parados.')
