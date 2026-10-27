"""Tutorial 9 — Maze: explorar seguindo a parede da direita, ladrilho a ladrilho.

Regra da mão direita: se a direita está livre, vira para a direita; senão, se a frente está
livre, segue; senão, vira para a esquerda (ou meia-volta). Simples e funciona em labirintos
sem "ilhas". Simulador da Maze:
    python simulador.py --programa CAMINHO/09_maze/mao_direita.py
"""
import math
import time

from pinosDigitais import PinosDigitais
from giroscopio import Giroscopio
from motores import Motores
from placaControleMotor import PlacaControleMotor
from portas import Portas
from sensorCorReflexao import CorReflexao
from vl53 import VL53L0X

LADRILHO = 300                                    # mm
MM_POR_CONTAGEM = math.pi * 70 / (17 * 34 * 2)    # roda de 70 mm, encoder do Mariola
PAREDE_LADO = 150                                 # mm: menos que isso = tem parede
PAREDE_FRENTE = 200

motores = Motores(False)
motores.direcao_motor(2, Motores.INVERTIDO)
barramento = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
placas = [PlacaControleMotor(barramento, 8), PlacaControleMotor(barramento, 51)]
placas[1].direcao_motor(PlacaControleMotor.INVERTIDO)
giro = Giroscopio(Portas.SERIAL5)
cor = CorReflexao(Portas.SERIAL6)
cor.usa_cores(['branco', 'preto', 'prata', 'azul', 'vermelho'])
vl = {'esquerda': VL53L0X(Portas.I2C1), 'direita': VL53L0X(Portas.I2C3), 'frente': VL53L0X(Portas.I2C5)}
botoes = PinosDigitais()
direcao = 0.0          # direção desejada em graus do giroscópio (múltiplos de 90)


def anda(ve, vd):
    motores.velocidade_motores(int(ve), int(vd))
    motores.atualiza_motores()
    placas[0].velocidade_motor(int(ve))
    placas[1].velocidade_motor(int(vd))


def z():
    return -giro.le_angulo_z()                    # + = esquerda


def distancias():
    for s in vl.values():
        s.solicita_leitura()
    time.sleep(0.034)
    return {nome: s.leitura_mm() for nome, s in vl.items()}


def gira(graus):
    global direcao
    direcao += graus                              # alvo acumulado: o erro não se soma
    fim = time.time() + 4
    while time.time() < fim:
        erro = direcao - z()
        if abs(erro) < 1.5:
            break
        v = max(15, min(45, abs(erro) * 0.9)) * (1 if erro > 0 else -1)
        anda(-v, v)
        time.sleep(0.01)
    anda(0, 0)


def avanca():
    """Anda um ladrilho reto. Para antes se a parede da frente chegar perto.
    Retorna 'ok' ou 'preto' (ladrilho proibido: volta para onde estava)."""
    motores.estado()
    motores.reseta_angulo_motor(1)
    motores.reseta_angulo_motor(2)
    andado = 0.0
    while andado < LADRILHO - 8:
        motores.estado()
        andado = (motores.angulo_motor(1) + motores.angulo_motor(2)) / 2 * MM_POR_CONTAGEM
        if cor.cores().count('preto') >= 2:
            anda(0, 0)
            volta_mm(andado)
            return 'preto'
        if vl['frente'].read_range_single_millimeters() < 60:
            break
        correcao = max(-12, min(12, (direcao - z()) * 2.5))
        anda(40 - correcao, 40 + correcao)
    anda(0, 0)
    time.sleep(0.1)
    return 'ok'


def volta_mm(mm):
    motores.estado()
    motores.reseta_angulo_motor(1)
    motores.reseta_angulo_motor(2)
    while abs(motores.angulo_motor(1)) * MM_POR_CONTAGEM < mm:
        anda(-35, -35)
        time.sleep(0.01)
        motores.estado()
    anda(0, 0)


def espera(segundos):
    """Espera parado mandando comando (o Mariola solta os motores após 5 s sem pacote)."""
    fim = time.time() + segundos
    while time.time() < fim:
        anda(0, 0)
        time.sleep(0.2)


try:
    while not botoes.botao_pressionado(PinosDigitais.P3):
        anda(0, 0)
        time.sleep(0.05)
    giro.reseta_z()
    time.sleep(0.1)
    inicio = time.time()
    acabou_de_ver_preto = False
    while time.time() - inicio < 120:             # 2 minutos de exploração
        d = distancias()
        if d['direita'] > PAREDE_LADO and not acabou_de_ver_preto:
            gira(-90)
        elif d['frente'] > PAREDE_FRENTE:
            pass
        elif d['esquerda'] > PAREDE_LADO:
            gira(90)
        else:
            gira(180)
        acabou_de_ver_preto = False
        resultado = avanca()
        if resultado == 'preto':
            # o preto conta como parede. Sem lembrar disso, na próxima volta a direita
            # estaria "livre" de novo e o robô entraria no preto para sempre
            print('ladrilho preto: voltei')
            gira(180)
            acabou_de_ver_preto = True
            continue
        piso = cor.cor_piso()
        if piso == 'azul':
            print('azul: parado 5 s')
            espera(5.5)
        elif piso == 'prata':
            print('checkpoint (prata)')
finally:
    anda(0, 0)
