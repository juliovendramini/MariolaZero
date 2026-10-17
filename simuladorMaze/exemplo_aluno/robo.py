"""Camada de hardware do robô da Maze usando as bibliotecas do Mariola.

Este arquivo roda igual no robô real e no simulador: as libs (motores.py,
placaControleMotor.py, giroscopio.py, vl53.py, sensorCorReflexao.py, botoes.py)
são as mesmas. Só deteccaoVitimas.py e dispensadorKits.py precisam da versão
do robô real (ver pasta robo_real/ do simulador).
"""

import math
import time

from botoes import Botoes
from deteccaoVitimas import DeteccaoVitimas
from dispensadorKits import DispensadorKits
from giroscopio import Giroscopio
from motores import Motores
from placaControleMotor import PlacaControleMotor
from portas import Portas
from sensorCorReflexao import CorReflexao
from vl53 import VL53L0X

# ------------------------------------------------------------------ constantes do robô
DIAMETRO_RODA = 70.0          # mm (roda do aspirador Xiaomi)
PULSOS_ENCODER_MOTOR = 17     # pulsos por volta do eixo do motor
REDUCAO = 34                  # caixa de redução do motor do aspirador (A MEDIR)
# o Mariola conta as duas bordas de um canal do encoder (x2); a placa de motor, quadratura (x4)
CONTAGENS_POR_VOLTA = PULSOS_ENCODER_MOTOR * REDUCAO * 2         # motores do Mariola
CONTAGENS_POR_VOLTA_PLACA = PULSOS_ENCODER_MOTOR * REDUCAO * 4   # placas de motor
GIRO_HORARIO_POSITIVO = True  # o Z do giroscópio cresce girando no sentido horário

# LEDs do Mariola (set_led_rgb_one): iluminação das câmeras e indicação de vítima
LEDS_CAMERA_ESQ = (0, 1, 2, 3)
LEDS_CAMERA_DIR = (4, 5, 6, 7)
LEDS_VITIMA = (8, 9)
MM_POR_CONTAGEM = math.pi * DIAMETRO_RODA / CONTAGENS_POR_VOLTA
LADRILHO = 300.0
FOLGA_FRENTE = 45.0           # mm entre a frente do robô e a parede com o robô no centro do ladrilho
LATERAL_CENTRO = 55.0         # mm do VL53 lateral até a parede com o robô centralizado
DIST_SENSORES_LATERAIS = 140.0

BOTAO_INICIO = Botoes.P3
PARA_CHOQUE_ESQ = Botoes.P1
PARA_CHOQUE_DIR = Botoes.P2


class Robo:
    def __init__(self):
        # tração 4x4: 2 motores no Mariola (traseiros) + 2 placas de motor (dianteiros)
        self.motores = Motores(False)
        self.motores.direcao_motor(2, Motores.INVERTIDO)
        porta = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
        self.m_de = PlacaControleMotor(porta, 8)
        self.m_dd = PlacaControleMotor(porta, 51)
        self.m_de.reset()
        self.m_dd.reset()
        self.m_dd.direcao_motor(PlacaControleMotor.INVERTIDO)

        self.giro = Giroscopio(Portas.SERIAL5)
        # cores aprendidas no campo com calibra_cores.py (se o arquivo existir)
        self.cor = CorReflexao(Portas.SERIAL6, arquivo_cores='cores_piso.json')
        self.cor.usa_cores(['branco', 'preto', 'prata', 'azul', 'vermelho'])   # cores da Maze
        self.vl = {
            'esq_frente': VL53L0X(Portas.I2C1),
            'esq_tras': VL53L0X(Portas.I2C2),
            'dir_frente': VL53L0X(Portas.I2C3),
            'dir_tras': VL53L0X(Portas.I2C4),
            'frente': VL53L0X(Portas.I2C5),
        }
        self.botoes = Botoes()
        self.camera = DeteccaoVitimas()
        self.kits = DispensadorKits()
        self.dist = {k: 8190 for k in self.vl}
        self.z_alvo = 0.0        # direção desejada (graus do giroscópio)

    # ------------------------------------------------------------------ motores
    def anda(self, ve, vd):
        """Velocidade (-100..100) dos lados esquerdo e direito."""
        ve, vd = int(max(-100, min(100, ve))), int(max(-100, min(100, vd)))
        self.motores.velocidade_motores(ve, vd)
        self.motores.atualiza_motores()      # também lê os encoders do Mariola
        self.m_de.velocidade_motor(ve)
        self.m_dd.velocidade_motor(vd)

    def para(self):
        self.anda(0, 0)

    def encoder_mm(self):
        """Distância média andada pelos motores do Mariola desde o último zera_encoder()."""
        e = self.motores.angulo_motor(1)
        d = self.motores.angulo_motor(2)
        return (e + d) / 2.0 * MM_POR_CONTAGEM

    def zera_encoder(self):
        self.motores.estado()
        self.motores.reseta_angulo_motor(1)
        self.motores.reseta_angulo_motor(2)

    # ------------------------------------------------------------------ sensores
    def le_distancias(self):
        for s in self.vl.values():
            s.solicita_leitura()
        time.sleep(0.034)
        for k, s in self.vl.items():
            try:
                self.dist[k] = s.leitura_mm()
            except (OSError, TimeoutError):
                self.dist[k] = 8190
        return self.dist

    def z(self):
        """Ângulo em graus, positivo = anti-horário (esquerda), acumulando."""
        z = self.giro.le_angulo_z()
        return -z if GIRO_HORARIO_POSITIVO else z

    def para_choque(self):
        return (self.botoes.botao_pressionado(PARA_CHOQUE_ESQ),
                self.botoes.botao_pressionado(PARA_CHOQUE_DIR))

    # Cor do piso pela lib (referências aprendidas no campo com calibra_cores.py)
    def piso(self):
        """'preto', 'prata', 'azul', 'vermelho', 'branco' ou 'desconhecida' (votação dos 3 TCS)."""
        return self.cor.cor_piso()

    def preto_na_frente(self):
        return self.cor.cores().count('preto') >= 2

    def espera(self, segundos):
        """Espera parado sem deixar o Mariola nem as placas de motor ficarem 5 s sem comando
        (o firmware desliga os motores e APAGA OS LEDS, inclusive a iluminação das câmeras)."""
        fim = time.time() + segundos
        while time.time() < fim:
            self.para()
            time.sleep(min(0.5, max(0.0, fim - time.time())))

    def espera_botao(self):
        print('Aguardando o botão de início...')
        while not self.botoes.botao_pressionado(BOTAO_INICIO):
            time.sleep(0.02)
        while self.botoes.botao_pressionado(BOTAO_INICIO):
            time.sleep(0.02)

    # ------------------------------------------------------------------ LED e kits
    def led(self, ligado, cor=(255, 0, 0)):
        """LEDs de indicação de vítima (não mexe na iluminação das câmeras)."""
        c = cor if ligado else (0, 0, 0)
        for i in LEDS_VITIMA:
            self.motores.set_led_rgb_one(i, *c)

    def ilumina_cameras(self, ligado=True, cor=(255, 255, 255)):
        c = cor if ligado else (0, 0, 0)
        for i in LEDS_CAMERA_ESQ + LEDS_CAMERA_DIR:
            self.motores.set_led_rgb_one(i, *c)

    def pisca(self, segundos, meio_periodo):
        """Pisca o LED de vítima (regra: 500 ms aceso / 500 ms apagado por 5 s parado)."""
        self.para()
        fim = time.time() + segundos
        while time.time() < fim:
            self.led(True)
            time.sleep(meio_periodo)
            self.led(False)
            time.sleep(meio_periodo)

    # ------------------------------------------------------------------ movimentos
    def gira(self, graus):
        """Gira no lugar (positivo = anti-horário/esquerda) usando o giroscópio."""
        self.z_alvo += graus
        self.gira_para(self.z_alvo)

    def gira_para(self, alvo, tol=1.0, tempo_max=4.0):
        t0 = time.time()
        while time.time() - t0 < tempo_max:
            erro = alvo - self.z()
            if abs(erro) <= tol:
                break
            v = max(14, min(45, abs(erro) * 0.9))
            v = v if erro > 0 else -v
            self.anda(-v, v)
            time.sleep(0.01)
        self.para()
        time.sleep(0.08)

    def anda_mm(self, mm, vel=45, olha_preto=False, parar_frente=None, centraliza=True):
        """Anda reto mm milímetros mantendo a direção z_alvo e (se houver paredes dos
        lados) o robô no meio do corredor. Retorna ('ok' | 'preto' | 'parede', mm_andados)."""
        self.zera_encoder()
        sentido = 1 if mm >= 0 else -1
        alvo = abs(mm)
        motivo = 'ok'
        t0 = time.time()
        while time.time() - t0 < 6.0:
            andado = abs(self.encoder_mm())
            if andado >= alvo - 8:          # ~8 mm de "freada" depois do comando de parar
                break
            if olha_preto and sentido > 0 and self.preto_na_frente():
                motivo = 'preto'
                break
            d = self.le_distancias() if (centraliza or parar_frente is not None) else None
            if parar_frente is not None and sentido > 0 and d['frente'] <= parar_frente:
                motivo = 'parede'
                break
            desvio = 0.0                    # + = robô à esquerda do centro do corredor
            if centraliza:
                e = []
                if d['esq_frente'] < 120 and d['esq_tras'] < 120:
                    e.append(LATERAL_CENTRO - (d['esq_frente'] + d['esq_tras']) / 2)
                if d['dir_frente'] < 120 and d['dir_tras'] < 120:
                    e.append((d['dir_frente'] + d['dir_tras']) / 2 - LATERAL_CENTRO)
                if e:
                    desvio = sum(e) / len(e)
            alvo_z = self.z_alvo - sentido * max(-8.0, min(8.0, 0.12 * desvio))
            erro = alvo_z - self.z()
            corr = max(-15, min(15, erro * 2.5))
            v = vel if alvo - andado > 70 else max(18, vel * 0.45)
            self.anda(sentido * v - corr, sentido * v + corr)
        self.para()
        time.sleep(0.05)
        return motivo, abs(self.encoder_mm())

    def encosta_na_frente(self, tempo_max=1.6):
        """Anda devagar até os dois botões do para-choque apertarem (alinha com a parede)."""
        t0 = time.time()
        ok = False
        while time.time() - t0 < tempo_max:
            e, d = self.para_choque()
            if e and d:
                ok = True
                break
            if e and not d:
                self.anda(10, 30)
            elif d and not e:
                self.anda(30, 10)
            else:
                self.anda(25, 25)
            time.sleep(0.01)
        self.para()
        return ok

    def alinha_parede_lateral(self):
        """Usa os dois VL53 de um lado para medir o ângulo do robô em relação à parede.
        Retorna o erro de ângulo (graus, + = robô girado para a esquerda) ou None."""
        soma = {k: 0.0 for k in self.vl}
        n = 4                       # média de 4 leituras: o VL53 tem alguns mm de ruído
        for _ in range(n):
            for k, v in self.le_distancias().items():
                soma[k] += v / n
        ef, et, df, dt = soma['esq_frente'], soma['esq_tras'], soma['dir_frente'], soma['dir_tras']
        angs = []
        if ef < 120 and et < 120:
            angs.append(math.degrees(math.atan2(et - ef, DIST_SENSORES_LATERAIS)))
        if df < 120 and dt < 120:
            angs.append(math.degrees(math.atan2(df - dt, DIST_SENSORES_LATERAIS)))
        if not angs:
            return None
        return sum(angs) / len(angs)
