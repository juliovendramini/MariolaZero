"""Física 2,5D do robô (pymunk no plano + altura do piso) e modelo dos sensores.

Unidades internas: mm, kg, s, rad. Ângulo do robô anti-horário a partir do leste.
Referencial do robô: x para frente, y para a esquerda, origem no centro da caixa do robô.

O plano é 2D (pymunk). A altura vem do mapa: rampas e gangorra mudam a altura do piso, o
que gera a força da gravidade na descida/subida, a inclinação do giroscópio e a distância
entre o sensor de linha e o chão (crista de rampa = sensor mais longe do piso).
"""

import math
import random
import threading

import numpy as np
import pymunk
from pymunk import Vec2d

from . import firmware as FW
from . import ladrilhos as LT
from . import resgate as RG
from .ladrilhos import TAM

G = 9810.0  # mm/s²
CAT_OBST = 0b0001
CAT_ROBO = 0b0010
CAT_SENSOR = 0b0100
CAT_PILAR = 0b1000
CAT_BOLA = RG.CAT_BOLA

PINOS = {'P1': 259, 'P2': 260, 'P3': 71, 'P4': 234, 'P5': 228, 'P6': 265, 'P7': 266, 'P8': 267}
CANAIS_I2C = {'I2C1': 0, 'I2C2': 1, 'I2C3': 7, 'I2C4': 2, 'I2C5': 3, 'I2C6': 6, 'I2C7': 5, 'I2C8': 4}


def pino_num(p):
    if isinstance(p, int):
        return p
    return PINOS[p]


def canal_mux(m):
    if isinstance(m, int):
        return m
    return CANAIS_I2C[m]


# --------------------------------------------------------------------------- motor
FREQ_PID = 40.0     # Hz do PID nos firmwares (TEMPO_PID = 25 ms)


class Motor:
    """Motor DC com encoder. O estado de controle (setpoint em pulsos por período do PID,
    alvo de giro, freio) é mexido pelo firmware emulado em sim/firmware.py.

    `contatos`: pontos (x, y) do robô onde esse motor empurra o chão. Roda = 1 ponto;
    esteira = vários pontos ao longo dela, todos com a mesma velocidade."""

    def __init__(self, cfg, padrao, diametro):
        p = dict(padrao)
        p.update(cfg)
        self.cfg = p
        self.nome = p['nome']
        self.tipo = p['controlador']          # 'mariola' ou 'placa'
        self.x = float(p['x'])
        self.y = float(p['y'])
        self.contatos = [(float(a), float(b)) for a, b in p.get('contatos', [(self.x, self.y)])]
        self.sentido = 1 if p.get('sentido', 1) >= 0 else -1
        cpr = p.get('contagens_por_volta_' + self.tipo, p.get('contagens_por_volta'))
        if cpr:
            self.cpr = float(cpr)
        else:
            mult = p.get('multiplicador_' + self.tipo, p.get('multiplicador', 1))
            self.cpr = float(p['pulsos_encoder_motor']) * float(p['reducao']) * float(mult)
        cal_medida = p.get('calibracao_' + self.tipo)
        if cal_medida:
            self.vlivre = abs(float(cal_medida)) / 0.8 * FREQ_PID
            self.rpm_livre = self.vlivre / self.cpr * 60.0
        else:
            self.rpm_livre = float(p.get('rpm_livre', p.get('rpm_max', 130)))
            self.vlivre = self.rpm_livre / 60.0 * self.cpr      # contagens/s com PWM 100%
        self.tau = float(p['tau_s'])
        self.forca_max = float(p['forca_max_N']) * 1000.0     # kg·mm/s²
        self.diametro = diametro
        c = int(abs(cal_medida)) if cal_medida else int(0.8 * self.vlivre / FREQ_PID)
        self.cal = [c, -c]
        self.reset()

    def reset(self):
        self.modo = 'pid'
        self.setpoint = 0
        self.pwm = 0
        self.alvo = None
        self.travado = False
        self.desligado = False
        self.vel = 0.0
        self.contagem = 0.0
        self.leitura = 0
        self.t_leitura = -1.0

    def mapa(self, v):
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


# --------------------------------------------------------------------------- sensor de linha
# Corrente relativa do ITR8307 x distância ao papel branco (forma aproximada da curva do
# datasheet: pico perto de 1 mm, caindo mais ou menos com 1/d² depois). [mm, relativo]
CURVA_ITR8307 = [[0, 0.0], [0.5, 0.7], [1, 1.0], [2, 0.85], [3, 0.6], [4, 0.42], [5, 0.3], [6, 0.22],
                 [8, 0.13], [10, 0.085], [12, 0.06], [15, 0.04], [20, 0.022], [30, 0.01], [60, 0.0]]


def _disco(raio):
    """Deslocamentos (dx, dy) de uma grade de 1 mm dentro de um disco."""
    r = max(0.5, float(raio))
    n = int(math.ceil(r))
    pts = [(dx, dy) for dx in range(-n, n + 1) for dy in range(-n, n + 1) if dx * dx + dy * dy <= r * r]
    return np.array(pts or [(0, 0)], dtype=np.float64)


class SensorLinha:
    """Geometria do sensor de linha/cor Pro1616 (sensorLinhaPro1616).

    * fileira de reflexão: N ITR8307 com passo fixo, agrupados de G em G -> N/G canais
    * fileira de cor: TCS34725 (um por canal de cor)
    Tudo em mm no referencial do robô (x para frente, y para a esquerda).
    """

    def __init__(self, cfg):
        c = cfg['sensor_linha']
        self.cfg = c
        n = int(c.get('n_ir', 12))
        passo = float(c.get('distancia_extremos_ir_mm', 65.0)) / (n - 1)
        self.passo = passo
        y0 = (n - 1) * passo / 2
        # elemento 0 = mais à esquerda (y positivo), como o canal 0 do sensor
        ys = [y0 - i * passo for i in range(n)]
        if c.get('ordem_ir') == 'direita_para_esquerda':
            ys = ys[::-1]
        x_ir = float(c['x_ir'])
        self.ir = [(x_ir, y) for y in ys]
        self.grupo = int(c.get('grupo_ir', 3))
        x_tcs = float(c['x_tcs'])
        ys_t = [float(y) for y in c.get('y_tcs', [20, 0, -20])]
        self.tcs = [(x_tcs, y) for y in ys_t]
        self.disco_ir = _disco(c.get('raio_mancha_ir_mm', 2.0))
        self.disco_tcs = _disco(c.get('raio_mancha_tcs_mm', 4.0))
        self.modo = c.get('modo_grupo', 'media')
        self.ruido = float(c.get('ruido', 2.0))
        self.altura = float(c.get('altura_mm', 5.0))
        # curva de resposta x distância (mm, relativo); a calibração vale na altura_mm
        self.curva_ir = np.array(c.get('curva_ir', CURVA_ITR8307), dtype=float)
        self.curva_tcs = np.array(c.get('curva_tcs', [[d * 2, v] for d, v in CURVA_ITR8307]), dtype=float)
        # pontos da placa do sensor que podem raspar no chão (pontas e meio das fileiras)
        ys_ir = [p[1] for p in self.ir]
        self.raspa = [(x_ir, max(ys_ir)), (x_ir, 0.0), (x_ir, min(ys_ir))] + \
                     [(x_tcs, y) for y in (max(ys_t), min(ys_t))]

    def resposta(self, d, curva):
        """Leitura relativa (1 = na altura normal, onde foi calibrado) com o sensor a d mm do
        piso. Mais longe cai; mais perto sobe até o pico da curva; encostado vai a zero."""
        g0 = np.interp(self.altura, curva[:, 0], curva[:, 1])
        if g0 <= 0:
            return 1.0
        return float(np.interp(max(0.0, d), curva[:, 0], curva[:, 1]) / g0)

    def canais_ir(self):
        """Posição média de cada canal (grupo) de IR."""
        g = self.grupo
        return [(sum(p[0] for p in self.ir[i:i + g]) / g, sum(p[1] for p in self.ir[i:i + g]) / g)
                for i in range(0, len(self.ir), g)]


# --------------------------------------------------------------------------- mundo
class Mundo:
    DT = 1.0 / 240.0

    def __init__(self, mapa, cfg, semente=None):
        self.lock = threading.RLock()
        self.cfg = cfg
        self.semente = semente
        self.semear(semente)
        self.mapa = mapa
        self.cat = mapa.cat
        self.t = 0.0
        self.space = None
        self.corpo = None
        g = cfg['geometria']
        self.L = float(g['comprimento'])
        self.W = float(g['largura'])
        self.massa = float(g['massa_kg'])
        r = cfg['rodas']
        self.diametro = float(r['diametro'])
        self.mu = float(r['atrito'])
        self.mu_lat = float(r['atrito_lateral'])
        self.esteira = cfg.get('tipo_tracao') == 'esteira'
        self.motores = [Motor(mc, cfg['motor_padrao'], self.diametro) for mc in cfg['motores']]
        self.contatos = [(i, cx, cy) for i, m in enumerate(self.motores) for (cx, cy) in m.contatos]
        xs = [c[1] for c in self.contatos]
        ys = [c[2] for c in self.contatos]
        self.eixo_frente, self.eixo_tras = max(xs), min(xs)
        self.lado_esq, self.lado_dir = max(ys), min(ys)
        self.por_mariola = {}
        self.por_placa = {}
        for m in self.motores:
            if m.cfg['controlador'] == 'mariola':
                self.por_mariola[int(m.cfg['canal'])] = m
            else:
                self.por_placa[(m.cfg['porta'], int(m.cfg['id']))] = m
        self.fw_mariola = FW.FirmwareMariola(self)
        self.fw_placas = {}
        for (porta, idp), m in self.por_placa.items():
            self.fw_placas.setdefault(porta, {})[idp] = FW.FirmwarePlaca(self, m, idp)
        self.on_vitima = None        # callback(bola, triangulo) quando uma vítima é resgatada
        self.resgate = RG.AreaResgate(self)
        self.resgate.semear(self._base_semente)
        if self.resgate.mec:
            self.resgate.mec.registra_firmwares(self.fw_placas)
        self.sensor = SensorLinha(cfg)
        self._monta_apoios()
        self._tabela_cores()
        self.cor_cache = None
        self.cor_t = -1.0
        self.cor_pedido = 0.0
        self.ultima_leitura = None   # detalhes da última leitura (para a interface)
        self.ordem = 0
        self.yaw_ref = 0.0
        self.deriva = 0.0
        self.eventos_incl = []
        self.no_ar = [0.0] * len(self.contatos)
        self.pos_ant_contatos = None
        self.detritos = {}
        self.leds = [(0, 0, 0)] * 10
        self.gpio_saida = {}
        self.botoes_gui = set()
        self.teclas_teclado = set()
        self.teclado_leds = 0x0F      # bits dos 4 LEDs (ao ligar, todos em 1 = acesos)
        self.oled = None              # imagem da tela OLED (1 bit por pixel) ou None = apagada
        self.oled_tam = (128, 64)
        self.raios = {}
        self.debug = {'pose': None, 'texto': '', 'marcas': []}
        self.servos = {}
        self.angs = {}               # ângulo atual de cada gangorra (graus)
        self.lad_centro = None
        self.h_centro = 0.0
        self.pitch = 0.0
        self.roll = 0.0
        self.h_robo = 0.0            # altura do plano do robô no centro
        self.suspenso = [False] * len(self.contatos)
        self._coef_eixo = None
        self.fora_da_pista = False
        self.construir()

    def semear(self, semente=None):
        """Um gerador de ruído para cada coisa: a ordem em que as threads do programa leem os
        sensores não muda os números sorteados (mesmo resultado em qualquer velocidade)."""
        base = semente if semente is not None else random.randrange(1 << 30)
        self._base_semente = base
        if getattr(self, 'resgate', None) is not None:
            self.resgate.semear(base)                   # vítimas, câmera, servos
        self.rng = random.Random(base)                  # terreno (solavancos, palitos)
        self.rng_vl53 = random.Random(base * 7 + 1)
        self.rng_giro = random.Random(base * 7 + 2)
        self.rng_cor = random.Random(base * 7 + 3)

    def _rngs(self):
        rs = [self.rng, self.rng_vl53, self.rng_giro, self.rng_cor]
        if getattr(self, 'resgate', None) is not None:
            rs += [self.resgate.rng_cam, self.resgate.rng_tcs]
        return rs

    def estado_ruido(self):
        return [r.getstate() for r in self._rngs()]

    def restaura_ruido(self, estado):
        for r, st in zip(self._rngs(), estado):
            r.setstate(st)

    def _tabela_cores(self):
        cores = self.cfg['cores_piso']
        n = len(LT.MATERIAIS)
        self.ir_mat = np.zeros(n)
        self.rgbc_mat = np.zeros((n, 4))
        for i, nome in enumerate(LT.MATERIAIS):
            c = cores.get(nome) or cores.get('branco')
            self.ir_mat[i] = float(c['ir'])
            self.rgbc_mat[i] = [float(v) for v in c['rgbc']]

    # ---------------------------------------------------------------- construção
    def construir(self):
        """(Re)cria o espaço físico a partir do mapa, mantendo a pose do robô."""
        pose = None
        if self.corpo is not None:
            pose = (self.corpo.position.x, self.corpo.position.y, self.corpo.angle)
        sp = pymunk.Space()
        sp.iterations = 20
        sp.gravity = (0, 0)
        momento = pymunk.moment_for_box(self.massa, (self.L, self.W))
        corpo = pymunk.Body(self.massa, momento)
        forma = pymunk.Poly.create_box(corpo, (self.L, self.W), radius=1.5)
        forma.friction = 0.4
        forma.elasticity = 0.0
        forma.filter = pymunk.ShapeFilter(categories=CAT_ROBO, mask=CAT_OBST | CAT_PILAR | CAT_BOLA)
        sp.add(corpo, forma)
        pc = self.cfg.get('para_choque')
        self.sensores_pc = {}
        if pc:
            curso = float(pc.get('curso_mm', 2.0))
            for lado in ('esquerdo', 'direito'):
                c = pc[lado]
                x = self.L / 2 + curso / 2
                s = pymunk.Segment(corpo, (x, c['y_min']), (x, c['y_max']), curso / 2 + 0.5)
                s.sensor = True
                s.filter = pymunk.ShapeFilter(categories=CAT_SENSOR, mask=CAT_OBST | CAT_PILAR)
                sp.add(s)
                self.sensores_pc[pino_num(c['pino'])] = s
        self.space = sp
        self.corpo = corpo
        self.forma = forma
        self._cria_obstaculos()
        self._cria_pilares()
        self.resgate.construir(sp)
        if pose:
            self.posicionar(*pose)
        else:
            self.vai_para_inicio()
        self.reset_gangorras()
        self._reset_detritos()

    def _cria_obstaculos(self):
        self.obstaculos = []
        m = self.mapa
        for t in m.ladrilhos.values():
            for ob in t.get('obstaculos', []):
                X, Y = m.mundo(t, float(ob['u']), float(ob['v']))
                lw, lc = float(ob.get('larg', 60)), float(ob.get('comp', 60))
                massa = float(ob.get('massa_kg', 1.5))
                if ob.get('fixo'):
                    b = pymunk.Body(body_type=pymunk.Body.STATIC)
                else:
                    b = pymunk.Body(massa, pymunk.moment_for_box(massa, (lw, lc)))
                b.position = (X, Y)
                b.angle = math.radians(float(ob.get('ang', 0)))
                s = pymunk.Poly.create_box(b, (lw, lc), radius=0.5)
                s.friction = 0.5
                s.filter = pymunk.ShapeFilter(categories=CAT_OBST, mask=CAT_ROBO | CAT_SENSOR | CAT_OBST)
                self.space.add(b, s)
                if not ob.get('fixo'):
                    # atrito com o chão (vista de cima)
                    mu = float(ob.get('atrito_chao', 0.6))
                    pj = pymunk.PivotJoint(self.space.static_body, b, (0, 0), (0, 0))
                    pj.max_bias = 0
                    pj.max_force = mu * massa * G
                    gj = pymunk.GearJoint(self.space.static_body, b, 0.0, 1.0)
                    gj.max_bias = 0
                    gj.max_force = mu * massa * G * (lw + lc) / 6
                    self.space.add(pj, gj)
                self.obstaculos.append({'corpo': b, 'forma': s, 'ob': ob, 'lad': m.chave(t),
                                        'h': m.base(t), 'larg': lw, 'comp': lc})

    def _cria_pilares(self):
        """Pilares de 25 x 25 mm nos cantos dos ladrilhos de ponte (célula com dois ladrilhos):
        o robô que passa por baixo pode bater neles."""
        m = self.mapa
        vistos = set()
        self.pilares = []
        for t in m.ladrilhos.values():
            cel = m.celula(t['x'], t['y'])
            if len(cel) < 2 or t is cel[0] or m.eh_gangorra(t):
                continue
            for (u, v) in ((0, 0), (TAM, 0), (0, TAM), (TAM, TAM)):
                X, Y = m.mundo(t, u, v)
                uu, vv = min(max(u, 1), TAM - 1), min(max(v, 1), TAM - 1)
                h = m.elevacao(t, *m.mundo(t, uu, vv))
                if h < 60:
                    continue
                k = (round(X), round(Y))
                if k in vistos:
                    continue
                vistos.add(k)
                dx = 12.5 if u == 0 else -12.5
                dy = 12.5 if v == 0 else -12.5
                s = pymunk.Poly(self.space.static_body, [(X + dx + a, Y + dy + b) for a, b in
                                                         ((-12.5, -12.5), (12.5, -12.5), (12.5, 12.5), (-12.5, 12.5))])
                s.friction = 0.4
                s.filter = pymunk.ShapeFilter(categories=CAT_PILAR, mask=0)
                self.space.add(s)
                self.pilares.append({'forma': s, 'h': h, 'pos': (X + dx, Y + dy)})

    def pose_inicio(self, chave=None, idx_caminho=None):
        """(x, y, ângulo) no centro do ladrilho, virado para a saída do caminho."""
        m = self.mapa
        passos = m.passos()
        if idx_caminho is not None and 0 <= idx_caminho < len(passos):
            p = passos[idx_caminho]
        elif passos:
            p = passos[0]
        else:
            p = None
        k = p['k'] if p else (chave or m.inicio)
        if k is None or k not in m.ladrilhos:
            return m.largura_mm / 2, m.altura_mm / 2, 0.0, None
        t = m.ladrilhos[k]
        saida = (p['saida'] if p else None) or m.inicio_dir or 'N'
        x, y = m.centro(t['x'], t['y'])
        return x, y, math.radians(LT.ANGULO[saida]), t

    def vai_para_inicio(self, idx_caminho=0):
        x, y, a, t = self.pose_inicio(idx_caminho=idx_caminho)
        self.posicionar(x, y, a, t)

    def posicionar(self, x, y, ang, lad=None):
        self.corpo.position = (x, y)
        self.corpo.angle = ang
        self.corpo.velocity = (0, 0)
        self.corpo.angular_velocity = 0
        self.space.reindex_shapes_for_body(self.corpo)
        self.pos_ant_contatos = None
        for m in self.motores:
            m.vel = 0.0
        if lad is not None:
            self.lad_centro = lad
            self.h_centro = self.mapa.elevacao(lad, x, y, self.angs.get(self.mapa.chave(lad)))
        else:
            # escolhe a camada mais alta sob o ponto (arrastar o robô para cima de uma ponte)
            c = self.mapa.celula_de(x, y)
            cand = self.mapa.celula(*c) if c else []
            if self.lad_centro is not None and self.lad_centro in cand:
                t = self.lad_centro
            else:
                t = self.mapa.ladrilho_em(x, y, self.h_centro, self.angs, tolerancia=1e9)
            self.lad_centro = t
            self.h_centro = self.mapa.elevacao(t, x, y, self.angs.get(self.mapa.chave(t))) if t else 0.0
        self.fora_da_pista = self.lad_centro is None
        self._atualiza_plano()

    def pose(self):
        p = self.corpo.position
        return p.x, p.y, self.corpo.angle

    def para_tudo(self):
        for m in self.motores:
            m.para()
        self.leds = [(0, 0, 0)] * 10

    def reset_gangorras(self):
        """Gangorras inclinadas para o lado de quem chega (ponta de entrada embaixo)."""
        m = self.mapa
        self.angs = {}
        for t in m.ladrilhos.values():
            if not m.eh_gangorra(t):
                continue
            k = m.chave(t)
            g = m.graus_gangorra(t)
            entrada = None
            for p in m.passos():
                if p['k'] == k:
                    entrada = p['entrada']
                    break
            eixo = m.eixo_gangorra(t)
            self.angs[k] = -g if entrada == eixo else g

    def gangorra_favoravel(self, idx_caminho):
        """No LoP a gangorra à frente pode ser virada a favor do robô."""
        m = self.mapa
        for p in m.passos()[idx_caminho:]:
            t = m.ladrilhos[p['k']]
            if m.eh_gangorra(t):
                g = m.graus_gangorra(t)
                self.angs[p['k']] = -g if p['entrada'] == m.eixo_gangorra(t) else g

    def _reset_detritos(self):
        self.detritos = {}
        for k, t in self.mapa.ladrilhos.items():
            if t.get('detritos'):
                self.detritos[k] = self.mapa.detritos_iniciais(t)

    def reset_rodada(self):
        self.semear(self.semente)
        self.ordem = 0
        self.no_ar = [0.0] * len(self.contatos)
        self.fw_mariola = FW.FirmwareMariola(self)
        self.fw_placas = {}
        for (porta, idp), m in self.por_placa.items():
            self.fw_placas.setdefault(porta, {})[idp] = FW.FirmwarePlaca(self, m, idp)
        self.cor_cache = None
        self.cor_t = -1.0
        self.cor_pedido = 0.0
        for m in self.motores:
            m.reset()
        self.leds = [(0, 0, 0)] * 10
        self.deriva = 0.0
        self.yaw_ref = self.corpo.angle
        self.eventos_incl = []
        self.debug = {'pose': None, 'texto': '', 'marcas': []}
        for o in self.obstaculos:
            b, ob = o['corpo'], o['ob']
            t = self.mapa.ladrilhos.get(o['lad'])
            if t is None:
                continue
            b.position = self.mapa.mundo(t, float(ob['u']), float(ob['v']))
            b.angle = math.radians(float(ob.get('ang', 0)))
            if b.body_type == pymunk.Body.DYNAMIC:
                b.velocity = (0, 0)
                b.angular_velocity = 0
            self.space.reindex_shapes_for_body(b)
        self.reset_gangorras()
        self._reset_detritos()
        self.resgate.reset()
        if self.resgate.mec:
            self.resgate.mec.registra_firmwares(self.fw_placas)

    # ---------------------------------------------------------------- altura e terreno
    def _lad_ponto(self, X, Y, h_ref=None):
        return self.mapa.ladrilho_em(X, Y, self.h_centro if h_ref is None else h_ref, self.angs)

    def altura_em(self, X, Y, h_ref=None):
        """(altura do piso, ladrilho) no ponto; ladrilho None = fora da pista/abismo."""
        t = self._lad_ponto(X, Y, h_ref)
        if t is None:
            return None, None
        return self.mapa.elevacao(t, X, Y, self.angs.get(self.mapa.chave(t))), t

    def _atualiza_centro(self):
        p = self.corpo.position
        m = self.mapa
        t = None
        if self.lad_centro is not None:
            # continua no mesmo ladrilho enquanto estiver dentro da célula dele
            c = m.celula_de(p.x, p.y)
            if c == (self.lad_centro['x'], self.lad_centro['y']):
                t = self.lad_centro
        if t is None:
            t = m.ladrilho_em(p.x, p.y, self.h_centro, self.angs)
        self.lad_centro = t
        self.fora_da_pista = t is None
        if t is not None:
            self.h_centro = m.elevacao(t, p.x, p.y, self.angs.get(m.chave(t)))

    def _monta_apoios(self):
        """Amostras no chão de cada roda / esteira para achar onde o robô se apoia.

        Roda: o eixo fica na altura máx(chão(s) + sqrt(R² - s²)) ao longo do diâmetro, então
        ela sobe na lombada antes de chegar nela e o palito levanta a roda só um pouco.
        Esteira: a parte de baixo é reta entre as polias. Um ressalto em qualquer ponto
        dela levanta aquele lado inteiro (alavanca longa), e isso dura até a esteira
        toda passar."""
        R = self.diametro / 2
        self.R = R
        loc, lift, xs_el = [], [], []
        self.elementos = []        # (tipo, x, y, índices das amostras)
        larg = float(self.cfg['rodas'].get('largura', 20 if self.esteira else 15))
        laterais = (-larg / 3, 0.0, larg / 3)
        for mot in self.motores:
            if self.esteira:
                xs = [c[0] for c in mot.contatos]
                x0, x1 = min(xs), max(xs)
                pos = np.arange(x0 - R, x1 + R + 0.01, 5.0)
                idx = []
                for x in pos:
                    d = max(0.0, x0 - x, x - x1)
                    lf = R - math.sqrt(max(0.0, R * R - d * d))
                    for dy in laterais:
                        idx.append(len(loc))
                        loc.append((x, mot.y + dy))
                        lift.append(lf)
                        xs_el.append(x)
                self.elementos.append(('esteira', (x0, x1), mot.y, np.array(idx)))
            else:
                for (cx, cy) in mot.contatos:
                    idx = []
                    for sx in np.arange(-R, R + 0.01, 2.5):
                        lf = R - math.sqrt(max(0.0, R * R - sx * sx))
                        for dy in laterais:
                            idx.append(len(loc))
                            loc.append((cx + sx, cy + dy))
                            lift.append(lf)
                            xs_el.append(cx)
                    self.elementos.append(('roda', cx, cy, np.array(idx)))
        self._amostras = np.array(loc)
        self._lift = np.array(lift)
        self._xs_el = np.array(xs_el)
        self._raspa = np.array(self.sensor.raspa)

    def _relevos(self):
        """Lombadas e palitos perto do robô: lista de (x1, y1, x2, y2, altura, meia_largura, tipo)."""
        m = self.mapa
        ter = self.cfg.get('terreno', {})
        h_lb = float(ter.get('lombada_altura_mm', 10.0))
        w_lb = float(ter.get('lombada_largura_mm', 30.0)) / 2
        r_dt = float(ter.get('detrito_diametro_mm', 3.0)) / 2
        p = self.corpo.position
        c = m.celula_de(p.x, p.y)
        if c is None:
            return []
        out = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for t in m.celula(c[0] + dx, c[1] + dy):
                    for seg in m.linhas_lombada(t):
                        out.append((*seg, h_lb, w_lb, 0))
                    for d in self.detritos.get(m.chave(t), []):
                        out.append((d[0], d[1], d[2], d[3], 2 * r_dt, r_dt, 1))
        return out

    def alturas_piso(self, pts, relevos=None):
        """Altura do piso (com lombadas e palitos) em cada ponto (N x 2); nan = sem piso."""
        m = self.mapa
        n = len(pts)
        out = np.full(n, np.nan)
        cx = np.floor(pts[:, 0] / TAM).astype(int)
        cy = m.altura - 1 - np.floor(pts[:, 1] / TAM).astype(int)
        chaves = cx * 10007 + cy
        for ch in np.unique(chaves):
            sel = np.nonzero(chaves == ch)[0]
            if not m.dentro(cx[sel[0]], cy[sel[0]]):
                continue
            px, py = pts[sel].mean(axis=0)
            t = self._lad_ponto(px, py)
            if t is None:
                continue
            a = self.angs.get(m.chave(t))
            e0 = m.elevacao(t, px, py, a)
            gx, gy = m.gradiente(t, a)
            out[sel] = e0 + gx * (pts[sel, 0] - px) + gy * (pts[sel, 1] - py)
        if relevos is None:
            relevos = self._relevos()
        if relevos:
            extra = np.zeros(n)
            for (x1, y1, x2, y2, h, w, tipo) in relevos:
                d = _dist_pts_seg(pts, (x1, y1, x2, y2))
                perto = d < w
                if not perto.any():
                    continue
                if tipo == 0:      # lombada: perfil arredondado (cos²)
                    hh = h * np.cos(np.pi / 2 * d[perto] / w) ** 2
                else:              # palito: cilindro deitado
                    hh = w + np.sqrt(np.maximum(0.0, w * w - d[perto] ** 2))
                extra[perto] = np.maximum(extra[perto], hh)
            out += extra
        return out

    def _mundo(self, loc):
        b = self.corpo
        c, s = math.cos(b.angle), math.sin(b.angle)
        X = b.position.x + loc[:, 0] * c - loc[:, 1] * s
        Y = b.position.y + loc[:, 0] * s + loc[:, 1] * c
        return np.column_stack([X, Y])

    def _atualiza_plano(self):
        """Onde o robô se apoia. Cada roda/esteira dá a altura do eixo sobre o chão (com
        lombadas e palitos). A placa do sensor também pode raspar no chão (ela fica
        'altura_mm' abaixo da base do robô). O plano dos eixos é a face da envoltória
        superior desses pontos sobre o centro do robô."""
        R = self.R
        rel = self._relevos()
        H = self.alturas_piso(self._mundo(self._amostras), rel)
        A = H + R - self._lift                       # altura do eixo que cada amostra pede
        cos_ant = getattr(self, '_cos_incl', 1.0)
        if self.esteira:
            # parte reta da esteira inclinada: o eixo fica R/cos acima do piso (na vertical)
            A = A + R * (1.0 / cos_ant - 1.0)
        A = np.where(np.isnan(A), -np.inf, A)
        pxs, pys, phs = [], [], []
        self._A_contato = []
        for (tipo, ex, ey, idx) in self.elementos:
            a = A[idx]
            if tipo == 'roda':
                v = float(a.max())
                if np.isfinite(v):
                    pxs.append(ex)
                    pys.append(ey)
                    phs.append(v)
                self._A_contato.append(('roda', v))
            else:
                xs = self._amostras[idx, 0]
                # máximo entre as amostras laterais de cada posição ao longo da esteira
                ux, inv = np.unique(np.round(xs, 2), return_inverse=True)
                env = np.full(len(ux), -np.inf)
                np.maximum.at(env, inv, a)
                ok = np.isfinite(env)
                # nas pontas (arco da polia) só o ponto mais alto de cada uma interessa
                x0, x1 = ex
                sel = ok & (ux >= x0 - 0.01) & (ux <= x1 + 0.01)
                for ponta in (ok & (ux < x0 - 0.01), ok & (ux > x1 + 0.01)):
                    if ponta.any():
                        k = np.nonzero(ponta)[0]
                        sel[k[np.argmax(env[k])]] = True
                if sel.any():
                    for (x, h) in _envoltoria_superior(ux[sel], env[sel]):
                        pxs.append(x)
                        pys.append(ey)
                        phs.append(h)
                self._A_contato.append(('esteira', (ux, env)))
        # placa do sensor (raspa se o chão subir mais que a altura dela)
        hs_raspa = self.alturas_piso(self._mundo(self._raspa), rel)
        h0 = self.sensor.altura
        for (lx, ly), h in zip(self._raspa, hs_raspa):
            if np.isfinite(h):
                pxs.append(lx)
                pys.append(ly)
                phs.append(h + (R - h0) / cos_ant)
        coef = None
        if len(phs) >= 3:
            coef = _plano_apoio(np.array(pxs), np.array(pys), np.array(phs))
        if coef is None:
            a0 = max(phs) if phs else self.h_centro + R
            coef = (a0, 0.0, 0.0)
        a0, sx, sy = coef
        cosi = 1.0 / math.sqrt(1.0 + sx * sx + sy * sy)
        self._coef_eixo = coef
        self._cos_incl = cosi
        self.h_robo = a0 - R / cosi
        self.pitch = math.atan(sx)
        self.roll = math.atan(sy)
        # contatos que ficaram no ar (o robô apoiou em outra coisa)
        susp = []
        ie = 0
        for im, mot in enumerate(self.motores):
            for (cx, cy) in mot.contatos:
                plano = a0 + sx * cx + sy * cy
                if self.esteira:
                    # a esteira é uma correia só: se algum trecho dela encosta no chão (ou na
                    # lombada), o motor tem tração em todos os pontos dela
                    ux, env = self._A_contato[im][1]
                    yy = mot.contatos[0][1]
                    plano_ux = a0 + sx * ux + sy * yy
                    a = plano if np.any(plano_ux - env < 2.0) else -np.inf
                else:
                    a = self._A_contato[ie][1]
                    ie += 1
                susp.append(not np.isfinite(a) or plano - a > 2.0)
        self.suspenso = susp

    def altura_eixos(self, lx, ly):
        c = self._coef_eixo
        if c is None:
            return self.h_robo + self.R
        return c[0] + c[1] * lx + c[2] * ly

    def distancia_sensor_piso(self, locais):
        """Distância (mm, perpendicular) de cada ponto da placa do sensor até o piso abaixo
        dele, contando rampa, robô inclinado, lombada e palito. nan = sem piso."""
        locais = np.asarray(locais, dtype=float)
        H = self.alturas_piso(self._mundo(locais))
        cosi = getattr(self, '_cos_incl', 1.0)
        base = np.array([self.altura_eixos(lx, ly) for lx, ly in locais]) - \
            (self.R - self.sensor.altura) / cosi
        return (base - H) * cosi

    def _gangorras(self, dt):
        m = self.mapa
        t = self.lad_centro
        if t is None or not m.eh_gangorra(t):
            return
        k = m.chave(t)
        g = m.graus_gangorra(t)
        p = self.corpo.position
        u, v = m.local(t, p.x, p.y)
        e = m.eixo_gangorra(t)
        s = {'N': v, 'S': TAM - v, 'L': u, 'O': TAM - u}[e] - TAM / 2
        if abs(s) < 8:
            return
        alvo = -g if s > 0 else g      # o peso do lado positivo abaixa a ponta positiva
        a = self.angs.get(k, alvo)
        vel = 2 * g / float(self.cfg.get('terreno', {}).get('tempo_gangorra_s', 0.35))
        passo = max(-vel * dt, min(vel * dt, alvo - a))
        if abs(passo) > 1e-6 and abs(a - alvo) > 1e-3:
            self.angs[k] = a + passo
            if abs(self.angs[k] - alvo) < 1e-3:
                self.eventos_incl.append((self.t, 0.15, 3.0 * (1 if alvo < 0 else -1), 0))

    def _solavanco(self, i, giro, pitch):
        _, cx, cy = self.contatos[i]
        self.corpo.angle += math.radians(self.rng.gauss(0, giro))
        frente = 1 if cx > 0 else -1
        lado = 1 if cy > 0 else -1
        self.eventos_incl.append((self.t, 0.12, frente * pitch, lado * pitch * 0.5))
        self.no_ar[i] = float(self.cfg['terreno'].get('tempo_no_ar_s', 0.0))

    def _terreno(self):
        ter = self.cfg['terreno']
        b = self.corpo
        atuais = [b.local_to_world((cx, cy)) for (_, cx, cy) in self.contatos]
        if self.pos_ant_contatos is not None:
            for i, (p0, p1) in enumerate(zip(self.pos_ant_contatos, atuais)):
                t = self._lad_ponto(p1.x, p1.y)
                if t is None:
                    continue
                k = self.mapa.chave(t)
                # a subida na lombada/palito é geometria (_atualiza_plano); aqui fica só a
                # vibração e o pequeno desvio de direção de quando a roda bate nela
                vib = float(ter.get('vibracao_graus', 1.0))
                if t.get('lombadas'):
                    for (x1, y1, x2, y2) in self.mapa.linhas_lombada(t):
                        if _cruza(p0, p1, (x1, y1), (x2, y2)):
                            self._solavanco(i, ter['lombada_giro_graus'], vib)
                for d in self.detritos.get(k, []):
                    if (p1 - p0).length > 0.01 and _dist_seg_seg(p0, p1, (d[0], d[1]), (d[2], d[3])) < 5:
                        self._solavanco(i, ter['detritos_giro_graus'], vib * 0.5)
                        # a roda/esteira passa por cima e o palito rola/escorrega um pouco
                        dv = (p1 - p0).normalized()
                        k = 0.4 if self.esteira else 1.0
                        empurra = dv * self.rng.uniform(2, 6) * k + \
                            Vec2d(self.rng.uniform(-2, 2), self.rng.uniform(-2, 2)) * k
                        rot = self.rng.uniform(-0.25, 0.25) * k
                        cx, cy = (d[0] + d[2]) / 2 + empurra.x, (d[1] + d[3]) / 2 + empurra.y
                        hx, hy = (d[2] - d[0]) / 2, (d[3] - d[1]) / 2
                        c, s = math.cos(rot), math.sin(rot)
                        hx, hy = hx * c - hy * s, hx * s + hy * c
                        d[:] = [cx - hx, cy - hy, cx + hx, cy + hy]
        self.pos_ant_contatos = atuais
        self.eventos_incl = [e for e in self.eventos_incl if self.t - e[0] < e[1]]

    # ---------------------------------------------------------------- rodas / esteiras
    def _rodas(self, dt):
        b = self.corpo
        th = b.angle
        f = Vec2d(math.cos(th), math.sin(th))
        lat = Vec2d(-math.sin(th), math.cos(th))
        n = len(self.contatos)
        invm = 1.0 / self.massa
        invI = 1.0 / b.moment
        # gravidade na rampa/gangorra (componente horizontal)
        gx = gy = 0.0
        nc = 0
        for (_, cx, cy) in self.contatos:
            p = b.local_to_world((cx, cy))
            t = self._lad_ponto(p.x, p.y)
            if t is None:
                continue
            a, c = self.mapa.gradiente(t, self.angs.get(self.mapa.chave(t)))
            gx += a
            gy += c
            nc += 1
        if nc:
            gx /= nc
            gy /= nc
        g2 = gx * gx + gy * gy
        cos_incl = 1.0 / math.sqrt(1.0 + g2)
        if g2 > 0:
            F = -self.massa * G / (1.0 + g2)
            b.apply_impulse_at_world_point((F * gx * dt, F * gy * dt), b.position)
        n_apoio = max(1, n - sum(1 for x in self.suspenso if x))
        N = self.massa * G * cos_incl / n_apoio
        # inclinação na direção do movimento (a roda anda na rampa, o plano vê a projeção)
        incl_f = gx * f.x + gy * f.y
        proj = 1.0 / math.sqrt(1.0 + incl_f * incl_f)
        # cada motor: média dos contatos dele para a velocidade do encoder
        soma_vl = [0.0] * len(self.motores)
        cont_vl = [0] * len(self.motores)
        livres = [m.livre() for m in self.motores]
        self.ordem = (self.ordem + 1) % n
        for k in range(n):
            ic = (k + self.ordem) % n
            imot, cx, cy = self.contatos[ic]
            mot = self.motores[imot]
            p = b.local_to_world((cx, cy))
            r = p - b.position
            if self.no_ar[ic] > 0:
                self.no_ar[ic] -= dt
                continue
            if self.suspenso[ic]:
                continue          # roda/trecho da esteira no ar (robô apoiado em outro ponto)
            if self._lad_ponto(p.x, p.y) is None:
                continue          # esse ponto está fora do piso
            # lateral
            v = b.velocity_at_world_point(p)
            rx = r.cross(lat)
            meff = 1.0 / (invm + rx * rx * invI)
            J = -v.dot(lat) * meff
            jmax = self.mu_lat * N * dt
            J = max(-jmax, min(jmax, J))
            b.apply_impulse_at_world_point(lat * J, p)
            # longitudinal
            v = b.velocity_at_world_point(p)
            vl = v.dot(f)
            rx = r.cross(f)
            meff = 1.0 / (invm + rx * rx * invI)
            if livres[imot]:
                J = -vl * meff * min(1.0, 3.0 * dt)
                b.apply_impulse_at_world_point(f * J, p)
                soma_vl[imot] += vl / proj
                cont_vl[imot] += 1
                continue
            w = mot.vel_superficie() * proj
            J = (w - vl) * meff
            jf = self.mu * N * dt
            jm = mot.forca_max * dt / len(mot.contatos)
            if abs(J) <= min(jf, jm):
                b.apply_impulse_at_world_point(f * J, p)
            elif jm < jf:
                Ja = math.copysign(jm, J)
                b.apply_impulse_at_world_point(f * Ja, p)
                soma_vl[imot] += (vl + Ja / meff) / proj
                cont_vl[imot] += 1
            else:
                b.apply_impulse_at_world_point(f * math.copysign(jf, J), p)
        for i, mot in enumerate(self.motores):
            if cont_vl[i] and (livres[i] or cont_vl[i] == len(mot.contatos)):
                mot.set_vel_superficie(soma_vl[i] / cont_vl[i])

    def _filtros_altura(self):
        """Obstáculos e pilares só colidem com o robô na mesma altura."""
        h = self.h_centro
        for o in self.obstaculos:
            perto = abs(o['h'] - h) < 80
            mask = (CAT_ROBO | CAT_SENSOR | CAT_OBST) if perto else CAT_OBST
            if o['forma'].filter.mask != mask:
                o['forma'].filter = pymunk.ShapeFilter(categories=CAT_OBST, mask=mask)
        for pl in self.pilares:
            embaixo = h < pl['h'] - 50
            mask = (CAT_ROBO | CAT_SENSOR) if embaixo else 0
            if pl['forma'].filter.mask != mask:
                pl['forma'].filter = pymunk.ShapeFilter(categories=CAT_PILAR, mask=mask)

    def passo(self, dt=None):
        dt = dt or self.DT
        for m in self.motores:
            m.atualiza_controle(dt)
        self._rodas(dt)
        self.space.step(dt)
        for m in self.motores:
            m.integra(dt)
        self.fw_mariola.passo(self.t)
        for fws in self.fw_placas.values():
            for fw in list(fws.values()):
                fw.passo(self.t)
        self.resgate.passo(dt, self.t)
        self._atualiza_centro()
        self._gangorras(dt)
        self._terreno()
        self._atualiza_plano()
        if int(self.t / dt) % 24 == 0:
            self._filtros_altura()
        self.deriva += float(self.cfg['giroscopio']['deriva_graus_min']) / 60.0 * dt
        self.t += dt

    def velocidade(self):
        return self.corpo.velocity.length, abs(self.corpo.angular_velocity)

    # ---------------------------------------------------------------- VL53
    def vl53(self, idx):
        sc = self.cfg['vl53'][idx]
        pr = self.cfg['vl53_params']
        b = self.corpo
        p0 = b.local_to_world((sc['x'], sc['y']))
        a0 = b.angle + math.radians(sc['angulo'])
        alcance = float(pr['alcance_mm'])
        cone = math.radians(float(pr['cone_graus']))
        altura = sc.get('altura')          # mm do chão; só vê o que for mais alto que isso
        if sc.get('na_garra'):
            mec = self.resgate.mec
            r = mec.vl53_garra(sc, alcance) if mec else None
            if r is None:
                self.raios[sc['nome']] = (p0, p0, None, self.t)
                return int(pr['fora_alcance'])
            if r != 'raio':
                d = r + self.rng_vl53.gauss(0, float(pr['ruido_mm']))
                self.raios[sc['nome']] = (p0, p0 + Vec2d(math.cos(a0), math.sin(a0)) * r, r, self.t)
                return max(0, int(round(d)))
        filtro = pymunk.ShapeFilter(mask=CAT_OBST | CAT_PILAR | CAT_BOLA)
        melhor = None
        for k, alc in ((-0.5, 0.35), (-0.25, 0.7), (0.0, 1.0), (0.25, 0.7), (0.5, 0.35)):
            a = a0 + k * cone
            p1 = p0 + Vec2d(math.cos(a), math.sin(a)) * (alcance + 200)
            for q in self.space.segment_query(p0, p1, 0, filtro):
                if q.shape is None or not self._visivel(q.shape):
                    continue
                if altura is not None and getattr(q.shape, 'altura_mm', 1e9) < float(altura):
                    continue
                d = (q.point - p0).length
                if k != 0 and d > alc * alcance:
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

    def _visivel(self, forma):
        """O feixe só vê obstáculos/pilares na mesma altura do robô."""
        f = forma.filter
        return bool(f.mask & CAT_SENSOR)

    def vl53_por_canal(self, canal):
        for i, sc in enumerate(self.cfg['vl53']):
            if canal_mux(sc['mux']) == canal:
                return i
        return None

    # ---------------------------------------------------------------- giroscópio
    def _inclinacao(self):
        pitch = math.degrees(self.pitch)
        roll = -math.degrees(self.roll)       # roll positivo = lado direito para baixo
        for (t0, dur, ap, ar) in self.eventos_incl:
            s = math.sin(math.pi * min(1.0, (self.t - t0) / dur))
            pitch += ap * s
            roll += ar * s
        return pitch, roll

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
        pitch, roll = self._inclinacao()
        pitch += self.rng_giro.gauss(0, ruido)
        roll += self.rng_giro.gauss(0, ruido)
        if gc.get('eixo_inclinacao_frente', 'x') == 'x':
            x, y = pitch, roll
        else:
            x, y = roll, pitch
        esc = float(gc['escala'])
        return [int(round(x * esc)), int(round(y * esc)), int(round(z * esc))]

    # ---------------------------------------------------------------- piso / sensor de linha
    def materiais(self, pts):
        """Material do piso em cada ponto (N x 2, mundo)."""
        m = self.mapa
        n = len(pts)
        out = np.full(n, LT.M_FORA, np.uint8)
        cx = np.floor(pts[:, 0] / TAM).astype(int)
        cy = m.altura - 1 - np.floor(pts[:, 1] / TAM).astype(int)
        chaves = cx * 10007 + cy
        for ch in np.unique(chaves):
            sel = np.nonzero(chaves == ch)[0]
            x, y = cx[sel[0]], cy[sel[0]]
            if not m.dentro(x, y):
                continue
            px, py = pts[sel].mean(axis=0)
            t = self._lad_ponto(px, py)
            if t is None:
                continue
            tex = self.cat.material_girado(t['tipo'], t['rot'])
            X0, Y0 = m.origem(x, y)
            col = np.clip((pts[sel, 0] - X0).astype(int), 0, TAM - 1)
            lin = np.clip((TAM - (pts[sel, 1] - Y0)).astype(int), 0, TAM - 1)
            out[sel] = tex[lin, col]
            dets = self.detritos.get(m.chave(t))
            if dets:
                for d in dets:
                    dd = _dist_pts_seg(pts[sel], d)
                    out[sel[dd < 1.6]] = LT.M_MADEIRA
        return out

    def leitura_sensor(self, ruido=True):
        """Lê o sensor de linha. Devolve dict com os 12 IR, 4 canais, 3 RGBC e os 16 bytes."""
        sl = self.sensor
        b = self.corpo
        th = b.angle
        c, s = math.cos(th), math.sin(th)
        px, py = b.position.x, b.position.y
        locais = sl.ir + sl.tcs
        centros = np.array([(px + lx * c - ly * s, py + lx * s + ly * c) for lx, ly in locais])
        nir = len(sl.ir)
        di, dt_ = sl.disco_ir, sl.disco_tcs
        pts = [centros[:nir, None, :] + di[None, :, :], centros[nir:, None, :] + dt_[None, :, :]]
        todos = np.concatenate([pts[0].reshape(-1, 2), pts[1].reshape(-1, 2)])
        mats = self.materiais(todos)
        ni = len(di)
        mi = mats[:nir * ni].reshape(nir, ni)
        mt = mats[nir * ni:].reshape(len(sl.tcs), len(dt_))
        ir12 = self.ir_mat[mi].mean(axis=1)
        rgbc = self.rgbc_mat[mt].mean(axis=1)
        dist = self.distancia_sensor_piso(locais)
        for i in range(nir):
            d = dist[i]
            ir12[i] *= 0.0 if not np.isfinite(d) else sl.resposta(d, sl.curva_ir)
        for j in range(len(sl.tcs)):
            d = dist[nir + j]
            rgbc[j] *= 0.0 if not np.isfinite(d) else sl.resposta(d, sl.curva_tcs)
        g = sl.grupo
        if sl.modo == 'minimo':
            canais = [float(min(ir12[i:i + g])) for i in range(0, nir, g)]
        else:
            canais = [float(np.mean(ir12[i:i + g])) for i in range(0, nir, g)]
        r = sl.ruido if ruido else 0.0
        canais_r = [v + self.rng_cor.gauss(0, r) for v in canais] if r else canais
        rgbc_r = [[v + self.rng_cor.gauss(0, r) for v in linha] for linha in rgbc] if r else rgbc.tolist()
        bytes16 = [max(0, min(255, int(round(v)))) for v in canais_r]
        for linha in rgbc_r:
            bytes16.extend(max(0, min(255, int(round(v)))) for v in linha)
        while len(bytes16) < 16:
            bytes16.append(0)
        return {'ir12': ir12.tolist(), 'canais': canais, 'rgbc': rgbc.tolist(), 'bytes': bytes16[:16],
                'centros': centros.tolist(), 'distancias': [float(x) for x in dist]}

    def cor_firmware(self):
        """O sensor atualiza na taxa do firmware e devolve o último valor lido. Se ficar 30 s
        sem pedido ele para de ler: o primeiro pedido depois disso devolve valores velhos."""
        ocioso = self.t - self.cor_pedido
        self.cor_pedido = self.t
        periodo = 1.0 / float(self.sensor.cfg.get('taxa_hz', 50))
        if self.cor_cache is None or (ocioso < 30.0 and self.t - self.cor_t >= periodo):
            self.ultima_leitura = self.leitura_sensor()
            self.cor_cache = self.ultima_leitura['bytes']
            self.cor_t = self.t
        return list(self.cor_cache)

    def cor_bytes(self):
        return self.leitura_sensor()['bytes']

    # ---------------------------------------------------------------- para-choque e GPIO
    def para_choque(self, pino):
        s = self.sensores_pc.get(pino)
        if s is None:
            return False
        for info in self.space.shape_query(s):
            if info.shape is not None and info.shape is not self.forma and \
                    info.shape.filter.categories & (CAT_OBST | CAT_PILAR) and \
                    info.shape.filter.mask & CAT_SENSOR:
                return True
        return False

    def gpio_nivel(self, pino):
        if pino in self.gpio_saida:
            return self.gpio_saida[pino]
        apertado = False
        if pino in self.sensores_pc:
            apertado = self.para_choque(pino)
        if pino in self.botoes_gui:
            apertado = True
        return 0 if apertado else 1

    @property
    def led(self):
        return max(self.leds, key=sum)

    def contorno_robo(self):
        b = self.corpo
        hl, hw = self.L / 2, self.W / 2
        return [b.local_to_world(p) for p in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))]


# --------------------------------------------------------------------------- utilidades
_TRIPLAS = {}


def _envoltoria_superior(xs, hs, tol=0.05):
    """Vértices da envoltória convexa superior de pontos (x, h) ordenados por x."""
    sup = []
    for q in zip(xs.tolist(), hs.tolist()):
        while len(sup) >= 2:
            (x1, y1), (x2, y2) = sup[-2], sup[-1]
            if (x2 - x1) * (q[1] - y1) - (y2 - y1) * (q[0] - x1) >= 0:
                sup.pop()
            else:
                break
        sup.append(q)
    # tira vértices quase alinhados (o arco das polias) para o plano de apoio ficar leve
    i = 1
    while i < len(sup) - 1 and len(sup) > 2:
        (x1, y1), (x2, y2), (x3, y3) = sup[i - 1], sup[i], sup[i + 1]
        corda = y1 + (y3 - y1) * (x2 - x1) / (x3 - x1) if x3 != x1 else y1
        if y2 - corda < tol:
            sup.pop(i)
        else:
            i += 1
    return sup


def _plano_apoio(xs, ys, hs):
    """(h no centro, dh/dx, dh/dy) do plano de apoio sobre (0, 0), ou None."""
    n = len(hs)
    T = _TRIPLAS.get(n)
    if T is None:
        from itertools import combinations
        T = _TRIPLAS[n] = np.array(list(combinations(range(n), 3)))
    A = np.column_stack([xs, ys, hs])
    a, b, c = A[T[:, 0]], A[T[:, 1]], A[T[:, 2]]
    nrm = np.cross(b - a, c - a)
    ok = np.abs(nrm[:, 2]) > 1e-6
    if not ok.any():
        return None
    nrm, a = nrm[ok], a[ok]
    kx = -nrm[:, 0] / nrm[:, 2]
    ky = -nrm[:, 1] / nrm[:, 2]
    h0 = a[:, 2] - kx * a[:, 0] - ky * a[:, 1]
    acima = (h0[:, None] + kx[:, None] * xs[None, :] + ky[:, None] * ys[None, :]) >= hs[None, :] - 0.05
    val = acima.all(axis=1)
    if not val.any():
        return None
    i = np.argmin(np.where(val, h0, np.inf))
    return float(h0[i]), float(kx[i]), float(ky[i])


def _apoio(us, hs):
    """Reta de apoio (inclinação, altura em u=0) de pontos (u, h): a aresta da envoltória
    superior que passa sobre u = 0 (o centro do robô)."""
    pts = {}
    for u, h in zip(us, hs):
        u = round(u, 3)
        pts[u] = max(h, pts.get(u, -1e9))
    p = sorted(pts.items())
    if len(p) == 1:
        return 0.0, p[0][1]
    sup = []
    for q in p:
        while len(sup) >= 2:
            (x1, y1), (x2, y2) = sup[-2], sup[-1]
            if (x2 - x1) * (q[1] - y1) - (y2 - y1) * (q[0] - x1) >= 0:
                sup.pop()
            else:
                break
        sup.append(q)
    for (x1, y1), (x2, y2) in zip(sup, sup[1:]):
        if x1 <= 0 <= x2 or (x2 < 0 and (x2, y2) == sup[-1]) or (x1 > 0 and (x1, y1) == sup[0]):
            k = (y2 - y1) / (x2 - x1) if x2 != x1 else 0.0
            return k, y1 - k * x1
    (x1, y1), (x2, y2) = sup[0], sup[-1]
    k = (y2 - y1) / (x2 - x1) if x2 != x1 else 0.0
    return k, y1 - k * x1


def _cruza(p0, p1, a, b):
    def orient(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    o1 = orient(a, b, p0)
    o2 = orient(a, b, p1)
    o3 = orient(p0, p1, a)
    o4 = orient(p0, p1, b)
    return (o1 > 0) != (o2 > 0) and (o3 > 0) != (o4 > 0)


def _dist_ponto_seg(p, a, b):
    ax, ay = a[0], a[1]
    bx, by = b[0], b[1]
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(p[0] - ax, p[1] - ay)
    t = max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L2))
    return math.hypot(p[0] - ax - t * dx, p[1] - ay - t * dy)


def _dist_seg_seg(a, b, c, d):
    if _cruza(a, b, c, d):
        return 0.0
    return min(_dist_ponto_seg(a, c, d), _dist_ponto_seg(b, c, d),
               _dist_ponto_seg(c, a, b), _dist_ponto_seg(d, a, b))


def _dist_pts_seg(pts, d):
    a = np.array(d[:2])
    b = np.array(d[2:])
    ab = b - a
    L2 = float(ab @ ab) or 1e-9
    t = np.clip(((pts - a) @ ab) / L2, 0, 1)
    proj = a + t[:, None] * ab
    return np.hypot(*(pts - proj).T)
