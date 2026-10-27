"""Tutorial 6a — esperar o botão de início, medir tempo e usar o para-choque.

No simulador o botão de início (P3) é apertado sozinho 1,5 s depois do programa subir
(Auto-botão), ou aperte B. Simulador da Maze (tem paredes para o para-choque):
    python simulador.py --programa CAMINHO/06_interface/botao_e_cronometro.py
"""
import time

from pinosDigitais import PinosDigitais
from cronometro import Cronometro
from motores import Motores
from placaControleMotor import PlacaControleMotor
from portas import Portas

BOTAO_INICIO = PinosDigitais.P3
PARA_CHOQUE_ESQ = PinosDigitais.P1
PARA_CHOQUE_DIR = PinosDigitais.P2

botoes = PinosDigitais()
motores = Motores(False)
motores.direcao_motor(2, Motores.INVERTIDO)
barramento = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
placas = [PlacaControleMotor(barramento, 8), PlacaControleMotor(barramento, 51)] if barramento else []
if placas:
    placas[1].direcao_motor(PlacaControleMotor.INVERTIDO)


def anda(ve, vd):
    motores.velocidade_motores(ve, vd)
    motores.atualiza_motores()
    for placa, v in zip(placas, (ve, vd)):
        placa.velocidade_motor(v)


def espera_botao(pino):
    """Espera apertar E soltar (assim o robô só sai quando o dedo já saiu do botão)."""
    while not botoes.botao_pressionado(pino):
        anda(0, 0)              # manda comando: o Mariola desliga tudo após 5 s sem pacote
        time.sleep(0.05)
    while botoes.botao_pressionado(pino):
        time.sleep(0.02)


try:
    print('Aperte o botão de início...')
    espera_botao(BOTAO_INICIO)
    relogio = Cronometro()
    relogio.inicia()
    print('Valendo! Andando até bater...')
    while relogio.tempo() < 20000:                  # no máximo 20 s (tempo() é em ms)
        esq = botoes.botao_pressionado(PARA_CHOQUE_ESQ)
        dir_ = botoes.botao_pressionado(PARA_CHOQUE_DIR)
        if esq or dir_:
            print(f'bateu depois de {relogio.tempo()} ms (esquerdo={esq}, direito={dir_})')
            break
        anda(40, 40)
        time.sleep(0.01)
    anda(-30, -30)                                  # dá uma ré curta para soltar
    time.sleep(0.4)
finally:
    anda(0, 0)
