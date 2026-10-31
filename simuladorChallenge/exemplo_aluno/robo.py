"""Camada de hardware do robô mecanum da RCB Challenge usando as bibliotecas do Mariola.

Este arquivo roda igual no robô real e no simulador: as libs (motores.py, placaControleMotor.py,
giroscopio.py, vl53.py, sensorCorReflexao.py, pinosDigitais.py) são as mesmas.
As constantes marcadas A DEFINIR seguem o robo_mecanum.json provisório do simulador.
"""

import math
import time

from giroscopio import Giroscopio
from motores import Motores
from pinosDigitais import PinosDigitais
from placaControleMotor import PlacaControleMotor
from portas import Portas
from sensorCorReflexao import CorReflexao
from tcs34725 import TCS34725
from vl53 import VL53L0X

# ------------------------------------------------------------------ constantes do robô (A DEFINIR)
DIAMETRO_RODA = 60.0          # mm (roda mecanum)
PULSOS_ENCODER_MOTOR = 17
REDUCAO = 34
# o Mariola conta as duas bordas de um canal do encoder (x2); a placa de motor, quadratura (x4)
MM_POR_CONTAGEM_MARIOLA = math.pi * DIAMETRO_RODA / (PULSOS_ENCODER_MOTOR * REDUCAO * 2)
MM_POR_CONTAGEM_PLACA = math.pi * DIAMETRO_RODA / (PULSOS_ENCODER_MOTOR * REDUCAO * 4)
GIRO_HORARIO_POSITIVO = True  # o Z do giroscópio cresce girando no sentido horário

BOTAO_INICIO = PinosDigitais.P3
PRETO = 40                    # IR abaixo disto = linha preta (0 = preto, ~100 = branco)

# garra (servos do Mariola): servo 1 abre/fecha, servo 2 sobe/desce
SERVO_DEDOS = 1
SERVO_BRACO = 2
DEDOS_ABERTOS = 90
DEDOS_FECHADOS = 0
BRACO_BAIXO = 0
BRACO_ALTO = 90
TEMPO_SERVO = 0.4             # s para o servo chegar (90° a ~300°/s, com folga)

# TCS34725 da frente (entre os dedos): abaixo disto (contagem do canal mais forte) é "escuro"
TCS_ESCURO = 900


class Robo:
    def __init__(self):
        # 4 rodas mecanum: traseiras no Mariola, dianteiras nas placas de motor
        self.motores = Motores(False)
        self.motores.direcao_motor(2, Motores.INVERTIDO)
        porta = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
        self.m_de = PlacaControleMotor(porta, 8)      # dianteira esquerda
        self.m_dd = PlacaControleMotor(porta, 51)     # dianteira direita
        self.m_de.reset()
        self.m_dd.reset()
        self.m_dd.direcao_motor(PlacaControleMotor.INVERTIDO)

        self.giro = Giroscopio(Portas.SERIAL5)
        self.cor = CorReflexao(Portas.SERIAL6)
        self.cor.usa_cores(['branco', 'preto', 'azul', 'vermelho', 'verde', 'amarelo'])
        self.vl = {
            'frente': VL53L0X(Portas.I2C1),
            'tras': VL53L0X(Portas.I2C2),
            'esquerda': VL53L0X(Portas.I2C3),
            'direita': VL53L0X(Portas.I2C4),
        }
        self.tcs = TCS34725(Portas.I2C5)              # entre os dedos da garra, olhando para frente
        self.pinos = PinosDigitais()
        self.dist = {k: 8190 for k in self.vl}

    # ------------------------------------------------------------------ motores
    def move(self, vx, vy=0.0, w=0.0):
        """Movimento mecanum, cada parte de -100 a 100:
        vx = para frente, vy = de lado para a ESQUERDA, w = girando para a ESQUERDA (anti-horário).
        Se a soma passar de 100 numa roda, as quatro são reduzidas na mesma proporção."""
        fe = vx - vy - w          # dianteira esquerda
        fd = vx + vy + w          # dianteira direita
        te = vx + vy - w          # traseira esquerda
        td = vx - vy + w          # traseira direita
        m = max(100.0, abs(fe), abs(fd), abs(te), abs(td))
        k = 100.0 / m
        fe, fd, te, td = (int(round(v * k)) for v in (fe, fd, te, td))
        self.motores.velocidade_motores(te, td)
        self.motores.atualiza_motores()      # também lê os encoders do Mariola
        self.m_de.velocidade_motor(fe)
        self.m_dd.velocidade_motor(fd)

    def para(self):
        self.move(0, 0, 0)

    def zera_encoder(self):
        self.motores.estado()
        self.motores.reseta_angulo_motor(1)
        self.motores.reseta_angulo_motor(2)
        self.m_de.reseta_angulo_motor()
        self.m_dd.reseta_angulo_motor()

    def deslocamento(self):
        """(frente_mm, esquerda_mm) andados desde o último zera_encoder(), pela média das 4 rodas.
        Andando de lado a roda mecanum escorrega um pouco: o real fica abaixo do que o encoder diz."""
        te = self.motores.angulo_motor(1) * MM_POR_CONTAGEM_MARIOLA
        td = self.motores.angulo_motor(2) * MM_POR_CONTAGEM_MARIOLA
        fe = self.m_de.angulo_motor() * MM_POR_CONTAGEM_PLACA
        fd = self.m_dd.angulo_motor() * MM_POR_CONTAGEM_PLACA
        return (fe + fd + te + td) / 4.0, (-fe + fd + te - td) / 4.0

    # ------------------------------------------------------------------ garra
    def garra(self, abre=None, sobe=None, espera=True):
        """abre=True/False abre/fecha os dedos; sobe=True/False sobe/desce o braço.
        Com espera=True fica parado o tempo de o servo chegar."""
        if abre is not None:
            self.motores.move_servo(SERVO_DEDOS, DEDOS_ABERTOS if abre else DEDOS_FECHADOS)
        if sobe is not None:
            self.motores.move_servo(SERVO_BRACO, BRACO_ALTO if sobe else BRACO_BAIXO)
        self.motores.atualiza_servos()
        if espera:
            self.espera(TEMPO_SERVO)

    def leds(self, r, g, b):
        """Os 10 LEDs RGB do Mariola (aviso ao árbitro: achei o cubo branco)."""
        self.motores.set_led_rgb_all(r, g, b)

    def cor_frente(self, leituras=3):
        """Cor do que está na frente do TCS da garra: o cubo preso (garra embaixo) ou a plataforma
        (garra em cima). 'preto' também quer dizer "nada na frente": confira com o VL53."""
        soma = [0, 0, 0, 0]
        for _ in range(leituras):
            for i, v in enumerate(self.tcs.le_valores()):
                soma[i] += v
            time.sleep(0.16)          # tempo de integração do TCS (~154 ms)
        return classifica_cor(*(v / leituras for v in soma))

    # ------------------------------------------------------------------ sensores
    def z(self):
        """Ângulo em graus, positivo = anti-horário (esquerda), acumulando."""
        z = self.giro.le_angulo_z()
        return -z if GIRO_HORARIO_POSITIVO else z

    def ir(self):
        """4 valores de reflexão do sensor de linha, da esquerda para a direita."""
        return self.cor.le_reflexao()

    def piso(self):
        """Cor embaixo do TCS do meio: 'preto', 'branco', 'azul', 'vermelho', 'verde', 'amarelo'..."""
        return self.cor.cor(2)

    def distancia(self, nome):
        s = self.vl[nome]
        s.solicita_leitura()
        time.sleep(0.034)
        try:
            self.dist[nome] = s.leitura_mm()
        except (OSError, TimeoutError):
            self.dist[nome] = 8190
        return self.dist[nome]

    def espera(self, segundos):
        """Espera parado sem deixar o Mariola nem as placas de motor ficarem 5 s sem comando."""
        fim = time.time() + segundos
        while time.time() < fim:
            self.para()
            time.sleep(min(0.5, max(0.0, fim - time.time())))

    def espera_botao(self):
        print('Aguardando o botão de início...')
        while not self.pinos.botao_pressionado(BOTAO_INICIO):
            self.para()
            time.sleep(0.02)
        while self.pinos.botao_pressionado(BOTAO_INICIO):
            time.sleep(0.02)


def classifica_cor(r, g, b, c):
    """Cor pela proporção entre os canais (não depende tanto da distância). Os limites são para o
    simulador: no robô, ajuste com os cubos e as plataformas de verdade."""
    m = max(r, g, b)
    if m < TCS_ESCURO:
        return 'preto'
    if min(r, g, b) / m > 0.7:
        return 'branco'
    if b == m:
        return 'azul'
    if g == m:
        return 'verde'
    if b / m < 0.35 and g / m > 0.7:
        return 'amarelo'
    if g / m < 0.35:
        return 'vermelho'
    return 'marrom'
