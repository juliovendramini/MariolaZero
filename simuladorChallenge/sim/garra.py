"""Garras do robô. Duas formas, escolhidas pelo "tipo" de cada garra no robo.json:

* 'dedos' (padrão): a garra simples provisória (classe Garra, abaixo).
* 'paralelogramo': a garra do robô real (classe GarraParalela, no fim do arquivo).

Garra simples na frente do robô: dois dedos (um servo abre/fecha) num braço que sobe e desce
(outro servo). Cinemática, como a garra do resgate da Line.

* Os dedos são dois segmentos presos ao corpo do robô. Com a garra embaixo eles empurram cubos e
  batem nas plataformas; com a garra acima de 50 mm passam por cima de tudo.
* Fechando, o cubo que estiver entre os dedos (e na altura deles) fica preso: sai da física 2D e
  acompanha a garra. Os dedos param na largura do cubo (o servo trava nele).
* Abrindo, o cubo é solto: se a garra está alta e o centro do cubo fica em cima de uma plataforma,
  ele fica em cima dela; senão, cai no chão.

Os servos são os do Mariola (porta SERVO1..4, lib motores.py: move_servo + atualiza_servos). O ângulo
de cada um anda até o alvo com a velocidade do servo; servo solto (ângulo > 180, ou o timeout de 5 s do
firmware) deixa a garra parada onde está e o braço desce sozinho com o peso.
"""

import math

import pymunk

CUBO = 50.0
ALTURA_OBJETO = 50.0


def _lerp(a, b, t):
    return a + (b - a) * t


def _encostam(s1, s2):
    """As duas formas se sobrepõem (vistas de cima)?"""
    if not s1.bb.intersects(s2.bb):
        return False
    try:
        return bool(s1.shapes_collide(s2).points)
    except AssertionError:       # o pymunk 7 reclama quando não há contato
        return False


class Garra:
    def __init__(self, robo, cfg):
        self.robo = robo
        self.cfg = cfg
        self.nome = cfg.get('nome', 'garra')
        self.servo_abre = str(cfg['servo_abre'])
        self.servo_sobe = str(cfg['servo_sobe'])
        self.ang_aberta = float(cfg['angulo_aberta'])
        self.ang_fechada = float(cfg['angulo_fechada'])
        self.abertura_aberta = float(cfg['abertura_aberta_mm'])
        self.abertura_fechada = float(cfg['abertura_fechada_mm'])
        self.ang_baixa = float(cfg['angulo_baixa'])
        self.ang_alta = float(cfg['angulo_alta'])
        self.altura_max = float(cfg['altura_max_mm'])
        self.x_base = float(cfg.get('x', robo.L / 2))
        self.comprimento = float(cfg.get('comprimento_dedos_mm', 60))
        self.raio_dedo = float(cfg.get('espessura_dedo_mm', 4)) / 2
        self.vel_servo = float(cfg.get('vel_servo_graus_s', 300))
        self.vel_queda = float(cfg.get('vel_queda_graus_s', 120))
        self.dedos = []
        self.reset()

    def reset(self):
        self.a_abre = self.ang_aberta if self.cfg.get('comeca_aberta', True) else self.ang_fechada
        self.a_sobe = self.ang_baixa
        self.preso = None          # Objeto na garra
        self.lx_preso = 0.0        # posição (x do robô) do centro do cubo preso

    # ---------------------------------------------------------------- geometria
    def abertura(self):
        """Distância entre os dedos (mm)."""
        t = (self.a_abre - self.ang_fechada) / (self.ang_aberta - self.ang_fechada)
        ab = _lerp(self.abertura_fechada, self.abertura_aberta, max(0.0, min(1.0, t)))
        if self.preso is not None:
            ab = max(ab, CUBO + 2 * self.raio_dedo)   # o cubo segura os dedos
        return ab

    def altura(self):
        """Altura (mm) da parte de baixo dos dedos = do cubo preso."""
        t = (self.a_sobe - self.ang_baixa) / (self.ang_alta - self.ang_baixa)
        return self.altura_max * max(0.0, min(1.0, t))

    def _pontos_dedos(self):
        y = self.abertura() / 2
        x0, x1 = self.x_base, self.x_base + self.comprimento
        return [((x0, y), (x1, y)), ((x0, -y), (x1, -y))]

    def cria(self, space, corpo, filtro_baixa):
        self.filtro_baixa = filtro_baixa
        self.filtro_alta = pymunk.ShapeFilter(categories=filtro_baixa.categories, mask=0)
        self.dedos = []
        for a, b in self._pontos_dedos():
            s = pymunk.Segment(corpo, a, b, self.raio_dedo)
            s.friction = 0.5
            s.elasticity = 0.0
            s.filter = filtro_baixa
            s.altura_mm = 1e9
            s.objeto = None
            s.robo = self.robo
            s.dedo = True
            space.add(s)
            self.dedos.append(s)

    # ---------------------------------------------------------------- passo
    def _anda(self, atual, chave, cai_para=None):
        alvo = self.robo.servos.get(chave, 200)
        if alvo > 180:
            if cai_para is None:
                return atual                          # servo solto: fica onde está
            alvo, vel = cai_para, self.vel_queda      # o braço desce com o peso
        else:
            vel = self.vel_servo
        passo = vel * self.robo.mundo.DT
        if abs(alvo - atual) <= passo:
            return float(alvo)
        return atual + math.copysign(passo, alvo - atual)

    def passo(self):
        """Antes do passo da física: servos, dedos, prender e soltar."""
        self.a_abre = self._anda(self.a_abre, self.servo_abre)
        self.a_sobe = self._anda(self.a_sobe, self.servo_sobe, cai_para=self.ang_baixa)
        h = self.altura()
        for s, (a, b) in zip(self.dedos, self._pontos_dedos()):
            s.unsafe_set_endpoints(a, b)
            s.filter = self.filtro_baixa if h < ALTURA_OBJETO else self.filtro_alta
        if self.dedos:
            self.robo.mundo.space.reindex_shapes_for_body(self.robo.corpo)
        folga = 6.0
        if self.preso is None:
            ab = self.abertura()
            if ab <= CUBO + 2 * self.raio_dedo + folga and h < 15.0:
                o = self._cubo_entre_os_dedos(ab)
                if o is not None:
                    self.preso = o
                    p = self.robo.corpo.world_to_local(o.corpo.position)
                    self.lx_preso = max(self.x_base + CUBO / 2 + 1, min(p.x, self.x_base + self.comprimento - 10))
                    self.robo.mundo.prende(self.robo, o, self)
        else:
            t = (self.a_abre - self.ang_fechada) / (self.ang_aberta - self.ang_fechada)
            ab_servo = _lerp(self.abertura_fechada, self.abertura_aberta, max(0.0, min(1.0, t)))
            if ab_servo > CUBO + 2 * self.raio_dedo + folga:
                o, self.preso = self.preso, None
                self.robo.mundo.solta(self.robo, o, self.posicao_preso(), h)

    def posicao_preso(self):
        return self.robo.corpo.local_to_world((self.lx_preso, 0.0))

    def segue(self):
        """Depois do passo da física: o cubo preso acompanha a garra."""
        o = self.preso
        if o is None:
            return
        b = o.corpo
        b.position = self.posicao_preso()
        b.angle = self.robo.corpo.angle
        b.velocity = (0, 0)
        b.angular_velocity = 0
        o.z = self.altura()
        o.atualiza_altura()
        b.space.reindex_shapes_for_body(b)

    def desenho(self):
        """Traços para a janela, no referencial do robô: [(a, b, espessura_mm, no_alto)]."""
        alto = self.altura() >= ALTURA_OBJETO
        esp = self.raio_dedo * 2
        (a0, a1), (b0, b1) = self._pontos_dedos()
        return [(a0, a1, esp, alto), (b0, b1, esp, alto), (a0, b0, esp, alto)]

    def info(self):
        return {'nome': self.nome, 'abertura': self.abertura(), 'altura': self.altura(),
                'preso': self.preso.cor if self.preso else None}

    def _cubo_entre_os_dedos(self, ab):
        corpo = self.robo.corpo
        for o in self.robo.mundo.objetos:
            if o.tipo != 'cubo' or o.estado != 'livre':
                continue
            p = corpo.world_to_local(o.corpo.position)
            if not (self.x_base + CUBO / 2 - 8 <= p.x <= self.x_base + self.comprimento - CUBO / 2 + 12):
                continue
            if abs(p.y) <= ab / 2 - CUBO / 2 + 4:
                return o
        return None


# =========================================================================== garra do robô real
class GarraParalela:
    """Garra do robô real (desenho "Bombertinho 2026 - Nacional CBR", 31/10/2026).

    * Braço: duas barras paralelas de mesmo comprimento ligam o suporte (preso ao robô) à cabeça.
      O servo de subir gira a barra de baixo; a cabeça sobe e desce sem inclinar, num arco: descendo,
      ela também chega para perto do robô (barra x (1 - cos)).
    * Cabeça: aberta embaixo, com a parede de trás, o teto e, correndo num trilho do teto, a peça que
      abre (comporta na ponta + dois braços em "V" dos lados do cubo). O servo de abrir gira uma
      engrenagem (24 dentes, módulo 1: 12 mm de raio) que empurra uma cremalheira: a comporta anda
      mm_por_grau por grau do servo. Fechada, sobram 50 mm (o cubo) entre a comporta e a parede.
    * Pegar: a cabeça desce por cima do cubo (com a comporta aberta) e a comporta fecha, apertando o
      cubo contra a parede. Se o robô estiver mal posicionado, a parede, a comporta ou os braços do
      "V" batem em cima do cubo e a cabeça para ali (o servo trava).
    * Soltar: abrindo a comporta o cubo cai; em cima da plataforma se a cabeça está alta (base do
      cubo a 45 mm ou mais) e o centro do cubo fica sobre ela.

    Referencial da garra: u = para fora (direção 'angulo' do robô), v = para a esquerda de quem
    olha para fora. As medidas da cabeça partem do furo de baixo dela (onde a barra de baixo gira);
    as alturas das peças são acima da base do cubo preso.
    """

    def __init__(self, robo, cfg):
        self.robo = robo
        self.cfg = cfg
        self.nome = cfg.get('nome', 'garra')
        self.servo_sobe = str(cfg['servo_sobe'])
        self.servo_abre = str(cfg['servo_abre'])
        self.x0 = float(cfg['x'])
        self.y0 = float(cfg['y'])
        self.ang = math.radians(float(cfg.get('angulo', 0)))
        self.barra = float(cfg['barra_mm'])
        self.h_eixo = float(cfg['altura_eixo_mm'])
        self.dz_cubo = float(cfg.get('base_cubo_mm', -12.0))
        self.ang_horizontal = float(cfg['angulo_horizontal'])
        self.sentido_sobe = -1.0 if float(cfg.get('sentido_sobe', 1)) < 0 else 1.0
        self.ang_fechada = float(cfg['angulo_fechada'])
        self.sentido_abre = -1.0 if float(cfg.get('sentido_abre', 1)) < 0 else 1.0
        self.mm_por_grau = float(cfg.get('mm_por_grau', 12.0 * math.pi / 180.0))
        self.curso_max = float(cfg.get('curso_max_mm', 25.0))
        self.vel_servo = float(cfg.get('vel_servo_graus_s', 300))
        self.vel_queda = float(cfg.get('vel_queda_graus_s', 120))
        self.altura_pegar = float(cfg.get('altura_max_pegar_mm', 17.0))
        c = cfg.get('cabeca', {})
        self.parede_u = float(c.get('parede_mm', 4.0))              # face de dentro da parede de trás
        self.parede_esp = float(c.get('espessura_parede_mm', 8.0))
        self.parede_larg = float(c.get('largura_parede_mm', 24.0))
        self.parede_baixo = float(c.get('parede_acima_da_base_mm', 5.0))
        self.comporta_esp = float(c.get('espessura_comporta_mm', 4.5))
        self.comporta_larg = float(c.get('largura_comporta_mm', 25.0))
        self.comporta_baixo = float(c.get('comporta_acima_da_base_mm', 23.0))
        self.bracos = c.get('bracos_v', [[56.5, 28.0], [25.0, 40.0]])   # (u, |v|) da comporta à ponta
        self.bracos_esp = float(c.get('espessura_bracos_mm', 3.5))
        self.bracos_baixo = float(c.get('bracos_acima_da_base_mm', 38.0))
        self.teto = float(c.get('comprimento_teto_mm', 61.0))
        self.teto_larg = float(c.get('largura_teto_mm', 30.0))
        # a parede de trás encosta no chão: limite de baixo da barra
        s = (-self.parede_baixo - self.dz_cubo - self.h_eixo) / self.barra
        self.barra_min = math.degrees(math.asin(max(-1.0, min(1.0, s))))
        self.barra_max = float(cfg.get('angulo_barra_max', 60.0))
        self.partes = []
        self.reset()

    def reset(self):
        self.a_sobe = self._a_de_barra(0.0)
        self.a_abre = self.ang_fechada
        self.preso = None

    # ---------------------------------------------------------------- geometria
    def _barra(self, a=None):
        """Ângulo da barra (graus, 0 = horizontal, + = para cima) para o ângulo a do servo."""
        b = self.sentido_sobe * ((self.a_sobe if a is None else a) - self.ang_horizontal)
        return max(self.barra_min, min(self.barra_max, b))

    def _a_de_barra(self, b):
        return self.ang_horizontal + b / self.sentido_sobe

    def _base(self, b):
        return self.h_eixo + self.barra * math.sin(math.radians(b)) + self.dz_cubo

    def altura(self):
        """Altura (mm) da base do cubo preso (pode ser negativa: a cabeça desce até a parede de trás
        encostar no chão)."""
        return self._base(self._barra())

    def curso(self):
        """Quanto a comporta está aberta (mm)."""
        c = self.sentido_abre * (self.a_abre - self.ang_fechada) * self.mm_por_grau
        return max(0.0, min(self.curso_max, c))

    def abertura(self):
        """Distância entre a parede de trás e a comporta (mm)."""
        return CUBO + self.curso()

    def _uh(self):
        return self.barra * math.cos(math.radians(self._barra()))

    def _local(self, u, v):
        ca, sa = math.cos(self.ang), math.sin(self.ang)
        return (self.x0 + u * ca - v * sa, self.y0 + u * sa + v * ca)

    def _uv(self, lx, ly):
        dx, dy = lx - self.x0, ly - self.y0
        ca, sa = math.cos(self.ang), math.sin(self.ang)
        return dx * ca + dy * sa, -dx * sa + dy * ca

    def _segmentos(self):
        """[(a, b, raio, altura_do_fundo_acima_da_base)] das peças da cabeça que batem nos objetos."""
        uh = self._uh()
        c = self.curso()
        r = self.parede_esp / 2
        up = uh + self.parede_u - r
        meia = self.parede_larg / 2 - r
        segs = [(self._local(up, -meia), self._local(up, meia), r, self.parede_baixo)]
        rc = self.comporta_esp / 2
        uc = uh + self.parede_u + CUBO + c + rc
        meia = self.comporta_larg / 2 - rc
        segs.append((self._local(uc, -meia), self._local(uc, meia), rc, self.comporta_baixo))
        (u1, v1), (u2, v2) = self.bracos
        for s in (1, -1):
            segs.append((self._local(uh + u1 + c, s * v1), self._local(uh + u2 + c, s * v2),
                         self.bracos_esp / 2, self.bracos_baixo))
        return segs

    def cria(self, space, corpo, filtro_baixa):
        self.filtro_baixa = filtro_baixa
        self.filtro_alta = pymunk.ShapeFilter(categories=filtro_baixa.categories, mask=0)
        self.partes = []
        for a, b, r, baixo in self._segmentos():
            s = pymunk.Segment(corpo, a, b, r)
            s.friction = 0.5
            s.elasticity = 0.0
            s.filter = filtro_baixa
            s.altura_mm = 1e9
            s.objeto = None
            s.robo = self.robo
            s.dedo = True              # os raios dos sensores não enxergam a garra
            s.baixo = baixo
            space.add(s)
            self.partes.append(s)

    # ---------------------------------------------------------------- passo
    def _anda(self, atual, chave, cai_para=None):
        alvo = self.robo.servos.get(chave, 200)
        if alvo > 180:
            if cai_para is None:
                return atual
            alvo, vel = cai_para, self.vel_queda
        else:
            vel = self.vel_servo
        passo = vel * self.robo.mundo.DT
        if abs(alvo - atual) <= passo:
            return float(alvo)
        return atual + math.copysign(passo, alvo - atual)

    def _base_minima(self, base):
        """A cabeça (ou o cubo preso) não atravessa o que está embaixo: devolve a menor altura da
        base que ela pode ter, saindo da altura 'base'."""
        minimo = 0.0 if self.preso is not None else -1e9
        formas = [(s, s.baixo) for s in self.partes]
        if self.preso is not None:
            formas.append((self.preso.forma, 0.0))
        for o in self.robo.mundo.objetos:
            if o is self.preso:
                continue
            if o.estado == 'livre':
                topo = o.altura
            elif o.estado == 'plataforma':
                topo = o.z + o.altura
            else:
                continue
            for s, baixo in formas:
                if base + baixo < topo - 0.5:
                    continue                 # já está abaixo do topo: a física 2D cuida
                if _encostam(s, o.forma):
                    minimo = max(minimo, topo - baixo)
        return minimo

    def passo(self):
        """Antes do passo da física: servos, cabeça, prender e soltar."""
        self.a_abre = self._anda(self.a_abre, self.servo_abre)
        antes = self.a_sobe
        self.a_sobe = self._anda(self.a_sobe, self.servo_sobe, cai_para=self._a_de_barra(self.barra_min))
        b_antes = self._barra(antes)
        if self._barra() < b_antes:
            minimo = self._base_minima(self._base(b_antes))
            if self.altura() < minimo:
                # bateu em cima de alguma coisa: o servo para onde encostou (sem subir)
                s = (minimo - self.dz_cubo - self.h_eixo) / self.barra
                b = math.degrees(math.asin(max(-1.0, min(1.0, s))))
                self.a_sobe = self._a_de_barra(min(b_antes, max(b, self._barra())))
        base = self.altura()
        for s, (a, b, r, baixo) in zip(self.partes, self._segmentos()):
            s.unsafe_set_endpoints(a, b)
            s.filter = self.filtro_baixa if base + baixo < ALTURA_OBJETO else self.filtro_alta
        if self.partes:
            self.robo.mundo.space.reindex_shapes_for_body(self.robo.corpo)
        folga = 3.0
        if self.preso is None:
            if self.curso() <= folga and base <= self.altura_pegar:
                o = self._cubo_na_cabeca()
                if o is not None:
                    self.preso = o
                    self.robo.mundo.prende(self.robo, o, self)
        elif self.curso() > folga:
            o, self.preso = self.preso, None
            self.robo.mundo.solta(self.robo, o, self.posicao_preso(), max(0.0, base))

    def posicao_preso(self):
        return self.robo.corpo.local_to_world(self._local(self._uh() + self.parede_u + CUBO / 2, 0.0))

    def segue(self):
        """Depois do passo da física: o cubo preso acompanha a cabeça."""
        o = self.preso
        if o is None:
            return
        b = o.corpo
        b.position = self.posicao_preso()
        b.angle = self.robo.corpo.angle + self.ang
        b.velocity = (0, 0)
        b.angular_velocity = 0
        o.z = max(0.0, self.altura())
        o.atualiza_altura()
        b.space.reindex_shapes_for_body(b)

    def _cubo_na_cabeca(self):
        """Cubo livre apertado entre a parede de trás e a comporta (e centrado pelo "V")."""
        corpo = self.robo.corpo
        uh = self._uh()
        centro = uh + self.parede_u + CUBO / 2
        for o in self.robo.mundo.objetos:
            if o.tipo != 'cubo' or o.estado != 'livre':
                continue
            p = corpo.world_to_local(o.corpo.position)
            u, v = self._uv(p.x, p.y)
            if centro - 4 <= u <= centro + self.curso() + 4 and abs(v) <= 8:
                return o
        return None

    # ---------------------------------------------------------------- sensores e janela
    def ponto_sensor(self, sc):
        """Sensor preso na cabeça: (x, y, ângulo em rad, altura) no referencial do robô.
        sc['u'], sc['v'] a partir do furo de baixo da cabeça; sc['altura'] acima da base do cubo."""
        x, y = self._local(self._uh() + float(sc.get('u', self.parede_u)), float(sc.get('v', 0)))
        return x, y, self.ang + math.radians(float(sc.get('angulo', 0))), self.altura() + float(sc.get('altura', 30))

    def desenho(self):
        base = self.altura()
        uh = self._uh()
        alto_teto = base + CUBO >= ALTURA_OBJETO
        meia = self.teto_larg / 2
        u0, u1 = uh + self.parede_u - self.parede_esp, uh + self.teto
        teto = [self._local(u0, -meia), self._local(u1, -meia), self._local(u1, meia), self._local(u0, meia)]
        out = [((self.x0, self.y0), self._local(uh, 0), 6, True)]
        out += [(teto[k], teto[(k + 1) % 4], 1.5, alto_teto) for k in range(4)]
        out += [(a, b, 2 * r, base + baixo >= ALTURA_OBJETO) for a, b, r, baixo in self._segmentos()]
        return out

    def info(self):
        return {'nome': self.nome, 'abertura': self.abertura(), 'altura': self.altura(),
                'preso': self.preso.cor if self.preso else None}


def cria_garras(robo, cfg):
    """Garras do robo.json: "garras" (lista) ou "garra" (uma só, a simples provisória)."""
    lista = cfg.get('garras')
    if lista is None:
        lista = [cfg['garra']] if cfg.get('garra') else []
    return [GarraParalela(robo, c) if c.get('tipo') == 'paralelogramo' else Garra(robo, c) for c in lista]
