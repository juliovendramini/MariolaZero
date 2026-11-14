"""Garra do robô de casa: pinça de dois dedos paralelos num braço de paralelogramo, com a câmera
na cabeça (medidas do modelo em Documents/modelos3D/robotica/roboCasa/garra/garra.py).

* Braço: duas barras de mesmo comprimento do eixo do servo de subir até a cabeça. A cabeça sobe e
  desce num arco sem inclinar. Ângulo da barra: 0 = horizontal, + = para cima.
* Pinça: engrenagem entre duas cremalheiras. Os dois dedos abrem juntos, sempre centrados.
* Câmera: num berço que um terceiro servo inclina (0 = horizontal, + = para baixo).

Na física 2D os dedos e a caixa da engrenagem são segmentos presos ao corpo do robô. Eles batem nas
paredes e nos móveis sempre, na caixa de guardar só quando o fundo dos dedos está abaixo da borda
dela, e nos objetos só quando estão na altura deles.

Fechando, o objeto que estiver entre os dedos fica preso quando a abertura chega na largura dele (o
servo trava ali): ele sai da física 2D e acompanha a cabeça. Abrindo, cai onde estiver (Mundo.solta).

Servos do Mariola (SERVO1..4, lib motores.py: move_servo + atualiza_servos). Cada um anda até o alvo
com a velocidade do servo. Servo solto (ângulo > 180 ou o timeout de 5 s do firmware) fica onde
está: o braço tem um elástico que segura o peso.
"""

import math

import pymunk


class GarraPinca:
    def __init__(self, robo, cfg):
        self.robo = robo
        self.cfg = cfg
        self.nome = cfg.get('nome', 'pinca')
        self.x_eixo = float(cfg['x'])
        self.h_eixo = float(cfg['altura_eixo_mm'])
        self.barra = float(cfg['barra_mm'])
        self.servo_sobe = str(cfg['servo_sobe'])
        self.ang_horizontal = float(cfg['angulo_horizontal'])
        self.sentido_sobe = -1.0 if float(cfg.get('sentido_sobe', 1)) < 0 else 1.0
        self.barra_min = float(cfg['barra_min'])
        self.barra_max = float(cfg['barra_max'])
        self.servo_abre = str(cfg['servo_abre'])
        self.ang_fechada = float(cfg['angulo_fechada'])
        self.sentido_abre = -1.0 if float(cfg.get('sentido_abre', 1)) < 0 else 1.0
        self.mm_por_grau = float(cfg['mm_por_grau'])
        self.ab_fechada = float(cfg.get('abertura_fechada_mm', 1.0))
        self.ab_max = float(cfg.get('abertura_max_mm', 80.0))
        self.dedo_x0 = float(cfg['dedo_x0'])
        self.dedo_x1 = float(cfg['dedo_x1'])
        self.dedo_z0 = float(cfg['dedo_z0'])
        self.dedo_z1 = float(cfg['dedo_z1'])
        self.esp = float(cfg.get('espessura_dedo_mm', 5.0))
        c = cfg.get('cabeca', {})
        self.cab_x0 = float(c.get('x0', 7.45))
        self.cab_x1 = float(c.get('x1', 54.55))
        self.cab_meia = float(c.get('meia_largura', 47.0))
        self.cab_z0 = float(c.get('z0', -8.0))
        self.cab_z1 = float(c.get('z1', 62.0))
        self.vel_servo = float(cfg.get('vel_servo_graus_s', 300))
        cam = cfg.get('camera')
        self.cam = cam
        if cam:
            self.servo_cam = str(cam['servo'])
            self.cam_horizontal = float(cam['angulo_horizontal'])
            self.cam_sentido = -1.0 if float(cam.get('sentido', 1)) < 0 else 1.0
            self.cam_min = float(cam.get('incl_min', -60))
            self.cam_max = float(cam.get('incl_max', 85))
        self.partes = []
        self.reset()

    def reset(self):
        self.a_sobe = self.ang_horizontal                      # liga com as barras na horizontal
        self.a_abre = self.ang_fechada
        self.a_cam = self.cam_horizontal + self.cam_sentido * 35.0 if self.cam else 0.0
        self.preso = None
        self.lx_preso = 0.0
        self.larg_preso = 0.0
        self.dz_preso = 0.0
        self.dang_preso = 0.0

    # ---------------------------------------------------------------- geometria
    def ang_barra(self):
        b = self.sentido_sobe * (self.a_sobe - self.ang_horizontal)
        return max(self.barra_min, min(self.barra_max, b))

    def pivo(self):
        """(x no referencial do robô, altura) do furo de baixo da cabeça."""
        b = math.radians(self.ang_barra())
        return self.x_eixo + self.barra * math.cos(b), self.h_eixo + self.barra * math.sin(b)

    def abertura_servo(self):
        ab = self.ab_fechada + self.sentido_abre * (self.a_abre - self.ang_fechada) * self.mm_por_grau
        return max(self.ab_fechada, min(self.ab_max, ab))

    def abertura(self):
        """Distância entre os dedos (mm). Com um objeto preso, ele segura os dedos."""
        ab = self.abertura_servo()
        if self.preso is not None:
            ab = max(ab, self.larg_preso)
        return ab

    def altura(self):
        """Altura (mm) do fundo dos dedos."""
        return self.pivo()[1] + self.dedo_z0

    def inclinacao(self):
        """Câmera: graus abaixo da horizontal (negativo = olhando para cima)."""
        if not self.cam:
            return 0.0
        i = self.cam_sentido * (self.a_cam - self.cam_horizontal)
        return max(self.cam_min, min(self.cam_max, i))

    def camera_local(self):
        """(x, y, altura, inclinação em graus) da lente no referencial do robô."""
        px, pz = self.pivo()
        i = math.radians(self.inclinacao())
        d = float(self.cam.get('lente_mm', 12.6))
        return (px + float(self.cam['eixo_x']) + d * math.cos(i), 0.0,
                pz + float(self.cam['eixo_z']) - d * math.sin(i), math.degrees(i))

    def _segmentos(self):
        """[(a, b, raio, z de baixo, z de cima)] no referencial do robô: dois dedos e a caixa da
        engrenagem (um segmento grosso atravessado)."""
        px, pz = self.pivo()
        y = self.abertura() / 2 + self.esp / 2
        r = self.esp / 2
        z0, z1 = pz + self.dedo_z0, pz + self.dedo_z1
        segs = [((px + self.dedo_x0 + r, y), (px + self.dedo_x1 - r, y), r, z0, z1),
                ((px + self.dedo_x0 + r, -y), (px + self.dedo_x1 - r, -y), r, z0, z1)]
        rc = (self.cab_x1 - self.cab_x0) / 2
        xc = px + (self.cab_x0 + self.cab_x1) / 2
        segs.append(((xc, -(self.cab_meia - rc)), (xc, self.cab_meia - rc), rc, pz + self.cab_z0, pz + self.cab_z1))
        return segs

    def caixas(self):
        """Peças que a câmera pode ver, no referencial do robô: [(x0, x1, y0, y1, z0, z1, rgb)]."""
        px, pz = self.pivo()
        ab = self.abertura() / 2
        z0, z1 = pz + self.dedo_z0, pz + self.dedo_z1
        x0, x1 = px + self.dedo_x0, px + self.dedo_x1
        # peças em cinza escuro (cor de impressão neutra): não se confundem com os objetos coloridos
        cinza = (62, 64, 70)
        return [(x0, x1, ab, ab + self.esp, z0, z1, cinza), (x0, x1, -ab - self.esp, -ab, z0, z1, cinza),
                (px + self.cab_x0, px + self.cab_x1, -self.cab_meia, self.cab_meia, pz - 2.0, pz + 18.0, (84, 86, 94))]

    # ---------------------------------------------------------------- física
    def cria(self, space, corpo, filtro_baixa):
        self.cat = filtro_baixa.categories
        self.partes = []
        for a, b, r, z0, z1 in self._segmentos():
            s = pymunk.Segment(corpo, a, b, r)
            s.friction = 0.5
            s.elasticity = 0.0
            s.filter = filtro_baixa
            s.altura_mm = 1e9
            s.objeto = None
            s.robo = self.robo
            s.dedo = True              # os raios dos sensores não enxergam a garra
            space.add(s)
            self.partes.append(s)

    def _anda(self, atual, chave):
        alvo = self.robo.servos.get(chave, 200)
        if alvo > 180:
            return atual                # servo solto: fica onde está (o elástico segura o braço)
        passo = self.vel_servo * self.robo.mundo.DT
        if abs(alvo - atual) <= passo:
            return float(alvo)
        return atual + math.copysign(passo, alvo - atual)

    def passo(self):
        """Antes do passo da física: servos, peças, prender e soltar."""
        m = self.robo.mundo
        self.a_abre = self._anda(self.a_abre, self.servo_abre)
        self.a_sobe = self._anda(self.a_sobe, self.servo_sobe)
        if self.cam:
            self.a_cam = self._anda(self.a_cam, self.servo_cam)
        for s, (a, b, r, z0, z1) in zip(self.partes, self._segmentos()):
            s.unsafe_set_endpoints(a, b)
            s.filter = pymunk.ShapeFilter(categories=self.cat, mask=m.mascara_altura(z0))
        if self.partes:
            m.space.reindex_shapes_for_body(self.robo.corpo)
        if self.preso is None:
            o = self._objeto_entre_os_dedos()
            if o is not None:
                p = self.robo.corpo.world_to_local(o.corpo.position)
                self.preso = o
                self.lx_preso = p.x
                self.larg_preso = self._largura(o)
                self.dz_preso = max(0.0, o.z - self.altura())
                self.dang_preso = o.corpo.angle - self.robo.corpo.angle
                m.prende(self.robo, o, self)
        elif self.abertura_servo() > self.larg_preso + 6.0:
            o, self.preso = self.preso, None
            m.solta(self.robo, o, self.posicao_preso(), max(0.0, self.altura() + self.dz_preso))

    def _largura(self, o):
        """Largura do objeto na direção em que os dedos fecham (y do robô)."""
        d = o.corpo.angle - self.robo.corpo.angle
        return abs(o.tam[0] * math.sin(d)) + abs(o.tam[1] * math.cos(d))

    def _objeto_entre_os_dedos(self):
        """Objeto livre que os dedos acabaram de apertar: no meio deles, na altura deles, com a
        abertura já na largura dele."""
        corpo = self.robo.corpo
        px, pz = self.pivo()
        ab = self.abertura_servo()
        z0 = pz + self.dedo_z0
        for o in self.robo.mundo.objetos:
            if o.estado != 'livre':
                continue
            if z0 > o.altura - 8.0:                   # os dedos pegam pelo menos 8 mm do objeto
                continue
            larg = self._largura(o)
            if larg > self.ab_max or ab > larg + 3.0:
                continue
            p = corpo.world_to_local(o.corpo.position)
            if not (px + self.dedo_x0 + 6.0 <= p.x <= px + self.dedo_x1 - 4.0):
                continue
            if abs(p.y) <= 8.0:
                return o
        return None

    def posicao_preso(self):
        px, _ = self.pivo()
        lx = max(px + self.dedo_x0 + 6.0, min(self.lx_preso, px + self.dedo_x1 - 4.0))
        return self.robo.corpo.local_to_world((lx, 0.0))

    def segue(self):
        """Depois do passo da física: o objeto preso acompanha a cabeça."""
        o = self.preso
        if o is None:
            return
        b = o.corpo
        b.position = self.posicao_preso()
        b.angle = self.robo.corpo.angle + self.dang_preso
        b.velocity = (0, 0)
        b.angular_velocity = 0
        o.z = max(0.0, self.altura() + self.dz_preso)
        o.atualiza_altura()
        b.space.reindex_shapes_for_body(b)

    # ---------------------------------------------------------------- janela
    def desenho(self):
        """Traços para a janela, no referencial do robô: [(a, b, espessura_mm, no_alto)]."""
        alto = self.altura() > 60.0
        return [(a, b, 2 * r, alto) for a, b, r, z0, z1 in self._segmentos()]

    def info(self):
        return {'nome': self.nome, 'abertura': self.abertura(), 'altura': self.altura(),
                'barra': self.ang_barra(), 'inclinacao': self.inclinacao(),
                'preso': self.preso.cor if self.preso else None}


def cria_garras(robo, cfg):
    """Garras do robo.json: "garras" (lista) ou "garra" (uma só)."""
    lista = cfg.get('garras')
    if lista is None:
        lista = [cfg['garra']] if cfg.get('garra') else []
    return [GarraPinca(robo, c) for c in lista]
