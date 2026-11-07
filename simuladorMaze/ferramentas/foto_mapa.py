"""Mapa do simulador da Maze a partir da foto de um labirinto de verdade (feito com o apoio do Claude).

O passo a passo está em MAPA_DA_FOTO.md, nesta pasta. Cada foto ganha uma pasta de trabalho em
simuladorMaze/fotos_mapa/<nome>/:
  foto.jpg        a foto, já de pé (o 'novo' aplica a orientação do celular)
  projeto.json    as calibrações (pontos da foto ligados a pontos do chão) e a câmera de cada uma
  descricao.json  o que foi reconhecido (paredes, pisos, rampas, vítimas); o 'monta' faz o mapa dele
  *.png, *.txt    imagens e listas de trabalho (saem de novo; o git ignora)

Coordenadas:
  foto     pixels da foto.jpg (x para a direita, y para baixo), os números da régua das imagens.
  chão     mm: X para o leste a partir da borda oeste do labirinto e Y para o SUL a partir da borda norte
           (o norte é o alto da tela do simulador). O ladrilho da coluna c e linha l vai de X = 300c a
           300c + 300 e de Y = 300l a 300l + 300. As linhas de grade ficam no EIXO das paredes.
  ladrilho (coluna, linha) nos comandos e nas áreas (c0,l0,c1,l1); no mapa é {"linha", "coluna"}.
  bordas   h<l>,<c> = borda norte do ladrilho (l, c) (l de 0 a linhas); v<l>,<c> = borda oeste do
           ladrilho (l, c) (c de 0 a colunas). São os índices de paredes_h e paredes_v do mapa.
  altura   mm acima do chão (topo das paredes, piso de cima depois de uma rampa).

Comandos (da pasta simuladorMaze):
  python ferramentas/foto_mapa.py novo NOME FOTO
  python ferramentas/foto_mapa.py recorta NOME x0 y0 x1 y1 [--zoom Z]
  python ferramentas/foto_mapa.py calibra NOME CALIB "fx,fy,X,Y" ... [--altura Z] [--ladrilhos c0,l0,c1,l1]
  python ferramentas/foto_mapa.py fugas NOME --leste "x1,y1,x2,y2" ... --sul "x1,y1,x2,y2" ... [--auto]
  python ferramentas/foto_mapa.py calibra NOME CALIB --fugas "ru,rv,X,Y" ... (pixels da vista_fugas.png)
  python ferramentas/foto_mapa.py camera NOME CALIB [--fov G] [--topo "fx,fy,X,Y" ...] [--altura Z]
  python ferramentas/foto_mapa.py vista NOME CALIB [--area c0,l0,c1,l1] [--altura Z]
  python ferramentas/foto_mapa.py paredes NOME CALIB [--area c0,l0,c1,l1] [--altura Z]
  python ferramentas/foto_mapa.py pisos NOME CALIB [--area c0,l0,c1,l1]
  python ferramentas/foto_mapa.py ponto NOME CALIB fx,fy ... [--altura Z | --parede]
  python ferramentas/foto_mapa.py monta NOME [--saida mapas/arquivo.json]
  python ferramentas/foto_mapa.py confere mapas/arquivo.json
  python ferramentas/foto_mapa.py compara NOME [mapas/arquivo.json]
As áreas são em ladrilhos (coluna, linha), com as duas pontas incluídas.
"""
import argparse
import json
import math
import os
import shutil
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)                       # simuladorMaze
PASTAS = os.path.join(RAIZ, 'fotos_mapa')
MAPAS = os.path.join(RAIZ, 'mapas')
sys.path.insert(0, RAIZ)
from sim.mapa import ALTURA_PAREDE, Mapa  # noqa: E402

T = 300
MAGENTA = (255, 0, 255)
CIANO = (255, 220, 0)
VERDE = (0, 200, 0)
MAX_LADO = 1600                                    # px: imagens maiores ficam ruins de ler
COR_PISO = {'branco': (235, 235, 235), 'preto': (30, 30, 30), 'prata': (190, 175, 160), 'azul': (200, 70, 20),
            'vermelho': (40, 40, 210)}
CODIGO_PISO = {'P': 'preto', 'A': 'azul', 'C': 'prata', 'V': 'vermelho'}      # no 'desenho' da descricao.json


# ------------------------------------------------------------------ pasta de trabalho
def pasta(nome):
    return os.path.join(PASTAS, nome)


def arq(nome, base):
    return os.path.join(pasta(nome), base)


def le_projeto(nome):
    p = arq(nome, 'projeto.json')
    if not os.path.exists(p):
        sys.exit(f'Não achei {p}. Comece com: foto_mapa.py novo {nome} FOTO')
    return json.load(open(p, encoding='utf-8'))


def grava_projeto(nome, proj):
    json.dump(proj, open(arq(nome, 'projeto.json'), 'w', encoding='utf-8'), indent=1, ensure_ascii=False)


def le_foto(nome):
    im = cv2.imread(arq(nome, 'foto.jpg'))
    if im is None:
        sys.exit(f'Não consegui ler {arq(nome, "foto.jpg")}')
    return im


def calibracao(proj, calib):
    c = proj['calibracoes'].get(calib)
    if c is None:
        sys.exit(f'Calibração "{calib}" não existe. Tem: {", ".join(proj["calibracoes"]) or "nenhuma"}')
    return c


def foto_para_chao(H, pts):
    return cv2.perspectiveTransform(np.float64(pts).reshape(-1, 1, 2), H).reshape(-1, 2)


def area_txt(txt):
    c0, l0, c1, l1 = (int(v) for v in txt.split(','))
    return min(c0, c1), min(l0, l1), max(c0, c1), max(l0, l1)


def grava(img, caminho, max_lado=MAX_LADO):
    """Grava reduzindo para caber em max_lado (as imagens vão ser lidas pelo Claude)."""
    h, w = img.shape[:2]
    e = min(1.0, max_lado / max(h, w))
    if e < 1:
        img = cv2.resize(img, (int(w * e), int(h * e)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(caminho, img)
    print('imagem:', caminho, f'({img.shape[1]} x {img.shape[0]})')


def texto(img, s, p, esc=0.5, cor=MAGENTA, esp=1):
    p = (int(p[0]), int(p[1]))
    cv2.putText(img, s, p, cv2.FONT_HERSHEY_SIMPLEX, esc, (0, 0, 0), esp + 2, cv2.LINE_AA)
    cv2.putText(img, s, p, cv2.FONT_HERSHEY_SIMPLEX, esc, cor, esp, cv2.LINE_AA)


def regua_foto(img, x0, y0, esc, passo):
    """Régua com as coordenadas da foto nas bordas e uma grade fraca (img já recortada/reduzida)."""
    h, w = img.shape[:2]
    for x in range((x0 // passo + 1) * passo, int(x0 + w / esc) + 1, passo):
        X = int((x - x0) * esc)
        forte = x % (2 * passo) == 0
        cv2.line(img, (X, 0), (X, h), (200, 120, 255) if forte else (150, 90, 200), 1)
        if forte:
            texto(img, str(x), (X + 3, 16), 0.5)
            texto(img, str(x), (X + 3, h - 6), 0.5)
    for y in range((y0 // passo + 1) * passo, int(y0 + h / esc) + 1, passo):
        Y = int((y - y0) * esc)
        forte = y % (2 * passo) == 0
        cv2.line(img, (0, Y), (w, Y), (200, 120, 255) if forte else (150, 90, 200), 1)
        if forte:
            texto(img, str(y), (3, Y - 4), 0.5)
            texto(img, str(y), (w - 48, Y - 4), 0.5)
    return img


def passo_regua(largura_foto_px):
    for p in (25, 50, 100, 200, 250, 500):
        if largura_foto_px / p <= 20:
            return p
    return 1000


def grade_ladrilhos(img, X0, Y0, ppm, cor=MAGENTA, rotulos=True):
    """Grade de 300 mm (eixos das paredes) numa vista de cima cujo canto é (X0, Y0) mm; rótulo c,l."""
    h, w = img.shape[:2]
    for c in range(math.floor(X0 / T), math.ceil((X0 + w / ppm) / T) + 1):
        X = int((c * T - X0) * ppm)
        cv2.line(img, (X, 0), (X, h), cor, 1)
    for l in range(math.floor(Y0 / T), math.ceil((Y0 + h / ppm) / T) + 1):
        Y = int((l * T - Y0) * ppm)
        cv2.line(img, (0, Y), (w, Y), cor, 1)
    if rotulos:
        for c in range(math.floor(X0 / T), math.ceil((X0 + w / ppm) / T)):
            for l in range(math.floor(Y0 / T), math.ceil((Y0 + h / ppm) / T)):
                texto(img, f'c{c} l{l}', (int((c * T - X0) * ppm) + 4, int((l * T - Y0) * ppm) + 16), 0.42, cor)
    return img


# ------------------------------------------------------------------ câmera (para as alturas)
def _pose(G, K):
    """Pose da câmera pela homografia chão (mm) -> foto e a matriz K. Devolve R, t, cima."""
    M = np.linalg.inv(K) @ G
    lam = (np.linalg.norm(M[:, 0]) + np.linalg.norm(M[:, 1])) / 2
    r1, r2, t = M[:, 0] / lam, M[:, 1] / lam, M[:, 2] / lam
    if t[2] < 0:
        r1, r2, t = -r1, -r2, -t
    U, _, Vt = np.linalg.svd(np.column_stack([r1, r2, np.cross(r1, r2)]))
    R = U @ Vt
    C = -R.T @ t
    return R, t, (1.0 if C[2] > 0 else -1.0)   # cima: sinal do eixo Z do chão do lado da câmera


def _K(f, w, h):
    return np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])


def foco_pela_homografia(G, w, h):
    """Foco (px) com o centro óptico no meio da foto e pixel quadrado: as duas restrições de Zhang
    (r1 . r2 = 0 e |r1| = |r2|) resolvidas para 1/f² por mínimos quadrados. None se não der."""
    T0 = np.array([[1, 0, -w / 2], [0, 1, -h / 2], [0, 0, 1.0]])
    g = T0 @ G
    (a1, b1, c1), (a2, b2, c2) = g[:, 0], g[:, 1]
    A = np.array([a1 * a2 + b1 * b2, a1 * a1 + b1 * b1 - a2 * a2 - b2 * b2])
    B = np.array([-c1 * c2, c2 * c2 - c1 * c1])
    n = np.abs(A) + 1e-12
    A, B = A / n, B / n
    x = float(A @ B / (A @ A))
    return 1 / math.sqrt(x) if x > 0 else None


class Camera:
    """Câmera de uma calibração do chão: projeta pontos (X, Y, altura) na foto e dá a homografia de um
    plano a qualquer altura."""

    def __init__(self, proj, calib, nome):
        c = calibracao(proj, calib)
        self.base = float(c.get('altura', 0.0))      # altura do plano da calibração
        cam = c.get('camera')
        if not cam:
            sys.exit(f'Calibração "{calib}" sem câmera: rode "camera {nome} {calib}" primeiro')
        self.w, self.h = cam['largura'], cam['altura']
        self.K = _K(cam['foco'], self.w, self.h)
        self.R, self.t, self.cima = _pose(np.linalg.inv(np.array(c['H'])), self.K)
        self.foco = cam['foco']

    def projeta(self, P):
        """(X, Y, altura acima do chão) -> pixel da foto."""
        P = np.atleast_2d(np.float64(P))
        Q = np.column_stack([P[:, 0], P[:, 1], self.cima * (P[:, 2] - self.base)])
        p = (self.K @ (self.R @ Q.T + self.t[:, None])).T
        return p[:, :2] / p[:, 2:3]

    def H_altura(self, z):
        """Homografia foto -> plano (X, Y) na altura z."""
        G = self.K @ np.column_stack([self.R[:, 0], self.R[:, 1], self.cima * (z - self.base) * self.R[:, 2] + self.t])
        return np.linalg.inv(G)

    def centro(self):
        C = -self.R.T @ self.t
        return C[0], C[1], self.base + self.cima * C[2]

    def raio(self, fx, fy):
        """Origem e direção (no chão: X, Y, altura) do raio que passa pelo pixel."""
        d = self.R.T @ np.linalg.inv(self.K) @ np.array([fx, fy, 1.0])
        return np.array(self.centro()), np.array([d[0], d[1], self.cima * d[2]])


# ------------------------------------------------------------------ pontos de fuga
def ponto_de_fuga(segs):
    """Ponto de fuga (homogêneo) de segmentos que no chão são paralelos: mínimos quadrados das retas."""
    L = []
    for x1, y1, x2, y2 in segs:
        r = np.cross([x1, y1, 1.0], [x2, y2, 1.0])
        L.append(r / np.hypot(r[0], r[1]))
    return np.linalg.svd(np.array(L))[2][-1]


def direcao(K, v, segs):
    """Direção 3D (câmera) de um ponto de fuga, no sentido em que os segmentos foram dados (p1 -> p2)."""
    d = np.linalg.inv(K) @ v
    d /= np.linalg.norm(d)
    if d[2] < 0:
        d = -d                                   # o ponto de fuga do sentido que se afasta da câmera
    x1, y1, x2, y2 = segs[0]
    vp = v[:2] / v[2] if abs(v[2]) > 1e-12 else None
    se_afasta = vp is not None and np.hypot(*(vp - (x2, y2))) < np.hypot(*(vp - (x1, y1)))
    return d if se_afasta else -d


def _residuos(x, grupos, w, h):
    """Seno do ângulo entre cada segmento e a reta do meio dele até o ponto de fuga da direção dele
    (x = vetor de rotação + log do foco), vezes a raiz do comprimento: segmento longo pesa mais."""
    R = cv2.Rodrigues(np.float64(x[:3]))[0]
    K = _K(math.exp(x[3]), w, h)
    out = []
    for j, segs in enumerate(grupos):
        if not len(segs):
            continue
        v = K @ R[:, j]
        s = segs[:, 2:4] - segs[:, 0:2]
        m = (segs[:, 0:2] + segs[:, 2:4]) / 2
        t = v[:2][None, :] - m * v[2]
        L = np.hypot(s[:, 0], s[:, 1])
        sen = (s[:, 0] * t[:, 1] - s[:, 1] * t[:, 0]) / (L * np.hypot(t[:, 0], t[:, 1]) + 1e-12)
        out.append(sen * np.sqrt(L / 100))
    return np.concatenate(out)


def _ajusta(x, grupos, w, h, voltas=60, foco_fixo=False):
    """Levenberg-Marquardt simples (jacobiano numérico) dos 4 parâmetros (3 com o foco fixo)."""
    lam = 1e-3
    r = _residuos(x, grupos, w, h)
    n = 3 if foco_fixo else len(x)
    for _ in range(voltas):
        J = np.zeros((len(r), len(x)))
        for k in range(n):
            dx = np.zeros(len(x))
            dx[k] = 1e-6
            J[:, k] = (_residuos(x + dx, grupos, w, h) - r) / 1e-6
        A = J.T @ J
        passo = -np.linalg.solve(A + lam * np.diag(np.diag(A) + 1e-12), J.T @ r)
        r2 = _residuos(x + passo, grupos, w, h)
        if r2 @ r2 < r @ r:
            x, r, lam = x + passo, r2, lam / 3
            if np.abs(passo).max() < 1e-7:
                break
        else:
            lam *= 5
    return x


def _classifica(segs, R, K, limite):
    """Para cada segmento: a direção (0 leste, 1 sul, 2 vertical) cujo ponto de fuga ele aponta, ou -1."""
    s = segs[:, 2:4] - segs[:, 0:2]
    m = (segs[:, 0:2] + segs[:, 2:4]) / 2
    L = np.hypot(s[:, 0], s[:, 1])
    ang = []
    for j in range(3):
        v = K @ R[:, j]
        t = v[:2][None, :] - m * v[2]
        sen = (s[:, 0] * t[:, 1] - s[:, 1] * t[:, 0]) / (L * np.hypot(t[:, 0], t[:, 1]) + 1e-12)
        ang.append(np.degrees(np.arcsin(np.clip(np.abs(sen), 0, 1))))
    ang = np.array(ang)
    j = ang.argmin(0)
    o = np.sort(ang, 0)
    j[(o[0] > limite) | (o[1] < 3 * o[0] + 1.5)] = -1      # longe de todas, ou perto de duas: fica de fora
    return j, ang.min(0)


def refina_fugas(foto, R, f, manuais, foco_fixo=False):
    """Acha os segmentos de reta da foto (LSD do OpenCV), liga cada um à direção mais parecida (leste, sul,
    vertical) e ajusta foco e rotação com todos (o centro óptico fica no meio da foto)."""
    h, w = foto.shape[:2]
    segs = cv2.createLineSegmentDetector().detect(cv2.cvtColor(foto, cv2.COLOR_BGR2GRAY))[0].reshape(-1, 4)
    segs = segs[np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1]) > 40].astype(np.float64)
    x = np.concatenate([cv2.Rodrigues(R)[0].ravel(), [math.log(f)]])
    # as retas dadas à mão contam 3 vezes (repetidas): elas é que dizem qual é cada direção
    mao = [np.repeat(np.float64(m).reshape(-1, 4), 3, 0) if m else np.zeros((0, 4)) for m in manuais]
    if sum(len(m) > 0 for m in mao) == 3:
        x = _ajusta(x, mao, w, h, foco_fixo=foco_fixo)      # primeiro só com elas (as três direções)
    for limite in (2.0, 1.5, 1.0, 1.0):
        Rk = cv2.Rodrigues(x[:3])[0]
        j, _ = _classifica(segs, Rk, _K(math.exp(x[3]), w, h), limite)
        grupos = [np.vstack([segs[j == k], mao[k]]) for k in range(3)]
        x = _ajusta(x, grupos, w, h, foco_fixo=foco_fixo)
    R = cv2.Rodrigues(x[:3])[0]
    K = _K(math.exp(x[3]), w, h)
    j, ang = _classifica(segs, R, K, 1.2)
    return R, math.exp(x[3]), segs, j, ang


def retificacao(fug, w, h):
    """Homografia foto -> vista de cima (pixels da vista_fugas.png) e o tamanho da imagem."""
    K = _K(fug['foco'], w, h)
    M = np.array(fug['R']).T @ np.linalg.inv(K)          # foto -> (u, v, 1) ~ (leste, sul) / distância
    return np.array(fug['S']) @ M, tuple(fug['tamanho'])


def cmd_fugas(a):
    """Orientação do chão e abertura da câmera pelas retas de duas direções do labirinto (bordas de piso,
    de degrau, base ou alto de parede: qualquer reta horizontal serve). --leste: retas no sentido do
    leste do mapa (primeiro ponto -> segundo ponto = para o leste); --sul: idem para o sul. O sul tem de
    ficar 90° à direita do leste olhando de cima (senão o mapa sai espelhado). Grava a vista de cima
    (vista_fugas.png): todos os planos horizontais (chão, piso de cima, alto das paredes) ficam sem
    perspectiva, cada um na sua escala (o mais perto da câmera, maior)."""
    proj = le_projeto(a.nome)
    foto = le_foto(a.nome)
    h, w = foto.shape[:2]
    A = [tuple(float(v) for v in s.split(',')) for s in a.leste]
    B = [tuple(float(v) for v in s.split(',')) for s in a.sul]
    if len(A) < 2 or len(B) < 2:
        sys.exit('Preciso de pelo menos 2 retas em cada direção ("x1,y1,x2,y2")')
    va, vb = ponto_de_fuga(A), ponto_de_fuga(B)
    c = np.array([w / 2, h / 2])
    if a.fov:
        f = (w / 2) / math.tan(math.radians(a.fov / 2))
    else:
        pa, pb = va[:2] / va[2], vb[:2] / vb[2]
        f2 = -float((pa - c) @ (pb - c))
        if f2 <= 0:
            sys.exit('As duas direções não dão um foco (retas de uma direção misturadas na outra?). Use --fov')
        f = math.sqrt(f2)
    K = _K(f, w, h)
    r1, r2 = direcao(K, va, A), direcao(K, vb, B)
    r2 = r2 - (r1 @ r2) * r1                     # ortogonaliza (com --fov elas não saem a 90°)
    r2 /= np.linalg.norm(r2)
    r3 = np.cross(r1, r2)
    R = np.column_stack([r1, r2, r3])
    if r3 @ (np.linalg.inv(K) @ [w / 2, h / 2, 1]) < 0:
        sys.exit('O sul não está 90° à direita do leste (o mapa sairia espelhado): troque o sentido das '
                 'retas de uma das direções')
    V = [tuple(float(v) for v in s.split(',')) for s in (a.vertical or [])]
    if a.auto:
        print(f'só pelas retas dadas: foco {f:.0f} px (abertura {2 * math.degrees(math.atan(w / 2 / f)):.1f}°)')
        R, f, segs, j, ang = refina_fugas(foto, R, f, [A, B, V], foco_fixo=bool(a.fov))
        K = _K(f, w, h)
        r1, r2, r3 = R[:, 0], R[:, 1], R[:, 2]
        va, vb = K @ r1, K @ r2
        nomes = ('leste', 'sul', 'vertical')
        for k in range(3):
            if (j == k).any():
                print(f'  {nomes[k]}: {(j == k).sum()} segmentos achados na foto, desvio médio {ang[j == k].mean():.2f}°')
        img = foto.copy()
        cores = [(60, 60, 230), (60, 200, 60), (230, 200, 0)]
        for (x1, y1, x2, y2), k in zip(segs, j):
            cv2.line(img, (int(x1), int(y1)), (int(x2), int(y2)), cores[k] if k >= 0 else (150, 150, 150),
                     3 if k >= 0 else 1, cv2.LINE_AA)
        texto(img, 'retas usadas: leste vermelho, sul verde, vertical azul claro; cinza = nenhuma',
              (8, h - 12), 0.6, (255, 255, 255))
        grava(img, arq(a.nome, 'fugas_retas.png'))
        vv = K @ r3
        if abs(vv[2]) > 1e-9:
            print(f'  ponto de fuga vertical em ({vv[0] / vv[2]:.0f}, {vv[1] / vv[2]:.0f})')
    # tamanho da vista: os pixels da foto pelo menos 'abaixo' graus abaixo do horizonte
    ys, xs = np.mgrid[0:h:8, 0:w:8]
    P = np.stack([xs.ravel(), ys.ravel(), np.ones(xs.size)])
    d = R.T @ np.linalg.inv(K) @ P
    ok = d[2] / np.linalg.norm(d, axis=0) > math.sin(math.radians(a.abaixo))
    u, v = d[0, ok] / d[2, ok], d[1, ok] / d[2, ok]
    u0, u1, v0, v1 = np.percentile(u, 0.5), np.percentile(u, 99.5), np.percentile(v, 0.5), np.percentile(v, 99.5)
    e = MAX_LADO / max(u1 - u0, v1 - v0)
    S = np.array([[e, 0, -u0 * e], [0, e, -v0 * e], [0, 0, 1]])
    tam = (int((u1 - u0) * e), int((v1 - v0) * e))
    fov = 2 * math.degrees(math.atan(w / 2 / f))
    proj['fugas'] = {'foco': f, 'R': R.tolist(), 'S': S.tolist(), 'tamanho': list(tam), 'leste': A, 'sul': B}
    grava_projeto(a.nome, proj)
    print(f'foco {f:.0f} px (abertura horizontal {fov:.1f}°); a câmera olha {math.degrees(math.asin(abs(r3[2]))):.0f}° '
          'para baixo')
    for nome_d, segs, v in (('leste', A, va), ('sul', B, vb)):
        if abs(v[2]) > 1e-9:
            p = v[:2] / v[2]
            res = []
            for x1, y1, x2, y2 in segs:              # quanto cada reta passa longe do ponto de fuga (graus)
                a1 = math.atan2(y2 - y1, x2 - x1)
                a2 = math.atan2(p[1] - y1, p[0] - x1)
                res.append(abs((math.degrees(a1 - a2) + 90) % 180 - 90))
            print(f'  fuga do {nome_d}: ({p[0]:.0f}, {p[1]:.0f}); desvio de cada reta (graus): '
                  + ' '.join(f'{r:.1f}' for r in res) + '  <- acima de ~1°, a reta está errada')
    H, tam = retificacao(proj['fugas'], w, h)
    vista = cv2.warpPerspective(foto, H, tam, flags=cv2.INTER_LINEAR, borderValue=(50, 50, 50))
    for k in range(0, max(w, h) + 1, 100):     # linhas de x e y da foto, para achar os pontos
        for eixo in (0, 1):
            if (eixo == 0 and k > w) or (eixo == 1 and k > h):
                continue
            t = np.linspace(0, h if eixo == 0 else w, 60)
            pts = np.stack([np.full_like(t, k), t] if eixo == 0 else [t, np.full_like(t, k)], 1)
            pr = cv2.perspectiveTransform(pts.reshape(-1, 1, 2), H).reshape(-1, 2)
            dd = R.T @ np.linalg.inv(K) @ np.vstack([pts.T, np.ones(len(t))])
            pr = pr[dd[2] / np.linalg.norm(dd, axis=0) > math.sin(math.radians(a.abaixo))]
            cor = (150, 90, 200) if eixo == 0 else (90, 160, 90)
            if len(pr) > 1:
                cv2.polylines(vista, [pr.astype(np.int32)], False, cor, 1, cv2.LINE_AA)
                if k % 200 == 0:
                    texto(vista, f'{"x" if eixo == 0 else "y"}{k}', pr[len(pr) // 2], 0.4, cor)
    for X in range(0, tam[0], 100):
        texto(vista, str(X), (X + 2, 14), 0.4, (255, 255, 255))
        cv2.line(vista, (X, 0), (X, 6), (255, 255, 255), 1)
    for Y in range(100, tam[1], 100):
        texto(vista, str(Y), (2, Y + 4), 0.4, (255, 255, 255))
        cv2.line(vista, (0, Y), (6, Y), (255, 255, 255), 1)
    texto(vista, 'leste ->  sul v   (rotulos brancos: pixels desta vista, para o calibra --fugas)',
          (8, tam[1] - 10), 0.5, (255, 255, 255))
    grava(vista, arq(a.nome, 'vista_fugas.png'), max_lado=MAX_LADO + 10)


# ------------------------------------------------------------------ desenho do mapa
def desenha_mapa(m, px=100):
    """Mapa visto de cima: pisos, terrenos, paredes, vítimas e início; rótulo c,l em cada ladrilho."""
    img = np.full((m.linhas * px, m.colunas * px, 3), 235, np.uint8)
    niveis = m.niveis()[0]
    for l in range(m.linhas):
        for c in range(m.colunas):
            x0, y0 = c * px, l * px
            cor = COR_PISO.get(m.piso(l, c), (235, 235, 235))
            if niveis.get((l, c), 0) > 1 and m.piso(l, c) == 'branco':
                cor = (240, 215, 200)                       # área alta: azulada, como no editor
            cv2.rectangle(img, (x0, y0), (x0 + px - 1, y0 + px - 1), cor, -1)
            if m.zona(l, c):
                cv2.rectangle(img, (x0 + 3, y0 + 3), (x0 + px - 4, y0 + px - 4), (0, 140, 255), 2)
            ter = m.terreno(l, c)
            inc = m.inclinacao(l, c)
            if inc:
                sobe, graus = inc
                dx, dy = {'N': (0, -1), 'S': (0, 1), 'L': (1, 0), 'O': (-1, 0)}[sobe]
                cx, cy = x0 + px // 2, y0 + px // 2
                cv2.arrowedLine(img, (int(cx - dx * px * 0.3), int(cy - dy * px * 0.3)),
                                (int(cx + dx * px * 0.3), int(cy + dy * px * 0.3)), (150, 60, 150), 3, tipLength=0.3)
                texto(img, f'{ter} {graus:g}', (x0 + 3, y0 + px - 6), 0.38, (150, 60, 150))
            elif ter:
                texto(img, ter, (x0 + 3, y0 + px - 6), 0.38, (0, 110, 0))
            if niveis.get((l, c), 0) > 1:
                texto(img, f'+{niveis[(l, c)]:.0f}', (x0 + px - 44, y0 + px - 6), 0.38, (150, 60, 150))
            texto(img, f'c{c} l{l}', (x0 + 3, y0 + 13), 0.35, (130, 130, 130))
    e = max(3, int(px * m.espessura_parede / T))
    for l in range(m.linhas + 1):
        for c in range(m.colunas):
            if m.paredes_h[l][c]:
                cv2.line(img, (c * px, l * px), ((c + 1) * px, l * px), (60, 60, 60), e)
    for l in range(m.linhas):
        for c in range(m.colunas + 1):
            if m.paredes_v[l][c]:
                cv2.line(img, (c * px, l * px), (c * px, (l + 1) * px), (60, 60, 60), e)
    for v in m.vitimas:
        l, c, d, p = v['linha'], v['coluna'], v['parede'], float(v.get('posicao', 0.5))
        x, y = {'N': (c + p, l + 0.1), 'S': (c + p, l + 0.9), 'O': (c + 0.1, l + 1 - p), 'L': (c + 0.9, l + 1 - p)}[d]
        s = v.get('letra', '?') if v.get('tipo') == 'letra' else 'cog'
        cv2.circle(img, (int(x * px), int(y * px)), max(6, px // 9), (0, 160, 240), -1)
        texto(img, s, (int(x * px) - 6, int(y * px) + 5), 0.42, (0, 0, 0), 1)
    l, c = m.inicio
    cv2.circle(img, (int((c + 0.5) * px), int((l + 0.5) * px)), px // 8, (0, 0, 230), -1)
    texto(img, 'inicio ' + (m.inicio_dir or ''), (c * px + 4, l * px + 30), 0.42, (0, 0, 230))
    return img


def foto_de_cima(nome, proj, colunas, linhas, px):
    """Foto retificada na grade do mapa (px por ladrilho): as calibrações sem região cobrem tudo; as com
    região (outro plano: piso de cima) são aplicadas por cima, só nela."""
    im = le_foto(nome)
    out = np.full((linhas * px, colunas * px, 3), 50, np.uint8)
    S = np.array([[px / T, 0, 0], [0, px / T, 0], [0, 0, 1]])
    cals = proj['calibracoes']
    for c in [c for c in cals if not cals[c].get('ladrilhos')] + [c for c in cals if cals[c].get('ladrilhos')]:
        w = cv2.warpPerspective(im, S @ np.array(cals[c]['H']), (colunas * px, linhas * px), flags=cv2.INTER_AREA,
                                borderValue=(50, 50, 50))
        r = cals[c].get('ladrilhos')
        if r:
            c0, l0, c1, l1 = r
            out[l0 * px:(l1 + 1) * px, c0 * px:(c1 + 1) * px] = w[l0 * px:(l1 + 1) * px, c0 * px:(c1 + 1) * px]
        else:
            out = w
    return out


# ------------------------------------------------------------------ comandos
def cmd_novo(a):
    os.makedirs(pasta(a.nome), exist_ok=True)
    im = cv2.imread(a.foto)                        # o imread já aplica a orientação (EXIF) do celular
    if im is None:
        sys.exit(f'Não consegui ler {a.foto}')
    cv2.imwrite(arq(a.nome, 'foto.jpg'), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
    if not os.path.exists(arq(a.nome, 'projeto.json')):
        grava_projeto(a.nome, {'foto_original': os.path.abspath(a.foto), 'calibracoes': {}})
    if not os.path.exists(arq(a.nome, 'descricao.json')):
        shutil.copy(os.path.join(AQUI, 'foto_mapa_descricao_modelo.json'), arq(a.nome, 'descricao.json'))
    h, w = im.shape[:2]
    print(f'foto {w} x {h} px em {arq(a.nome, "foto.jpg")}')
    e = min(1.0, MAX_LADO / max(w, h))
    img = cv2.resize(im, (int(w * e), int(h * e)), interpolation=cv2.INTER_AREA)
    grava(regua_foto(img, 0, 0, e, passo_regua(w)), arq(a.nome, 'foto_regua.png'))


def cmd_recorta(a):
    im = le_foto(a.nome)
    x0, y0, x1, y1 = a.x0, a.y0, a.x1, a.y1
    r = im[max(0, y0):y1, max(0, x0):x1]
    zoom = a.zoom or min(4.0, MAX_LADO / max(r.shape[:2]))
    r = cv2.resize(r, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_AREA if zoom < 1 else cv2.INTER_CUBIC)
    g = cv2.cvtColor(r, cv2.COLOR_BGR2LAB)
    g[:, :, 0] = cv2.createCLAHE(2.0, (8, 8)).apply(g[:, :, 0])
    r = cv2.cvtColor(g, cv2.COLOR_LAB2BGR)
    regua_foto(r, max(0, x0), max(0, y0), zoom, passo_regua(x1 - x0))
    grava(r, a.saida or arq(a.nome, f'recorte_{x0}_{y0}.png'), max_lado=int(MAX_LADO * 1.25))


def cmd_calibra(a):
    proj = le_projeto(a.nome)
    pts = [tuple(float(v) for v in p.split(',')) for p in a.pontos]
    if a.fugas:
        return calibra_fugas(a, proj, pts)
    if len(pts) < 4 or any(len(p) != 4 for p in pts):
        sys.exit('Preciso de pelo menos 4 pontos "fx,fy,X,Y" (foto -> chão em mm)')
    src = np.float64([p[:2] for p in pts])
    dst = np.float64([p[2:] for p in pts])
    if len(pts) == 4:
        H = cv2.getPerspectiveTransform(np.float32(src), np.float32(dst)).astype(np.float64)
    else:
        H, _ = cv2.findHomography(src, dst, 0)          # mínimos quadrados com todos os pontos
    err = np.linalg.norm(foto_para_chao(H, src) - dst, axis=1)
    c = {'pontos': [list(p) for p in pts], 'H': H.tolist(), 'altura': a.altura}
    if a.ladrilhos:
        c['ladrilhos'] = list(area_txt(a.ladrilhos))
    if a.obs:
        c['obs'] = a.obs
    proj['calibracoes'][a.calib] = c
    grava_projeto(a.nome, proj)
    print(f'calibração "{a.calib}" gravada com {len(pts)} pontos (plano a {a.altura:g} mm do chão)')
    if len(pts) > 4:
        print('erro de cada ponto (mm):', ' '.join(f'{v:.0f}' for v in err),
              ' <- acima de ~20 mm, algum ponto está errado ou não está no mesmo plano')
    a.fov, a.topo, a.altura_paredes = None, None, None
    cmd_camera(a)
    a.area = a.area or a.ladrilhos
    a.altura_vista = None
    cmd_vista(a)


def calibra_fugas(a, proj, pts):
    """Calibração de um plano horizontal pela vista_fugas.png: só falta a escala e a posição (a orientação e
    o foco vêm do 'fugas'), então 2 pontos bastam ("ru,rv,X,Y": pixel da vista_fugas -> mm)."""
    if 'fugas' not in proj:
        sys.exit('Rode o "fugas" antes do "calibra --fugas"')
    if len(pts) < 2 or any(len(p) != 4 for p in pts):
        sys.exit('Preciso de pelo menos 2 pontos "ru,rv,X,Y" (pixel da vista_fugas.png -> chão em mm)')
    h, w = le_foto(a.nome).shape[:2]
    Hr, _ = retificacao(proj['fugas'], w, h)
    # X = s*ru + X0, Y = s*rv + Y0 (a vista já está sem perspectiva e com leste/sul nos eixos)
    A, b = [], []
    for ru, rv, X, Y in pts:
        A += [[ru, 1, 0], [rv, 0, 1]]
        b += [X, Y]
    (s, X0, Y0), *_ = np.linalg.lstsq(np.array(A, float), np.array(b, float), rcond=None)
    S2 = np.array([[s, 0, X0], [0, s, Y0], [0, 0, 1]])
    H = S2 @ Hr
    err = [math.hypot(s * ru + X0 - X, s * rv + Y0 - Y) for ru, rv, X, Y in pts]
    fs = np.array(proj['fugas']['S'])
    dist = s * fs[0, 0]                          # mm por unidade de (u, v) = distância da câmera ao plano
    src = foto_para_chao(np.linalg.inv(H), [p[2:] for p in pts])
    c = {'pontos': [[float(x), float(y), p[2], p[3]] for (x, y), p in zip(src, pts)], 'H': H.tolist(),
         'altura': a.altura, 'pela_fuga': [list(p) for p in pts], 'distancia_mm': dist,
         'camera': {'foco': proj['fugas']['foco'], 'largura': w, 'altura': h, 'origem': 'pontos de fuga'}}
    if a.ladrilhos:
        c['ladrilhos'] = list(area_txt(a.ladrilhos))
    if a.obs:
        c['obs'] = a.obs
    proj['calibracoes'][a.calib] = c
    grava_projeto(a.nome, proj)
    print(f'calibração "{a.calib}" pela fuga, {len(pts)} pontos: {s:.2f} mm por pixel da vista, '
          f'a câmera fica {dist:.0f} mm acima deste plano')
    print('erro de cada ponto (mm):', ' '.join(f'{v:.0f}' for v in err))
    outros = {k: v['distancia_mm'] - dist for k, v in proj['calibracoes'].items()
              if k != a.calib and v.get('distancia_mm')}
    for k, dd in outros.items():
        print(f'  este plano está {dd:+.0f} mm em relação ao "{k}" (+ = mais alto)')
    a.area = a.area or a.ladrilhos
    a.altura_vista = None
    cmd_vista(a)


def cmd_camera(a):
    """Foco da câmera (para saber onde fica o alto das paredes). Sem --topo: pela própria homografia
    (centro óptico no meio da foto); com --topo (pontos do alto das paredes, X, Y em mm): o foco (e a
    altura das paredes, se não der --altura) que melhor leva esses pontos aos lugares certos da foto."""
    proj = le_projeto(a.nome)
    c = calibracao(proj, a.calib)
    h, w = le_foto(a.nome).shape[:2]
    G = np.linalg.inv(np.array(c['H']))
    base = float(c.get('altura', 0.0))
    if a.fov:
        f = (w / 2) / math.tan(math.radians(a.fov / 2))
        origem = f'abertura dada ({a.fov:g}°)'
    elif getattr(a, 'topo', None):
        topo = [tuple(float(v) for v in p.split(',')) for p in a.topo]
        alturas = [a.altura_paredes] if a.altura_paredes else list(range(100, 401, 5))
        melhor = None
        for fov10 in range(300, 1001, 5):
            f = (w / 2) / math.tan(math.radians(fov10 / 20))
            K = _K(f, w, h)
            R, t, cima = _pose(G, K)
            for z in alturas:
                e = 0.0
                for fx, fy, X, Y in topo:
                    p = K @ (R @ np.array([X, Y, cima * (z - base)]) + t)
                    e += math.hypot(p[0] / p[2] - fx, p[1] / p[2] - fy)
                e /= len(topo)
                if melhor is None or e < melhor[0]:
                    melhor = (e, f, fov10 / 10, z)
        e, f, fov, z = melhor
        origem = f'pelos {len(topo)} pontos do alto das paredes: abertura {fov:g}°, paredes de {z:g} mm, ' \
                 f'erro médio {e:.1f} px'
        c['altura_paredes'] = z
    else:
        f = foco_pela_homografia(G, w, h)
        origem = 'pela homografia do chão'
        if f is None or not (0.3 * w < f < 5 * w):
            f = (w / 2) / math.tan(math.radians(35))
            origem = 'chute (70°): a homografia não deu o foco; use --topo com pontos do alto das paredes'
    cam = {'foco': f, 'largura': w, 'altura': h, 'origem': origem}
    c['camera'] = cam
    grava_projeto(a.nome, proj)
    cm = Camera(proj, a.calib, a.nome)
    X, Y, Z = cm.centro()
    fov = 2 * math.degrees(math.atan(w / 2 / f))
    print(f'câmera "{a.calib}": foco {f:.0f} px (abertura horizontal {fov:.0f}°), {origem}')
    print(f'  a câmera está em X {X:.0f} Y {Y:.0f} mm, {Z:.0f} mm acima do chão')
    if not (300 < Z < 5000):
        print('  AVISO: altura da câmera estranha: confira a calibração ou use --topo / --fov')


def cmd_vista(a):
    proj = le_projeto(a.nome)
    c = calibracao(proj, a.calib)
    H = np.array(c['H'])
    z = getattr(a, 'altura_vista', None)
    if z is not None:
        H = Camera(proj, a.calib, a.nome).H_altura(z)
    if a.area:
        c0, l0, c1, l1 = area_txt(a.area)
    elif c.get('ladrilhos'):
        c0, l0, c1, l1 = c['ladrilhos']
    else:
        dst = np.float64([p[2:] for p in c['pontos']])
        c0, l0 = (np.floor(dst.min(0) / T).astype(int) - 1).tolist()
        c1, l1 = (np.floor((dst.max(0) - 1) / T).astype(int) + 1).tolist()
    X0, Y0, X1, Y1 = c0 * T - 60, l0 * T - 60, (c1 + 1) * T + 60, (l1 + 1) * T + 60
    ppm = min(1.0, MAX_LADO / max(X1 - X0, Y1 - Y0))
    S = np.array([[ppm, 0, -X0 * ppm], [0, ppm, -Y0 * ppm], [0, 0, 1]])
    v = cv2.warpPerspective(le_foto(a.nome), S @ H, (int((X1 - X0) * ppm), int((Y1 - Y0) * ppm)),
                            flags=cv2.INTER_AREA, borderValue=(50, 50, 50))
    grade_ladrilhos(v, X0, Y0, ppm)
    if z is None:
        for fx, fy, X, Y in c['pontos']:          # os pontos usados, em verde
            cv2.circle(v, (int((X - X0) * ppm), int((Y - Y0) * ppm)), 6, VERDE, 2)
    else:
        texto(v, f'plano a {z:g} mm do chao: o alto das paredes desta altura cai na grade', (8, v.shape[0] - 10),
              0.55, (255, 255, 255))
    suf = '' if z is None else f'_a{z:g}'
    grava(v, a.saida or arq(a.nome, f'vista_{a.calib}{suf}.png'))


def _bordas(c0, l0, c1, l1):
    """Bordas da área: ('h', l, c) para l de l0 a l1+1 e ('v', l, c) para c de c0 a c1+1."""
    b = [('h', l, c) for l in range(l0, l1 + 2) for c in range(c0, c1 + 1)]
    return b + [('v', l, c) for l in range(l0, l1 + 1) for c in range(c0, c1 + 2)]


def _segmento(b):
    """Pontas (X, Y) em mm do eixo da borda."""
    t, l, c = b
    if t == 'h':
        return (c * T, l * T), ((c + 1) * T, l * T)
    return (c * T, l * T), (c * T, (l + 1) * T)


def _contraste(cinza, p, q, n=24):
    """Degrau de brilho atravessando o segmento p-q da foto (média de |I(+3 px) - I(-3 px)| na normal)."""
    p, q = np.float64(p), np.float64(q)
    d = q - p
    L = np.hypot(*d)
    if L < 8:
        return 0.0
    nrm = np.array([-d[1], d[0]]) / L
    h, w = cinza.shape
    s = []
    for k in np.linspace(0.15, 0.85, n):
        a = p + d * k + 3 * nrm
        b = p + d * k - 3 * nrm
        if 0 <= a[0] < w and 0 <= a[1] < h and 0 <= b[0] < w and 0 <= b[1] < h:
            s.append(abs(float(cinza[int(a[1]), int(a[0])]) - float(cinza[int(b[1]), int(b[0])])))
    return float(np.median(s)) if len(s) > n // 2 else 0.0


def cmd_paredes(a):
    """Cada borda da área desenhada na foto como a parede que estaria ali (base em magenta, alto em
    ciano), com o nome dela, e a vista de cima na altura das paredes (o alto de cada parede que existe
    cai em cima da grade). Lista o contraste no alto e na base de cada borda (pista, não resposta)."""
    proj = le_projeto(a.nome)
    c = calibracao(proj, a.calib)
    cm = Camera(proj, a.calib, a.nome)
    z = a.altura or c.get('altura_paredes') or ALTURA_PAREDE
    c0, l0, c1, l1 = area_txt(a.area) if a.area else (c.get('ladrilhos') or _area_pontos(c))
    foto = le_foto(a.nome)
    cinza = cv2.GaussianBlur(cv2.cvtColor(foto, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    img = foto.copy()
    linhas = []
    for b in _bordas(c0, l0, c1, l1):
        (Xa, Ya), (Xb, Yb) = _segmento(b)
        base = cm.projeta([(Xa, Ya, cm.base), (Xb, Yb, cm.base)])
        topo = cm.projeta([(Xa, Ya, cm.base + z), (Xb, Yb, cm.base + z)])
        kt, kb = _contraste(cinza, *topo), _contraste(cinza, *base)
        nomeb = f'{b[0]}{b[1]},{b[2]}'
        linhas.append((kt + kb, nomeb, kt, kb))
        cv2.line(img, tuple(map(int, base[0])), tuple(map(int, base[1])), MAGENTA, 1, cv2.LINE_AA)
        cv2.line(img, tuple(map(int, topo[0])), tuple(map(int, topo[1])), CIANO, 1, cv2.LINE_AA)
        m = (topo[0] + topo[1]) / 2
        texto(img, nomeb, (m[0] - 18, m[1] - 3), 0.38, CIANO)
    for X, Y in {(cc * T, ll * T) for cc in range(c0, c1 + 2) for ll in range(l0, l1 + 2)}:
        p, q = cm.projeta([(X, Y, cm.base), (X, Y, cm.base + z)])
        cv2.line(img, tuple(map(int, p)), tuple(map(int, q)), (150, 90, 200), 1, cv2.LINE_AA)
    texto(img, f'paredes de {z:g} mm: base magenta, alto ciano; h<l>,<c> = norte do ladrilho, v<l>,<c> = oeste',
          (8, img.shape[0] - 12), 0.6, (255, 255, 255))
    grava(img, arq(a.nome, f'paredes_{a.calib}.png'), max_lado=1800)
    linhas.sort(reverse=True)
    txt = arq(a.nome, f'paredes_{a.calib}.txt')
    open(txt, 'w', encoding='utf-8').write(
        f'# paredes de {z:g} mm; contraste (0-255) no alto e na base de cada borda, do maior para o menor.\n'
        '# Alto e base altos = provavelmente tem parede; baixo nos dois = provavelmente não. Borda escondida\n'
        '# atrás de outra parede ou com a borda de outra coisa passando por cima engana: confira nas imagens.\n'
        + '\n'.join(f'{n:8s} alto {kt:5.1f}  base {kb:5.1f}' for _, n, kt, kb in linhas) + '\n')
    print('lista:', txt)
    a.altura_vista, a.area, a.saida = cm.base + z, f'{c0},{l0},{c1},{l1}', None
    cmd_vista(a)


def _area_pontos(c):
    dst = np.float64([p[2:] for p in c['pontos']])
    c0, l0 = np.floor(dst.min(0) / T).astype(int)
    c1, l1 = np.floor((dst.max(0) - 1) / T).astype(int)
    return int(c0), int(l0), int(c1), int(l1)


def cmd_pisos(a):
    """Cor de cada ladrilho no meio dele (a parte de fora fica perto das paredes, que escondem o piso):
    mediana em HSV e um palpite (branco, preto, azul, vermelho, prata?)."""
    proj = le_projeto(a.nome)
    c = calibracao(proj, a.calib)
    c0, l0, c1, l1 = area_txt(a.area) if a.area else (c.get('ladrilhos') or _area_pontos(c))
    px = 100
    S = np.array([[px / T, 0, -c0 * px], [0, px / T, -l0 * px], [0, 0, 1]])
    NC, NL = c1 - c0 + 1, l1 - l0 + 1
    ret = cv2.warpPerspective(le_foto(a.nome), S @ np.array(c['H']), (NC * px, NL * px), flags=cv2.INTER_AREA,
                              borderValue=(0, 0, 0))
    hsv = cv2.cvtColor(ret, cv2.COLOR_BGR2HSV)
    linhas = []
    for l in range(NL):
        for k in range(NC):
            q = hsv[l * px + 30:l * px + 70, k * px + 30:k * px + 70].reshape(-1, 3)
            bgr = ret[l * px + 30:l * px + 70, k * px + 30:k * px + 70].reshape(-1, 3)
            H, Sa, V = np.median(q, axis=0)
            dv = float(np.std(q[:, 2]))
            if (bgr.max(1) == 0).mean() > 0.3:
                palpite = 'fora'                    # o meio do ladrilho cai fora da foto
            elif V < 70:
                palpite = 'preto'
            elif Sa > 90 and 95 <= H <= 135:
                palpite = 'azul'
            elif Sa > 90 and (H <= 10 or H >= 165):
                palpite = 'vermelho'
            elif Sa < 60 and (V < 170 or dv > 25):
                palpite = 'prata?'
            else:
                palpite = 'branco'
            linhas.append(f'c{c0 + k} l{l0 + l}: {palpite:9s} H {H:3.0f} S {Sa:3.0f} V {V:3.0f} (variação {dv:.0f})')
            texto(ret, palpite, (k * px + 4, l * px + px - 8), 0.4, (0, 255, 255))
    grade_ladrilhos(ret, c0 * T, l0 * T, px / T)
    txt = arq(a.nome, f'pisos_{a.calib}.txt')
    open(txt, 'w', encoding='utf-8').write('\n'.join(linhas) + '\n')
    print('\n'.join(linhas))
    grava(ret, arq(a.nome, f'pisos_{a.calib}.png'))


def cmd_ponto(a):
    """Ponto da foto -> chão (ou um plano a --altura). Com --parede: as faces de parede que o raio
    atravessa entre o chão e o alto das paredes, da mais perto da câmera para a mais longe, com o
    ladrilho, o lado e a posição (0-1) como no campo 'vitimas' do mapa."""
    proj = le_projeto(a.nome)
    c = calibracao(proj, a.calib)
    for p in a.pontos:
        fx, fy = (float(v) for v in p.split(','))
        if not a.parede:
            H = np.array(c['H']) if a.altura is None else Camera(proj, a.calib, a.nome).H_altura(a.altura)
            X, Y = foto_para_chao(H, [(fx, fy)])[0]
            print(f'foto ({fx:.0f}, {fy:.0f}) -> X {X:.0f} Y {Y:.0f} mm = ladrilho c{int(X // T)} l{int(Y // T)}'
                  + (f' (plano a {a.altura:g} mm)' if a.altura is not None else ''))
            continue
        cm = Camera(proj, a.calib, a.nome)
        z_max = cm.base + (c.get('altura_paredes') or ALTURA_PAREDE)
        o, d = cm.raio(fx, fy)
        esp = a.espessura / 2
        faces = []
        for eixo in (0, 1):                     # 0: paredes norte-sul (X constante); 1: leste-oeste (Y constante)
            if abs(d[eixo]) < 1e-9:
                continue
            for k in range(-2, 60):
                for lado in (-1, 1):            # as duas faces da parede
                    plano = k * T + lado * esp
                    s = (plano - o[eixo]) / d[eixo]
                    if s <= 0:
                        continue
                    P = o + s * d
                    if not (cm.base - 5 <= P[2] <= z_max + 5):
                        continue
                    if (o[eixo] - plano) * lado < 0:   # face virada para longe da câmera: não se vê
                        continue
                    u = P[1 - eixo]
                    i = int(u // T)
                    pos = (u - i * T) / T
                    if eixo == 0:                       # parede na borda oeste/leste: vítima no ladrilho do lado da face
                        cc = k if lado > 0 else k - 1
                        l, col, ladop = i, cc, 'O' if lado > 0 else 'L'
                        posicao = 1 - pos                # de sul para norte
                        borda = f'v{i},{k}'
                    else:
                        ll = k if lado > 0 else k - 1
                        l, col, ladop = ll, i, 'N' if lado > 0 else 'S'
                        posicao = pos                    # de oeste para leste
                        borda = f'h{k},{i}'
                    faces.append((s, borda, l, col, ladop, posicao, P[2] - cm.base))
        faces.sort()
        print(f'foto ({fx:.0f}, {fy:.0f}): faces atravessadas, da mais perto para a mais longe:')
        for s, borda, l, col, ladop, posicao, z in faces[:6]:
            print(f'  borda {borda:7s} -> vítima {{"linha": {l}, "coluna": {col}, "parede": "{ladop}", '
                  f'"posicao": {posicao:.2f}}}  a {z:.0f} mm do chão')
        print('  vale a primeira borda que TEM parede')


def le_descricao(nome):
    return json.load(open(arq(nome, 'descricao.json'), encoding='utf-8'))


def desenho_para_paredes(desenho, linhas, colunas):
    """'desenho' em texto (+--+, |, 2 caracteres por ladrilho) -> paredes_h, paredes_v e pisos."""
    if len(desenho) != 2 * linhas + 1:
        sys.exit(f'desenho com {len(desenho)} linhas de texto: para {linhas} linhas de ladrilhos são {2 * linhas + 1}')
    ph, pv, pisos = [], [], {}
    for i, s in enumerate(desenho):
        s = s.ljust(3 * colunas + 1)
        if i % 2 == 0:
            ph.append(''.join('1' if s[3 * c + 1:3 * c + 3].strip() else '0' for c in range(colunas)))
        else:
            l = i // 2
            pv.append(''.join('1' if s[3 * c] not in ' .' else '0' for c in range(colunas + 1)))
            for c in range(colunas):
                cod = s[3 * c + 1].upper()
                if cod in CODIGO_PISO:
                    pisos[(l, c)] = CODIGO_PISO[cod]
                elif cod not in ' .':
                    sys.exit(f'desenho, linha {l} coluna {c}: código de piso "{cod}" (use P, A, C, V ou espaço)')
    return ph, pv, pisos


def monta_dict(d):
    """descricao.json -> dicionário do mapa (formato maze-sim-1)."""
    L, C = d['linhas'], d['colunas']
    pisos = {}
    if d.get('desenho'):
        ph, pv, pisos = desenho_para_paredes(d['desenho'], L, C)
    else:
        ph, pv = d['paredes_h'], d['paredes_v']
    lads = {}
    for (l, c), p in pisos.items():
        lads[(l, c)] = {'linha': l, 'coluna': c, 'piso': p}
    for e in d.get('ladrilhos', []):
        k = (e['linha'], e['coluna'])
        lads.setdefault(k, {'linha': k[0], 'coluna': k[1]}).update(
            {kk: v for kk, v in e.items() if not kk.startswith('_')})
    m = {'formato': 'maze-sim-1', 'nome': d['nome']}
    if d.get('_comentario'):
        m['_comentario'] = d['_comentario']
    m.update({'linhas': L, 'colunas': C, 'inicio': d.get('inicio', {'linha': L - 1, 'coluna': 0, 'direcao': 'N'}),
              'semente': d.get('semente', 1), 'espessura_parede': float(d.get('espessura_parede', 20)),
              'paredes_h': ph, 'paredes_v': pv, 'ladrilhos': [lads[k] for k in sorted(lads)],
              'vitimas': [{k: v for k, v in x.items() if not k.startswith('_')} for x in d.get('vitimas', [])]})
    return m


def confere(caminho, imagem=None):
    m = Mapa.carregar(caminho)
    niveis, _ = m.niveis()
    altos = sorted({round(v) for v in niveis.values() if v > 1})
    print(f'{caminho}: {m.linhas} linhas x {m.colunas} colunas, {len(m.vitimas)} vítimas, '
          f'{len(m.ladrilhos)} ladrilhos especiais' + (f', pisos altos a {altos} mm' if altos else ''))
    av = m.validar()
    for v in av:
        print('  aviso:', v)
    if not av:
        print('  sem avisos')
    if imagem:
        grava(desenha_mapa(m), imagem)
    return m


def cmd_monta(a):
    d = le_descricao(a.nome)
    m = monta_dict(d)
    saida = a.saida or os.path.join(MAPAS, d['nome'] + '.json')
    try:
        mp = Mapa.de_dict(json.loads(json.dumps(m)))
    except (ValueError, KeyError, IndexError) as e:
        sys.exit(f'descricao.json com erro: {e}')
    mp.salvar(saida)                             # o mesmo formato que o editor grava
    if m.get('_comentario'):                      # o Mapa não guarda o comentário: põe de volta
        dd = json.load(open(saida, encoding='utf-8'))
        dd = {'_comentario': m['_comentario'], **dd}
        json.dump(dd, open(saida, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('mapa gravado:', saida)
    confere(saida, arq(a.nome, 'mapa.png'))


def cmd_confere(a):
    confere(a.mapa, a.imagem or os.path.splitext(a.mapa)[0] + '_desenho.png')


def cmd_compara(a):
    """foto de cima | mapa, e o mapa desenhado em cima da foto (paredes em 3D)."""
    proj = le_projeto(a.nome)
    d = le_descricao(a.nome)
    mapa = a.mapa or os.path.join(MAPAS, d['nome'] + '.json')
    m = Mapa.carregar(mapa)
    px = max(60, min(150, MAX_LADO // (2 * m.colunas)))
    foto = foto_de_cima(a.nome, proj, m.colunas, m.linhas, px)
    grade_ladrilhos(foto, 0, 0, px / T)
    sim = desenha_mapa(m, px)
    out = np.full((m.linhas * px + 30, 2 * m.colunas * px + 20, 3), 30, np.uint8)
    out[:m.linhas * px, :m.colunas * px] = foto
    out[:m.linhas * px, m.colunas * px + 20:] = sim
    texto(out, 'foto vista de cima (chao), na grade do mapa', (8, m.linhas * px + 21), 0.55, (255, 255, 255))
    texto(out, os.path.basename(mapa), (m.colunas * px + 28, m.linhas * px + 21), 0.55, (255, 255, 255))
    grava(out, arq(a.nome, 'comparacao.png'), max_lado=1800)
    # o mapa em cima da foto: as paredes do mapa (e as vítimas) projetadas pela câmera de cada calibração
    cals = [k for k, v in proj['calibracoes'].items() if v.get('camera')]
    if not cals:
        print('sem câmera em nenhuma calibração: rode "camera" para ver o mapa em cima da foto')
        return
    principal = a.calib or next((k for k in cals if not proj['calibracoes'][k].get('ladrilhos')), cals[0])
    cm = Camera(proj, principal, a.nome)
    z = proj['calibracoes'][principal].get('altura_paredes') or ALTURA_PAREDE
    niveis = m.niveis()[0]
    img = le_foto(a.nome)
    sobre = img.copy()

    def h_piso(l, c):
        return niveis.get((l, c), 0.0)

    for l in range(m.linhas + 1):
        for c in range(m.colunas):
            if m.paredes_h[l][c]:
                hb = max([h_piso(ll, c) for ll in (l - 1, l) if m.dentro(ll, c)] or [0])
                _parede_3d(sobre, cm, (c * T, l * T), ((c + 1) * T, l * T), hb, z)
    for l in range(m.linhas):
        for c in range(m.colunas + 1):
            if m.paredes_v[l][c]:
                hb = max([h_piso(l, cc) for cc in (c - 1, c) if m.dentro(l, cc)] or [0])
                _parede_3d(sobre, cm, (c * T, l * T), (c * T, (l + 1) * T), hb, z)
    for (l, c), lad in m.ladrilhos.items():
        p = lad.get('piso')
        if p in COR_PISO and p != 'branco':
            q = cm.projeta([(c * T + 40, l * T + 40, h_piso(l, c)), ((c + 1) * T - 40, l * T + 40, h_piso(l, c)),
                            ((c + 1) * T - 40, (l + 1) * T - 40, h_piso(l, c)), (c * T + 40, (l + 1) * T - 40, h_piso(l, c))])
            cv2.polylines(sobre, [q.astype(np.int32)], True, COR_PISO[p], 3, cv2.LINE_AA)
            texto(sobre, p, q.mean(0), 0.5, (255, 255, 255))
    for v in m.vitimas:
        (x, y), _ = m.ponto_vitima(v)
        X, Y = x, m.altura_mm - y
        q = cm.projeta([(X, Y, h_piso(v['linha'], v['coluna']) + 70)])[0]
        cv2.circle(sobre, tuple(map(int, q)), 10, (0, 160, 240), 2)
        texto(sobre, v.get('letra', 'cog') if v.get('tipo') == 'letra' else 'cog', (q[0] + 12, q[1]), 0.6,
              (0, 160, 240))
    out = cv2.addWeighted(img, 0.45, sobre, 0.55, 0)
    texto(out, f'mapa {os.path.basename(mapa)} em cima da foto (camera "{principal}", paredes de {z:g} mm)',
          (8, out.shape[0] - 12), 0.6, (255, 255, 255))
    grava(out, arq(a.nome, 'sobreposicao.png'), max_lado=1800)


def _parede_3d(img, cm, A, B, hb, z):
    q = cm.projeta([(A[0], A[1], hb), (B[0], B[1], hb), (B[0], B[1], hb + z), (A[0], A[1], hb + z)]).astype(np.int32)
    cv2.fillConvexPoly(img, q, (60, 200, 60))
    cv2.polylines(img, [q], True, (0, 90, 0), 2, cv2.LINE_AA)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('novo', help='cria a pasta de trabalho com a foto')
    p.add_argument('nome'); p.add_argument('foto')
    p = sp.add_parser('recorta', help='pedaço da foto ampliado, com régua')
    p.add_argument('nome'); [p.add_argument(k, type=int) for k in ('x0', 'y0', 'x1', 'y1')]
    p.add_argument('--zoom', type=float); p.add_argument('--saida')
    p = sp.add_parser('calibra', help='grava uma calibração (pontos foto -> chão) e mostra a vista de cima')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('pontos', nargs='+')
    p.add_argument('--altura', type=float, default=0.0, help='altura do plano dos pontos (piso de cima)')
    p.add_argument('--ladrilhos', help='região do mapa em que ela vale: c0,l0,c1,l1')
    p.add_argument('--fugas', action='store_true', help='pontos "ru,rv,X,Y" da vista_fugas.png (2 bastam)')
    p.add_argument('--area', help='região da vista: c0,l0,c1,l1'); p.add_argument('--obs'); p.add_argument('--saida')
    p = sp.add_parser('fugas', help='orientação do chão e foco pelas retas (vista de cima sem pontos conhecidos)')
    p.add_argument('nome'); p.add_argument('--leste', nargs='+', required=True, help='retas "x1,y1,x2,y2" para o leste')
    p.add_argument('--sul', nargs='+', required=True, help='retas "x1,y1,x2,y2" para o sul')
    p.add_argument('--vertical', nargs='+', help='retas "x1,y1,x2,y2" verticais (perfis, quinas de parede)')
    p.add_argument('--auto', action='store_true',
                   help='também acha as retas da foto e ajusta o foco com elas (confira: na foto1 entortou o chão)')
    p.add_argument('--fov', type=float, help='abertura horizontal, se souber')
    p.add_argument('--abaixo', type=float, default=10, help='graus abaixo do horizonte que a vista mostra')
    p = sp.add_parser('camera', help='foco da câmera (para as alturas); refaça com --topo para acertar')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('--fov', type=float, help='abertura horizontal')
    p.add_argument('--topo', nargs='+', help='pontos "fx,fy,X,Y" do alto das paredes (X, Y do eixo da parede)')
    p.add_argument('--altura', dest='altura_paredes', type=float, help='altura das paredes (mm), se souber')
    p = sp.add_parser('vista', help='vista de cima com a grade dos ladrilhos')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('--area')
    p.add_argument('--altura', dest='altura_vista', type=float, help='plano a esta altura (mm) em vez do chão')
    p.add_argument('--saida')
    p = sp.add_parser('paredes', help='as paredes possíveis desenhadas na foto, com o nome de cada borda')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('--area'); p.add_argument('--altura', type=float)
    p = sp.add_parser('pisos', help='cor do meio de cada ladrilho e um palpite')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('--area')
    p = sp.add_parser('ponto', help='ponto da foto -> mm e ladrilho; --parede: a face de parede (vítimas)')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('pontos', nargs='+')
    p.add_argument('--altura', type=float); p.add_argument('--parede', action='store_true')
    p.add_argument('--espessura', type=float, default=20.0, help='espessura das paredes (mm)')
    p = sp.add_parser('monta', help='descricao.json -> mapa (e confere)')
    p.add_argument('nome'); p.add_argument('--saida')
    p = sp.add_parser('confere', help='avisos e desenho de um mapa')
    p.add_argument('mapa'); p.add_argument('--imagem')
    p = sp.add_parser('compara', help='foto de cima | mapa, e o mapa em cima da foto')
    p.add_argument('nome'); p.add_argument('mapa', nargs='?'); p.add_argument('--calib')
    # ponto com coordenada negativa ("-300,889,0,0") não é opção: o espaço na frente avisa o argparse
    a = ap.parse_args([' ' + s if s[:1] == '-' and s[1:2].isdigit() else s for s in sys.argv[1:]])
    globals()['cmd_' + a.cmd](a)


if __name__ == '__main__':
    main()
