"""Tutorial 3 — girar ângulos exatos e andar reto com o giroscópio.

    python simulador.py --robo robo_esteira.json --programa CAMINHO/03_giroscopio/gira_e_anda_reto.py
"""
import time

from giroscopio import Giroscopio
from motores import Motores
from portas import Portas

motores = Motores(False)
motores.direcao_motor(2, Motores.INVERTIDO)
giro = Giroscopio(Portas.SERIAL5)

HORARIO_POSITIVO = True     # no Mariola o Z cresce girando no sentido horário


def anda(ve, vd):
    motores.velocidade_motores(int(ve), int(vd))
    motores.atualiza_motores()


def z():
    """Ângulo em graus, positivo = esquerda (anti-horário), sem voltar a zero em 360."""
    return -giro.le_angulo_z() if HORARIO_POSITIVO else giro.le_angulo_z()


def gira_para(alvo, tolerancia=1.5, tempo_max=4.0):
    """Gira no lugar até z() chegar no alvo (controle proporcional com velocidade mínima)."""
    inicio = time.time()
    while time.time() - inicio < tempo_max:
        erro = alvo - z()
        if abs(erro) <= tolerancia:
            break
        v = max(15, min(50, abs(erro) * 0.8))   # longe: rápido; perto: devagar
        if erro < 0:
            v = -v
        anda(-v, v)                               # esquerda para trás, direita para frente
        time.sleep(0.01)
    anda(0, 0)


def anda_reto(segundos, vel=40):
    """Anda reto corrigindo a direção pelo giroscópio."""
    alvo = z()
    inicio = time.time()
    while time.time() - inicio < segundos:
        erro = alvo - z()                         # + = robô virou para a direita
        correcao = max(-15, min(15, erro * 2.0))
        anda(vel - correcao, vel + correcao)
        time.sleep(0.01)
    anda(0, 0)


try:
    print('Calibrando (robô parado!)...')
    giro.calibra()
    giro.reseta_z()
    time.sleep(0.1)
    print('z inicial:', z())

    alvo = 0
    for _ in range(4):                 # um quadrado: anda, gira 90° à esquerda
        anda_reto(1.2)
        alvo += 90                     # o alvo acumula: o erro de um giro não passa para o próximo
        gira_para(alvo)
        time.sleep(0.2)
        print(f'alvo {alvo}°, giroscópio {z()}°')
finally:
    anda(0, 0)
