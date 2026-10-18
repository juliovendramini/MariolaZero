"""Camada de hardware do robô da Rescue Line usando as bibliotecas do Mariola.

Roda igual no robô real e no simulador. Serve para os dois robôs:
* 4x4: 2 motores no Mariola (traseiros) + 2 placas de motor (dianteiros, SERIAL1)
* esteira: só os 2 motores do Mariola
TRACAO = 'auto' descobre sozinho: se não houver nada na SERIAL1, é a esteira.

Sensor de linha Pro1616 (SERIAL6): 4 canais de reflexão (cada um = 3 ITR8307) e 3 TCS34725.
Canal 0 / TCS1 = lado esquerdo do robô.
"""

import math
import time

from botoes import Botoes
from giroscopio import Giroscopio
from motores import Motores
from placaControleMotor import PlacaControleMotor
from portas import Portas
from sensorCorReflexao import CorReflexao
from vl53 import VL53L0X

try:
    from placaControleServo import PlacaControleServo
except ImportError:            # robô sem a lib dos servos
    PlacaControleServo = None
try:
    from tcs34725 import TCS34725
except ImportError:
    TCS34725 = None

TRACAO = 'auto'               # '4x4', 'esteira' ou 'auto'

# ------------------------------------------------------------------ constantes (A MEDIR no robô)
DIAMETRO_RODA = {'4x4': 70.0, 'esteira': 40.0}     # mm (roda / polia da esteira)
PULSOS_ENCODER_MOTOR = 17
REDUCAO = 34
CONTAGENS_POR_VOLTA = PULSOS_ENCODER_MOTOR * REDUCAO * 2      # motores do Mariola (x2)
GIRO_HORARIO_POSITIVO = True

# posição lateral (mm, + = esquerda) de cada canal de reflexão: grupos de 3 ITR8307 com passo 65/11
PASSO_IR = 65.0 / 11
Y_CANAIS = [(5.5 - (3 * k + 1)) * PASSO_IR for k in range(4)]    # 26.6, 8.9, -8.9, -26.6

# ------------------------------------------------------------------ mecanismo de resgate (A CALIBRAR)
# IDs dos servos inteligentes (mesmo barramento das placas de motor) e a leitura do potenciômetro
# em cada posição. Têm que bater com o robô (e com o "resgate" do robo_4x4.json no simulador).
SERVO_BRACO, SERVO_DEDO_ESQ, SERVO_DEDO_DIR, SERVO_PORTA = 70, 71, 72, 73
BRACO_BAIXO, BRACO_ALTO = 820, 270
DEDO_ESQ_ABERTO, DEDO_ESQ_FECHADO = 380, 680
DEDO_DIR_ABERTO, DEDO_DIR_FECHADO = 640, 340
PORTA_FECHADA, PORTA_SOLTA_ESQ, PORTA_SOLTA_DIR = 512, 330, 700

# VL53 extras e TCS34725 horizontais (canais do mux)
VL53_CANAIS = {'frente': Portas.I2C5, 'esquerda': Portas.I2C1, 'direita': Portas.I2C3, 'garra': Portas.I2C2}
TCS_CANAIS = {'frente': Portas.I2C6, 'tras': Portas.I2C7}

BOTAO_INICIO = Botoes.P3
PARA_CHOQUE_ESQ = Botoes.P1
PARA_CHOQUE_DIR = Botoes.P2


class Robo:
    def __init__(self):
        self.motores = Motores(False)
        self.motores.direcao_motor(2, Motores.INVERTIDO)
        self.placas = []
        tracao = TRACAO
        if tracao in ('auto', '4x4'):
            porta = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
            if porta is not None:
                m_de = PlacaControleMotor(porta, 8)
                m_dd = PlacaControleMotor(porta, 51)
                m_de.reset()
                m_dd.reset()
                m_dd.direcao_motor(PlacaControleMotor.INVERTIDO)
                self.placas = [m_de, m_dd]
                tracao = '4x4'
            elif tracao == '4x4':
                raise RuntimeError('placas de motor não encontradas na SERIAL1')
        if not self.placas:
            tracao = 'esteira'
        self.tracao = tracao
        self.mm_por_contagem = math.pi * DIAMETRO_RODA[tracao] / CONTAGENS_POR_VOLTA
        print(f'Tração: {tracao}')

        self.giro = Giroscopio(Portas.SERIAL5)
        self.cor = CorReflexao(Portas.SERIAL6, arquivo_cores='cores_line.json')
        self.cor.usa_cores(['branco', 'preto', 'verde', 'vermelho', 'prata'])
        self.botoes = Botoes()
        self.vl = {}             # nome -> [sensor, última distância, momento do pedido]
        for nome, canal in VL53_CANAIS.items():
            try:
                self.vl[nome] = [VL53L0X(canal), 8190, 0.0]
            except Exception as e:   # robô sem esse sensor
                print(f'VL53 {nome} não encontrado:', e)
        self.vl_frente = self.vl.get('frente', [None])[0]
        self.tcs = {}
        if TCS34725 is not None:
            for nome, canal in TCS_CANAIS.items():
                try:
                    self.tcs[nome] = TCS34725(canal)
                except Exception:
                    pass
        self.garra = Garra.procura(Portas.SERIAL1)
        self.z_ref = 0.0

    # ------------------------------------------------------------------ motores
    def anda(self, ve, vd):
        """Velocidade (-100..100) dos lados esquerdo e direito."""
        ve, vd = int(max(-100, min(100, ve))), int(max(-100, min(100, vd)))
        self.motores.velocidade_motores(ve, vd)
        self.motores.atualiza_motores()      # também lê os encoders do Mariola
        if self.placas:
            self.placas[0].velocidade_motor(ve)
            self.placas[1].velocidade_motor(vd)

    def para(self):
        self.anda(0, 0)

    def encoder_mm(self):
        e = self.motores.angulo_motor(1)
        d = self.motores.angulo_motor(2)
        return (e + d) / 2.0 * self.mm_por_contagem

    def zera_encoder(self):
        self.motores.estado()
        self.motores.reseta_angulo_motor(1)
        self.motores.reseta_angulo_motor(2)

    # ------------------------------------------------------------------ sensores
    def reflexao(self):
        """4 canais: 0 = preto, ~100 = branco."""
        return self.cor.le_reflexao()

    def cores(self):
        """Cor embaixo de cada TCS: [esquerda, meio, direita].

        Na borda da linha, com pouca luz, uma leitura isolada pode ser classificada como verde ou
        vermelho. Por isso verde/vermelho só valem se o RGB também tiver a cor dominante."""
        out = []
        for k, nome in enumerate(self.cor.cores(), start=1):
            if nome in ('verde', 'vermelho'):
                r, g, b, c = self.cor.le_rgbc(k)
                if nome == 'verde' and not (g > 1.4 * r and g > 1.15 * b and c > 20):
                    nome = 'desconhecida'
                elif nome == 'vermelho' and not (r > 1.8 * g and r > 1.8 * b and c > 20):
                    nome = 'desconhecida'
            out.append(nome)
        return out

    def z(self):
        """Ângulo em graus, positivo = anti-horário (esquerda), acumulando."""
        z = self.giro.le_angulo_z()
        return -z if GIRO_HORARIO_POSITIVO else z

    def inclinacao(self):
        """Graus, positivo = frente para cima (subindo rampa)."""
        return self.giro.le_angulo_x()

    def distancia(self, nome):
        """Distância (mm) do VL53 'nome' (lê no máximo a cada ~36 ms, sem esperar a medida)."""
        v = self.vl.get(nome)
        if v is None:
            return 8190
        sensor, ultima, t_pedido = v
        agora = time.time()
        if agora - t_pedido > 0.036:      # medida pedida antes já ficou pronta (~33 ms)
            try:
                if t_pedido > 0:
                    v[1] = sensor.leitura_mm()
                sensor.solicita_leitura()   # já pede a próxima sem esperar
            except (OSError, TimeoutError):
                v[1] = 8190
            v[2] = time.time()
        return v[1]

    def frente_mm(self):
        return self.distancia('frente')

    def cor_tcs(self, nome):
        """(r, g, b, c) cru de um TCS34725 horizontal, ou None se não houver."""
        s = self.tcs.get(nome)
        if s is None:
            return None
        try:
            return s.le_valores()
        except OSError:
            return None

    def para_choque(self):
        return (self.botoes.botao_pressionado(PARA_CHOQUE_ESQ) or
                self.botoes.botao_pressionado(PARA_CHOQUE_DIR))

    def espera_botao(self):
        print('Aguardando o botão de início...')
        while not self.botoes.botao_pressionado(BOTAO_INICIO):
            self.para()
            time.sleep(0.05)
        while self.botoes.botao_pressionado(BOTAO_INICIO):
            time.sleep(0.02)

    # ------------------------------------------------------------------ movimentos
    def gira_para(self, alvo, tol=2.0, tempo_max=4.0):
        t0 = time.time()
        while time.time() - t0 < tempo_max:
            erro = alvo - self.z()
            if abs(erro) <= tol:
                break
            v = max(18, min(50, abs(erro) * 0.9))
            v = v if erro > 0 else -v
            self.anda(-v, v)
            time.sleep(0.01)
        self.para()

    def gira(self, graus, **kw):
        """Gira no lugar (positivo = esquerda) pelo giroscópio."""
        self.gira_para(self.z() + graus, **kw)

    def anda_mm(self, mm, vel=40, para_se=None, tempo_max=5.0):
        """Anda reto mm milímetros mantendo a direção. para_se(): função que interrompe.
        Retorna True se andou tudo, False se parou pelo para_se."""
        self.zera_encoder()
        z0 = self.z()
        s = 1 if mm >= 0 else -1
        t0 = time.time()
        while time.time() - t0 < tempo_max:
            if abs(self.encoder_mm()) >= abs(mm) - 3:
                break
            if para_se and para_se():
                self.para()
                return False
            corr = max(-15, min(15, (z0 - self.z()) * 2.0))
            self.anda(s * vel - corr, s * vel + corr)
            time.sleep(0.01)
        self.para()
        return True


class Garra:
    """Braço + dois dedos + porta da caçamba (4 servos inteligentes no barramento SERIAL1).

    Cuidados (iguais no robô):
    * o braço só se segura sozinho todo levantado; no meio, sem força, ele cai;
    * os dedos só seguram a bolinha com força enquanto empurram: depois do tempo de trava da
      placa (calibrado na EEPROM) o motor desliga 2 s e a bolinha pode cair com o braço subindo;
    * mande os comandos de novo antes de 5 s (senão a placa desliga o motor);
    * para ler a posição sem soltar o servo use consulta_posicao() (le_posicao() desliga o motor).
    """
    POT = 230

    def __init__(self, porta):
        self.braco = PlacaControleServo(porta, SERVO_BRACO)
        self.dedo_esq = PlacaControleServo(porta, SERVO_DEDO_ESQ)
        self.dedo_dir = PlacaControleServo(porta, SERVO_DEDO_DIR)
        self.porta = PlacaControleServo(porta, SERVO_PORTA)
        self.alvos = {}

    @classmethod
    def procura(cls, porta):
        if PlacaControleServo is None:
            return None
        try:
            g = cls(porta)
            if g.braco.consulta_posicao() is None:
                print('Garra: servo do braço não respondeu (robô sem mecanismo de resgate)')
                return None
            print('Garra encontrada')
            return g
        except Exception as e:
            print('Garra não encontrada:', e)
            return None

    def _move(self, servo, pos, pot=None):
        self.alvos[servo] = (pos, pot or self.POT)
        servo.move_servo(pos, pot or self.POT, 6)

    def mantem(self):
        """Repete os últimos comandos (chame de tempos em tempos)."""
        for servo, (pos, pot) in self.alvos.items():
            servo.move_servo(pos, pot, 6)

    def espera_braco(self, alvo, tol=30, tempo_max=1.5):
        t0 = time.time()
        while time.time() - t0 < tempo_max:
            p = self.braco.consulta_posicao()
            if p is not None and abs(p - alvo) <= tol:
                return True
            time.sleep(0.02)
        return False

    def abaixa_aberta(self):
        self._move(self.dedo_esq, DEDO_ESQ_ABERTO)
        self._move(self.dedo_dir, DEDO_DIR_ABERTO)
        self._move(self.braco, BRACO_BAIXO, 200)
        self.espera_braco(BRACO_BAIXO, tol=40)

    def fecha(self):
        self._move(self.dedo_esq, DEDO_ESQ_FECHADO)
        self._move(self.dedo_dir, DEDO_DIR_FECHADO)
        time.sleep(0.35)

    def levanta(self):
        self._move(self.braco, BRACO_ALTO, 255)
        self.espera_braco(BRACO_ALTO)

    def joga_na_cacamba(self, lado):
        """Com o braço no alto, abre só o dedo do lado e fecha de novo."""
        if lado == 'esq':
            self._move(self.dedo_esq, DEDO_ESQ_ABERTO)
        else:
            self._move(self.dedo_dir, DEDO_DIR_ABERTO)
        time.sleep(0.4)
        self.fecha()

    def solta(self, lado, tempo=1.2):
        """Abre a porta de um lado da caçamba e fecha de novo."""
        self._move(self.porta, PORTA_SOLTA_ESQ if lado == 'esq' else PORTA_SOLTA_DIR, 200)
        time.sleep(tempo)
        self._move(self.porta, PORTA_FECHADA, 200)
        time.sleep(0.3)

    def guarda(self):
        """Posição de andar: braço no alto, dedos fechados, porta fechada."""
        self._move(self.dedo_esq, DEDO_ESQ_FECHADO)
        self._move(self.dedo_dir, DEDO_DIR_FECHADO)
        self._move(self.porta, PORTA_FECHADA)
        self._move(self.braco, BRACO_ALTO, 255)
