"""Camada de hardware do Bombertinho (robô real da RCB Challenge 2026) usando as bibliotecas do Mariola.

Este arquivo roda igual no robô real e no simulador (robo_bombertinho.json): as libs são as mesmas.
Portas, canais, servos e sentido dos motores são os do código da equipe (defs.py e movimentos.py, de
30/10/2026). As constantes marcadas A DEFINIR seguem o robo_bombertinho.json; mudou no robô, mude nos dois.
"""

import math
import os
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
DIAMETRO_RODA = 58.0          # mm (medido)
# o código da equipe anda 75 contagens do Mariola por cm (movimentos.andar_reto_distancia);
# a placa de motor conta o dobro
MM_POR_CONTAGEM_MARIOLA = 10.0 / 75.0
MM_POR_CONTAGEM_PLACA = 10.0 / 150.0
GIRO_HORARIO_POSITIVO = False  # deduzido do código da equipe (cidade.ajeitar_angulo): Z cresce para a esquerda
OFFSET_VL53 = 60              # mm que os VL53 leem a mais (deduzido do código da equipe; A MEDIR)

BOTAO_INICIO = PinosDigitais.P3
PRETO = 40                    # IR abaixo disto = linha preta (0 = preto, ~100 = branco)

# ------------------------------------------------------------------ garras
# Paralelogramo: duas barras do eixo do servo de subir até a cabeça. A altura é a da BASE do cubo
# preso (do chão): com as barras na horizontal, ALTURA_EIXO + BASE_CUBO = 54 mm (acima da
# plataforma, que tem 50). A comporta corre numa cremalheira: engrenagem de 24 dentes, módulo 1
# (raio 12 mm), 0,21 mm por grau do servo.
GARRAS = {
    #             servo de subir, servo de abrir, barra (mm), TCS da cabeça (como no código da equipe)
    'frente':   {'sobe': 3, 'abre': 4, 'barra': 66.5, 'tcs': Portas.I2C8},
    'esquerda': {'sobe': 2, 'abre': 1, 'barra': 79.0, 'tcs': Portas.I2C6},
}
ALTURA_EIXO = 66.0            # mm do chão até o eixo do servo de subir
BASE_CUBO = -12.0             # base do cubo preso em relação ao furo de baixo da cabeça
ANGULO_HORIZONTAL = 90        # ângulo do servo com as barras na horizontal (A DEFINIR)
SENTIDO_SOBE = 1              # +1: aumentar o ângulo levanta a garra (A DEFINIR)
ANGULO_FECHADA = 0            # ângulo do servo com a comporta fechada (a equipe usa 0 fechada, 180 aberta)
SENTIDO_ABRE = 1              # +1: aumentar o ângulo abre
MM_POR_GRAU = 12.0 * math.pi / 180.0
ABERTA = 25                   # mm que a comporta abre (A DEFINIR)
ALTA = 54                     # base do cubo com as barras na horizontal: passa por cima de cubos e plataformas
PEGAR = 10                    # base do cubo para pegar (a comporta aperta 17 mm da lateral do cubo)
TEMPO_SERVO = 0.4             # s para o servo chegar (com folga)

# TCS34725: contagem de cada canal num branco encostado (a equipe usa estes) e o "escuro" (0-255)
TCS_MAX = (1580, 1880, 1770)
TCS_ESCURO = 33


class Robo:
    def __init__(self):
        # 4 rodas mecanum: traseiras no Mariola, dianteiras nas placas de motor
        # canal 1 do Mariola = traseira DIREITA, canal 2 = traseira esquerda (invertido)
        self.motores = Motores(False)
        self.motores.direcao_motor(2, Motores.INVERTIDO)
        porta = Portas().abre_porta_serial(Portas.SERIAL2, 250000, timeout=0.005)
        self.m_de = PlacaControleMotor(porta, 8)      # dianteira esquerda
        self.m_dd = PlacaControleMotor(porta, 51)     # dianteira direita
        self.m_de.reset()
        self.m_dd.reset()
        self.m_dd.direcao_motor(PlacaControleMotor.INVERTIDO)

        self.giro = Giroscopio(Portas.SERIAL5)
        # cores da lona: as referências padrão da lib são só um começo. cores_lona.json faz o papel do
        # aprende_cor() no campo, com as cores que a equipe mediu (o azul é bem menos saturado)
        cores = ['branco', 'preto', 'azul', 'vermelho', 'verde', 'amarelo']
        arquivo_cores = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cores_lona.json')
        self.cor = CorReflexao(Portas.SERIAL1, arquivo_cores=arquivo_cores)        # sensor da frente
        self.cor.usa_cores(cores)
        self.cor_esq = CorReflexao(Portas.SERIAL3, arquivo_cores=arquivo_cores)    # o da esquerda
        self.cor_esq.usa_cores(cores)
        self.vl = {
            'frente': VL53L0X(Portas.I2C4),
            'tras': VL53L0X(Portas.I2C7),
            'esquerda': VL53L0X(Portas.I2C2),
            'direita': VL53L0X(Portas.I2C5),
        }
        self.tcs = {'frente': TCS34725(Portas.I2C3)}  # baixo, na frente, 31 mm à direita do centro
        for nome, g in GARRAS.items():
            self.tcs['garra_' + nome] = TCS34725(g['tcs'])
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
        self.motores.velocidade_motores(td, te)
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
        td = self.motores.angulo_motor(1) * MM_POR_CONTAGEM_MARIOLA
        te = self.motores.angulo_motor(2) * MM_POR_CONTAGEM_MARIOLA
        fe = self.m_de.angulo_motor() * MM_POR_CONTAGEM_PLACA
        fd = self.m_dd.angulo_motor() * MM_POR_CONTAGEM_PLACA
        return (fe + fd + te + td) / 4.0, (-fe + fd + te - td) / 4.0

    # ------------------------------------------------------------------ garras
    def garra(self, nome, abertura=None, altura=None, espera=True):
        """Garra 'frente' ou 'esquerda'. abertura = mm que a comporta abre (0 = fechada, aperta o
        cubo); altura = mm do chão até a base do cubo preso (ALTA = barras na horizontal).
        Com espera=True fica parado o tempo de o servo chegar."""
        g = GARRAS[nome]
        if abertura is not None:
            self.motores.move_servo(g['abre'], angulo_abre(abertura))
        if altura is not None:
            self.motores.move_servo(g['sobe'], angulo_sobe(altura, g['barra']))
        self.motores.atualiza_servos()
        if espera:
            self.espera(TEMPO_SERVO)

    def leds(self, r, g, b):
        """Os 10 LEDs RGB do Mariola (aviso ao árbitro: achei o cubo branco)."""
        self.motores.set_led_rgb_all(r, g, b)

    def cor_tcs(self, nome, leituras=3):
        """Cor vista por um TCS: 'frente' (baixo, na frente: a plataforma) ou 'garra_frente' /
        'garra_esquerda' (na parede de trás da cabeça: o cubo). 'preto' também quer dizer "nada na
        frente": confira com o VL53."""
        soma = [0, 0, 0, 0]
        for _ in range(leituras):
            for i, v in enumerate(self.tcs[nome].le_valores()):
                soma[i] += v
            time.sleep(0.16)          # tempo de integração do TCS (~154 ms)
        return classifica_cor(*(v / leituras for v in soma))

    # ------------------------------------------------------------------ sensores
    def z(self):
        """Ângulo em graus, positivo = anti-horário (esquerda), acumulando."""
        z = self.giro.le_angulo_z()
        return -z if GIRO_HORARIO_POSITIVO else z

    def ir(self):
        """4 valores de reflexão do sensor de linha da frente, da esquerda para a direita (no sensor
        do robô os IR estão na ordem trocada: o canal 0 fica à direita)."""
        return list(reversed(self.cor.le_reflexao()))

    def piso(self):
        """Cor embaixo do TCS do meio do sensor da frente: 'preto', 'branco', 'azul'..."""
        return self.cor.cor(2)

    def distancia(self, nome):
        """Distância (mm) do VL53, já sem o que ele lê a mais (OFFSET_VL53)."""
        s = self.vl[nome]
        s.solicita_leitura()
        time.sleep(0.034)
        try:
            d = s.leitura_mm()
            self.dist[nome] = d - OFFSET_VL53 if d < 8000 else d
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


def angulo_sobe(altura, barra):
    """Ângulo do servo de subir para a base do cubo ficar a 'altura' mm do chão."""
    s = (altura - BASE_CUBO - ALTURA_EIXO) / barra
    graus_barra = math.degrees(math.asin(max(-1.0, min(1.0, s))))
    return int(round(ANGULO_HORIZONTAL + SENTIDO_SOBE * graus_barra))


def angulo_abre(abertura):
    """Ângulo do servo de abrir para a comporta abrir 'abertura' mm."""
    return int(round(ANGULO_FECHADA + SENTIDO_ABRE * abertura / MM_POR_GRAU))


def classifica_cor(r, g, b, c):
    """Cor pela proporção entre os canais (não depende tanto da distância), com cada canal dividido
    pela contagem dele no branco (TCS_MAX), como a equipe faz. Os limites são para o simulador: no
    robô, ajuste com os cubos e as plataformas de verdade."""
    r, g, b = (v / mx * 255 for v, mx in zip((r, g, b), TCS_MAX))
    m = max(r, g, b)
    if m < TCS_ESCURO:
        return 'preto'
    if min(r, g, b) / m > 0.85:
        return 'branco'
    if b == m:
        return 'azul'
    if g == m:
        return 'verde'
    if b / m < 0.45 and g / m > 0.7:
        return 'amarelo'
    if g / m < 0.35:
        return 'vermelho'
    return 'marrom'
