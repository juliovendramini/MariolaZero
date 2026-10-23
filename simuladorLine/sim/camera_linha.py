"""Câmera de linha: câmera USB embaixo do robô, olhando reto para o chão (para seguir linha com OpenCV).

Não é a câmera das vítimas (essa continua sendo o stub do módulo visao). Esta gera a imagem de
verdade: o programa abre com cv2.VideoCapture('/dev/video_usb2') e recebe quadros BGR como no robô.

Como a câmera olha reto para baixo e o piso é plano, cada pixel corresponde a um ponto do chão
(câmera pinhole, sem distorção de lente). As rodas da frente aparecem nas bordas da imagem: para
cada pixel o raio que sai da câmera é testado contra as rodas (cilindros) e contra as "tampas"
(placas embaixo do robô, como a do sensor de linha). A luz vem só dos LEDs do robô (a luz de fora
não entra no modelo):

* sem "leds" no json: luz igual em tudo, só um pouco mais fraca nos cantos;
* com "leds": uma fita de N LEDs. Cada LED ilumina o chão caindo com a distância (Lambert) e faz
  um reflexo onde o ângulo do LED e o da câmera batem (Blinn-Phong): a fita isolante e a fita prata
  brilham e estouram nesses pontos, o branco fosco quase não. Com "difusor", cada LED vira uma
  faixa de luz (várias fontes fracas), passa só parte da luz e os reflexos ficam largos e fracos.
  "exposicao": "auto" (a câmera compensa a luz e o ruído cresce junto) ou um número (fixa: com
  menos luz, a imagem escurece).

Divisão do trabalho: o simulador só diz o material do chão em cada pixel (é o que depende da
pista); a cor, as rodas, a luz, o ruído e o desfoque são feitos aqui, no processo do programa
(o mesmo código monta a imagem que aparece na janela do simulador).
"""

import base64
import math
import zlib

import numpy as np

from .ladrilhos import COR_MATERIAL, MATERIAIS

PADRAO = {
    'x': 50, 'y': 0,                # mm, no referencial do robô (x para frente, y para a esquerda)
    'altura_mm': 106,                # lente até o chão
    'fov_horizontal_graus': 76,
    'rotacao_graus': 0,              # 0 = frente do robô no topo da imagem; gira no sentido horário
    'largura_px': 320, 'altura_px': 240, 'fps': 30,
    'dispositivos': ['/dev/video_usb2'],
    'brilho': 0.92,                  # quanto da cor do piso chega (exposição da câmera)
    'vinheta': 0.18,                 # perda de luz nos cantos (0 = luz igual em tudo)
    'ruido': 2.5,                    # desvio do ruído de cada pixel (0-255)
    'desfoque': True,                # foco um pouco mole (média 3x3)
    'tampas': [],                    # placas embaixo do robô: {x0, x1, y0, y1, z, cor:[r,g,b]}
    'cor_roda': [28, 28, 30], 'cor_lateral_roda': [52, 52, 56], 'cor_cubo_roda': [140, 140, 145],
}

LEDS_PADRAO = {
    'quantidade': 8,
    'x': None,                       # mm (None = na mesma linha da câmera)
    'y_inicio': -80, 'y_fim': 80,    # a fita atravessa o robô de um lado ao outro (caixa de 170 mm)
    'altura_mm': None,               # None = na altura da câmera
    'difusor': False,
    'transmissao_difusor': 0.55,     # parte da luz que passa pelo difusor
    'largura_difusor_mm': 12,        # largura da faixa de luz com difusor
    'reflexos': True,                # False = chão todo fosco (sem pontos estourados)
    'exposicao': 'auto',             # 'auto' ou multiplicador fixo (1 = certo para a fita sem difusor)
}

# reflexo de cada material: (parte da luz refletida como espelho, rugosidade em radianos).
# Rugosidade pequena = reflexo pequeno e forte. Fita isolante: ~5% como espelho, bem lisa;
# fita prata: metal escovado; papel/lona: quase fosco.
ESPECULAR = {
    'branco': (0.03, 0.30), 'preto': (0.05, 0.05), 'verde': (0.03, 0.25), 'vermelho': (0.03, 0.25),
    'prata': (0.60, 0.10), 'madeira': (0.02, 0.40), 'fora': (0.0, 1.0),
}
TAMANHO_LED_MM = 1.5                 # LED sem difusor: quase um ponto


def config(cfg_robo):
    """Configuração da câmera de linha do robô (PADRAO + "camera_linha" do robo.json) ou None."""
    c = cfg_robo.get('camera_linha')
    if not c:
        return None
    out = dict(PADRAO)
    out.update({k: v for k, v in c.items() if not k.startswith('_')})
    return out


class Geometria:
    """Tudo que não muda de um quadro para o outro: o ponto do chão de cada pixel (referencial do
    robô), o que as rodas e as tampas cobrem, e a luz dos LEDs."""

    def __init__(self, cfg_robo, largura, altura):
        c = config(cfg_robo)
        self.c = c
        self.w, self.h = int(largura), int(altura)
        H = float(c['altura_mm'])
        cx, cy = float(c['x']), float(c['y'])
        f = (self.w / 2.0) / math.tan(math.radians(float(c['fov_horizontal_graus'])) / 2.0)
        a = math.radians(float(c['rotacao_graus']))
        cima = np.array([math.cos(a), -math.sin(a)])          # direção do topo da imagem no chão
        direita = np.array([-math.sin(a), -math.cos(a)])      # direção da direita da imagem
        u = np.arange(self.w) + 0.5 - self.w / 2.0
        v = self.h / 2.0 - (np.arange(self.h) + 0.5)
        uu, vv = np.meshgrid(u, v)                             # (h, w)
        gx = cx + H / f * (vv * cima[0] + uu * direita[0])
        gy = cy + H / f * (vv * cima[1] + uu * direita[1])
        self.chao = np.stack([gx, gy], axis=-1).reshape(-1, 2).astype(np.float64)
        self.mm_por_px = H / f

        # rodas e tampas: o que estiver mais perto da câmera ao longo do raio tapa o chão
        n = self.w * self.h
        t_min = np.full(n, np.inf)
        cor = np.zeros((n, 3))
        dx, dy = gx.ravel() - cx, gy.ravel() - cy
        rodas = cfg_robo.get('rodas', {})
        R = float(rodas.get('diametro', 70)) / 2.0
        L = float(rodas.get('largura', 15))
        for m in cfg_robo.get('motores', []):
            if 'x' not in m or 'y' not in m:
                continue
            t, lado, cubo = self._raio_roda(cx, cy, H, dx, dy, float(m['x']), float(m['y']), R, L)
            perto = t < t_min
            t_min[perto] = t[perto]
            cor[perto] = c['cor_roda']
            cor[perto & lado] = c['cor_lateral_roda']
            cor[perto & lado & cubo] = c['cor_cubo_roda']
        for tp in c.get('tampas', []):
            z = float(tp['z'])
            if z >= H:
                continue
            t = (H - z) / H
            px, py = cx + t * dx, cy + t * dy
            dentro = ((px >= tp['x0']) & (px <= tp['x1']) & (py >= tp['y0']) & (py <= tp['y1']))
            perto = dentro & (t < t_min)
            t_min[perto] = t
            cor[perto] = tp.get('cor', [20, 70, 30])
        self.tapado = np.isfinite(t_min).reshape(self.h, self.w)
        # profundidade: as partes mais altas das rodas ficam mais perto dos LEDs (mais claras)
        prof = np.where(np.isfinite(t_min), t_min, 1.0).reshape(self.h, self.w)
        self.cor_tapado = (cor.reshape(self.h, self.w, 3) * (1.25 - 0.35 * prof[..., None]))

        r2 = (uu / (self.w / 2.0)) ** 2 * 0.64 + (vv / (self.h / 2.0)) ** 2 * 0.36   # 1 no canto
        self.luz = float(c['brilho']) * (1.0 - float(c['vinheta']) * r2)
        self.cam = (cx, cy, H)
        self.leds = None
        if c.get('leds'):
            self.leds = dict(LEDS_PADRAO)
            self.leds.update({k: v for k, v in c['leds'].items() if not k.startswith('_')})
        self._luz_pronta = False
        self.ganho_ruido = 1.0

    def prepara_luz(self):
        """Calcula a luz dos LEDs em cada pixel (uma vez por resolução).

        Luz difusa: cada LED virado para baixo ilumina o chão com cos^2/d^2. Reflexo: o chão liso
        mostra a "imagem" de cada LED no ponto de espelho (entre a câmera e o LED). A imagem é uma
        mancha gaussiana: o tamanho vem da rugosidade do material e do tamanho da fonte (LED ~ponto;
        com difusor, a faixa do difusor), e a energia se espalha nela: fonte maior = reflexo mais
        largo e mais fraco. No centro da mancha o reflexo vale ks * E_led / (2 sigma^2) (sigma em
        radianos), na mesma escala da luz difusa vezes a cor."""
        if self._luz_pronta:
            return
        self._luz_pronta = True
        if self.leds is None:
            return
        L = self.leds
        cx, cy, H = self.cam
        gx = self.chao[:, 0].astype(np.float32)
        gy = self.chao[:, 1].astype(np.float32)
        n_led = int(L['quantidade'])
        lx = float(cx if L['x'] is None else L['x'])
        z = float(H if L['altura_mm'] is None else L['altura_mm'])
        y0, y1 = float(L['y_inicio']), float(L['y_fim'])
        ys = np.linspace(y0, y1, n_led) if n_led > 1 else np.array([(y0 + y1) / 2])
        passo = (y1 - y0) / (n_led - 1) if n_led > 1 else 10.0
        difusor = bool(L['difusor'])
        t = float(L['transmissao_difusor']) if difusor else 1.0

        D = H * z / (H + z)                  # rugosidade (rad) -> tamanho da mancha no chão (mm)
        f = H / (H + z)                      # tamanho da fonte -> tamanho da mancha no chão
        if difusor:                          # faixa de luz: atravessa o difusor e emenda nos vizinhos
            src_x, src_y = float(L['largura_difusor_mm']) / 2.5 * f, passo * 0.6 * f
        else:
            src_x = src_y = TAMANHO_LED_MM / 2.0 * f
        reflexos = bool(L['reflexos'])

        E = np.zeros_like(gx)
        R = {nome: np.zeros_like(gx) for nome in MATERIAIS} if reflexos else {}
        for ly in ys:
            dx, dy = lx - gx, ly - gy
            d2 = dx * dx + dy * dy + z * z
            e = (z * z / d2) / d2                            # LED virado para baixo (Lambert)
            E += e
            if not reflexos:
                continue
            px, py = (cx * z + lx * H) / (H + z), (cy * z + ly * H) / (H + z)   # ponto de espelho
            qx2, qy2 = (gx - px) ** 2, (gy - py) ** 2
            for nome, (ks, sig) in ESPECULAR.items():
                if ks <= 0:
                    continue
                sx = math.hypot(sig * D, src_x)
                sy = math.hypot(sig * D, src_y)
                R[nome] += (ks * t * D * D / (2 * sx * sy)) * e * np.exp(-qx2 / (2 * sx * sx) - qy2 / (2 * sy * sy))

        # exposição pela parte clara da imagem (90% dos pixels do chão com menos luz que isso): o
        # branco no meio fica no "brilho" e as bordas, mais longe dos LEDs, escurecem
        livre = ~self.tapado.ravel()
        E_ref_padrao = float(np.percentile(E[livre], 90))    # a fita sem difusor, exposição 1
        E = E * t
        if L['exposicao'] == 'auto':
            E_ref = float(np.percentile(E[livre], 90))       # a câmera compensa a luz que tem
        else:
            E_ref = E_ref_padrao / float(L['exposicao'])
        self.ganho_ruido = max(1.0, E_ref_padrao / E_ref)
        self._difusa = (E / E_ref).reshape(self.h, self.w, 1).astype(np.float32)
        n = self.w * self.h
        self._reflexo = np.zeros((len(MATERIAIS), n), np.float32)
        for k, nome in enumerate(MATERIAIS):
            if nome in R:
                self._reflexo[k] = R[nome] / E_ref * 255.0
        self._idx = np.arange(n)

    @staticmethod
    def _raio_roda(cx, cy, H, dx, dy, wx, wy, R, L):
        """Raio P(t) = câmera + t * (chão - câmera), t de 0 (câmera) a 1 (chão), contra a roda
        (cilindro de eixo paralelo a y, centro em (wx, wy, R)). Devolve t da entrada (inf se não
        bate), se entrou pela lateral e se a lateral foi no cubo."""
        n = len(dx)
        t0 = np.zeros(n)
        t1 = np.ones(n)
        lo, hi = wy - L / 2.0, wy + L / 2.0
        com_dy = np.abs(dy) > 1e-9
        ta = np.where(com_dy, (lo - cy) / np.where(com_dy, dy, 1.0), -np.inf)
        tb = np.where(com_dy, (hi - cy) / np.where(com_dy, dy, 1.0), np.inf)
        dentro_y = (cy >= lo) & (cy <= hi)
        ta = np.where(com_dy, ta, np.where(dentro_y, -np.inf, np.inf))
        tb = np.where(com_dy, tb, np.where(dentro_y, np.inf, -np.inf))
        ty0, ty1 = np.minimum(ta, tb), np.maximum(ta, tb)
        # disco no plano x-z: (cx + t dx - wx)^2 + (H - t H - R)^2 <= R^2
        A = dx * dx + H * H
        B = 2.0 * (dx * (cx - wx) - H * (H - R))
        C = (cx - wx) ** 2 + (H - R) ** 2 - R * R
        disc = B * B - 4 * A * C
        ok = disc >= 0
        raiz = np.sqrt(np.where(ok, disc, 0.0))
        td0 = (-B - raiz) / (2 * A)
        td1 = (-B + raiz) / (2 * A)
        ent = np.maximum.reduce([t0, ty0, td0])
        sai = np.minimum.reduce([t1, ty1, td1])
        bate = ok & (ent <= sai)
        t = np.where(bate, ent, np.inf)
        lado = bate & (ty0 >= td0)
        # cubo: perto do centro da roda na lateral
        px = cx + ent * dx
        pz = H - ent * H
        cubo = (px - wx) ** 2 + (pz - R) ** 2 < (0.38 * R) ** 2
        return t, lado, cubo


PALETA = np.zeros((256, 3), np.float32)       # cor BGR de cada material (o OpenCV usa BGR)
for _mat, _rgb in COR_MATERIAL.items():
    PALETA[_mat] = _rgb[::-1]


def _media3(a, eixo):
    n = a.shape[eixo]
    p = np.concatenate([a.take([0], eixo), a, a.take([n - 1], eixo)], axis=eixo)
    return (p.take(range(0, n), eixo) + p.take(range(1, n + 1), eixo) + p.take(range(2, n + 2), eixo)) / 3.0


def compoe(geo, mats, rng=None):
    """Imagem BGR (h, w, 3) uint8 a partir do material do chão em cada pixel."""
    if not hasattr(geo, '_tapado_luz'):
        geo.prepara_luz()
        geo._luz3 = geo.luz[..., None].astype(np.float32)
        geo._tapado_luz = (geo.cor_tapado * geo._luz3).astype(np.float32)
        if geo.leds is not None:
            geo._luz3 = geo._luz3 * geo._difusa
    img = PALETA[mats.reshape(geo.h, geo.w)] * geo._luz3
    if geo.leds is not None and geo.leds['reflexos']:
        img += (geo._reflexo[mats, geo._idx].reshape(geo.h, geo.w) * geo.luz)[..., None]
    img[geo.tapado] = geo._tapado_luz[geo.tapado]
    if geo.c.get('desfoque'):
        try:
            import cv2
            img = cv2.blur(img, (3, 3), borderType=cv2.BORDER_REPLICATE)
        except ImportError:
            img = _media3(_media3(img, 0), 1)
    r = float(geo.c.get('ruido', 0)) * geo.ganho_ruido      # menos luz + exposição automática = mais ruído
    if r > 0 and rng is not None:
        img += rng.standard_normal(img.shape, dtype=np.float32) * np.float32(r)
    img += np.float32(0.5)
    return np.clip(img, 0, 255, out=img).astype(np.uint8)


def codifica(mats):
    return base64.b64encode(zlib.compress(np.ascontiguousarray(mats, np.uint8).tobytes(), 1)).decode('ascii')


def decodifica(s, n):
    return np.frombuffer(zlib.decompress(base64.b64decode(s)), np.uint8)[:n]
