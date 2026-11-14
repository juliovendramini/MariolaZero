"""Câmera do robô de casa: desenha em 3D o que a lente vê (piso, paredes, móveis, a caixa, os
objetos e os dedos da própria garra) e devolve a imagem BGR, como o OpenCV.

Usado dos dois lados: no processo do programa (fake_hw/camera.py, o cv2.VideoCapture falso) e na
janela do simulador (tecla C). O servidor manda só o que muda (pose da lente e caixas dos objetos e
da garra); os sólidos fixos vêm da casa.

É um desenho simples: caixas de cor chapada com luz difusa, z-buffer, lente sem distorção e um
pouco de ruído. Não tem sombra, reflexo nem desfoque.
"""

import math

import numpy as np

from .casa import Casa, TETO

PERTO = 12.0          # mm: plano de corte da frente da lente
LUZ = np.array([0.35, 0.25, 0.90])
LUZ = LUZ / np.linalg.norm(LUZ)
AMBIENTE = 0.58


def campo_de_visao(cam_cfg):
    """(fov horizontal, fov vertical) em graus a partir do fov da diagonal e da proporção."""
    diag = float(cam_cfg.get('fov_diagonal', 76.0))
    px, py = cam_cfg.get('proporcao', [4, 3])
    t = math.tan(math.radians(diag / 2)) / math.hypot(px, py)
    return 2 * math.degrees(math.atan(t * px)), 2 * math.degrees(math.atan(t * py))


def _faces_caixa(cx, cy, ang, sx, sy, z0, z1, rgb):
    """As 6 faces de uma caixa: [(4 vértices no mundo, normal, cor)]."""
    ca, sa = math.cos(ang), math.sin(ang)
    hx, hy = sx / 2, sy / 2
    cant = [(cx + lx * ca - ly * sa, cy + lx * sa + ly * ca) for lx, ly in ((hx, hy), (-hx, hy), (-hx, -hy), (hx, -hy))]
    cor = np.array(rgb, dtype=float)
    faces = []
    topo = np.array([(x, y, z1) for x, y in cant])
    faces.append((topo, np.array([0.0, 0.0, 1.0]), cor))
    if z0 > 1.0:
        faces.append((np.array([(x, y, z0) for x, y in cant[::-1]]), np.array([0.0, 0.0, -1.0]), cor))
    for i in range(4):
        a, b = cant[i], cant[(i + 1) % 4]
        n = np.array([b[1] - a[1], -(b[0] - a[0]), 0.0])
        nn = np.linalg.norm(n)
        if nn < 1e-9:
            continue
        n = n / nn                                   # cantos em sentido anti-horário: (dy, -dx) aponta para fora
        faces.append((np.array([(a[0], a[1], z0), (b[0], b[1], z0), (b[0], b[1], z1), (a[0], a[1], z1)]), n, cor))
    return faces


def _sombreia(cor, n):
    k = AMBIENTE + (1.0 - AMBIENTE) * max(0.0, float(n @ LUZ))
    return np.clip(cor * k, 0, 255)


class Cena:
    """Os sólidos fixos da casa, já em faces."""

    def __init__(self, casa):
        if isinstance(casa, dict):
            casa = Casa.de_dict(casa)
        self.casa = casa
        self.fixas = []
        for i, (ret, rgb) in enumerate(casa.chao()):
            z = 0.2 * i                                # as faixas ficam um fio acima do piso
            v = np.array([(ret[0], ret[1], z), (ret[2], ret[1], z), (ret[2], ret[3], z), (ret[0], ret[3], z)], dtype=float)
            self.fixas.append((v, np.array([0.0, 0.0, 1.0]), np.array(rgb, dtype=float)))
        for (cx, cy, ang, sx, sy, z0, z1, rgb, nome) in casa.solidos():
            self.fixas.extend(_faces_caixa(cx, cy, ang, sx, sy, z0, z1, rgb))

    def desenha(self, cam, din, largura, altura, fov_h, fov_v, rng=None, ruido=2.5):
        """cam = [x, y, z, guinada (rad), inclinação para baixo (rad)]; din = caixas que se mexem
        [cx, cy, ang, sx, sy, z0, z1, r, g, b]. Devolve a imagem BGR (altura x largura x 3, uint8)."""
        C = np.array(cam[:3], dtype=float)
        yaw, inc = float(cam[3]), float(cam[4])
        f = np.array([math.cos(yaw) * math.cos(inc), math.sin(yaw) * math.cos(inc), -math.sin(inc)])
        r = np.array([math.sin(yaw), -math.cos(yaw), 0.0])
        u = np.cross(r, f)
        R = np.stack([r, u, f])                        # mundo -> câmera (x direita, y cima, z frente)
        fx = (largura / 2) / math.tan(math.radians(fov_h) / 2)
        fy = (altura / 2) / math.tan(math.radians(fov_v) / 2)
        cx0, cy0 = largura / 2, altura / 2
        img = np.empty((altura, largura, 3), dtype=np.float32)
        img[:] = TETO
        zbuf = np.zeros((altura, largura), dtype=np.float32)       # guarda 1/z (0 = infinito)
        faces = list(self.fixas)
        for d in din:
            faces.extend(_faces_caixa(d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7:10]))
        for verts, n, cor in faces:
            if float(n @ (C - verts[0])) <= 0.0:       # de costas para a câmera
                continue
            pc = (verts - C) @ R.T
            if pc[:, 2].max() < PERTO:
                continue
            pol = _corta_perto(pc)
            if len(pol) < 3:
                continue
            px = cx0 + fx * pol[:, 0] / pol[:, 2]
            py = cy0 - fy * pol[:, 1] / pol[:, 2]
            if px.max() < 0 or px.min() > largura or py.max() < 0 or py.min() > altura:
                continue
            iz = 1.0 / pol[:, 2]
            c = _sombreia(cor, n)
            for k in range(1, len(pol) - 1):
                _triangulo(img, zbuf, (px[0], py[0], iz[0]), (px[k], py[k], iz[k]), (px[k + 1], py[k + 1], iz[k + 1]), c)
        if rng is not None and ruido > 0:
            img += rng.normal(0.0, ruido, img.shape).astype(np.float32)
        return np.clip(img[:, :, ::-1], 0, 255).astype(np.uint8)        # RGB -> BGR


def _corta_perto(p):
    """Corta o polígono (no referencial da câmera) no plano z = PERTO."""
    res = []
    n = len(p)
    for i in range(n):
        a, b = p[i], p[(i + 1) % n]
        da, db = a[2] - PERTO, b[2] - PERTO
        if da >= 0:
            res.append(a)
        if (da >= 0) != (db >= 0):
            t = da / (da - db)
            res.append(a + (b - a) * t)
    return np.array(res) if res else np.empty((0, 3))


def _triangulo(img, zbuf, a, b, c, cor):
    h, w = zbuf.shape
    x0 = max(0, int(math.floor(min(a[0], b[0], c[0]))))
    x1 = min(w - 1, int(math.ceil(max(a[0], b[0], c[0]))))
    y0 = max(0, int(math.floor(min(a[1], b[1], c[1]))))
    y1 = min(h - 1, int(math.ceil(max(a[1], b[1], c[1]))))
    if x1 < x0 or y1 < y0:
        return
    den = (b[1] - c[1]) * (a[0] - c[0]) + (c[0] - b[0]) * (a[1] - c[1])
    if abs(den) < 1e-9:
        return
    xs = np.arange(x0, x1 + 1, dtype=np.float32) + 0.5
    ys = np.arange(y0, y1 + 1, dtype=np.float32) + 0.5
    X, Y = np.meshgrid(xs, ys)
    l1 = ((b[1] - c[1]) * (X - c[0]) + (c[0] - b[0]) * (Y - c[1])) / den
    l2 = ((c[1] - a[1]) * (X - c[0]) + (a[0] - c[0]) * (Y - c[1])) / den
    l3 = 1.0 - l1 - l2
    eps = -1e-4
    iz = l1 * a[2] + l2 * b[2] + l3 * c[2]
    sub = zbuf[y0:y1 + 1, x0:x1 + 1]
    m = (l1 >= eps) & (l2 >= eps) & (l3 >= eps) & (iz > sub)
    if not m.any():
        return
    sub[m] = iz[m]
    img[y0:y1 + 1, x0:x1 + 1][m] = cor
