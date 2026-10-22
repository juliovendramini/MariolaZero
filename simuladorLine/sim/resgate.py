"""Área de resgate (regra 2026, seções 3.9 e 3.10) e o mecanismo de resgate do robô.

* Área: paredes de 10 cm com o vão da entrada e da saída, triângulos (pontos de evacuação)
  com paredes de 6 cm, obstáculo opcional, 2 vítimas vivas (prata) + 1 morta (preta) que rolam.
* Servos "inteligentes" (placaControleServo.ino unificado) no mesmo barramento das placas de
  motor: protocolo de 6 bytes, broadcast, troca de ID, calibração do tempo de trava, trava
  (1 s parado = motor desliga 2 s), 5 s sem comando = motor desliga, 10 s = placa reinicia.
* Mecanismo: braço que abaixa a garra, dois dedos (um servo cada) e caçamba de dois lados
  com uma porta que solta um lado de cada vez.
  - O braço cai pelo peso quando o servo dele está sem força, a não ser que esteja todo levantado.
  - Os dedos só seguram a bolinha com força enquanto os motores deles empurram. Se um deles
    desliga (trava, potência 0, timeout) com o braço se mexendo, a bolinha cai.
  - Com o braço no alto, abrir um dedo só joga a bolinha no lado da caçamba daquele dedo.
  - A porta solta as bolinhas de um lado, a ~10 cm do chão, atrás do robô.
* Stub da câmera: detecções de vítimas e triângulos com 90% de acerto (sem imagem).

Unidades: mm, kg, s. Referencial do robô: x para frente, y para a esquerda.
"""

import hashlib
import math
import random

import pymunk
from pymunk import Vec2d

from . import mapa as M

CAT_OBST = 0b0001
CAT_ROBO = 0b0010
CAT_SENSOR = 0b0100
CAT_BOLA = 0b10000
CAT_GARRA = 0b100000

RAIO_BOLA = 22.5            # regra: esfera de 4 a 5 cm
MASSA_BOLA = 0.07           # regra: até 80 g

CORES = {
    'viva': (185, 190, 198),        # prata refletiva
    'morta': (25, 25, 25),
    'falsa': (150, 150, 150),
    'verde': (0, 166, 81),
    'vermelho': (200, 20, 20),
    'obstaculo': (90, 90, 95),
}
REFLETE_VIVA = 1.6                  # prata devolve mais luz que uma superfície branca

MASK_ZONA = CAT_ROBO | CAT_SENSOR | CAT_OBST | CAT_BOLA | CAT_GARRA


def _h(*partes):
    """Número em [0, 1) determinístico a partir das partes (erro "preso" ao ponto de vista)."""
    d = hashlib.blake2b(repr(partes).encode(), digest_size=8).digest()
    return int.from_bytes(d, 'little') / 2.0 ** 64


def _ponto_no_triangulo(p, tri):
    (x1, y1), (x2, y2), (x3, y3) = tri
    x, y = p

    def s(ax, ay, bx, by):
        return (x - bx) * (ay - by) - (ax - bx) * (y - by)
    d1, d2, d3 = s(x1, y1, x2, y2), s(x2, y2, x3, y3), s(x3, y3, x1, y1)
    neg = d1 < 0 or d2 < 0 or d3 < 0
    pos = d1 > 0 or d2 > 0 or d3 > 0
    return not (neg and pos)


def _dist_reta(p, a, b):
    ax, ay = a
    bx, by = b
    L = math.hypot(bx - ax, by - ay)
    return abs((bx - ax) * (ay - p[1]) - (ax - p[0]) * (by - ay)) / L


# =========================================================================== servos
class ServoFisico:
    """MG90S com o potenciômetro lido pela placa (0-1023)."""

    def __init__(self, nome, cfg, cfg_servo, pot0):
        self.nome = nome
        self.cfg = cfg
        graus_s = float(cfg_servo.get('graus_por_s', 500.0))
        self.vmax = graus_s * float(cfg_servo.get('pot_por_grau', 3.41)) * float(cfg.get('carga', 1.0))
        self.pwm_min = float(cfg_servo.get('pwm_minimo', 60))
        self.pot = float(pot0)
        self.pwm = 0                 # comando da ponte H (-255..255)
        self.bloqueado = False
        self.vel = 0.0               # pot/s do último passo

    def integra(self, dt, lo, hi, passivo=0.0):
        """Anda com o motor (ou com a velocidade passiva, ex.: braço caindo) dentro de [lo, hi].
        Se já estiver fora dos limites (a bolinha entrou entre os dedos), só pode voltar."""
        p0 = self.pot
        v = passivo
        if self.pwm != 0 and abs(self.pwm) > self.pwm_min:
            v = math.copysign(self.vmax * (abs(self.pwm) - self.pwm_min) / (255.0 - self.pwm_min), self.pwm)
        lo, hi = min(lo, hi), max(lo, hi)
        novo = self.pot + v * dt
        self.bloqueado = False
        if novo < lo and v < 0:
            novo = max(novo, min(self.pot, lo))
            self.bloqueado = True
        elif novo > hi and v > 0:
            novo = min(novo, max(self.pot, hi))
            self.bloqueado = True
        self.pot = novo
        self.vel = (self.pot - p0) / dt if dt > 0 else 0.0


class FirmwareServo:
    """placaControleServo.ino (versão de 21/10/2026: polaridade e controle proporcional).

    O laço do firmware roda bem mais rápido que a física (240 Hz); a velocidade do termo D é medida
    a cada "período" e normalizada para contagens por período, como o firmware vê."""
    ID_BROADCAST = 254
    COMANDO_CALIBRACAO = 65000
    COMANDO_POLARIDADE = 65002
    COMANDO_CONTROLE = 65003
    DESCANSO = 2.0
    TIMEOUT_COMUNICACAO = 5.0
    TIMEOUT_RESET = 10.0
    TEMPO_AUTODETECCAO = 0.3          # s: dois pulsos curtos, sem atender a serial
    MODO_LIGA_DESLIGA, MODO_PROPORCIONAL = 0, 1
    ESCALA = 16                       # KP, KD e KI em 1/16
    # modo, KP, KD, PWM mínimo, histerese, período (ms), KI, faixa do termo I, limite do termo I
    CONTROLE_PADRAO = (1, 48, 128, 60, 4, 5, 0, 40, 150)
    P_MODO, P_KP, P_KD, P_PWM_MIN, P_HIST, P_PERIODO, P_KI, P_FAIXA_I, P_LIMITE_I = range(9)
    RESTAURA, SO_CONSULTA = 0x7F, 0x80

    def __init__(self, mundo, servo, id_placa, tabela, tempo_trava, rng):
        self.servo = servo
        self.id = id_placa
        self.tabela = tabela          # dict id -> firmware do barramento (troca de ID muda a chave)
        self.tempo_trava = max(1.0, min(5.0, tempo_trava))
        self.rng = rng
        self.eh_servo = True
        # o que fica na EEPROM (sobrevive ao reset): a placa já fez a autodetecção no primeiro boot
        self.controle = list(self.CONTROLE_PADRAO)
        self.polaridade_invertida = False
        self.polaridade_calibrada = True
        self.status_autodeteccao = 0  # 0 não rodou desde o boot, 1 sucesso, 2 falhou
        self.ocupado_ate = -1.0
        self._reinicia(0.0)

    def _reinicia(self, t):
        self.alvo = 512
        self.potencia = 0
        self.zona = 5
        self.status_autodeteccao = 0
        self.ult_com = t
        self.servo.pwm = 0
        self._reinicia_controle(t)
        self.pos_amostra = self.leitura()
        self.ult_amostra = t
        self.vel = 0.0

    def _reinicia_controle(self, t):
        """reiniciarControle(): histerese, termo I e proteção contra trava do zero."""
        self.parado = True
        self.integral = 0
        self.integral_bloqueada = False
        self.travado = False
        self.ini_descanso = 0.0
        self.pos_ant = self.leitura()
        self.ult_mudanca = t

    def leitura(self, media=False):
        """analogRead do potenciômetro; com media=True, a média de 8 leituras (menos ruído)."""
        ruido = 0.6 / (8 ** 0.5) if media else 0.6
        return max(0, min(1023, int(round(self.servo.pot + self.rng.gauss(0, ruido)))))

    def _pacote(self, campo_pos, c3, c4):
        r = [self.id, (campo_pos >> 8) & 0xFF, campo_pos & 0xFF, c3 & 0xFF, c4 & 0xFF]
        x = 0
        for b in r:
            x ^= b
        return bytes(r + [x])

    def _resp(self, pos=None):
        return self._pacote(self.leitura() if pos is None else pos, self.potencia, self.zona)

    def quadro(self, f, t):
        """Pacote de 6 bytes com CRC certo, para este ID ou broadcast."""
        if t < self.ocupado_ate:          # autodetectando: a serial não é atendida
            return None
        self.ult_com = t
        br = f[0] == self.ID_BROADCAST
        valor = (f[1] << 8) | f[2]
        if f[1] == 0xFF and f[3] == 0xAA and f[4] == 0x55:
            if not br and f[2] < self.ID_BROADCAST:
                self.tabela.pop(self.id, None)
                self.id = f[2]
                self.tabela[self.id] = self
            return None
        if valor == self.COMANDO_CALIBRACAO:
            self.tempo_trava = max(1.0, min(5.0, ((f[3] << 8) | f[4]) / 1000.0))
            return None if br else (self._resp(self.COMANDO_CALIBRACAO), 0.0006)
        if valor == self.COMANDO_POLARIDADE:
            acao = (f[3] << 8) | f[4]
            if acao == 2:
                # no simulador o motor está ligado do jeito normal: a autodetecção acerta
                self.ocupado_ate = t + self.TEMPO_AUTODETECCAO
                self.servo.pwm = 0
                self.polaridade_invertida = False
                self.polaridade_calibrada = True
                self.status_autodeteccao = 1
                self._reinicia_controle(t)
                return None
            if acao in (0, 1):
                self.polaridade_invertida = acao == 1
                self.polaridade_calibrada = True
                self._reinicia_controle(t)
            if br:
                return None
            pol = (1 if self.polaridade_invertida else 0) if self.polaridade_calibrada else 0xFF
            return self._pacote(self.COMANDO_POLARIDADE, pol, self.status_autodeteccao), 0.0006
        if valor == self.COMANDO_CONTROLE:
            so_consulta = bool(f[3] & self.SO_CONSULTA)
            par = f[3] & ~self.SO_CONSULTA & 0xFF
            if par == self.RESTAURA:
                if not so_consulta:
                    self.controle = list(self.CONTROLE_PADRAO)
                    self._reinicia_controle(t)
                return None if br else (self._pacote(self.COMANDO_CONTROLE, self.RESTAURA, 0), 0.0006)
            if par >= len(self.controle):
                return None if br else (self._pacote(self.COMANDO_CONTROLE, 0xFF, 0), 0.0006)
            if not so_consulta:
                v = f[4]
                if not (par == self.P_MODO and v > self.MODO_PROPORCIONAL):
                    if par == self.P_PERIODO:
                        v = max(1, min(100, v))
                    self.controle[par] = v
                    self._reinicia_controle(t)
            return None if br else (self._pacote(self.COMANDO_CONTROLE, par, self.controle[par]), 0.0006)
        if valor > 1023:                  # 65001 (consulta) e outros: responde sem mudar o comando
            return None if br else (self._resp(), 0.0006)
        if abs(valor - self.alvo) > self.controle[self.P_FAIXA_I]:
            self.integral = 0             # alvo novo longe: a força guardada no termo I não vale mais
        self.alvo = valor
        self.potencia = f[3]
        self.zona = f[4]
        return None if br else (self._resp(), 0.0006)

    # ------------------------------------------------------------------ controle
    def _aciona(self, aumentar, pwm):
        """acionarMotor(): o sentido da ponte H depende da polaridade (o motor do simulador é normal)."""
        self.servo.pwm = pwm if aumentar != self.polaridade_invertida else -pwm

    def _amostra_velocidade(self, pos, t):
        periodo = self.controle[self.P_PERIODO] / 1000.0
        dec = t - self.ult_amostra
        if dec < periodo - 1e-9:
            return False
        self.vel = (pos - self.pos_amostra) * periodo / dec if dec <= 2 * periodo + 1e-9 else 0.0
        self.pos_amostra = pos
        self.ult_amostra = t
        return True

    def _acumula_integral(self, erro):
        c = self.controle
        if c[self.P_KI] == 0 or abs(erro) > c[self.P_FAIXA_I]:
            return
        aumentaria = self.integral == 0 or (erro > 0) == (self.integral > 0)
        if self.integral_bloqueada and aumentaria:
            return
        lim = c[self.P_LIMITE_I] * self.ESCALA
        self.integral = max(-lim, min(lim, self.integral + c[self.P_KI] * erro))

    def _proporcional(self, erro, potencia, periodo_novo):
        c = self.controle
        if periodo_novo:
            self._acumula_integral(erro)
        num = c[self.P_KP] * erro - c[self.P_KD] * self.vel + self.integral
        saida = math.trunc(num / self.ESCALA)          # divisão inteira do C (para o zero)
        if saida == 0 or (saida > 0) != (erro > 0):
            self.integral_bloqueada = True
            self.servo.pwm = 0                         # as duas saídas em LOW: freia
            return
        mag = abs(saida)
        self.integral_bloqueada = mag >= potencia
        pwm = min(mag, 255)
        pwm = max(pwm, c[self.P_PWM_MIN])
        pwm = min(pwm, potencia)                       # a potência do pacote é sempre o teto
        self._aciona(erro > 0, pwm)

    def passo(self, t):
        s = self.servo
        if t < self.ocupado_ate:
            s.pwm = 0
            return
        if t - self.ult_com > self.TIMEOUT_RESET:
            self._reinicia(t)           # watchdog: a placa reinicia (EEPROM mantém ID, trava, polaridade e controle)
            return
        if t - self.ult_com > self.TIMEOUT_COMUNICACAO:
            self.potencia = 0
        prop = self.controle[self.P_MODO] == self.MODO_PROPORCIONAL
        pos = self.leitura(media=prop)
        erro = self.alvo - pos
        periodo_novo = self._amostra_velocidade(pos, t)
        limite = self.zona + (self.controle[self.P_HIST] if prop and self.parado else 0)
        dentro = abs(erro) <= limite
        self.parado = dentro or self.potencia == 0
        if dentro or self.potencia == 0:
            if self.potencia == 0:
                self.integral = 0
            self.integral_bloqueada = False
            s.pwm = 0
            self.travado = False
            self.pos_ant = pos
            self.ult_mudanca = t
            return
        if self.travado:
            s.pwm = 0
            if t - self.ini_descanso >= self.DESCANSO:
                self.travado = False
                self.pos_ant = pos
                self.ult_mudanca = t
            return
        if abs(pos - self.pos_ant) > 2 * self.zona:
            self.pos_ant = pos
            self.ult_mudanca = t
        if t - self.ult_mudanca >= self.tempo_trava:
            self.travado = True
            self.integral = 0           # senão volta do descanso empurrando a trava com o termo I cheio
            self.ini_descanso = t
            s.pwm = 0
            return
        if prop:
            self._proporcional(erro, self.potencia, periodo_novo)
        else:
            self._aciona(erro > 0, self.potencia)   # liga-desliga: potência cheia até a zona morta

    @property
    def com_forca(self):
        return self.servo.pwm != 0


# =========================================================================== área
class AreaResgate:
    def __init__(self, mundo):
        self.w = mundo
        self.mapa = mundo.mapa
        self.ativa = bool(self.mapa.zona)
        self.bolas = []
        self.formas = []             # formas estáticas (paredes, triângulos)
        self.obst = None
        self.triangulos = {}
        self.falsas = []
        self.space = None
        self.rng = random.Random(1)
        self.rng_cam = random.Random(2)
        self.mec = None
        cfg = mundo.cfg.get('resgate') or {}
        if cfg.get('ativo', True) and cfg.get('braco'):
            self.mec = Mecanismo(mundo, self, cfg)
        self.camera_cfg = mundo.cfg.get('camera')
        self.ult_cam = {}
        self.tcs_cfg = mundo.cfg.get('tcs_i2c', [])
        self.rng_tcs = random.Random(9)

    # ------------------------------------------------------------------ construção
    def semear(self, base):
        self.rng = random.Random(base * 7 + 5)
        self.rng_cam = random.Random(base * 7 + 6)
        self.rng_tcs = random.Random(base * 7 + 9)
        self.base_semente = base
        if self.mec:
            self.mec.semear(base)

    def construir(self, space):
        self.space = space
        self.ativa = bool(self.mapa.zona)
        self.bolas = []
        self.formas = []
        self.obst = None
        self.triangulos = {}
        self.falsas = []
        if self.mec:
            self.mec.solta_tudo()
            self.mec.construir(space)
        if not self.ativa:
            return
        m = self.mapa
        z = m.zona
        cor = tuple(z.get('cor_parede', [200, 200, 205]))
        for (x1, y1, x2, y2) in m.paredes_zona():
            self._segmento(space, (x1, y1), (x2, y2), M.PAREDE_ESPESSURA / 2, M.PAREDE_ALTURA, cor, 'parede')
        self.triangulos = {}
        e = M.ESPESSURA_TRIANGULO
        for nome in ('verde', 'vermelho'):
            tri = m.triangulo(z[nome])
            self.triangulos[nome] = tri
            c, a, b = tri
            # hipotenusa (a parede que importa) e os catetos encostados nas paredes da área
            self._segmento(space, a, b, e / 2, M.TRIANGULO_ALTURA, CORES[nome], 'triangulo', nome)
            for p in (a, b):
                d = Vec2d(p[0] - c[0], p[1] - c[1]).normalized()
                n = Vec2d(-d.y, d.x)
                cen = Vec2d((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                if (cen - Vec2d(*c)).dot(n) < 0:
                    n = -n
                off = n * (e / 2 + 0.5)
                self._segmento(space, Vec2d(*c) + off + d * 6, Vec2d(*p) + off, e / 2, M.TRIANGULO_ALTURA,
                               CORES[nome], 'triangulo', nome)
        if z.get('obstaculo'):
            X0, Y0, X1, Y1 = m.retangulo_zona()
            ob = z['obstaculo']
            massa = 1.5
            b = pymunk.Body(massa, pymunk.moment_for_box(massa, (60, 60)))
            b.position = (X0 + float(ob['u']), Y0 + float(ob['v']))
            s = pymunk.Poly.create_box(b, (60, 60), radius=0.5)
            s.friction = 0.5
            s.filter = pymunk.ShapeFilter(categories=CAT_OBST, mask=MASK_ZONA)
            s.altura_mm, s.cor, s.tipo_obj = 150.0, CORES['obstaculo'], 'obstaculo'
            space.add(b, s)
            for j in self._atrito_chao(space, b, massa, 0.6, 60):
                space.add(j)
            self.obst = {'corpo': b, 'forma': s, 'pos': tuple(b.position)}
        self.sorteia_vitimas()

    def _segmento(self, space, a, b, raio, altura, cor, tipo, nome=None):
        s = pymunk.Segment(space.static_body, tuple(a), tuple(b), raio)
        s.friction = 0.5
        s.elasticity = 0.2
        s.filter = pymunk.ShapeFilter(categories=CAT_OBST, mask=MASK_ZONA)
        s.altura_mm, s.cor, s.tipo_obj, s.nome = altura, cor, tipo, nome
        space.add(s)
        self.formas.append(s)
        return s

    @staticmethod
    def _atrito_chao(space, b, massa, mu, tam):
        pj = pymunk.PivotJoint(space.static_body, b, (0, 0), (0, 0))
        pj.max_bias = 0
        pj.max_force = mu * massa * 9810.0
        gj = pymunk.GearJoint(space.static_body, b, 0.0, 1.0)
        gj.max_bias = 0
        gj.max_force = mu * massa * 9810.0 * tam / 3
        return pj, gj

    # ------------------------------------------------------------------ vítimas
    def _nova_bola(self, tipo, pos, ident):
        b = pymunk.Body(MASSA_BOLA, pymunk.moment_for_circle(MASSA_BOLA, 0, RAIO_BOLA))
        b.position = pos
        s = pymunk.Circle(b, RAIO_BOLA)
        s.friction = 0.4
        s.elasticity = 0.35
        s.filter = pymunk.ShapeFilter(categories=CAT_BOLA, mask=MASK_ZONA)
        s.altura_mm, s.cor, s.tipo_obj = 2 * RAIO_BOLA, CORES[tipo], 'bola'
        bola = {'id': ident, 'tipo': tipo, 'corpo': b, 'forma': s, 'estado': 'chao', 'fase': 0.0,
                'excentrico': self.rng.uniform(-1, 1), 'local': None, 'lado': None}
        s.bola = bola
        b.velocity_func = self._vel_bola(bola)
        return bola

    def _vel_bola(self, bola):
        def f(body, gravidade, amortecimento, dt):
            v = body.velocity
            s = v.length
            if s < 1e-6:
                body.velocity = (0, 0)
                return
            # resistência ao rolamento + centro de massa deslocado (a bolinha "torce" rolando)
            ns = max(0.0, s - 120.0 * dt) * (1.0 - 0.4 * dt)
            bola['fase'] += s * dt / RAIO_BOLA
            giro = 0.5 * bola['excentrico'] * math.sin(bola['fase']) * dt * min(1.0, s / 200.0)
            body.velocity = v.rotated(giro) * (ns / s)
            body.angular_velocity *= max(0.0, 1.0 - 3.0 * dt)
        return f

    def _livre(self, p, outros, folga=100.0):
        m = self.mapa
        X0, Y0, X1, Y1 = m.interior_zona()
        x, y = p
        if not (X0 + 50 <= x <= X1 - 50 and Y0 + 50 <= y <= Y1 - 50):
            return False
        for tri in self.triangulos.values():
            c, a, b = tri
            cen = ((c[0] + a[0] + b[0]) / 3, (c[1] + a[1] + b[1]) / 3)
            if _ponto_no_triangulo(p, tri) or _dist_reta(p, a, b) < 60 and \
                    math.hypot(x - cen[0], y - cen[1]) < 260:
                return False
        for ab in (m.zona['entrada'], m.zona['saida']):
            (cx, cy), _ = m.abertura_mundo(ab)
            if math.hypot(x - cx, y - cy) < 260:
                return False
        if self.obst and math.hypot(x - self.obst['pos'][0], y - self.obst['pos'][1]) < 110:
            return False
        return all(math.hypot(x - o[0], y - o[1]) >= folga for o in outros)

    def _posicao_livre(self, outros):
        X0, Y0, X1, Y1 = self.mapa.interior_zona()
        for _ in range(500):
            p = (self.rng.uniform(X0 + 60, X1 - 60), self.rng.uniform(Y0 + 60, Y1 - 60))
            if self._livre(p, outros):
                return p
        return ((X0 + X1) / 2, (Y0 + Y1) / 2)

    def sorteia_vitimas(self):
        for bola in self.bolas:
            if bola['corpo'] in self.space.bodies:
                self.space.remove(bola['corpo'], bola['forma'])
        self.bolas = []
        self.falsas = []
        if not self.ativa:
            return
        z = self.mapa.zona
        X0, Y0, X1, Y1 = self.mapa.retangulo_zona()
        lista = z.get('vitimas')
        usados = []
        if lista:
            itens = [(v['tipo'], (X0 + float(v['u']), Y0 + float(v['v']))) for v in lista]
        else:
            itens = []
            for tipo in ('viva', 'viva', 'morta'):
                p = self._posicao_livre(usados)
                usados.append(p)
                itens.append((tipo, p))
        for i, (tipo, p) in enumerate(itens):
            bola = self._nova_bola(tipo, p, i)
            self.space.add(bola['corpo'], bola['forma'])
            self.bolas.append(bola)
            usados.append(p)
        for _ in range(int(z.get('falsas', 0))):
            p = self._posicao_livre(usados)
            usados.append(p)
            self.falsas.append({'pos': p, 'id': len(self.falsas)})
        self.inicio_bolas = [(b['tipo'], tuple(b['corpo'].position)) for b in self.bolas]

    def reset(self):
        if self.mec:
            self.mec.reset()
        if not self.ativa:
            return
        if self.obst:
            b = self.obst['corpo']
            b.position = self.obst['pos']
            b.angle = 0
            b.velocity = (0, 0)
            b.angular_velocity = 0
            self.space.reindex_shapes_for_body(b)
        self.sorteia_vitimas()

    # ------------------------------------------------------------------ passo
    def passo(self, dt, t):
        if self.mec:
            self.mec.passo(dt, t)
        if not self.ativa:
            return
        for bola in self.bolas:
            if bola['estado'] == 'chao':
                self._confere_resgate(bola, t)

    def bolas_no_chao(self):
        return [b for b in self.bolas if b['estado'] == 'chao']

    def _confere_resgate(self, bola, t):
        """Vítima inteira dentro de um triângulo e sem o robô encostar: o juiz tira do campo."""
        p = tuple(bola['corpo'].position)
        for nome, tri in self.triangulos.items():
            c, a, b = tri
            if not _ponto_no_triangulo(p, tri) or _dist_reta(p, a, b) < M.ESPESSURA_TRIANGULO / 2 + RAIO_BOLA - 1:
                continue
            if any(q.shape is self.w.forma or getattr(q.shape, 'garra', False)
                   for q in self.space.shape_query(bola['forma'])):
                return
            if bola.get('no_triangulo') == nome:
                return                      # já foi avaliada e ficou lá (triângulo errado etc.)
            vale = self.w.on_vitima(bola, nome) if self.w.on_vitima else True
            if vale:
                bola['estado'] = 'resgatada'
                bola['triangulo'] = nome
                bola['t'] = t
                bola['pos_final'] = p
                self.space.remove(bola['corpo'], bola['forma'])
            else:
                bola['no_triangulo'] = nome
            return
        bola.pop('no_triangulo', None)

    def coloca_bola(self, bola, pos, vel=(0, 0)):
        """Põe uma bolinha de volta no chão (caiu da garra, LoP...)."""
        X0, Y0, X1, Y1 = self.mapa.interior_zona()
        x = min(max(pos[0], X0 + RAIO_BOLA + 1), X1 - RAIO_BOLA - 1)
        y = min(max(pos[1], Y0 + RAIO_BOLA + 1), Y1 - RAIO_BOLA - 1)
        b = bola['corpo']
        b.position = (x, y)
        b.velocity = vel
        b.angular_velocity = 0
        bola['estado'] = 'chao'
        bola['local'] = None
        bola['lado'] = None
        if b not in self.space.bodies:
            self.space.add(b, bola['forma'])
        else:
            self.space.reindex_shapes_for_body(b)

    def lop(self, dentro_da_area):
        """Regra 5.5.6: vítimas que estavam com o robô ficam onde o robô estava; se o LoP foi na
        saída (com vítimas), elas são espalhadas pela área."""
        if not self.ativa:
            if self.mec:
                self.mec.solta_tudo()
            return
        com_robo = self.mec.solta_tudo() if self.mec else []
        p = self.w.corpo.position
        usados = [tuple(b['corpo'].position) for b in self.bolas_no_chao()]
        for i, bola in enumerate(com_robo):
            if dentro_da_area:
                ang = 2 * math.pi * i / max(1, len(com_robo))
                pos = (p.x + 70 * math.cos(ang), p.y + 70 * math.sin(ang))
            else:
                pos = self._posicao_livre(usados)
            usados.append(pos)
            self.coloca_bola(bola, pos)

    # ------------------------------------------------------------------ geometria para sensores
    def ponto_dentro(self, p):
        if not self.ativa:
            return False
        X0, Y0, X1, Y1 = self.mapa.retangulo_zona()
        return X0 <= p[0] <= X1 and Y0 <= p[1] <= Y1

    def raio_cor(self, p0, ang, altura, alcance=150.0):
        """Primeira coisa que um sensor horizontal (TCS) vê: (distância, cor rgb, fator de reflexo)."""
        if not self.ativa and not (self.mec and self.mec.bola_na_garra()):
            return None
        u = Vec2d(math.cos(ang), math.sin(ang))
        recuo = 15.0       # começa dentro do robô: encostado, o sensor pode estar "dentro" da parede fina
        pi = p0 - u * recuo
        p1 = p0 + u * alcance
        melhor = None
        filtro = pymunk.ShapeFilter(mask=CAT_OBST | CAT_BOLA)
        for q in self.space.segment_query(pi, p1, 0, filtro):
            s = q.shape
            if s is None or getattr(s, 'altura_mm', 1e9) < altura or not hasattr(s, 'cor'):
                continue
            d = max(0.0, (q.point - pi).length - recuo)
            if melhor is None or d < melhor[0]:
                refl = REFLETE_VIVA if getattr(s, 'bola', None) and s.bola['tipo'] == 'viva' else 1.0
                melhor = (d, s.cor, refl)
        return melhor


    # ------------------------------------------------------------------ TCS34725 horizontais
    def tcs(self, idx):
        """Leitura de um TCS34725 apontado para o lado (frente/trás do robô), como fração do
        branco a ~1 cm: [r, g, b, clear]. Só o que fica na altura do sensor é visto."""
        sc = self.tcs_cfg[idx]
        corpo = self.w.corpo
        p0 = corpo.local_to_world((float(sc['x']), float(sc['y'])))
        ang = corpo.angle + math.radians(float(sc.get('angulo', 0)))
        h = float(sc.get('altura', 30))
        amb = float(sc.get('ambiente', 0.03))
        hit = self.raio_cor(p0, ang, h) if self.space is not None else None
        if hit is None:
            rgb = [amb, amb, amb]
        else:
            d, cor, refl = hit
            f = refl / (1.0 + (d / 12.0) ** 2)      # LED do módulo: cai com a distância
            rgb = [amb + f * c / 255.0 for c in cor]
        rgb = [max(0.0, v * (1 + self.rng_tcs.gauss(0, 0.01))) for v in rgb]
        return rgb + [1.1 * sum(rgb) / 3.0]

    # ------------------------------------------------------------------ câmera (stub)
    def _cfg_cam(self):
        c = dict(CAMERA_PADRAO)
        c.update(self.camera_cfg or {})
        return c

    def _visao_livre(self, p0, p1, ignora=None, altura=50.0, margem=0.0):
        """O segmento p0-p1 (no plano, à altura da câmera) não passa por parede/obstáculo/bolinha?"""
        filtro = pymunk.ShapeFilter(mask=CAT_OBST | CAT_BOLA)
        L = (p1 - p0).length
        for q in self.space.segment_query(p0, p1, 0, filtro):
            s = q.shape
            if s is None or s is ignora:
                continue
            if getattr(s, 'tipo_obj', None) == 'bola':
                # uma bolinha mais perto tapa a outra (a câmera fica pouco acima delas)
                if (q.point - p0).length < L - margem - RAIO_BOLA:
                    return False
                continue
            if getattr(s, 'altura_mm', 1e9) >= altura and (q.point - p0).length < L - margem:
                return False
        return True

    def camera(self, tipo):
        """Detecções do stub da câmera. tipo = 'vitimas' ou 'triangulos'."""
        out = self._camera(tipo)
        self.ult_cam[tipo] = (self.w.t, out)
        return out

    def _camera(self, tipo):
        c = self._cfg_cam()
        mec = self.mec
        if self.space is None or (mec and mec.garra_abaixada()):
            return []                       # garra toda abaixada tapa a câmera
        corpo = self.w.corpo
        p0 = corpo.local_to_world((float(c['x']), float(c['y'])))
        ang0 = corpo.angle + math.radians(float(c.get('angulo', 0)))
        h = float(c['altura'])
        meia = math.radians(float(c['fov_graus'])) / 2
        W, H = int(c['largura_px']), int(c['altura_px'])
        f = (W / 2) / math.tan(meia)
        alcance = float(c['alcance_mm'])
        # ponto de vista arredondado: parado, o resultado se mantém; andando, sorteia de novo
        vista = (round(p0.x / 40), round(p0.y / 40), round(math.degrees(ang0) / 8))
        sem = getattr(self, 'base_semente', 0)

        def rel(p):
            d = Vec2d(*p) - p0
            dist = d.length
            a = math.atan2(d.y, d.x) - ang0
            a = (a + math.pi) % (2 * math.pi) - math.pi
            return dist, a

        out = []
        if tipo == 'vitimas':
            if not self.ativa:
                return []
            alvos = [(b['tipo'], b['corpo'].position, b['forma'], ('b', b['id'])) for b in self.bolas_no_chao()]
            alvos += [('falsa', Vec2d(*fz['pos']), None, ('f', fz['id'])) for fz in self.falsas]
            for tipo_b, pos, forma, ident in alvos:
                dist, a = rel(pos)
                if dist > alcance or dist < 60 or abs(a) > meia + math.atan(RAIO_BOLA / max(dist, 1)):
                    continue
                if not self._visao_livre(p0, Vec2d(*pos), forma, h):
                    continue
                if ident[0] == 'f':
                    if _h(sem, 'falsa', ident, vista) >= float(c['falsa_detectada']):
                        continue
                    tipo_d = 'viva'
                else:
                    if _h(sem, 'det', ident, vista) >= float(c['acerto']) or self.rng_cam.random() < 0.02:
                        continue
                    tipo_d = tipo_b
                    if _h(sem, 'classe', ident, vista) < float(c['erro_classe']):
                        tipo_d = 'morta' if tipo_b == 'viva' else 'viva'
                a_m = a + math.radians(self.rng_cam.gauss(0, float(c['ruido_graus'])))
                d_m = dist * (1 + self.rng_cam.gauss(0, float(c['ruido_distancia_pct']) / 100.0))
                if abs(a_m) > meia:
                    continue
                dep = math.atan2(h - RAIO_BOLA, d_m)
                out.append({'tipo': tipo_d, 'angulo': round(math.degrees(a_m), 1), 'distancia': round(d_m),
                            'x': round(W / 2 - f * math.tan(a_m)), 'y': round(H / 2 + f * math.tan(dep)),
                            'raio_px': round(f * RAIO_BOLA / max(d_m, 1), 1),
                            'confianca': round(0.70 + 0.28 * _h(sem, 'conf', ident, vista), 2)})
            out.sort(key=lambda d: d['distancia'])
            return out
        # triângulos: a parede colorida (hipotenusa) vista de frente
        for nome, tri in self.triangulos.items():
            _, a, b = tri
            pts = [Vec2d(*a) + (Vec2d(*b) - Vec2d(*a)) * k for k in (0.08, 0.3, 0.5, 0.7, 0.92)]
            vis = []
            for q in pts:
                dist, an = rel(q)
                if dist <= alcance and abs(an) <= meia and self._visao_livre(p0, q, None, h, margem=8.0):
                    vis.append((dist, an))
            if not vis:
                continue
            if _h(sem, 'tri', nome, vista) >= float(c['acerto_triangulos']):
                continue
            angs = [v[1] for v in vis]
            # centro da parte visível da parede (o que o centróide da mancha de cor daria)
            pv = [q for q, v in zip(pts, [rel(q) for q in pts]) if v in vis]
            cen = Vec2d(sum(q.x for q in pv) / len(pv), sum(q.y for q in pv) / len(pv))
            dc, a_c = rel(cen)
            a_c += math.radians(self.rng_cam.gauss(0, float(c['ruido_graus']) / 2))
            x1, x2 = W / 2 - f * math.tan(max(angs)), W / 2 - f * math.tan(min(angs))
            out.append({'cor': nome, 'angulo': round(math.degrees(a_c), 1),
                        'distancia': round(dc * (1 + self.rng_cam.gauss(0, 0.04))),
                        'x': round((x1 + x2) / 2), 'x_min': round(x1), 'x_max': round(x2),
                        'largura_px': round(x2 - x1)})
        return out


CAMERA_PADRAO = {
    'x': 100, 'y': 0, 'altura': 50, 'angulo': 0, 'fov_graus': 62, 'largura_px': 320, 'altura_px': 240,
    'alcance_mm': 1300, 'acerto': 0.9, 'acerto_triangulos': 0.97, 'erro_classe': 0.03,
    'ruido_graus': 1.0, 'ruido_distancia_pct': 8, 'falsa_detectada': 0.25,
    'fps_vitimas': 4, 'fps_triangulos': 30,
}


# =========================================================================== mecanismo
class Mecanismo:
    """Braço + garra de dois dedos + caçamba de dois lados (um servo inteligente cada)."""

    PARTES = ('braco', 'dedo_esq', 'dedo_dir', 'porta')

    def __init__(self, mundo, area, cfg):
        self.w = mundo
        self.area = area
        self.cfg = cfg
        self.porta_serial = cfg.get('porta_serial', 'SERIAL1')
        self.cfg_servo = cfg.get('servo', {})
        g = cfg.get('garra', {})
        self.x_base = float(g.get('x_base', mundo.L / 2))
        self.comp = float(g.get('comprimento', 60.0))
        self.W = float(g.get('abertura', 60.0)) / 2
        cc = cfg.get('cacamba', {})
        self.cap = int(cc.get('capacidade_lado', 2))
        self.saida_x = float(cc.get('saida_x', -mundo.L / 2))
        self.saida_y = float(cc.get('saida_y', 30.0))
        self.queda = float(cc.get('distancia_queda', 20.0))
        self.altura_saida = float(cc.get('altura_saida', 100.0))
        self.tempo_trava = float(cfg.get('tempo_trava_ms', 1000)) / 1000.0
        self.rng = random.Random(3)
        self.rng_fw = random.Random(4)
        self.dedos = {}
        self.space = None
        self.reset()

    def semear(self, base):
        self.rng = random.Random(base * 7 + 7)
        self.rng_fw = random.Random(base * 7 + 8)

    def reset(self):
        c = self.cfg
        self.servos = {
            'braco': ServoFisico('braco', c['braco'], self.cfg_servo, c['braco']['alto']),
            'dedo_esq': ServoFisico('dedo_esq', c['dedo_esq'], self.cfg_servo, c['dedo_esq']['aberto']),
            'dedo_dir': ServoFisico('dedo_dir', c['dedo_dir'], self.cfg_servo, c['dedo_dir']['aberto']),
            'porta': ServoFisico('porta', c['porta'], self.cfg_servo, c['porta']['fechada']),
        }
        self.firmwares = {}
        self.na_garra = None
        self.cacamba = {'esq': [], 'dir': []}
        self.t_solta = {'esq': -1.0, 'dir': -1.0}
        self.a_ant = self.braco()

    def registra_firmwares(self, fw_placas):
        """Coloca as placas de servo no barramento (mesmo dicionário das placas de motor)."""
        tab = fw_placas.setdefault(self.porta_serial, {})
        self.firmwares = {}
        for nome in self.PARTES:
            idp = int(self.cfg[nome]['id'])
            fw = FirmwareServo(self.w, self.servos[nome], idp, tab, self.tempo_trava, self.rng_fw)
            tab[idp] = fw
            self.firmwares[nome] = fw

    def construir(self, space):
        self.space = space
        corpo = self.w.corpo
        self.dedos = {}
        for lado in ('esq', 'dir'):
            s = pymunk.Segment(corpo, (0, 0), (1, 0), 3.0)
            s.friction = 0.5
            s.garra = True
            s.filter = pymunk.ShapeFilter(categories=CAT_GARRA, mask=0)
            space.add(s)
            self.dedos[lado] = s
        self._atualiza_dedos()

    # ------------------------------------------------------------------ estado em frações
    def _fracao(self, nome, a_key, b_key):
        c = self.cfg[nome]
        a, b = float(c[a_key]), float(c[b_key])
        return (self.servos[nome].pot - a) / (b - a) if b != a else 0.0

    def braco(self):
        """0 = garra no chão, 1 = toda levantada."""
        return self._fracao('braco', 'baixo', 'alto')

    def fechamento(self, lado):
        """0 = dedo aberto, 1 = fechado (encostando no outro)."""
        return self._fracao('dedo_' + lado, 'aberto', 'fechado')

    def porta(self):
        """-1 = soltando o lado esquerdo, 0 = fechada, +1 = soltando o direito."""
        c = self.cfg['porta']
        p = self.servos['porta'].pot
        f, e, d = float(c['fechada']), float(c['solta_esq']), float(c['solta_dir'])
        if (p - f) * (e - f) > 0:
            return -(p - f) / (e - f)
        return (p - f) / (d - f) if d != f else 0.0

    def y_dedo(self, lado):
        c = max(0.0, min(1.0, self.fechamento(lado)))
        y = self.W * (1.0 - c)
        return y if lado == 'esq' else -y

    def bola_na_garra(self):
        return self.na_garra is not None

    def garra_abaixada(self):
        return self.braco() < 0.12

    # ------------------------------------------------------------------ limites mecânicos
    def _pot(self, nome, chave_a, chave_b, frac):
        c = self.cfg[nome]
        a, b = float(c[chave_a]), float(c[chave_b])
        return a + (b - a) * frac

    def _limites(self, nome):
        if nome == 'braco':
            return self._pot('braco', 'baixo', 'alto', 0.0), self._pot('braco', 'baixo', 'alto', 1.06)
        if nome == 'porta':
            c = self.cfg['porta']
            e, d = float(c['solta_esq']), float(c['solta_dir'])
            f = float(c['fechada'])
            return e + 0.08 * (e - f), d + 0.08 * (d - f)
        lado = nome[5:]
        mx = 1.0
        if self.na_garra is not None:
            # bolinha presa: cada dedo para encostado nela
            yb = self.na_garra['local'][1]
            ylim = yb + RAIO_BOLA if lado == 'esq' else -(yb - RAIO_BOLA)
            mx = max(0.0, min(1.0, 1.0 - ylim / self.W))
        elif self._bola_entre_dedos() is not None:
            # o dedo pode fechar até a bolinha ficar espremida contra o outro dedo
            if lado == 'esq':
                ylim = self.y_dedo('dir') + 2 * RAIO_BOLA
            else:
                ylim = -(self.y_dedo('esq') - 2 * RAIO_BOLA)
            mx = max(0.0, min(1.0, 1.0 - ylim / self.W))
        return self._pot(nome, 'aberto', 'fechado', -0.12), self._pot(nome, 'aberto', 'fechado', mx)

    def _bola_entre_dedos(self):
        """(bola, y local) da bolinha entre os dedos (ou a que está presa)."""
        if self.na_garra is not None:
            return self.na_garra, self.na_garra['local'][1]
        if self.braco() > 0.2 or not self.area.ativa:
            return None
        corpo = self.w.corpo
        melhor = None
        for bola in self.area.bolas_no_chao():
            lx, ly = corpo.world_to_local(bola['corpo'].position)
            if self.x_base + 4 <= lx <= self.x_base + self.comp + RAIO_BOLA * 0.4 and \
                    self.y_dedo('dir') - RAIO_BOLA * 0.3 < ly < self.y_dedo('esq') + RAIO_BOLA * 0.3:
                if melhor is None or lx < melhor[2]:
                    melhor = (bola, ly, lx)
        return None if melhor is None else (melhor[0], melhor[1])

    # ------------------------------------------------------------------ passo
    def passo(self, dt, t):
        # os firmwares das placas de servo rodam junto com os das placas de motor (Mundo.passo)
        a0 = self.braco()
        # braço: sem força cai pelo peso, a não ser que esteja todo levantado (trava no fim de curso)
        sb = self.servos['braco']
        lo, hi = self._limites('braco')
        passivo = 0.0
        if sb.pwm == 0 and a0 < 0.95:
            c = self.cfg['braco']
            passivo = -math.copysign(2.0 * abs(float(c['alto']) - float(c['baixo'])),
                                     float(c['alto']) - float(c['baixo']))
        sb.integra(dt, lo, hi, passivo)
        for nome in ('dedo_esq', 'dedo_dir'):
            lo, hi = self._limites(nome)
            self.servos[nome].integra(dt, lo, hi)
        lo, hi = self._limites('porta')
        self.servos['porta'].integra(dt, lo, hi)
        a = self.braco()
        da = (a - a0) / dt if dt > 0 else 0.0
        self._empurra_bola()
        self._atualiza_dedos()
        self._garra(a, da, t)
        self._cacamba(t)

    def _empurra_bola(self):
        """Dedo fechando empurra a bolinha para o meio da garra."""
        if self.na_garra is not None or self.braco() > 0.2:
            return
        r = self._bola_entre_dedos()
        if r is None:
            return
        bola, yb = r
        ye, yd = self.y_dedo('esq'), self.y_dedo('dir')
        novo = min(max(yb, yd + RAIO_BOLA), ye - RAIO_BOLA) if ye - yd >= 2 * RAIO_BOLA else (ye + yd) / 2
        if abs(novo - yb) > 0.05:
            corpo = self.w.corpo
            lx, _ = corpo.world_to_local(bola['corpo'].position)
            bola['corpo'].position = corpo.local_to_world((lx, novo))
            self.area.space.reindex_shapes_for_body(bola['corpo'])

    def _atualiza_dedos(self):
        if not self.dedos:
            return
        baixa = self.braco() < 0.25
        for lado, s in self.dedos.items():
            y = self.y_dedo(lado)
            s.unsafe_set_endpoints((self.x_base + 2, y), (self.x_base + self.comp, y))
            mask = (CAT_BOLA | CAT_OBST) if baixa else 0
            if s.filter.mask != mask:
                s.filter = pymunk.ShapeFilter(categories=CAT_GARRA, mask=mask)

    def _segura_com_forca(self):
        """Os dois dedos estão com o motor ligado? (abrindo também conta: aí quem decide é a
        abertura dos dedos). Sem força a redução escorrega e a bolinha pesada cai."""
        return all(self.servos['dedo_' + lado].pwm != 0 for lado in ('esq', 'dir'))

    def _garra(self, a, da, t):
        area = self.area
        if self.na_garra is None:
            if a < 0.12:
                r = self._bola_entre_dedos()
                if r is not None:
                    bola, yb = r
                    if self.y_dedo('esq') - self.y_dedo('dir') <= 2 * RAIO_BOLA + 1.5:
                        corpo = self.w.corpo
                        lx, ly = corpo.world_to_local(bola['corpo'].position)
                        area.space.remove(bola['corpo'], bola['forma'])
                        bola['estado'] = 'garra'
                        bola['local'] = (lx, ly)
                        self.na_garra = bola
            return
        bola = self.na_garra
        yb = bola['local'][1]
        folga_e = self.y_dedo('esq') - (yb + RAIO_BOLA)
        folga_d = (yb - RAIO_BOLA) - self.y_dedo('dir')
        if folga_e > 5 or folga_d > 5:
            if a >= 0.9:
                # no alto, abrir um dedo joga a bolinha naquele lado da caçamba
                lado = 'esq' if folga_e >= folga_d else 'dir'
                if len(self.cacamba[lado]) < self.cap:
                    self.cacamba[lado].append(bola)
                    bola['estado'] = 'cacamba'
                    bola['lado'] = lado
                    self.na_garra = None
                    return
            self._cai_da_garra(bola, a)
            return
        if a > 0.12 and abs(da) > 0.05 and not self._segura_com_forca():
            self._cai_da_garra(bola, a)        # motor do dedo desligado com o braço se mexendo

    def _cai_da_garra(self, bola, a):
        corpo = self.w.corpo
        x = self.x_base + (self.comp * 0.6 if a < 0.5 else 15.0)
        p = corpo.local_to_world((x, 0))
        v = corpo.velocity + corpo.rotation_vector.rotated(self.rng.uniform(-0.6, 0.6)) * 60
        self.na_garra = None
        self.area.coloca_bola(bola, p, v)

    def _cacamba(self, t):
        d = self.porta()
        for lado, sinal in (('esq', -1), ('dir', 1)):
            if d * sinal < 0.6 or not self.cacamba[lado]:
                continue
            if t - self.t_solta[lado] < 0.2:
                continue
            self.t_solta[lado] = t
            bola = self.cacamba[lado].pop(0)
            self._deposita(bola, lado)

    def _deposita(self, bola, lado):
        """A bolinha cai da caçamba a ~10 cm do chão, um pouco atrás do robô."""
        corpo = self.w.corpo
        y = self.saida_y if lado == 'esq' else -self.saida_y
        p = corpo.local_to_world((self.saida_x - self.queda, y))
        area = self.area
        if not area.ativa:
            bola['estado'] = 'fora'
            return
        destino = (p.x, p.y)
        e = M.ESPESSURA_TRIANGULO
        for tri in area.triangulos.values():
            c, a, b = tri
            dentro = _ponto_no_triangulo(destino, tri)
            dist = _dist_reta(destino, a, b)
            if dist < e / 2 + RAIO_BOLA:
                # caiu em cima da parede do triângulo: rola para um dos lados
                cen = Vec2d((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
                para_c = (Vec2d(*c) - cen).normalized()
                lado_dentro = self.rng.random() < (0.75 if dentro else 0.25)
                q = Vec2d(*destino)
                sinal = 1 if lado_dentro else -1
                # projeta até ficar inteira de um lado da parede
                for _ in range(40):
                    if _dist_reta(tuple(q), a, b) >= e / 2 + RAIO_BOLA + 1 and \
                            _ponto_no_triangulo(tuple(q), tri) == lado_dentro:
                        break
                    q = q + para_c * sinal * 2.0
                destino = tuple(q)
        area.coloca_bola(bola, destino, (0, 0))

    def solta_tudo(self):
        """Tira do robô as bolinhas da garra e da caçamba (LoP)."""
        out = []
        if self.na_garra is not None:
            out.append(self.na_garra)
            self.na_garra = None
        for lado in ('esq', 'dir'):
            out.extend(self.cacamba[lado])
            self.cacamba[lado] = []
        return out

    # ------------------------------------------------------------------ sensores
    def vl53_garra(self, sc, alcance):
        """VL53 da garra: olha para a frente a partir do fundo da garra."""
        if self.na_garra is not None:
            lx = self.na_garra['local'][0]
            return max(0.0, lx - RAIO_BOLA - float(sc.get('x', self.x_base)))
        if not self.garra_abaixada():
            return None
        return 'raio'
