"""Camada de hardware do robô de casa (Bombertinho com uma pinça e uma câmera), usando as bibliotecas
do Mariola. Roda igual no robô real e no simulador (robo_casa.json): as libs são as mesmas.

As constantes dos servos seguem o robo_casa.json. Mudou no robô, mude nos dois.
"""

import math
import time

import cv2

from giroscopio import Giroscopio
from motores import Motores
from pinosDigitais import PinosDigitais
from placaControleMotor import PlacaControleMotor
from portas import Portas
from vl53 import VL53L0X

MM_POR_CONTAGEM_MARIOLA = 10.0 / 75.0
MM_POR_CONTAGEM_PLACA = 10.0 / 150.0
GIRO_HORARIO_POSITIVO = False  # Z cresce para a esquerda
OFFSET_VL53 = 60               # mm que os VL53 leem a mais (A MEDIR no robô)
ALCANCE_VL53 = 1200            # mm: daqui para a frente o VL53 não vê (leitura 8190)
# onde fica cada VL53 no robô: (x para frente, y para a esquerda, rumo em graus), do robo_casa.json
VL53_POSE = {'frente': (90.7, -11.4, 0.0), 'tras': (-90.8, 0.0, 180.0),
             'esquerda': (14.8, 69.7, 90.0), 'direita': (4.2, -48.8, -90.0)}
EFICIENCIA_LATERAL = 0.9       # de lado o robô anda menos do que os encoders contam (A MEDIR no robô)
BOTAO_INICIO = PinosDigitais.P3

# ------------------------------------------------------------------ servos (A DEFINIR no robô)
SERVO_SUBIR, SERVO_PINCA, SERVO_CAMERA = 3, 4, 2
SUBIR_HORIZONTAL = 60          # ângulo do servo com as barras na horizontal
PINCA_FECHADA = 10             # ângulo do servo com os dedos fechados (1 mm)
MM_POR_GRAU = 0.4887           # abertura dos dedos por grau do servo
CAMERA_HORIZONTAL = 60         # ângulo do servo com a câmera na horizontal

BARRAS_CHAO = -32.2            # dedos a 1 mm do chão
BARRAS_DESCANSO = 0.0          # barras na horizontal: a cabeça fica abaixo da tela
BARRAS_CAIXA = 66.9            # fundo dos dedos a 110 mm: passa por cima da borda da caixa de 10 cm
ABERTA = 80.0

# ------------------------------------------------------------------ câmera
CAMERA = 0                     # no robô: o número ou o /dev/video da câmera USB
LARGURA, ALTURA = 320, 240
# onde a lente fica (do garra.py / robo_casa.json), para saber que ponto do chão aparece em cada pixel
GARRA_X, GARRA_Z, BARRA_MM = 49.46, 66.0, 75.0      # eixo do servo de subir e comprimento das barras
CAM_EIXO_X, CAM_EIXO_Z, CAM_LENTE = 64.0, 50.0, 12.6  # eixo de inclinação (a partir da ponta das barras) e lente
FOV_DIAGONAL = 76.0            # graus, imagem 4:3
_T = math.tan(math.radians(FOV_DIAGONAL / 2)) / 5.0
FOCO_X = (LARGURA / 2) / (_T * 4.0)                  # distância focal em pixels (64,0° x 50,2°)
FOCO_Y = (ALTURA / 2) / (_T * 3.0)


class Interrompido(Exception):
    """A pessoa falou com o robô no meio de uma tarefa. fala = o que ela disse."""

    def __init__(self, fala):
        super().__init__(fala)
        self.fala = fala


class Robo:
    def __init__(self):
        # 4 rodas mecanum: traseiras no Mariola, dianteiras nas placas de motor
        self.motores = Motores(False)
        self.motores.direcao_motor(2, Motores.INVERTIDO)
        porta = Portas().abre_porta_serial(Portas.SERIAL2, 250000, timeout=0.005)
        self.m_de = PlacaControleMotor(porta, 8)      # dianteira esquerda
        self.m_dd = PlacaControleMotor(porta, 51)     # dianteira direita
        self.m_de.reset()
        self.m_dd.reset()
        self.m_dd.direcao_motor(PlacaControleMotor.INVERTIDO)
        self.giro = Giroscopio(Portas.SERIAL5)
        self.vl = {
            'frente': VL53L0X(Portas.I2C4),
            'tras': VL53L0X(Portas.I2C7),
            'esquerda': VL53L0X(Portas.I2C2),
            'direita': VL53L0X(Portas.I2C5),
        }
        self.pinos = PinosDigitais()
        self.dist = {k: 8190 for k in self.vl}
        self.cam = cv2.VideoCapture(CAMERA)
        self.cam.set(cv2.CAP_PROP_FRAME_WIDTH, LARGURA)
        self.cam.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTURA)
        self.barras = BARRAS_DESCANSO
        self.inclinacao = 35.0
        self._zero = (0.0, 0.0, 0.0, 0.0)
        self.loc = None            # o Localizador (localiza.py) se pendura aqui e acompanha cada movimento
        # interrompe: função consultada a cada move() durante uma tarefa. Se devolve um texto (o que a pessoa
        # falou), o robô para e o move() levanta Interrompido, que desmonta a tarefa em curso.
        self.interrompe = None
        self.rosto = None          # o Rosto (rosto.py): cada move() redesenha a carinha

    # ------------------------------------------------------------------ motores
    def move(self, vx, vy=0.0, w=0.0):
        """Movimento mecanum, cada parte de -100 a 100:
        vx = para frente, vy = de lado para a ESQUERDA, w = girando para a ESQUERDA (anti-horário)."""
        if self.interrompe is not None:
            # alguém falou com o robô no meio de uma tarefa? para os motores e sai de onde estiver
            fala = self.interrompe()
            if fala:
                self.interrompe = None
                self.move(0, 0, 0)
                raise Interrompido(fala)
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
        if self.loc is not None:
            self.loc.passo()
        if self.rosto is not None:
            self.rosto.passo()

    def para(self):
        self.move(0, 0, 0)

    def rodas(self, atualiza=True):
        """Quanto cada roda já andou desde que o programa começou, em mm: (dianteira esquerda,
        dianteira direita, traseira esquerda, traseira direita). Nunca é zerado: a localização
        acompanha estes números."""
        if atualiza:
            self.motores.estado()
        td = self.motores.angulo_motor(1) * MM_POR_CONTAGEM_MARIOLA
        te = self.motores.angulo_motor(2) * MM_POR_CONTAGEM_MARIOLA
        fe = self.m_de.angulo_motor() * MM_POR_CONTAGEM_PLACA
        fd = self.m_dd.angulo_motor() * MM_POR_CONTAGEM_PLACA
        return fe, fd, te, td

    def zera_encoder(self):
        """Marca o ponto de partida do deslocamento() (os encoders em si não são zerados)."""
        self._zero = self.rodas()

    def deslocamento(self):
        """(frente_mm, esquerda_mm) andados desde o último zera_encoder(), pela média das 4 rodas."""
        fe, fd, te, td = (a - b for a, b in zip(self.rodas(atualiza=False), self._zero))
        return (fe + fd + te + td) / 4.0, (-fe + fd + te - td) / 4.0

    # ------------------------------------------------------------------ garra e câmera
    def garra(self, barras=None, abertura=None, inclinacao=None, espera=0.0):
        """barras = ângulo das barras do braço (graus; 0 = horizontal, BARRAS_CHAO, BARRAS_CAIXA);
        abertura = mm entre os dedos (0 = fechada); inclinacao = câmera, graus para baixo (negativo
        olha para cima)."""
        if barras is not None:
            self.barras = barras
            self.motores.move_servo(SERVO_SUBIR, int(round(SUBIR_HORIZONTAL + barras)))
        if abertura is not None:
            self.motores.move_servo(SERVO_PINCA, int(round(PINCA_FECHADA + max(0.0, abertura - 1.0) / MM_POR_GRAU)))
        if inclinacao is not None:
            self.inclinacao = inclinacao
            self.motores.move_servo(SERVO_CAMERA, int(round(CAMERA_HORIZONTAL + inclinacao)))
        self.motores.atualiza_servos()
        if espera:
            self.espera(espera)

    def foto(self):
        """Um quadro da câmera (BGR), ou None."""
        ok, img = self.cam.read()
        return img if ok else None

    def lente(self):
        """(x para frente, altura, inclinação em rad para baixo) da lente, no referencial do robô,
        pelos últimos ângulos mandados para os servos."""
        b = math.radians(self.barras)
        i = math.radians(self.inclinacao)
        return (GARRA_X + BARRA_MM * math.cos(b) + CAM_EIXO_X + CAM_LENTE * math.cos(i),
                GARRA_Z + BARRA_MM * math.sin(b) + CAM_EIXO_Z - CAM_LENTE * math.sin(i), i)

    def no_chao(self, u, v):
        """Ponto do chão que aparece no pixel (u, v) da imagem: (frente, esquerda, distância da lente)
        em mm, no referencial do robô. None se o pixel está no horizonte ou acima dele."""
        x, h, i = self.lente()
        a = -(u - LARGURA / 2) / FOCO_X            # para a esquerda
        c = -(v - ALTURA / 2) / FOCO_Y             # para cima
        rx = math.cos(i) + c * math.sin(i)         # raio = frente + a * esquerda + c * cima (câmera inclinada)
        rz = -math.sin(i) + c * math.cos(i)
        if rz > -0.02:
            return None
        t = h / -rz
        return x + t * rx, t * a, t * math.sqrt(rx * rx + a * a + rz * rz)

    # ------------------------------------------------------------------ sensores
    def z(self):
        """Ângulo em graus, positivo = anti-horário (esquerda), acumulando."""
        z = self.giro.le_angulo_z()
        return -z if GIRO_HORARIO_POSITIVO else z

    def distancias(self):
        """Mede com os quatro VL53 ao mesmo tempo (uns 35 ms) e devolve {'frente': mm, 'tras': ...,
        'esquerda': ..., 'direita': ...}, já sem o que eles leem a mais (OFFSET_VL53).
        8190 = nada à vista."""
        pediu = []
        for nome, s in self.vl.items():
            try:
                s.solicita_leitura()
                pediu.append(nome)
            except (OSError, TimeoutError):
                self.dist[nome] = 8190
        time.sleep(0.034)
        for nome in pediu:
            try:
                d = self.vl[nome].leitura_mm()
                self.dist[nome] = d - OFFSET_VL53 if d < 8000 else 8190
            except (OSError, TimeoutError):
                self.dist[nome] = 8190
        if self.loc is not None:
            self.loc.mede(self.dist)
        return dict(self.dist)

    def distancia(self, nome):
        """Distância (mm) de um VL53 ('frente', 'tras', 'esquerda', 'direita'). 8190 = nada à vista."""
        return self.distancias()[nome]

    def espera(self, segundos):
        """Espera parado sem deixar o Mariola nem as placas de motor ficarem 5 s sem comando."""
        fim = time.time() + segundos
        while time.time() < fim:
            self.para()
            time.sleep(min(0.3, max(0.0, fim - time.time())))

    def espera_botao(self):
        print('Aguardando o botão de início...')
        while not self.pinos.botao_pressionado(BOTAO_INICIO):
            self.para()
            time.sleep(0.02)
        while self.pinos.botao_pressionado(BOTAO_INICIO):
            time.sleep(0.02)

    # ------------------------------------------------------------------ movimentos prontos
    def gira(self, graus, vel=30):
        """Gira no lugar 'graus' (positivo = esquerda), pelo giroscópio."""
        alvo = self.z() + graus
        t0 = time.time()
        while time.time() - t0 < 8:
            erro = alvo - self.z()
            if abs(erro) < 1.5:
                break
            self.move(0, 0, max(-vel, min(vel, erro * 1.2)) or 0)
            time.sleep(0.02)
        self.para()

    def anda(self, mm, vel=30):
        """Anda reto 'mm' (negativo = para trás), pelos encoders, segurando o rumo pelo giroscópio."""
        self.zera_encoder()
        rumo = self.z()
        t0 = time.time()
        while time.time() - t0 < 4 + abs(mm) / 40:
            frente, _ = self.deslocamento()
            falta = mm - frente
            if abs(falta) < 4:
                break
            v = max(-vel, min(vel, falta * 0.6))
            if abs(v) < 10:
                v = math.copysign(10, v)
            self.move(v, 0, (rumo - self.z()) * 2.0)
            time.sleep(0.02)
        self.para()

    def desliza(self, mm, vel=30):
        """Anda de lado 'mm' (positivo = esquerda, negativo = direita) sem girar, pelos encoders."""
        self.zera_encoder()
        rumo = self.z()
        t0 = time.time()
        while time.time() - t0 < 4 + abs(mm) / 30:
            _, lado = self.deslocamento()
            falta = mm - lado
            if abs(falta) < 6:
                break
            v = max(-vel, min(vel, falta * 0.6))
            if abs(v) < 12:
                v = math.copysign(12, v)
            self.move(0, v, (rumo - self.z()) * 2.0)
            time.sleep(0.02)
        self.para()
