"""Física 2D (pymunk) da RCB Challenge: robôs com rodas mecanum (ou comuns), cubos e plataformas
soltos na pista, e o modelo dos sensores.

Unidades internas: mm, kg, s, rad. Ângulo anti-horário a partir do eixo x da arena.
Referencial do robô: x para frente, y para a esquerda.

Cada robô (classe Robo) tem o próprio corpo, motores, firmwares emulados e sensores; o Mundo tem o
espaço físico, a arena, os objetos e a lista de robôs. Hoje a simulação usa um robô só; a classe
já está separada para entrar o adversário depois.
"""

import math
import random
import threading

import pymunk
from pymunk import Vec2d

from . import arena as A
from . import firmware as FW
from .garra import cria_garras

G = 9810.0  # mm/s²
CAT_ROBO = 0b0001
CAT_CUBO = 0b0010
CAT_PLATAFORMA = 0b0100
CAT_SENSOR = 0b1000
CAT_ALTO = 0b10000          # cubo preso na garra ou em cima da plataforma: só os sensores enxergam
CAT_OBJETOS = CAT_ROBO | CAT_CUBO | CAT_PLATAFORMA

PINOS = {'P1': 259, 'P2': 260, 'P3': 71, 'P4': 234, 'P5': 228, 'P6': 265, 'P7': 266, 'P8': 267}
CANAIS_I2C = {'I2C1': 0, 'I2C2': 1, 'I2C3': 7, 'I2C4': 2, 'I2C5': 3, 'I2C6': 6, 'I2C7': 5, 'I2C8': 4}

# Refletância (r, g, b) da face dos cubos e plataformas para os TCS34725 apontados para o lado
# (fração do branco). Estimadas para PLA/PETG; troque pelas medidas no robô.
REFLETANCIA = {
    'branco': (0.95, 0.95, 0.93), 'preto': (0.05, 0.05, 0.06), 'vermelho': (0.80, 0.13, 0.12),
    'azul': (0.10, 0.22, 0.72), 'verde': (0.12, 0.55, 0.22), 'amarelo': (0.90, 0.80, 0.15),
    'marrom': (0.36, 0.20, 0.10), 'robo': (0.20, 0.20, 0.22),
}

# Mancha que cada ponto do sensor de linha enxerga no chão: disco de 5 mm de raio, 19 amostras (centro,
# 6 a 2,5 mm e 12 a 5 mm). Numa borda entre duas cores a leitura passa por 19 degraus; com a cruz de 5
# pontos de antes pulava de 20% em 20%, e um limiar estreito (o alinhamento na borda verde/amarela da
# equipe Challenger quer o canal R entre 43 e 57) nunca era atingido.
PONTOS_MANCHA = ((0.0, 0.0),) + tuple(
    (round(r * math.cos(math.radians(a)), 3), round(r * math.sin(math.radians(a)), 3))
    for r, n in ((2.5, 6), (5.0, 12)) for a in range(0, 360, 360 // n))

CUBO = A.QUADRADO                  # 50 mm
PLATAFORMA = (50.0, 160.0)         # em x e y quando está no local de descarte
ALTURA_OBJETO = 50.0


def pino_num(p):
    if isinstance(p, int):
        return p
    return PINOS[p]


def sensores_linha(cfg):
    """Sensores de linha Pro1616 do robo.json: "cor_reflexao" é um (na porta serial marcada
    cor_reflexao_v2) ou uma lista, cada um com a sua "porta"."""
    cc = cfg.get('cor_reflexao')
    if cc is None:
        return []
    if isinstance(cc, dict):
        portas = [p for p, t in cfg.get('portas_serial', {}).items() if t == 'cor_reflexao_v2']
        return [dict(cc, porta=cc.get('porta', portas[0] if portas else 'SERIAL6'))]
    return list(cc)


def canal_mux(m):
    if isinstance(m, int):
        return m
    return CANAIS_I2C[m]


# --------------------------------------------------------------------------- motor
FREQ_PID = 40.0     # Hz do PID nos firmwares (TEMPO_PID = 25 ms)


class Motor:
    """Motor DC com encoder. O estado de controle (setpoint em pulsos por período do PID,
    alvo de giro, freio) é mexido pelo firmware emulado em sim/firmware.py."""

    def __init__(self, cfg, padrao, diametro):
        p = dict(padrao)
        p.update(cfg)
        self.cfg = p
        self.nome = p['nome']
        self.tipo = p['controlador']          # 'mariola' ou 'placa'
        self.x = float(p['x'])
        self.y = float(p['y'])
        self.sentido = 1 if p.get('sentido', 1) >= 0 else -1
        # mecanum: ângulo do eixo dos roletes que tocam o chão (visto de cima, graus, anti-horário
        # a partir da frente do robô). None = roda comum.
        self.rolete = math.radians(float(p['rolete'])) if p.get('rolete') is not None else None
        cpr = p.get('contagens_por_volta_' + self.tipo, p.get('contagens_por_volta'))
        if cpr:
            self.cpr = float(cpr)
        else:
            mult = p.get('multiplicador_' + self.tipo, p.get('multiplicador', 1))
            self.cpr = float(p['pulsos_encoder_motor']) * float(p['reducao']) * float(mult)
        cal_medida = p.get('calibracao_' + self.tipo)
        if cal_medida:
            # valor da EEPROM (obtem_calibracao_motores / obter_calibracao) = 80% da
            # velocidade livre em pulsos por 25 ms -> dá a rotação livre real
            self.vlivre = abs(float(cal_medida)) / 0.8 * FREQ_PID
            self.rpm_livre = self.vlivre / self.cpr * 60.0
        else:
            self.rpm_livre = float(p.get('rpm_livre', p.get('rpm_max', 130)))
            self.vlivre = self.rpm_livre / 60.0 * self.cpr      # contagens/s com PWM 100%
        self.tau = float(p['tau_s'])
        self.forca_max = float(p['forca_max_N']) * 1000.0     # kg·mm/s²
        self.diametro = diametro
        # calibração gravada na EEPROM: 80% da velocidade máxima, em pulsos por período do PID
        c = int(abs(cal_medida)) if cal_medida else int(0.8 * self.vlivre / FREQ_PID)
        self.cal = [c, -c]
        self.reset()

    def reset(self):
        """Estado de quando a placa liga (a EEPROM/calibração não muda)."""
        self.modo = 'pid'
        self.setpoint = 0          # pulsos por período do PID
        self.pwm = 0               # -100..100 no modo potência
        self.alvo = None           # contagem absoluta onde o giro por ângulo para
        self.travado = False
        self.desligado = False     # timeout de comunicação: PWM zerado, motor solto
        self.vel = 0.0             # contagens/s
        self.contagem = 0.0
        self.leitura = 0
        self.t_leitura = -1.0

    def mapa(self, v):
        """map() do Arduino com divisão inteira (trunca para zero)."""
        v = int(v)
        if v >= 0:
            return int(v * self.cal[0] / 100)
        return int(v * self.cal[1] / -100)

    def alvo_vel(self):
        if self.desligado:
            return None
        if self.modo == 'pwm':
            return max(-1.0, min(1.0, self.pwm / 100.0)) * self.vlivre
        if self.setpoint == 0:
            return 0.0
        return max(-self.vlivre, min(self.vlivre, self.setpoint * FREQ_PID))

    def atualiza_controle(self, dt):
        t = self.alvo_vel()
        if t is None:
            return
        if t == 0 and self.travado:
            self.vel = 0.0
            return
        k = min(1.0, dt / self.tau)
        self.vel += (t - self.vel) * k

    def livre(self):
        if self.desligado:
            return True
        return self.alvo_vel() == 0 and not self.travado and abs(self.vel) < 0.03 * self.vlivre

    def vel_superficie(self):
        """mm/s da superfície da roda no sentido 'para frente' do robô."""
        return self.vel / self.cpr * math.pi * self.diametro * self.sentido

    def set_vel_superficie(self, v):
        self.vel = v / (math.pi * self.diametro) * self.cpr * self.sentido

    def integra(self, dt):
        self.contagem += self.vel * dt
        if self.alvo is not None and self.modo == 'pid' and self.setpoint != 0:
            if (self.setpoint > 0 and self.contagem >= self.alvo) or \
               (self.setpoint < 0 and self.contagem <= self.alvo):
                self.setpoint = 0
                self.alvo = None
                if self.travado:
                    self.vel = 0.0

    def estado(self):
        if self.desligado:
            return 0
        if self.modo == 'pwm':
            return 0 if self.pwm == 0 else (1 if self.pwm > 0 else 2)
        if self.setpoint == 0:
            return 0
        return 1 if self.setpoint > 0 else 2

    def le_contagem(self, t):
        """Contagem que a placa devolve: com o PID rodando ela só é atualizada a cada 25 ms."""
        if self.modo == 'pid' and self.setpoint != 0 and not self.desligado:
            if t - self.t_leitura >= 1.0 / FREQ_PID:
                self.leitura = int(math.floor(self.contagem))
                self.t_leitura = t
        else:
            self.leitura = int(math.floor(self.contagem))
            self.t_leitura = t
        return self.leitura

    def contagem_int(self):
        return int(math.floor(self.contagem))

    def para(self):
        self.setpoint = 0
        self.pwm = 0
        self.modo = 'pid'
        self.alvo = None
        self.vel = 0.0


# --------------------------------------------------------------------------- objetos
class Objeto:
    """Cubo ou plataforma solto na pista. Fica onde o árbitro pôs (posição nomeada) até alguém
    empurrar; o atrito com a lona faz ele parar."""

    def __init__(self, tipo, cor, pos, massa, mu):
        self.tipo = tipo               # 'cubo' ou 'plataforma'
        self.cor = cor
        self.pos = pos                 # nome da posição inicial (A2, X1', P3...)
        p = A.POSICOES[pos]
        self.x0, self.y0, self.a0 = p['x'], p['y'], 0.0
        self.massa = massa
        self.mu = mu
        self.tam = (CUBO, CUBO) if tipo == 'cubo' else PLATAFORMA
        self.altura = ALTURA_OBJETO
        im = (self.tam[0] ** 2 + self.tam[1] ** 2) / 12.0      # I/m de um retângulo
        self.k_giro = 0.9 / math.sqrt(im)                     # atrito de giro (distância média / (I/m))
        self.corpo = None
        self.forma = None
        # 'livre' (no chão, na física 2D), 'preso' (na garra) ou 'plataforma' (em cima de uma)
        self.estado = 'livre'
        self.z = 0.0               # altura da base (mm)
        self.sobre = None          # plataforma embaixo dele
        self.off = (0.0, 0.0, 0.0)   # posição e ângulo no referencial da plataforma

    def cria(self, space):
        corpo = pymunk.Body(self.massa, pymunk.moment_for_box(self.massa, self.tam))
        corpo.position = (self.x0, self.y0)
        corpo.angle = self.a0
        forma = pymunk.Poly.create_box(corpo, self.tam, radius=0.5)
        forma.friction = 0.4
        forma.elasticity = 0.0
        forma.objeto = self
        space.add(corpo, forma)
        self.corpo, self.forma = corpo, forma
        self.muda_estado('livre')

    def muda_estado(self, estado, z=0.0):
        self.estado = estado
        self.z = z
        if estado == 'livre':
            cat = CAT_CUBO if self.tipo == 'cubo' else CAT_PLATAFORMA
            self.forma.filter = pymunk.ShapeFilter(categories=cat, mask=CAT_OBJETOS | CAT_SENSOR)
            self.sobre = None
        else:
            # fora da física 2D (está no ar), mas os sensores continuam vendo
            self.forma.filter = pymunk.ShapeFilter(categories=CAT_ALTO, mask=CAT_SENSOR)
        self.corpo.velocity = (0, 0)
        self.corpo.angular_velocity = 0
        self.atualiza_altura()

    def atualiza_altura(self):
        self.forma.base_mm = self.z
        self.forma.altura_mm = self.z + self.altura

    def volta(self):
        """O árbitro devolve o objeto para a posição inicial."""
        self.muda_estado('livre')
        self.corpo.position = (self.x0, self.y0)
        self.corpo.angle = self.a0
        self.corpo.space.reindex_shapes_for_body(self.corpo)

    def deslocamento(self):
        p = self.corpo.position
        return math.hypot(p.x - self.x0, p.y - self.y0)

    def cantos(self):
        hx, hy = self.tam[0] / 2, self.tam[1] / 2
        return [self.corpo.local_to_world(p) for p in ((hx, hy), (hx, -hy), (-hx, -hy), (-hx, hy))]


# --------------------------------------------------------------------------- robô
class Robo:
    def __init__(self, mundo, cfg, lado='esq', indice=0):
        self.mundo = mundo
        self.cfg = cfg
        self.lado = lado
        self.indice = indice
        self.corpo = None
        self.forma = None
        g = cfg['geometria']
        self.L = float(g['comprimento'])
        self.W = float(g['largura'])
        self.altura = float(g.get('altura', 120))
        self.massa = float(g['massa_kg'])
        r = cfg['rodas']
        self.diametro = float(r['diametro'])
        self.largura_roda = float(r.get('largura', 25))
        self.mu = float(r['atrito'])
        self.mu_lat = float(r.get('atrito_lateral', r['atrito']))
        self.mu_rolete = float(r.get('atrito_rolete', 0.06))
        self.ef_lateral = max(0.3, min(1.0, float(r.get('eficiencia_lateral', 0.9))))
        self.motores = [Motor(mc, cfg['motor_padrao'], self.diametro) for mc in cfg['motores']]
        self.garras = cria_garras(self, cfg)
        self.linhas = sensores_linha(cfg)
        self.mecanum = any(m.rolete is not None for m in self.motores)
        self.por_mariola = {}
        self.por_placa = {}
        for m in self.motores:
            if m.cfg['controlador'] == 'mariola':
                self.por_mariola[int(m.cfg['canal'])] = m
            else:
                self.por_placa[(m.cfg['porta'], int(m.cfg['id']))] = m
        self.ordem = 0
        self.semear(0)
        self.reset()

    @property
    def t(self):
        return self.mundo.t

    @property
    def garra(self):
        """A primeira garra (ou None)."""
        return self.garras[0] if self.garras else None

    def garra_por_nome(self, nome):
        for g in self.garras:
            if g.nome == nome:
                return g
        raise KeyError(f'garra "{nome}" não existe no robo.json')

    def semear(self, base):
        """Um gerador de ruído para cada sensor: ler um sensor a mais não muda o ruído dos outros
        (mesmo resultado em qualquer velocidade)."""
        b = base * 13 + self.indice * 101
        self.rng_vl53 = random.Random(b + 1)
        self.rng_giro = random.Random(b + 2)
        # um por sensor de linha: cada um é lido por uma thread da lib, em qualquer ordem
        self.rng_cor = [random.Random(b + 3 + 1000 * i) for i in range(max(1, len(self.linhas)))]
        self.rng_tcs = random.Random(b + 4)

    def reset(self):
        """Robô ligado de novo: firmwares, motores e estado dos periféricos."""
        self.fw_mariola = FW.FirmwareMariola(self)
        self.fw_placas = {}       # porta -> {id: FirmwarePlaca}
        for (porta, idp), m in self.por_placa.items():
            self.fw_placas.setdefault(porta, {})[idp] = FW.FirmwarePlaca(self, m, idp)
        for m in self.motores:
            m.reset()
        self.cor_cache = {}       # firmware do sensor de cor lê a 50 Hz (um por sensor de linha)
        self.cor_t = {}
        self.cor_pedido = {}
        self.yaw_ref = self.corpo.angle if self.corpo is not None else 0.0
        self.deriva = 0.0
        self.leds = [(0, 0, 0)] * 10
        self.servos = {}
        self.gpio_saida = {}
        self.botoes_gui = set()    # pinos "apertados" pela interface
        self.teclas_teclado = set()
        self.teclado_leds = 0x0F   # bits dos 4 LEDs (ao ligar, todos em 1 = acesos)
        self.oled = None           # imagem da tela OLED (1 bit por pixel) ou None = apagada
        self.oled_tam = (128, 64)
        self.raios = {}            # nome -> (p0, p1, dist, t)
        self.debug = {'pose': None, 'texto': '', 'marcas': []}
        for g in self.garras:
            g.reset()

    # ---------------------------------------------------------------- corpo
    def cria(self, space, pose):
        corpo = pymunk.Body(self.massa, pymunk.moment_for_box(self.massa, (self.L, self.W)))
        forma = pymunk.Poly.create_box(corpo, (self.L, self.W), radius=1.5)
        forma.friction = 0.4
        forma.elasticity = 0.0
        forma.filter = pymunk.ShapeFilter(categories=CAT_ROBO, mask=CAT_OBJETOS | CAT_SENSOR)
        forma.altura_mm = self.altura
        forma.objeto = None
        forma.robo = self
        space.add(corpo, forma)
        self.sensores_pc = {}
        pc = self.cfg.get('para_choque')
        if pc:
            curso = float(pc.get('curso_mm', 2.0))
            for lado in ('esquerdo', 'direito'):
                c = pc.get(lado)
                if not c:
                    continue
                x = self.L / 2 + curso / 2
                s = pymunk.Segment(corpo, (x, c['y_min']), (x, c['y_max']), curso / 2 + 0.5)
                s.sensor = True
                s.filter = pymunk.ShapeFilter(categories=CAT_SENSOR, mask=CAT_OBJETOS)
                space.add(s)
                self.sensores_pc[pino_num(c['pino'])] = s
        self.corpo, self.forma = corpo, forma
        for g in self.garras:
            g.cria(space, corpo, forma.filter)
        self.posicionar(*pose)

    def posicionar(self, x, y, ang):
        self.corpo.position = (x, y)
        self.corpo.angle = ang
        self.corpo.velocity = (0, 0)
        self.corpo.angular_velocity = 0
        if self.corpo.space is not None:
            self.corpo.space.reindex_shapes_for_body(self.corpo)
        for m in self.motores:
            m.vel = 0.0

    def pose(self):
        p = self.corpo.position
        return p.x, p.y, self.corpo.angle

    def velocidade(self):
        return self.corpo.velocity.length, abs(self.corpo.angular_velocity)

    def para_tudo(self):
        for m in self.motores:
            m.para()
        self.leds = [(0, 0, 0)] * 10

    def contorno(self):
        b = self.corpo
        hl, hw = self.L / 2, self.W / 2
        return [b.local_to_world(p) for p in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))]

    def tocando(self):
        """Formas (cubos, plataformas, outro robô) encostadas no robô agora."""
        res = []
        self.corpo.each_arbiter(lambda arb: res.extend(s for s in arb.shapes if s.body is not self.corpo))
        return res

    # ---------------------------------------------------------------- rodas
    def rodas(self, dt, iteracoes=4):
        """Força de cada roda no chão (impulsos sequenciais, com o total de cada roda limitado
        pelo atrito e pela força do motor).

        Roda comum: tração na direção da roda e trava de lado (até o atrito lateral).
        Roda mecanum: os roletes giram soltos, então a roda só empurra o chão na direção
        perpendicular ao eixo dos roletes (d). A velocidade da superfície da roda (frente) vira
        a condição v·d = w·(f·d); ao longo dos roletes sobra só o atrito de rolamento deles."""
        b = self.corpo
        th = b.angle
        f = Vec2d(math.cos(th), math.sin(th))
        lat = Vec2d(-math.sin(th), math.cos(th))
        n = len(self.motores)
        N = self.massa * G / n
        invm = 1.0 / self.massa
        invI = 1.0 / b.moment
        rest = []     # [motor, ponto, direção, meff, alvo, limite, acumulado, f·d, motor limita?]
        soltas = []   # (motor, ponto, d, f·d) das rodas sem tração
        self.ordem = (self.ordem + 1) % n
        for k in range(n):
            mot = self.motores[(k + self.ordem) % n]
            p = b.local_to_world((mot.x, mot.y))
            r = p - b.position
            if mot.rolete is not None:
                e = Vec2d(math.cos(th + mot.rolete), math.sin(th + mot.rolete))   # eixo dos roletes
                d = e.perpendicular()
                lim_lado = self.mu_rolete * N * dt
                # perda de lado: a parte lateral (do robô) da velocidade "conta mais" para a roda,
                # então andando de lado o robô faz só eficiencia_lateral do caminho ideal
                dm = f * f.dot(d) + lat * (lat.dot(d) / self.ef_lateral)
            else:
                e, d = lat, f
                lim_lado = self.mu_lat * N * dt
                dm = d
            fd = f.dot(d)
            meff_d = 1.0 / (invm * d.dot(dm) + r.cross(d) * r.cross(dm) * invI)
            meff_e = 1.0 / (invm + r.cross(e) ** 2 * invI)
            rest.append([mot, p, e, e, meff_e, 0.0, lim_lado, 0.0, 1.0, False])
            if mot.livre():
                # roda solta: acompanha o chão, só resistência ao rolamento
                vd = b.velocity_at_world_point(p).dot(dm)
                b.apply_impulse_at_world_point(d * (-vd * meff_d * min(1.0, 3.0 * dt)), p)
                soltas.append((mot, p, dm, fd))
                continue
            jf = self.mu * N * dt
            jm = mot.forca_max * dt / max(abs(fd), 0.2)
            rest.append([mot, p, d, dm, meff_d, mot.vel_superficie() * fd, min(jf, jm), 0.0, fd, jm < jf])
        for _ in range(iteracoes):
            for c in rest:
                mot, p, d, dm, meff, alvo, lim, acc = c[:8]
                v = b.velocity_at_world_point(p).dot(dm)
                novo = max(-lim, min(lim, acc + (alvo - v) * meff))
                if novo != acc:
                    b.apply_impulse_at_world_point(d * (novo - acc), p)
                    c[7] = novo
        # roda solta acompanha o chão; motor que afogou (força no limite dele) também: o encoder
        # conta o que a roda andou de verdade. Roda que patina (limite do atrito) segue girando.
        for mot, p, dm, fd in soltas:
            mot.set_vel_superficie(b.velocity_at_world_point(p).dot(dm) / fd)
        for mot, p, d, dm, meff, alvo, lim, acc, fd, motor_limita in rest:
            if motor_limita and abs(acc) >= lim - 1e-9:
                mot.set_vel_superficie(b.velocity_at_world_point(p).dot(dm) / fd)

    def integra(self, dt):
        for m in self.motores:
            m.integra(dt)
        self.fw_mariola.passo(self.t)
        for fws in self.fw_placas.values():
            for fw in fws.values():
                fw.passo(self.t)
        self.deriva += float(self.cfg['giroscopio']['deriva_graus_min']) / 60.0 * dt

    # ---------------------------------------------------------------- sensores
    def _raio(self, p0, ang, alcance, altura, ignora_corpo=True):
        """Primeira forma atingida por um raio horizontal na altura 'altura' (mm do chão).
        Objetos mais baixos que o sensor só aparecem quando já estão longe o bastante para
        entrar no cone (6° abaixo da horizontal). Devolve (distância, forma, normal) ou None."""
        p1 = p0 + Vec2d(math.cos(ang), math.sin(ang)) * alcance
        filtro = pymunk.ShapeFilter(categories=CAT_SENSOR, mask=CAT_OBJETOS | CAT_ALTO)
        melhor = None
        cone = math.tan(math.radians(6))
        for q in self.mundo.space.segment_query(p0, p1, 0, filtro):
            s = q.shape
            if s is None or (ignora_corpo and s.body is self.corpo) or s.sensor or getattr(s, 'dedo', False):
                continue
            d = (q.point - p0).length
            if getattr(s, 'altura_mm', 1e9) < altura - d * cone:
                continue                     # mais baixo que o feixe
            if getattr(s, 'base_mm', 0.0) > altura + d * cone:
                continue                     # passa por baixo (cubo no alto da garra ou na plataforma)
            if melhor is None or d < melhor[0]:
                melhor = (d, s, q.normal)
        return melhor

    def vl53(self, idx):
        """Distância em mm (int) do VL53 de índice idx na lista de configuração."""
        sc = self.cfg['vl53'][idx]
        pr = self.cfg['vl53_params']
        b = self.corpo
        p0 = b.local_to_world((sc['x'], sc['y']))
        a0 = b.angle + math.radians(sc['angulo'])
        alcance = float(pr['alcance_mm'])
        cone = math.radians(float(pr['cone_graus']))
        h = float(sc.get('altura', 40))
        melhor = None
        # raios no cone; os da borda do campo de visão só "enxergam" alvos mais perto
        # (o sinal que volta da borda do cone é fraco)
        for k, alc in ((-0.5, 0.35), (-0.25, 0.7), (0.0, 1.0), (0.25, 0.7), (0.5, 0.35)):
            a = a0 + k * cone
            q = self._raio(p0, a, alcance + 200, h)
            if q is None:
                continue
            d, _, normal = q
            if k != 0 and d > alc * alcance:
                continue
            if k != 0:
                # retorno de superfície muito rasante é fraco: ignora
                u = Vec2d(math.cos(a), math.sin(a))
                if abs(u.dot(normal)) < math.cos(math.radians(72)):
                    continue
            if melhor is None or d < melhor:
                melhor = d
        fim = p0 + Vec2d(math.cos(a0), math.sin(a0)) * min(melhor or alcance, alcance)
        self.raios[sc['nome']] = (p0, fim, melhor, self.t)
        if melhor is None or melhor > alcance:
            return int(pr['fora_alcance'])
        d = melhor + float(pr.get('offset_mm', 0))
        d += self.rng_vl53.gauss(0, float(pr['ruido_mm']) + melhor * float(pr['ruido_percentual']) / 100.0)
        return max(0, int(round(d)))

    def vl53_por_canal(self, canal):
        for i, sc in enumerate(self.cfg['vl53']):
            if canal_mux(sc['mux']) == canal:
                return i
        return None

    def tcs(self, idx):
        """TCS34725 (lib tcs34725.py) apontado para o lado, como na Line: fração do branco a ~1 cm,
        [r, g, b, clear]. Lê a face do que estiver na frente dele, na altura dele."""
        sc = self.cfg['tcs_i2c'][idx]
        b = self.corpo
        lx, ly, la, h = self.pose_tcs(sc)
        p0 = b.local_to_world((lx, ly))
        ang = b.angle + la
        amb = float(sc.get('ambiente', 0.03))
        ganho = float(sc.get('ganho', 1.0))
        tabela = dict(REFLETANCIA, **self.cfg.get('refletancia', {}))    # o robo.json pode trocar
        hit = self._raio(p0, ang, 150.0, h)
        if hit is None:
            rgb = [amb, amb, amb]
        else:
            d, s, _ = hit
            obj = getattr(s, 'objeto', None)
            refl = tabela.get(obj.cor if obj is not None else 'robo', tabela['robo'])
            f = 1.0 / (1.0 + (d / 12.0) ** 2)      # LED do módulo: cai com a distância
            rgb = [amb + ganho * f * c for c in refl]
        rgb = [max(0.0, v * (1 + self.rng_tcs.gauss(0, 0.01))) for v in rgb]
        return rgb + [1.1 * sum(rgb) / 3.0]

    def pose_tcs(self, sc):
        """(x, y, ângulo em rad, altura) do TCS no referencial do robô. Com "garra": o sensor vai
        na cabeça daquela garra e sobe e desce com ela."""
        if sc.get('garra'):
            return self.garra_por_nome(sc['garra']).ponto_sensor(sc)
        return (float(sc['x']), float(sc['y']), math.radians(float(sc.get('angulo', 0))),
                float(sc.get('altura', 25)))

    def tcs_por_canal(self, canal):
        for i, sc in enumerate(self.cfg.get('tcs_i2c', [])):
            if canal_mux(sc['mux']) == canal:
                return i
        return None

    def giro_reset_z(self):
        self.yaw_ref = self.corpo.angle
        self.deriva = 0.0

    def giro(self):
        gc = self.cfg['giroscopio']
        ruido = float(gc['ruido_graus'])
        z = math.degrees(self.corpo.angle - self.yaw_ref) + self.deriva + self.rng_giro.gauss(0, ruido)
        if gc.get('z_horario_positivo'):
            z = -z
        if not gc.get('z_continuo', True):
            z = (z + 180.0) % 360.0 - 180.0
        x = self.rng_giro.gauss(0, ruido)       # pista plana: inclinação é só ruído
        y = self.rng_giro.gauss(0, ruido)
        esc = float(gc['escala'])
        return [int(round(x * esc)), int(round(y * esc)), int(round(z * esc))]

    def _amostra_piso(self, lx, ly):
        b = self.corpo
        cores = self.cfg['cores_piso']
        acc = [0.0, 0.0, 0.0, 0.0, 0.0]
        pts = PONTOS_MANCHA
        for dx, dy in pts:
            p = b.local_to_world((lx + dx, ly + dy))
            c = cores.get(A.piso(p.x, p.y), cores['branco'])
            for k in range(4):
                acc[k] += c['rgbc'][k]
            acc[4] += c['ir']
        return [a / len(pts) for a in acc]

    def linha_da_porta(self, porta=None):
        """Índice do sensor de linha ligado na porta serial (None = o primeiro)."""
        for i, cc in enumerate(self.linhas):
            if porta is None or cc['porta'] == porta:
                return i
        raise KeyError(f'nenhum sensor de linha na porta {porta}')

    def cor_firmware(self, porta=None):
        """O sensor de cor atualiza a ~50 Hz e devolve o último valor lido. Se ficar 30 s sem
        pedido ele para de ler: o primeiro pedido depois disso devolve valores velhos."""
        i = self.linha_da_porta(porta)
        ocioso = self.t - self.cor_pedido.get(i, 0.0)
        self.cor_pedido[i] = self.t
        if i not in self.cor_cache or (ocioso < 30.0 and self.t - self.cor_t[i] >= 0.02):
            self.cor_cache[i] = self.cor_bytes(i)
            self.cor_t[i] = self.t
        return list(self.cor_cache[i])

    def cor_bytes(self, i=0):
        cc = self.linhas[i]
        rng = self.rng_cor[i]
        ruido = float(cc.get('ruido', 3))
        out = []
        for s in cc['ir']:
            v = self._amostra_piso(s['x'], s['y'])[4]
            out.append(v + rng.gauss(0, ruido))
        for s in cc['tcs']:
            v = self._amostra_piso(s['x'], s['y'])[:4]
            out.extend(x + rng.gauss(0, ruido) for x in v)
        return [max(0, min(255, int(round(x)))) for x in out]

    def para_choque(self, pino):
        s = self.sensores_pc.get(pino)
        if s is None:
            return False
        for info in self.mundo.space.shape_query(s):
            if info.shape is not None and info.shape.body is not self.corpo and not info.shape.sensor:
                return True
        return False

    def gpio_nivel(self, pino):
        """Nível lógico de um pino de entrada (1 = ALTO/ACTIVE, 0 = BAIXO/INACTIVE)."""
        if pino in self.gpio_saida:
            return self.gpio_saida[pino]
        apertado = pino in self.botoes_gui
        if pino in self.sensores_pc:
            apertado = apertado or self.para_choque(pino)
        return 0 if apertado else 1


# --------------------------------------------------------------------------- mundo
class Mundo:
    DT = 1.0 / 240.0

    def __init__(self, cenario, cfg, semente=None):
        self.lock = threading.RLock()
        self.cenario = cenario
        self.semente = semente
        self.t = 0.0
        self.space = None
        self.objetos = []
        self.robos = [Robo(self, cfg, 'esq', 0)]
        self.semear(semente)
        self.construir()

    @property
    def robo(self):
        return self.robos[0]

    @property
    def cfg(self):
        return self.robo.cfg

    def semear(self, semente=None):
        base = semente if semente is not None else getattr(self, '_base_semente', None)
        if base is None:
            base = random.randrange(1 << 30)    # sem semente: sorteia uma e repete nas rodadas
        self._base_semente = base
        self.rng = random.Random(base)          # massa dos cubos e plataformas
        for r in self.robos:
            r.semear(base)

    def pose_inicio(self, robo):
        x, y, a = self.cenario.inicio[robo.lado]
        return x, y, math.radians(a)

    # ---------------------------------------------------------------- construção
    def construir(self, manter_robos=False):
        """(Re)cria o espaço físico: objetos do cenário nas posições iniciais e os robôs no início
        (ou onde estavam, com manter_robos)."""
        poses = [r.pose() for r in self.robos] if manter_robos and self.robos[0].corpo else None
        sp = pymunk.Space()
        sp.iterations = 25
        sp.gravity = (0, 0)
        self.space = sp
        self.objetos = []
        self.eventos_garra = []    # (tipo, robo, objeto, plataforma) para o juiz: 'preso', 'plataforma', 'chao'
        rng = self.rng
        for pos, cor in sorted(self.cenario.plataformas.items()):
            o = Objeto('plataforma', cor, pos, rng.uniform(0.40, 0.50), 0.45)
            o.cria(sp)
            self.objetos.append(o)
        for pos, cor in sorted(self.cenario.cubos.items()):
            o = Objeto('cubo', cor, pos, rng.uniform(0.025, 0.040), 0.35)
            o.cria(sp)
            self.objetos.append(o)
        for i, r in enumerate(self.robos):
            if poses:
                x, y, a = poses[i]
            else:
                x, y, a = self.pose_inicio(r)
            r.cria(sp, (x, y, a))

    def reset_rodada(self):
        """Rodada nova: tudo como ao ligar (mesma semente + mesmo programa = mesma rodada)."""
        self.semear(self.semente)
        self.construir()
        for r in self.robos:
            r.reset()

    def troca_cenario(self, cenario):
        self.cenario = cenario
        self.reset_rodada()

    # ---------------------------------------------------------------- passo
    def _atrito_objetos(self, dt):
        """Atrito dos objetos com a lona (o pymunk é 2D, não tem chão)."""
        for o in self.objetos:
            if o.estado != 'livre':
                continue
            b = o.corpo
            v = b.velocity
            sp = v.length
            dv = o.mu * G * dt
            if sp > 0.0:
                b.velocity = (0, 0) if sp <= dv else v * (1.0 - dv / sp)
            w = b.angular_velocity
            dw = o.mu * G * dt * o.k_giro
            if w != 0.0:
                b.angular_velocity = 0.0 if abs(w) <= dw else w - math.copysign(dw, w)

    def passo(self, dt=None):
        dt = dt or self.DT
        for r in self.robos:
            for m in r.motores:
                m.atualiza_controle(dt)
            for g in r.garras:
                g.passo()
            r.rodas(dt)
        self._atrito_objetos(dt)
        self.space.step(dt)
        for r in self.robos:
            for g in r.garras:
                g.segue()
            r.integra(dt)
        self._segue_plataformas()
        self.t += dt

    # ---------------------------------------------------------------- garra
    def prende(self, robo, o, garra):
        o.muda_estado('preso', max(0.0, garra.altura()))
        self.eventos_garra.append(('preso', robo, o, None))

    def solta(self, robo, o, pos, altura):
        """A garra abriu com o cubo: em cima da plataforma (garra alta e o centro do cubo sobre ela)
        ou no chão."""
        plat = None
        if altura >= ALTURA_OBJETO - 5.0:
            for p in self.objetos:
                if p.tipo == 'plataforma' and p.forma.point_query(pos).distance <= 0:
                    plat = p
                    break
        b = o.corpo
        b.position = pos
        if plat is not None:
            lp = plat.corpo.world_to_local(pos)
            o.off = (lp.x, lp.y, b.angle - plat.corpo.angle)
            o.muda_estado('plataforma', ALTURA_OBJETO)
            o.sobre = plat
            self.eventos_garra.append(('plataforma', robo, o, plat))
        else:
            o.muda_estado('livre')
            self.eventos_garra.append(('chao', robo, o, None))
        self.space.reindex_shapes_for_body(b)

    def _segue_plataformas(self):
        for o in self.objetos:
            if o.estado != 'plataforma' or o.sobre is None:
                continue
            p = o.sobre.corpo
            b = o.corpo
            b.position = p.local_to_world(o.off[:2])
            b.angle = p.angle + o.off[2]
            self.space.reindex_shapes_for_body(b)

    def cubos_na_plataforma(self, plat):
        return [o for o in self.objetos if o.estado == 'plataforma' and o.sobre is plat]

    def objeto_em(self, x, y):
        for o in self.objetos:
            if o.forma.point_query((x, y)).distance <= 0:
                return o
        return None
