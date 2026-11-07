"""Foto sintética de um mapa da Maze, para testar o foto_mapa.py com a resposta conhecida.

    python ferramentas/foto_mapa_sintetica.py mapas/exemplo1.json saida.jpg      (da pasta simuladorMaze)

Câmera de celular (foco 1150 px, 1200 x 1600) a 1,25 m, a sudoeste do labirinto, olhando para o meio dele.
Paredes de 150 mm (cinza claro com quina escura), piso branco com emendas, pisos coloridos, vítimas (letra
num quadrado branco a 70 mm do chão; a letra é desenhada por cima de tudo, mesmo atrás de parede).
Imprime pontos de calibração (cantos da grade, "fx,fy,X,Y") e onde cada vítima caiu na foto.
Teste de 06/11/2026 (exemplo1): calibra com os 5 pontos -> câmera no lugar certo (foco 1150, X -150,
Y 2150, 1250 mm); descricao.json = o próprio exemplo1 -> monta dá o mesmo mapa; o contraste do 'paredes'
acertou só 2 de cada 3 bordas (é pista, não resposta).
"""
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sim.mapa import Mapa  # noqa: E402

T, HP, ESP = 300.0, 150.0, 20.0
m = Mapa.carregar(sys.argv[1])
W, H, f = 1200, 1600, 1150.0
K = np.array([[f, 0, W / 2], [0, f, H / 2], [0, 0, 1]])
# mundo: X leste, Y sul (mm, borda noroeste = 0), Z para cima. Câmera a sudoeste, olhando para o meio.
C = np.array([-150.0, m.linhas * T + 350, 1250.0])
alvo = np.array([m.colunas * T * 0.5, m.linhas * T * 0.55, 0.0])
fwd = alvo - C
fwd /= np.linalg.norm(fwd)
right = np.cross(fwd, [0, 0, 1.0])
right /= np.linalg.norm(right)
down = np.cross(fwd, right)
Rcw = np.vstack([right, down, fwd])        # mundo -> câmera
if np.linalg.det(Rcw) > 0:                 # o mundo (leste, sul, cima) é de mão esquerda
    Rcw[0] *= -1


def proj(P):
    P = np.atleast_2d(np.float64(P))
    q = (K @ (Rcw @ (P - C).T)).T
    return q[:, :2] / q[:, 2:3], q[:, 2]


img = np.full((H, W, 3), (70, 80, 90), np.uint8)
polys = []                                   # (pontos 3D, cor, borda)
cores = {'preto': (25, 25, 25), 'azul': (170, 60, 20), 'prata': (175, 175, 165), 'vermelho': (40, 40, 200)}
for l in range(m.linhas):
    for c in range(m.colunas):
        q = [(c * T, l * T, 0), ((c + 1) * T, l * T, 0), ((c + 1) * T, (l + 1) * T, 0), (c * T, (l + 1) * T, 0)]
        polys.append((q, (238, 238, 238), (205, 205, 205)))
        p = m.piso(l, c)
        if p in cores:
            d = 15
            q2 = [(c * T + d, l * T + d, 0.5), ((c + 1) * T - d, l * T + d, 0.5), ((c + 1) * T - d, (l + 1) * T - d, 0.5),
                  (c * T + d, (l + 1) * T - d, 0.5)]
            polys.append((q2, cores[p], None))


def caixa(x0, y0, x1, y1, z1, cor):
    """Paralelepípedo (paredes) como 5 faces."""
    v = [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0), (x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)]
    faces = [(0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7), (4, 5, 6, 7)]
    tons = [0.92, 0.8, 0.95, 0.85, 1.0]
    for fc, t in zip(faces, tons):
        polys.append(([v[i] for i in fc], tuple(int(k * t) for k in cor), (120, 120, 120)))


e = ESP / 2
for l in range(m.linhas + 1):
    for c in range(m.colunas):
        if m.paredes_h[l][c]:
            caixa(c * T - e, l * T - e, (c + 1) * T + e, l * T + e, HP, (215, 215, 210))
for l in range(m.linhas):
    for c in range(m.colunas + 1):
        if m.paredes_v[l][c]:
            caixa(c * T - e, l * T - e, c * T + e, (l + 1) * T + e, HP, (215, 215, 210))
vits = []
for v in m.vitimas:
    (x, y), (nx, ny) = m.ponto_vitima(v)
    X, Y = x, m.altura_mm - y
    nX, nY = nx, -ny
    tX, tY = -nY, nX
    centro = np.array([X + nX * 1.0, Y + nY * 1.0, 70.0])
    q = [centro + s * np.array([tX, tY, 0]) * 30 + u * np.array([0, 0, 30.0]) for s, u in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    polys.append((q, (250, 250, 250), (0, 0, 0)))
    vits.append((v, centro))


def profundidade(q):
    return float(np.mean(proj(np.array(q, float))[1]))


for q, cor, borda in sorted(polys, key=lambda t: -profundidade(t[0])):   # do mais longe para o mais perto
    p, z = proj(np.array(q, float))
    if (z <= 1).any():
        continue
    cv2.fillPoly(img, [p.astype(np.int32)], cor, cv2.LINE_AA)
    if borda:
        cv2.polylines(img, [p.astype(np.int32)], True, borda, 1, cv2.LINE_AA)
for v, centro in vits:
    p, _ = proj(centro)
    cv2.putText(img, v.get('letra', 'C'), (int(p[0, 0]) - 6, int(p[0, 1]) + 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6,
                (0, 0, 0), 2)
img = cv2.GaussianBlur(img, (3, 3), 0)
cv2.imwrite(sys.argv[2], img, [cv2.IMWRITE_JPEG_QUALITY, 92])
print('câmera em', C.round(), '; foco', f)
pts = []
for l, c in ((m.linhas, 0), (m.linhas, m.colunas), (0, m.colunas), (0, 0), (m.linhas // 2, m.colunas // 2)):
    p, _ = proj([c * T, l * T, 0])
    pts.append(f'"{p[0, 0]:.1f},{p[0, 1]:.1f},{c * T:.0f},{l * T:.0f}"')
print('pontos:', ' '.join(pts))
for v, centro in vits:
    p, _ = proj(centro)
    print(f'vitima {v["linha"]},{v["coluna"]} {v["parede"]} pos {v.get("posicao", 0.5)} -> foto {p[0, 0]:.0f},{p[0, 1]:.0f}')
