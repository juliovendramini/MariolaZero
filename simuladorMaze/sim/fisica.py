"""Física 2D do robô (pymunk) + modelo dos sensores.

Unidades internas: mm, kg, s, rad. Ângulo do robô anti-horário a partir do leste.
Referencial do robô: x para frente, y para a esquerda.
"""

import math
import random
import threading

import pymunk
from pymunk import Vec2d

from . import mapa as M

G = 9810.0  # mm/s²
CAT_PAREDE = 0b001
CAT_ROBO = 0b010
CAT_SENSOR = 0b100

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
class Motor:
    """Modelo de um motor DC com encoder + controlador da placa (PID de velocidade)."""

    def __init__(self, cfg, padrao, diametro):
        p = dict(padrao)
        p.update(cfg)
        self.cfg = p
        self.nome = p['nome']
        self.x = float(p['x'])
        self.y = float(p['y'])
        self.sentido = 1 if p.get('sentido', 1) >= 0 else -1
        if 'contagens_por_volta' in p:
            self.cpr = float(p['contagens_por_volta'])
        else:
            self.cpr = float(p['pulsos_encoder_motor']) * float(p['reducao']) * float(p.get('multiplicador', 1))
        self.rpm_max = float(p['rpm_max'])
        self.tau = float(p['tau_s'])
        self.forca_max = float(p['forca_max_N']) * 1000.0   # kg·mm/s²
        self.diametro = diametro
        self.calibracao = [int(p.get('calibracao', 208)), -int(p.get('calibracao', 208))]
        self.reset()

    def reset(self):
        self.modo = 'pid'
        self.cmd = 0.0
        self.alvo = 0
        self.inicio = 0.0
        self.travado = False
        self.vel = 0.0          # contagens/s, sinal do motor
        self.contagem = 0.0
        self.parou_alvo = False

    @property
    def vmax(self):
        return self.rpm_max / 60.0 * self.cpr

    def comando(self, modo, valor, alvo=0):
        self.modo = modo
        self.cmd = float(valor)
        self.alvo = int(abs(alvo))
        self.inicio = self.contagem
        self.parou_alvo = False

    def alvo_vel(self):
        return max(-1.2, min(1.2, self.cmd / 100.0)) * self.vmax

    def atualiza_controle(self, dt):
        t = self.alvo_vel()
        if t == 0 and self.travado:
            self.vel = 0.0
            return
        k = min(1.0, dt / self.tau)
        self.vel += (t - self.vel) * k

    def livre(self):
        return self.cmd == 0 and not self.travado and abs(self.vel) < 0.03 * self.vmax

    def vel_superficie(self):
        """mm/s da superfície da roda no sentido 'para frente' do robô."""
        return self.vel / self.cpr * math.pi * self.diametro * self.sentido

    def set_vel_superficie(self, v):
        self.vel = v / (math.pi * self.diametro) * self.cpr * self.sentido

    def integra(self, dt):
        self.contagem += self.vel * dt
        if self.alvo > 0 and abs(self.contagem - self.inicio) >= self.alvo:
            self.cmd = 0.0
            self.alvo = 0
            self.parou_alvo = True
            if self.travado:
                self.vel = 0.0

    def estado(self):
        if abs(self.vel) < 0.02 * self.vmax and self.cmd == 0:
            return 0
        return 1 if self.vel > 0 else 2

    def contagem_int(self):
        return int(math.floor(self.contagem))


# --------------------------------------------------------------------------- mundo
class Mundo:
    DT = 1.0 / 240.0

    def __init__(self, mapa, cfg, semente=None):
        self.lock = threading.RLock()
        self.cfg = cfg
        self.rng = random.Random(semente)
        self.mapa = mapa
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
        self.motores = [Motor(mc, cfg['motor_padrao'], self.diametro) for mc in cfg['motores']]
        xs = [m.x for m in self.motores]
        ys = [m.y for m in self.motores]
        self.eixo_frente, self.eixo_tras = max(xs), min(xs)
        self.lado_esq, self.lado_dir = max(ys), min(ys)
        self.por_mariola = {}
        self.por_placa = {}
        for m in self.motores:
            if m.cfg['controlador'] == 'mariola':
                self.por_mariola[int(m.cfg['canal'])] = m
            else:
                self.por_placa[(m.cfg['porta'], int(m.cfg['id']))] = m
        self.ordem = 0
        # estados auxiliares
        self.yaw_ref = 0.0
        self.deriva = 0.0
        self.eventos_incl = []     # (t0, dur, pitch_graus, roll_graus)
        self.no_ar = [0.0] * len(self.motores)
        self.pos_ant_rodas = None
        self.detritos = {}
        self.leds = [(0, 0, 0)] * 11
        self.gpio_saida = {}
        self.botoes_gui = set()    # pinos "apertados" pela interface
        self.teclas_teclado = set()
        self.kits = []             # {'x','y','t','lado'}
        self.kits_restantes = int(cfg['kits']['capacidade'])
        self.raios = {}            # nome -> (p0, p1, dist, t)
        self.debug = {'pose': None, 'texto': '', 'marcas': []}
        self.servos = {}
        self.construir()

    # ---------------------------------------------------------------- construção
    def construir(self):
        """(Re)cria o espaço físico a partir do mapa, mantendo a pose do robô."""
        pose = None
        if self.corpo is not None:
            pose = (self.corpo.position.x, self.corpo.position.y, self.corpo.angle)
        sp = pymunk.Space()
        sp.iterations = 25
        sp.gravity = (0, 0)
        atr = float(self.cfg['rodas'].get('atrito_parede', 0.25))
        self.formas_parede = []
        for (x1, y1, x2, y2) in self.mapa.segmentos_parede():
            s = pymunk.Segment(sp.static_body, (x1, y1), (x2, y2), M.MEIA_PAREDE)
            s.friction = atr
            s.elasticity = 0.0
            s.filter = pymunk.ShapeFilter(categories=CAT_PAREDE)
            sp.add(s)
            self.formas_parede.append(s)
        momento = pymunk.moment_for_box(self.massa, (self.L, self.W))
        corpo = pymunk.Body(self.massa, momento)
        forma = pymunk.Poly.create_box(corpo, (self.L, self.W), radius=1.5)
        forma.friction = atr
        forma.elasticity = 0.0
        forma.filter = pymunk.ShapeFilter(categories=CAT_ROBO, mask=CAT_PAREDE)
        sp.add(corpo, forma)
        # sensores do para-choque (segmentos finos logo à frente da face dianteira)
        pc = self.cfg['para_choque']
        curso = float(pc.get('curso_mm', 2.0))
        self.sensores_pc = {}
        for lado in ('esquerdo', 'direito'):
            c = pc[lado]
            x = self.L / 2 + curso / 2
            s = pymunk.Segment(corpo, (x, c['y_min']), (x, c['y_max']), curso / 2 + 0.5)
            s.sensor = True
            s.filter = pymunk.ShapeFilter(categories=CAT_SENSOR, mask=CAT_PAREDE)
            sp.add(s)
            self.sensores_pc[pino_num(c['pino'])] = s
        self.space = sp
        self.corpo = corpo
        self.forma = forma
        if pose:
            self.posicionar(*pose)
        else:
            l, c = self.mapa.inicio
            x, y = self.mapa.centro(l, c)
            self.posicionar(x, y, M.ANGULO_DIR[self.mapa.inicio_dir])
        self.detritos = {}
        for (l, c), lad in self.mapa.ladrilhos.items():
            if lad.get('terreno') == 'detritos':
                self.detritos[(l, c)] = self.mapa.detritos_iniciais(l, c)

    def posicionar(self, x, y, ang):
        self.corpo.position = (x, y)
        self.corpo.angle = ang
        self.corpo.velocity = (0, 0)
        self.corpo.angular_velocity = 0
        self.space.reindex_shapes_for_body(self.corpo)
        self.pos_ant_rodas = None
        for m in self.motores:
            m.vel = 0.0

    def pose(self):
        p = self.corpo.position
        return p.x, p.y, self.corpo.angle

    def para_tudo(self):
        for m in self.motores:
            m.cmd = 0.0
            m.alvo = 0
            m.vel = 0.0
        self.leds = [(0, 0, 0)] * 11

    def reset_rodada(self):
        for m in self.motores:
            m.reset()
        self.leds = [(0, 0, 0)] * 11
        self.kits = []
        self.kits_restantes = int(self.cfg['kits']['capacidade'])
        self.deriva = 0.0
        self.yaw_ref = self.corpo.angle
        self.eventos_incl = []
        self.debug = {'pose': None, 'texto': '', 'marcas': []}
        self.detritos = {}
        for (l, c), lad in self.mapa.ladrilhos.items():
            if lad.get('terreno') == 'detritos':
                self.detritos[(l, c)] = self.mapa.detritos_iniciais(l, c)

    # ---------------------------------------------------------------- terreno
    def _lad_em(self, x, y):
        return self.mapa.ladrilho_em(x, y)

    def _fator_tracao(self, x, y):
        lc = self._lad_em(x, y)
        if lc is None:
            return 1.0
        ter = self.mapa.terreno(*lc)
        if ter == 'escada':
            return float(self.cfg['terreno']['escada_atrito'])
        if ter == 'detritos':
            return 0.85
        return 1.0

    def altura(self, x, y):
        lc = self._lad_em(x, y)
        if lc is None:
            return 0.0
        if self.mapa.terreno(*lc) == 'escada':
            return self.mapa.perfil_escada(lc[0], lc[1], x, y)
        return 0.0

    def _solavanco(self, i, giro, pitch):
        m = self.motores[i]
        self.corpo.angle += math.radians(self.rng.gauss(0, giro))
        frente = 1 if m.x > 0 else -1
        lado = 1 if m.y > 0 else -1
        self.eventos_incl.append((self.t, 0.12, frente * pitch, lado * pitch * 0.5))
        self.no_ar[i] = float(self.cfg['terreno']['tempo_no_ar_s'])

    def _terreno(self):
        ter = self.cfg['terreno']
        atuais = [self.corpo.local_to_world((m.x, m.y)) for m in self.motores]
        if self.pos_ant_rodas is not None:
            for i, (p0, p1) in enumerate(zip(self.pos_ant_rodas, atuais)):
                lc = self._lad_em(p1.x, p1.y)
                if lc is None:
                    continue
                t = self.mapa.terreno(*lc)
                zona = self.mapa.zona(*lc)
                k = 2.0 if zona else 1.0
                if t == 'lombada':
                    for (x1, y1, x2, y2) in self.mapa.linhas_lombada(*lc):
                        if _cruza(p0, p1, (x1, y1), (x2, y2)):
                            self._solavanco(i, ter['lombada_giro_graus'] * k, ter['lombada_pitch_graus'] * k)
                elif t == 'escada':
                    h0 = self.altura(p0.x, p0.y)
                    h1 = self.altura(p1.x, p1.y)
                    if abs(h1 - h0) > 1:
                        self._solavanco(i, ter['lombada_giro_graus'] * 0.7, 0)
                elif t == 'detritos':
                    for d in self.detritos.get(lc, []):
                        if _dist_ponto_seg((d[0], d[1]), p0, p1) < 9 and (p1 - p0).length > 0.01:
                            self._solavanco(i, ter['detritos_giro_graus'], ter['lombada_pitch_graus'] * 0.6)
                            dv = (p1 - p0).normalized()
                            d[0] += dv.x * 18 + self.rng.uniform(-6, 6)
                            d[1] += dv.y * 18 + self.rng.uniform(-6, 6)
        self.pos_ant_rodas = atuais
        self.eventos_incl = [e for e in self.eventos_incl if self.t - e[0] < e[1]]

    # ---------------------------------------------------------------- rodas
    def _rodas(self, dt):
        b = self.corpo
        th = b.angle
        f = Vec2d(math.cos(th), math.sin(th))
        lat = Vec2d(-math.sin(th), math.cos(th))
        n = len(self.motores)
        N = self.massa * G / n
        invm = 1.0 / self.massa
        invI = 1.0 / b.moment
        self.ordem = (self.ordem + 1) % n
        for k in range(n):
            i = (k + self.ordem) % n
            mot = self.motores[i]
            p = b.local_to_world((mot.x, mot.y))
            r = p - b.position
            if self.no_ar[i] > 0:
                self.no_ar[i] -= dt
                continue
            tf = self._fator_tracao(p.x, p.y)
            # --- lateral: pneu não escorrega de lado (até o limite de atrito)
            v = b.velocity_at_world_point(p)
            rx = r.cross(lat)
            meff = 1.0 / (invm + rx * rx * invI)
            J = -v.dot(lat) * meff
            jmax = self.mu_lat * tf * N * dt
            J = max(-jmax, min(jmax, J))
            b.apply_impulse_at_world_point(lat * J, p)
            # --- longitudinal
            v = b.velocity_at_world_point(p)
            vl = v.dot(f)
            rx = r.cross(f)
            meff = 1.0 / (invm + rx * rx * invI)
            if mot.livre():
                # roda solta: acompanha o chão, só resistência ao rolamento
                J = -vl * meff * min(1.0, 3.0 * dt)
                b.apply_impulse_at_world_point(f * J, p)
                mot.set_vel_superficie(vl)
                continue
            w = mot.vel_superficie()
            J = (w - vl) * meff
            jf = self.mu * tf * N * dt
            jm = mot.forca_max * dt
            if abs(J) <= min(jf, jm):
                b.apply_impulse_at_world_point(f * J, p)
            elif jm < jf:
                Ja = math.copysign(jm, J)
                b.apply_impulse_at_world_point(f * Ja, p)
                mot.set_vel_superficie(vl + Ja / meff)     # motor afoga: encoder segue o chão
            else:
                b.apply_impulse_at_world_point(f * math.copysign(jf, J), p)   # patina

    def passo(self, dt=None):
        dt = dt or self.DT
        for m in self.motores:
            m.atualiza_controle(dt)
        self._rodas(dt)
        self.space.step(dt)
        for m in self.motores:
            m.integra(dt)
        self._terreno()
        self.deriva += float(self.cfg['giroscopio']['deriva_graus_min']) / 60.0 * dt
        self.t += dt

    def velocidade(self):
        return self.corpo.velocity.length, abs(self.corpo.angular_velocity)

    # ---------------------------------------------------------------- sensores
    def vl53(self, idx):
        """Distância em mm (int) do VL53 de índice idx na lista de configuração."""
        sc = self.cfg['vl53'][idx]
        pr = self.cfg['vl53_params']
        b = self.corpo
        p0 = b.local_to_world((sc['x'], sc['y']))
        a0 = b.angle + math.radians(sc['angulo'])
        alcance = float(pr['alcance_mm'])
        cone = math.radians(float(pr['cone_graus']))
        filtro = pymunk.ShapeFilter(mask=CAT_PAREDE)
        melhor = None
        # raios no cone; os da borda do campo de visão só "enxergam" alvos mais perto
        # (o sinal que volta da borda do cone é fraco)
        for k, alc in ((-0.5, 0.35), (-0.25, 0.7), (0.0, 1.0), (0.25, 0.7), (0.5, 0.35)):
            a = a0 + k * cone
            p1 = p0 + Vec2d(math.cos(a), math.sin(a)) * (alcance + 200)
            q = self.space.segment_query_first(p0, p1, 0, filtro)
            if q is not None:
                d = (q.point - p0).length
                if k != 0 and d > alc * alcance:
                    continue
                if k != 0:
                    # retorno de superfície muito rasante (parede lateral do corredor) é fraco: ignora
                    u = (p1 - p0).normalized()
                    if abs(u.dot(q.normal)) < math.cos(math.radians(72)):
                        continue
                if melhor is None or d < melhor:
                    melhor = d
        fim = p0 + Vec2d(math.cos(a0), math.sin(a0)) * min(melhor or alcance, alcance)
        self.raios[sc['nome']] = (p0, fim, melhor, self.t)
        if melhor is None or melhor > alcance:
            return int(pr['fora_alcance'])
        d = melhor + float(pr.get('offset_mm', 0))
        d += self.rng.gauss(0, float(pr['ruido_mm']) + melhor * float(pr['ruido_percentual']) / 100.0)
        return max(0, int(round(d)))

    def vl53_por_canal(self, canal):
        for i, sc in enumerate(self.cfg['vl53']):
            if canal_mux(sc['mux']) == canal:
                return i
        return None

    def _inclinacao(self):
        b = self.corpo

        def h(lx, ly):
            p = b.local_to_world((lx, ly))
            return self.altura(p.x, p.y)

        hf, hr = h(self.eixo_frente, 0), h(self.eixo_tras, 0)
        hl, hd = h(0, self.lado_esq), h(0, self.lado_dir)
        pitch = math.degrees(math.atan2(hf - hr, self.eixo_frente - self.eixo_tras))
        roll = math.degrees(math.atan2(hd - hl, self.lado_esq - self.lado_dir))
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
        z = math.degrees(self.corpo.angle - self.yaw_ref) + self.deriva + self.rng.gauss(0, ruido)
        if gc.get('z_horario_positivo'):
            z = -z
        if not gc.get('z_continuo', True):
            z = (z + 180.0) % 360.0 - 180.0
        pitch, roll = self._inclinacao()
        pitch += self.rng.gauss(0, ruido)
        roll += self.rng.gauss(0, ruido)
        if gc.get('eixo_inclinacao_frente', 'x') == 'x':
            x, y = pitch, roll
        else:
            x, y = roll, pitch
        esc = float(gc['escala'])
        return [int(round(x * esc)), int(round(y * esc)), int(round(z * esc))]

    def _amostra_piso(self, lx, ly):
        b = self.corpo
        cores = self.cfg['cores_piso']
        acc = [0.0, 0.0, 0.0, 0.0, 0.0]
        pts = ((0, 0), (5, 0), (-5, 0), (0, 5), (0, -5))
        for dx, dy in pts:
            p = b.local_to_world((lx + dx, ly + dy))
            lc = self._lad_em(p.x, p.y)
            piso = self.mapa.piso(*lc) if lc else 'branco'
            c = cores.get(piso, cores['branco'])
            for k in range(4):
                acc[k] += c['rgbc'][k]
            acc[4] += c['ir']
        return [a / len(pts) for a in acc]

    def cor_bytes(self):
        cc = self.cfg['cor_reflexao']
        ruido = float(cc.get('ruido', 3))
        out = []
        for s in cc['ir']:
            v = self._amostra_piso(s['x'], s['y'])[4]
            out.append(v + self.rng.gauss(0, ruido))
        for s in cc['tcs']:
            v = self._amostra_piso(s['x'], s['y'])[:4]
            out.extend(x + self.rng.gauss(0, ruido) for x in v)
        return [max(0, min(255, int(round(x)))) for x in out]

    def para_choque(self, pino):
        s = self.sensores_pc.get(pino)
        if s is None:
            return False
        for info in self.space.shape_query(s):
            if info.shape is not None and info.shape in self.formas_parede:
                return True
        return False

    def gpio_nivel(self, pino):
        """Nível lógico de um pino de entrada (1 = ALTO/ACTIVE, 0 = BAIXO/INACTIVE)."""
        if pino in self.gpio_saida:
            return self.gpio_saida[pino]
        apertado = False
        if pino in self.sensores_pc:
            apertado = self.para_choque(pino)
        if pino in self.botoes_gui:
            apertado = True
        return 0 if apertado else 1

    # ---------------------------------------------------------------- vítimas e kits
    def vitimas_visiveis(self, camera=None):
        res = []
        b = self.corpo
        filtro = pymunk.ShapeFilter(mask=CAT_PAREDE)
        for cam in self.cfg['cameras']:
            if camera is not None and cam['nome'] != camera:
                continue
            if not self.camera_iluminada(cam['nome']):
                continue
            pc = b.local_to_world((cam['x'], cam['y']))
            a = b.angle + math.radians(cam['angulo'])
            dirc = Vec2d(math.cos(a), math.sin(a))
            for idx, v in enumerate(self.mapa.vitimas):
                (vx, vy), (nx, ny) = self.mapa.ponto_vitima(v)
                q = Vec2d(vx, vy)
                d = q - pc
                dist = d.length
                if dist < 1 or dist > cam['alcance_mm']:
                    continue
                cosang = d.dot(dirc) / dist
                if cosang < math.cos(math.radians(cam['fov'] / 2)):
                    continue
                # a vítima precisa estar de frente para a câmera
                if Vec2d(nx, ny).dot(-d / dist) < math.cos(math.radians(75)):
                    continue
                alvo = q + Vec2d(nx, ny) * 3
                hit = self.space.segment_query_first(pc, alvo, 0, filtro)
                if hit is not None and (hit.point - pc).length < dist - 15:
                    continue
                res.append((dist, cam['nome'], idx, v))
        res.sort(key=lambda r: r[0])
        return res

    def deposita_kit(self, qtd, lado):
        qtd = int(qtd)
        if qtd <= 0 or self.kits_restantes <= 0:
            return 0
        qtd = min(qtd, self.kits_restantes)
        b = self.corpo
        sinal = 1 if lado == 'esquerda' else -1
        ly = sinal * (self.W / 2 + float(self.cfg['kits']['distancia_lateral_mm']))
        for k in range(qtd):
            p = b.local_to_world((-15 + 30 * k, ly))
            self.kits.append({'x': p.x, 'y': p.y, 't': self.t, 'lado': lado})
        self.kits_restantes -= qtd
        return qtd

    def indices_led(self, grupo):
        return [i for i in self.cfg.get('leds', {}).get(grupo, []) if 0 <= i < len(self.leds)]

    def cor_grupo(self, grupo):
        idx = self.indices_led(grupo)
        if not idx:
            return (0, 0, 0)
        return max((self.leds[i] for i in idx), key=sum)

    @property
    def led(self):
        """Cor dos LEDs de indicação de vítima."""
        if 'vitima' not in self.cfg.get('leds', {}):
            return max(self.leds, key=sum)
        return self.cor_grupo('vitima')

    def led_aceso(self):
        alvo = self.cfg.get('led_vitima', 'mariola_rgb')
        if alvo.startswith('gpio:'):
            return self.gpio_saida.get(pino_num(alvo[5:]), 0) == 1
        return any(self.led)

    def camera_iluminada(self, nome):
        if not self.cfg.get('deteccao', {}).get('exige_iluminacao', False):
            return True
        if not self.indices_led('camera_' + nome):
            return True
        return any(self.cor_grupo('camera_' + nome))

    def contorno_robo(self):
        b = self.corpo
        hl, hw = self.L / 2, self.W / 2
        return [b.local_to_world(p) for p in ((hl, hw), (hl, -hw), (-hl, -hw), (-hl, hw))]


# --------------------------------------------------------------------------- utilidades
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


def dist_ponto_poligono(p, pts):
    """Distância de um ponto ao polígono (0 se dentro)."""
    dentro = False
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        if (a[1] > p[1]) != (b[1] > p[1]):
            xi = a[0] + (p[1] - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
            if p[0] < xi:
                dentro = not dentro
    if dentro:
        return 0.0
    return min(_dist_ponto_seg(p, pts[i], pts[(i + 1) % len(pts)]) for i in range(n))
