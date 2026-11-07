"""Mapa do simulador a partir da foto de uma pista de verdade (feito com o apoio do Claude).

O passo a passo está em MAPA_DA_FOTO.md, nesta pasta. Cada foto ganha uma pasta de trabalho em
simuladorLine/fotos_mapa/<nome>/:
  foto.jpg        a foto, já de pé (o 'novo' aplica a orientação do celular)
  projeto.json    as calibrações: pontos da foto ligados a pontos do chão
  descricao.json  o que foi reconhecido (ladrilhos, itens, área de resgate); o 'monta' faz o mapa dele
  *.png           imagens de trabalho (saem de novo; o git ignora)

Coordenadas:
  foto   pixels da foto.jpg (x para a direita, y para baixo), os números da régua das imagens.
  chão   mm no referencial do mapa: X para o leste a partir da borda oeste do mapa e Y para o SUL a partir
         da borda norte (o norte é o alto da tela do simulador). O ladrilho (x, y) vai de X = 300x a
         300x + 300 e de Y = 300y a 300y + 300.
  u, v   dentro de um ladrilho (lombadas, obstáculos) ou da área de resgate: mm a partir do canto
         sudoeste, v para o norte, como no arquivo do mapa.

Comandos (da pasta simuladorLine):
  python ferramentas/foto_mapa.py novo NOME FOTO
  python ferramentas/foto_mapa.py recorta NOME x0 y0 x1 y1 [--zoom Z] [--emendas]
  python ferramentas/foto_mapa.py calibra NOME CALIB "fx,fy,X,Y" ... [--ladrilhos x0,y0,x1,y1] [--area ...]
  python ferramentas/foto_mapa.py vista NOME CALIB [--area x0,y0,x1,y1] [--emendas | --preto]
  python ferramentas/foto_mapa.py ponto NOME CALIB fx,fy ... [--zona x,y,alt]
  python ferramentas/foto_mapa.py casa NOME CALIB x0,y0,x1,y1 [--limiar V,S]
  python ferramentas/foto_mapa.py ladrilho NOME CALIB x y
  python ferramentas/foto_mapa.py catalogo
  python ferramentas/foto_mapa.py candidatos tile-16_2 tile-30/90 ...
  python ferramentas/foto_mapa.py inclinacao NOME CALIB --sobe N --dobra Y --em X --topo fx,fy --comprimento L
  python ferramentas/foto_mapa.py monta NOME [--saida mapas/arquivo.json]
  python ferramentas/foto_mapa.py confere mapas/arquivo.json
  python ferramentas/foto_mapa.py compara NOME [mapas/arquivo.json]
As áreas (--area, --ladrilhos e a do 'casa') são em ladrilhos, com as duas pontas incluídas.
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
RAIZ = os.path.dirname(AQUI)                       # simuladorLine
PASTAS = os.path.join(RAIZ, 'fotos_mapa')
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
sys.path.insert(0, RAIZ)
from sim import ladrilhos as LT  # noqa: E402
from sim.mapa import OBSTACULO_PADRAO, Mapa  # noqa: E402

T = LT.TAM                                         # 300 mm
MAGENTA = (255, 0, 255)
CIANO = (255, 220, 0)
MAX_LADO = 1600                                    # px: imagens maiores ficam ruins de ler


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


def homografia(proj, calib):
    c = proj['calibracoes'].get(calib)
    if c is None:
        sys.exit(f'Calibração "{calib}" não existe. Tem: {", ".join(proj["calibracoes"]) or "nenhuma"}')
    return np.array(c['H'], np.float64)


def foto_para_chao(H, pts):
    return cv2.perspectiveTransform(np.float64(pts).reshape(-1, 1, 2), H).reshape(-1, 2)


def area_ladrilhos(txt):
    x0, y0, x1, y1 = (int(v) for v in txt.split(','))
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def grava(img, caminho, max_lado=MAX_LADO):
    """Grava reduzindo para caber em max_lado (as imagens vão ser lidas pelo Claude)."""
    h, w = img.shape[:2]
    e = min(1.0, max_lado / max(h, w))
    if e < 1:
        img = cv2.resize(img, (int(w * e), int(h * e)), interpolation=cv2.INTER_AREA)
    cv2.imwrite(caminho, img)
    print('imagem:', caminho, f'({img.shape[1]} x {img.shape[0]})')


def realca_emendas(img, raio=5, teto=16):
    """Realça riscos finos um pouco mais escuros que o branco em volta (emendas dos ladrilhos)."""
    c = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    d = cv2.subtract(cv2.GaussianBlur(c, (0, 0), raio), c)
    d = cv2.normalize(np.clip(d, 0, teto), None, 0, 255, cv2.NORM_MINMAX)
    return cv2.cvtColor(255 - d, cv2.COLOR_GRAY2BGR)


def mascara_preto(img, limiar=(105, 110)):
    """Pixels de fita preta: escuros (V < limiar[0]) e sem cor (S < limiar[1])."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    m = ((hsv[:, :, 2] < limiar[0]) & (hsv[:, :, 1] < limiar[1])).astype(np.uint8)
    return cv2.morphologyEx(m, cv2.MORPH_OPEN, np.ones((5, 5), np.uint8))


def texto(img, s, p, esc=0.5, cor=MAGENTA, esp=1):
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


def passo_regua(largura_foto_px, largura_img_px):
    """Passo da régua (px da foto) para dar umas 10-20 linhas na imagem."""
    for p in (25, 50, 100, 200, 250, 500):
        if largura_foto_px / p <= 20:
            return p
    return 1000


# ------------------------------------------------------------------ desenho do mapa
def desenha_mapa(m, px=150):
    """Mapa visto de cima (ladrilhos, lombadas, obstáculos, área, início), px por ladrilho."""
    e = px / T
    img = np.full((m.altura * px, m.largura * px, 3), 70, np.uint8)
    for k in sorted(m.ladrilhos, key=lambda k: k[2]):
        t = m.ladrilhos[k]
        x, y = k[0], k[1]
        if not m.dentro(x, y):
            continue
        rgb = cv2.resize(m.cat.rgb(t['tipo'], t['rot'])[:, :, ::-1], (px, px), interpolation=cv2.INTER_AREA)
        if t.get('inclinacao') or t.get('rampa'):
            rgb = (0.75 * rgb + 0.25 * np.array([200, 80, 160])).astype(np.uint8)
        img[y * px:(y + 1) * px, x * px:(x + 1) * px] = rgb
        if t.get('checkpoint'):
            cv2.rectangle(img, (x * px + 3, y * px + 3), ((x + 1) * px - 4, (y + 1) * px - 4), (0, 210, 255), 3)
        p = t.get('inclinacao') or t.get('rampa')
        if p:
            texto(img, f"{'incl' if t.get('inclinacao') else 'rampa'} {p.get('sobe')} {p.get('graus')}",
                  (x * px + 4, (y + 1) * px - 8), 0.38, (255, 255, 255))
    if m.zona:
        z = m.zona
        cv2.rectangle(img, (z['x'] * px, z['y'] * px), ((z['x'] + z['larg']) * px - 1, (z['y'] + z['alt']) * px - 1),
                      (130, 130, 130), max(2, int(25 * e)))
        for ob in z.get('obstaculos') or []:
            X, Y = z['x'] * T + ob['u'], (z['y'] + z['alt']) * T - ob['v']
            _caixa(img, X * e, Y * e, ob, e)
    for k, t in m.ladrilhos.items():
        X0, Y1 = k[0] * T, (k[1] + 1) * T                 # canto sudoeste do ladrilho, em mm
        for lb in t.get('lombadas', []):
            u1, v1, u2, v2 = m.segmento_lombada(lb)
            a = (int((X0 + u1) * e), int((Y1 - v1) * e))
            b = (int((X0 + u2) * e), int((Y1 - v2) * e))
            cv2.line(img, a, b, (40, 40, 40), max(3, int(14 * e)))
            cv2.line(img, a, b, (250, 250, 250), max(1, int(8 * e)))
        for ob in t.get('obstaculos', []):
            _caixa(img, (X0 + ob['u']) * e, (Y1 - ob['v']) * e, ob, e)
    if m.inicio:
        x, y = m.inicio[0], m.inicio[1]
        c = (int((x + 0.5) * px), int((y + 0.5) * px))
        cv2.circle(img, c, int(px * 0.12), (0, 0, 230), -1)
        texto(img, 'inicio ' + (m.inicio_dir or ''), (x * px + 4, y * px + 16), 0.45, (0, 0, 230))
    for x in range(m.largura + 1):
        cv2.line(img, (x * px, 0), (x * px, m.altura * px), (160, 160, 160), 1)
    for y in range(m.altura + 1):
        cv2.line(img, (0, y * px), (m.largura * px, y * px), (160, 160, 160), 1)
    for x in range(m.largura):
        for y in range(m.altura):
            texto(img, f'{x},{y}', (x * px + px - 34, y * px + 14), 0.35, (120, 120, 120))
    return img


def _caixa(img, cx, cy, ob, e):
    lx, ly = ob.get('larg', OBSTACULO_PADRAO['larg']) * e / 2, ob.get('comp', OBSTACULO_PADRAO['comp']) * e / 2
    cv2.rectangle(img, (int(cx - lx), int(cy - ly)), (int(cx + lx), int(cy + ly)), (0, 200, 240), -1)
    cv2.rectangle(img, (int(cx - lx), int(cy - ly)), (int(cx + lx), int(cy + ly)), (0, 90, 120), 1)


def foto_de_cima(nome, proj, largura, altura, px, so_calib=None):
    """Foto retificada na grade do mapa (px por ladrilho). Cada calibração com 'ladrilhos' só vale
    naquela região; as sem região cobrem o resto (as com região são aplicadas por cima)."""
    im = le_foto(nome)
    out = np.full((altura * px, largura * px, 3), 50, np.uint8)
    e = px / T
    S = np.array([[e, 0, 0], [0, e, 0], [0, 0, 1]])
    cals = proj['calibracoes']
    ordem = [c for c in cals if not cals[c].get('ladrilhos')] + [c for c in cals if cals[c].get('ladrilhos')]
    if so_calib:
        ordem = [so_calib]
    for c in ordem:
        w = cv2.warpPerspective(im, S @ np.array(cals[c]['H']), (largura * px, altura * px),
                                flags=cv2.INTER_AREA, borderValue=(50, 50, 50))
        r = cals[c].get('ladrilhos')
        if r and not so_calib:
            x0, y0, x1, y1 = r
            out[y0 * px:(y1 + 1) * px, x0 * px:(x1 + 1) * px] = w[y0 * px:(y1 + 1) * px, x0 * px:(x1 + 1) * px]
        else:
            out = w
    return out


def grade_ladrilhos(img, X0, Y0, ppm, cor=MAGENTA, rotulos=True):
    """Grade de 300 mm (ladrilhos do mapa) numa vista de cima cujo canto é (X0, Y0) mm."""
    h, w = img.shape[:2]
    for x in range(math.floor(X0 / T), math.ceil((X0 + w / ppm) / T) + 1):
        X = int((x * T - X0) * ppm)
        cv2.line(img, (X, 0), (X, h), cor, 1)
    for y in range(math.floor(Y0 / T), math.ceil((Y0 + h / ppm) / T) + 1):
        Y = int((y * T - Y0) * ppm)
        cv2.line(img, (0, Y), (w, Y), cor, 1)
    if rotulos:
        for x in range(math.floor(X0 / T), math.ceil((X0 + w / ppm) / T)):
            for y in range(math.floor(Y0 / T), math.ceil((Y0 + h / ppm) / T)):
                texto(img, f'{x},{y}', (int((x * T - X0) * ppm) + 4, int((y * T - Y0) * ppm) + 16), 0.45, cor)
    return img


# ------------------------------------------------------------------ comandos
def cmd_novo(a):
    os.makedirs(pasta(a.nome), exist_ok=True)
    im = cv2.imread(a.foto)                        # o imread já aplica a orientação (EXIF) do celular
    if im is None:
        sys.exit(f'Não consegui ler {a.foto}')
    cv2.imwrite(arq(a.nome, 'foto.jpg'), im, [cv2.IMWRITE_JPEG_QUALITY, 95])
    p = arq(a.nome, 'projeto.json')
    if not os.path.exists(p):
        grava_projeto(a.nome, {'foto_original': os.path.abspath(a.foto), 'calibracoes': {}})
    d = arq(a.nome, 'descricao.json')
    if not os.path.exists(d):
        shutil.copy(os.path.join(AQUI, 'foto_mapa_descricao_modelo.json'), d)
    h, w = im.shape[:2]
    print(f'foto {w} x {h} px em {arq(a.nome, "foto.jpg")}')
    e = MAX_LADO / max(w, h)
    img = cv2.resize(im, (int(w * e), int(h * e)), interpolation=cv2.INTER_AREA)
    grava(regua_foto(img, 0, 0, e, passo_regua(w, img.shape[1])), arq(a.nome, 'foto_regua.png'))


def cmd_recorta(a):
    im = le_foto(a.nome)
    x0, y0, x1, y1 = a.x0, a.y0, a.x1, a.y1
    r = im[max(0, y0):y1, max(0, x0):x1]
    zoom = a.zoom or min(4.0, MAX_LADO / max(r.shape[:2]))
    r = cv2.resize(r, None, fx=zoom, fy=zoom, interpolation=cv2.INTER_AREA if zoom < 1 else cv2.INTER_CUBIC)
    if a.emendas:
        r = realca_emendas(r, raio=max(2, 5 * zoom))
    else:
        g = cv2.cvtColor(r, cv2.COLOR_BGR2LAB)
        g[:, :, 0] = cv2.createCLAHE(2.0, (8, 8)).apply(g[:, :, 0])
        r = cv2.cvtColor(g, cv2.COLOR_LAB2BGR)
    regua_foto(r, max(0, x0), max(0, y0), zoom, passo_regua(x1 - x0, r.shape[1]))
    grava(r, a.saida or arq(a.nome, f'recorte_{x0}_{y0}.png'), max_lado=int(MAX_LADO * 1.25))


def cmd_calibra(a):
    proj = le_projeto(a.nome)
    pts = [tuple(float(v) for v in p.split(',')) for p in a.pontos]
    if len(pts) < 4 or any(len(p) != 4 for p in pts):
        sys.exit('Preciso de pelo menos 4 pontos "fx,fy,X,Y" (foto -> chão em mm)')
    src = np.float64([p[:2] for p in pts])
    dst = np.float64([p[2:] for p in pts])
    if len(pts) == 4:
        H = cv2.getPerspectiveTransform(np.float32(src), np.float32(dst)).astype(np.float64)
    else:
        H, _ = cv2.findHomography(src, dst, 0)          # mínimos quadrados com todos os pontos
    err = np.linalg.norm(foto_para_chao(H, src) - dst, axis=1)
    c = {'pontos': [list(p) for p in pts], 'H': H.tolist()}
    if a.ladrilhos:
        c['ladrilhos'] = list(area_ladrilhos(a.ladrilhos))
    if a.obs:
        c['obs'] = a.obs
    proj['calibracoes'][a.calib] = c
    grava_projeto(a.nome, proj)
    print(f'calibração "{a.calib}" gravada com {len(pts)} pontos')
    if len(pts) > 4:
        print('erro de cada ponto (mm):', ' '.join(f'{v:.0f}' for v in err),
              ' <- acima de ~20 mm, algum ponto está errado ou o chão não é plano ali')
    a.area = a.area or a.ladrilhos
    a.emendas = a.preto = False
    a.ppm = None
    cmd_vista(a)


def area_da_calibracao(c):
    """A região dela, ou os ladrilhos dos pontos e mais um em volta."""
    if c.get('ladrilhos'):
        return tuple(c['ladrilhos'])
    dst = np.float64([p[2:] for p in c['pontos']])
    x0, y0 = np.floor(dst.min(0) / T).astype(int) - 1
    x1, y1 = np.floor((dst.max(0) - 1) / T).astype(int) + 1
    return int(x0), int(y0), int(x1), int(y1)


def cmd_vista(a):
    proj = le_projeto(a.nome)
    H = homografia(proj, a.calib)
    x0, y0, x1, y1 = area_ladrilhos(a.area) if a.area else area_da_calibracao(proj['calibracoes'][a.calib])
    X0, Y0, X1, Y1 = x0 * T - 60, y0 * T - 60, (x1 + 1) * T + 60, (y1 + 1) * T + 60
    ppm = a.ppm or min(1.0, MAX_LADO / max(X1 - X0, Y1 - Y0))
    S = np.array([[ppm, 0, -X0 * ppm], [0, ppm, -Y0 * ppm], [0, 0, 1]])
    W, Hh = int((X1 - X0) * ppm), int((Y1 - Y0) * ppm)
    v = cv2.warpPerspective(le_foto(a.nome), S @ H, (W, Hh), flags=cv2.INTER_AREA, borderValue=(50, 50, 50))
    if a.emendas:
        v = realca_emendas(v, raio=max(2, 6 * ppm), teto=18)
    elif a.preto:
        v = cv2.cvtColor(255 - mascara_preto(v) * 255, cv2.COLOR_GRAY2BGR)
    grade_ladrilhos(v, X0, Y0, ppm)
    for fx, fy, X, Y in proj['calibracoes'][a.calib]['pontos']:     # os pontos usados, em verde
        cv2.circle(v, (int((X - X0) * ppm), int((Y - Y0) * ppm)), 6, (0, 200, 0), 2)
    suf = '_emendas' if a.emendas else '_preto' if a.preto else ''
    grava(v, a.saida or arq(a.nome, f'vista_{a.calib}{suf}.png'))


def cmd_ponto(a):
    proj = le_projeto(a.nome)
    H = homografia(proj, a.calib)
    zona = [int(v) for v in a.zona.split(',')] if a.zona else None
    for p in a.pontos:
        fx, fy = (float(v) for v in p.split(','))
        X, Y = foto_para_chao(H, [(fx, fy)])[0]
        x, y = int(X // T), int(Y // T)
        s = f'foto ({fx:.0f}, {fy:.0f}) -> chão X {X:.0f} Y {Y:.0f} mm = ladrilho ({x}, {y}), ' \
            f'u {X - x * T:.0f} v {(y + 1) * T - Y:.0f}'
        if zona:
            zx, zy, alt = zona
            s += f'; na área: u {X - zx * T:.0f} v {(zy + alt) * T - Y:.0f}'
        print(s)


def cmd_ladrilho(a):
    """Um ladrilho de perto (2 px/mm) com régua u/v a cada 50 mm, para medir lombadas e obstáculos."""
    proj = le_projeto(a.nome)
    H = homografia(proj, a.calib)
    mg, E = a.margem, 2
    S = np.array([[E, 0, -(a.x * T - mg) * E], [0, E, -(a.y * T - mg) * E], [0, 0, 1]])
    L = (T + 2 * mg) * E
    img = cv2.warpPerspective(le_foto(a.nome), S @ H, (L, L), flags=cv2.INTER_CUBIC, borderValue=(50, 50, 50))
    for k in range(-50, T + 51, 50):
        p = (mg + k) * E
        cor = MAGENTA if k in (0, T) else (200, 120, 255)
        cv2.line(img, (p, 0), (p, L), cor, 1)                    # u = k
        cv2.line(img, (0, L - p), (L, L - p), cor, 1)            # v = k
        texto(img, str(k), (p + 2, 14), 0.42)
        texto(img, str(k), (2, L - p - 4), 0.42)
    texto(img, f'ladrilho ({a.x}, {a.y})  u ->   v ^', (8, L - 8), 0.55, (255, 255, 255))
    try:                                                         # lombadas já descritas, em ciano
        lad = json.load(open(arq(a.nome, 'descricao.json'), encoding='utf-8'))['ladrilhos'].get(f'{a.x},{a.y}')
        for lb in (lad.get('lombadas', []) if isinstance(lad, dict) else []):
            u1, v1, u2, v2 = Mapa().segmento_lombada(lb)
            cv2.line(img, (int((mg + u1) * E), int(L - (mg + v1) * E)), (int((mg + u2) * E), int(L - (mg + v2) * E)),
                     CIANO, 2)
    except (OSError, KeyError, ValueError, AttributeError):
        pass
    grava(img, a.saida or arq(a.nome, f'ladrilho_{a.x}_{a.y}.png'))


def cmd_casa(a):
    """Compara cada quadrado da foto retificada com os ladrilhos oficiais (4 rotações, deslocamentos
    de até 40 mm). Nota = distância média (mm) entre as linhas pretas da foto e as do ladrilho, nos
    dois sentidos (0 = igual). Grava os 6 melhores de cada quadrado e uma imagem foto | escolhido."""
    proj = le_projeto(a.nome)
    H = homografia(proj, a.calib)
    x0, y0, x1, y1 = area_ladrilhos(a.area)
    NC, NL, PAD = x1 - x0 + 1, y1 - y0 + 1, 50
    S = np.array([[1, 0, -(x0 * T - PAD)], [0, 1, -(y0 * T - PAD)], [0, 0, 1]], np.float64)
    W, Hh = NC * T + 2 * PAD, NL * T + 2 * PAD
    ret = cv2.warpPerspective(le_foto(a.nome), S @ H, (W, Hh), flags=cv2.INTER_AREA, borderValue=(90, 90, 90))
    lim = tuple(int(v) for v in a.limiar.split(','))
    preto = mascara_preto(ret, lim)
    grava(cv2.cvtColor(255 - preto * 255, cv2.COLOR_GRAY2BGR), arq(a.nome, f'casa_{x0}_{y0}_preto.png'))
    dt_foto = cv2.distanceTransform(1 - preto, cv2.DIST_L2, 3)

    cat = LT.catalogo()
    nomes = [n for n in cat.nomes() if n != 'gangorra']
    CLIP = 45.0
    desl = [(dx, dy) for dx in range(-40, 41, 8) for dy in range(-40, 41, 8)]
    D = np.array(desl)
    rng = np.random.default_rng(1)
    modelos = {}
    for n in nomes:
        for rot in (0, 90, 180, 270):
            mt = cat.material_girado(n, rot)
            pre = (mt == LT.M_PRETO) | (mt == LT.M_VERDE) | (mt == LT.M_VERMELHO)
            ys, xs = np.nonzero(pre)
            if len(xs) > 500:
                k = rng.choice(len(xs), 500, replace=False)
                xs, ys = xs[k], ys[k]
            dt = cv2.distanceTransform((~pre).astype(np.uint8), cv2.DIST_L2, 3) if pre.any() else None
            modelos[(n, rot)] = (xs, ys, dt)

    escolha, linhas = {}, []
    for r in range(NL):
        for c in range(NC):
            ox, oy = PAD + c * T, PAD + r * T
            ys, xs = np.nonzero(preto[oy:oy + T, ox:ox + T])
            if len(xs) > 500:
                k = rng.choice(len(xs), 500, replace=False)
                xs, ys = xs[k], ys[k]
            notas = []
            for (n, rot), (tx, ty, tdt) in modelos.items():
                if len(tx):        # linhas do ladrilho longe das da foto
                    da = np.minimum(dt_foto[oy + ty[None, :] + D[:, 1:], ox + tx[None, :] + D[:, :1]], CLIP).mean(1)
                else:
                    da = np.zeros(len(D))
                if len(xs):        # linhas da foto longe das do ladrilho
                    if tdt is None:
                        db = np.full(len(D), CLIP)
                    else:
                        qx = np.clip(xs[None, :] - D[:, :1], 0, T - 1)
                        qy = np.clip(ys[None, :] - D[:, 1:], 0, T - 1)
                        db = np.minimum(tdt[qy, qx], CLIP).mean(1)
                else:
                    db = np.zeros(len(D))
                s = da + db
                i = int(np.argmin(s))
                notas.append((float(s[i]), n, rot, desl[i]))
            notas.sort()
            escolha[(c, r)] = notas[0]
            linhas.append(f'({x0 + c},{y0 + r}): ' + '  '.join(f'{n}/{rot} {s:.1f} d{d}' for s, n, rot, d in notas[:6]))
    txt = arq(a.nome, f'casa_{x0}_{y0}.txt')
    open(txt, 'w', encoding='utf-8').write(
        '# (x,y): ladrilho/rotação nota(mm, menor = melhor) d(deslocamento da grade em mm)\n' + '\n'.join(linhas) + '\n')
    lado = np.full((NL * T, NC * T * 2 + 20, 3), 90, np.uint8)
    lado[:, :NC * T] = ret[PAD:PAD + NL * T, PAD:PAD + NC * T]
    for (c, r), (s, n, rot, d) in escolha.items():
        X = NC * T + 20 + c * T
        lado[r * T:(r + 1) * T, X:X + T] = cat.rgb(n, rot)[:, :, ::-1]
        cv2.rectangle(lado, (X, r * T), (X + T - 1, (r + 1) * T - 1), (200, 0, 200), 1)
        texto(lado, f'{n} {rot}', (X + 4, r * T + 18), 0.55)
        texto(lado, f'{s:.0f}', (X + 4, r * T + 40), 0.5)
    for c in range(NC + 1):
        cv2.line(lado, (c * T, 0), (c * T, NL * T), (200, 0, 200), 1)
    for r in range(NL + 1):
        cv2.line(lado, (0, r * T), (NC * T, r * T), (200, 0, 200), 1)
    for r in range(NL):
        for c in range(NC):
            texto(lado, f'{x0 + c},{y0 + r}', (c * T + 4, r * T + 18), 0.55)
    print('\n'.join(linhas))
    print('lista:', txt)
    grava(lado, arq(a.nome, f'casa_{x0}_{y0}.png'))


def cmd_catalogo(a):
    cat = LT.catalogo()
    nomes = cat.nomes()
    TT, COLS = 150, 12
    img = np.full((((len(nomes) + COLS - 1) // COLS) * (TT + 22), COLS * TT, 3), 110, np.uint8)
    for i, n in enumerate(nomes):
        x, y = (i % COLS) * TT, (i // COLS) * (TT + 22)
        img[y + 3:y + TT - 3, x + 3:x + TT - 3] = cv2.resize(cat.rgb(n, 0)[:, :, ::-1], (TT - 6, TT - 6),
                                                              interpolation=cv2.INTER_AREA)
        texto(img, n, (x + 4, y + TT + 14), 0.45, (255, 255, 255))
    os.makedirs(PASTAS, exist_ok=True)
    grava(img, a.saida or os.path.join(PASTAS, 'catalogo_ladrilhos.png'), max_lado=1800)


def cmd_candidatos(a):
    """Ladrilhos grandes, com rotação e as ligações (entrada->saída), para decidir à mão."""
    cat = LT.catalogo()
    TT, COLS = 220, 6
    img = np.full((((len(a.ladrilhos) + COLS - 1) // COLS) * (TT + 42), COLS * (TT + 10), 3), 110, np.uint8)
    for i, n in enumerate(a.ladrilhos):
        rot = 0
        if '/' in n:
            n, rot = n.split('/')
            rot = int(rot)
        if not cat.existe(n):
            print('não existe:', n)
            continue
        x, y = (i % COLS) * (TT + 10), (i // COLS) * (TT + 42)
        img[y:y + TT, x:x + TT] = cv2.resize(cat.rgb(n, rot)[:, :, ::-1], (TT, TT), interpolation=cv2.INTER_AREA)
        texto(img, f'{n} {rot}', (x + 2, y + TT + 16), 0.5, (255, 255, 255))
        cam = ' '.join(f'{e}>{s}' for e, s in cat.caminhos(n, rot).items())
        texto(img, cam[:34], (x + 2, y + TT + 34), 0.42, (255, 255, 0))
    os.makedirs(PASTAS, exist_ok=True)
    grava(img, a.saida or os.path.join(PASTAS, 'candidatos.png'))


def cmd_inclinacao(a):
    """Estima os graus de um tabuleiro inclinado. A calibração do chão dá a posição da câmera (supondo
    o centro óptico no meio da foto e testando a abertura horizontal, que não se sabe); depois procura o
    ângulo que leva a borda de cima do tabuleiro (a 'comprimento' mm da dobra) ao ponto 'topo' da foto."""
    proj = le_projeto(a.nome)
    Hc = np.linalg.inv(homografia(proj, a.calib))                 # chão (mm) -> foto
    h, w = le_foto(a.nome).shape[:2]
    tx, ty = (float(v) for v in a.topo.split(','))
    eixo = {'N': (0, -1), 'S': (0, 1), 'L': (1, 0), 'O': (-1, 0)}[a.sobe]
    for fov in range(55, 90, 5):
        f = (w / 2) / math.tan(math.radians(fov / 2))
        K = np.array([[f, 0, w / 2], [0, f, h / 2], [0, 0, 1.0]])
        M = np.linalg.inv(K) @ Hc
        lam = (np.linalg.norm(M[:, 0]) + np.linalg.norm(M[:, 1])) / 2
        r1, r2, t = M[:, 0] / lam, M[:, 1] / lam, M[:, 2] / lam
        if t[2] < 0:
            r1, r2, t = -r1, -r2, -t
        R = np.column_stack([r1, r2, np.cross(r1, r2)])
        C = -R.T @ t
        cima = 1.0 if C[2] > 0 else -1.0                          # o lado do chão em que a câmera está

        def projeta(P):
            p = K @ (R @ np.array(P, float) + t)
            return p[:2] / p[2]

        def borda(th, em):
            """Ponto da borda de cima do tabuleiro inclinado th rad, na posição 'em' ao longo dela."""
            d, z = a.comprimento * math.cos(th), cima * a.comprimento * math.sin(th)
            if eixo[0]:
                return projeta((a.dobra + eixo[0] * d, em, z))
            return projeta((em, a.dobra + eixo[1] * d, z))

        melhor = None
        for g10 in range(0, 451):
            th = math.radians(g10 / 10)
            q1, q2 = borda(th, a.em - 300), borda(th, a.em + 300)
            u = q2 - q1                       # distância do ponto 'topo' à borda prevista (a reta inteira)
            e = abs(u[0] * (ty - q1[1]) - u[1] * (tx - q1[0])) / max(1e-9, math.hypot(*u))
            if melhor is None or e < melhor[0]:
                melhor = (e, g10 / 10)
        e, g = melhor
        aviso = '  <- não chega no ponto: confira dobra/comprimento' if e > 5 or g in (0, 45) else ''
        print(f'abertura {fov}°: câmera a {abs(C[2]):.0f} mm de altura, ortogonalidade {r1 @ r2:+.3f} '
              f'-> {g:.1f}° (sobra {e:.0f} px){aviso}')
    print('Vale a linha da abertura com ortogonalidade mais perto de 0 (celular: 65-80°).')


def monta_dict(d):
    """descricao.json -> dicionário do mapa (formato simuladorLine/1)."""
    lads = []
    for chave, v in d['ladrilhos'].items():
        xyz = [int(s) for s in chave.split(',')]
        x, y, z = (xyz + [0])[:3]
        if isinstance(v, str):
            partes = v.split()
            v = {'tipo': partes[0], 'rot': int(partes[1]) if len(partes) > 1 else 0}
        t = {'x': x, 'y': y, 'z': z, 'tipo': v['tipo'], 'rot': int(v.get('rot', 0)) % 360}
        for k, val in v.items():
            if k in ('tipo', 'rot') or k.startswith('_'):
                continue
            if k == 'obstaculos':
                val = [dict(OBSTACULO_PADRAO, **ob) for ob in val]
            t[k] = val
        lads.append(t)
    for inc in d.get('inclinacao', []):
        (xa, ya), (xb, yb) = inc['de'], inc['ate']
        for t in lads:
            if min(xa, xb) <= t['x'] <= max(xa, xb) and min(ya, yb) <= t['y'] <= max(ya, yb) and 'rampa' not in t:
                t.setdefault('inclinacao', {'sobe': inc['sobe'], 'graus': inc['graus']})
    lads.sort(key=lambda t: (t['z'], t['y'], t['x']))
    inicio = list(d['inicio']) + [0] * (3 - len(d['inicio'])) if d.get('inicio') else None
    m = {'formato': 'simuladorLine/1', 'regra': 'RoboCupJunior Rescue Line 2026', 'nome': d['nome']}
    if d.get('_comentario'):
        m['_comentario'] = d['_comentario']
    m.update({'largura': d['largura'], 'altura': d['altura'], 'inicio': inicio,
              'inicio_dir': d.get('inicio_dir'), 'tempo': float(d.get('tempo', 480.0)), 'ladrilhos': lads})
    if d.get('zona_resgate'):
        m['zona_resgate'] = d['zona_resgate']
    return m


def confere(caminho, imagem=None):
    m = Mapa.carregar(caminho)
    p = m.passos()
    print(f'{caminho}: {m.largura} x {m.altura}, {len([t for t in m.ladrilhos.values() if not t.get("_zona")])} '
          f'ladrilhos, caminho com {len(p)} passos')
    print('  ' + ' '.join(f"{s['k'][0]},{s['k'][1]}{'*' if s.get('zona') else ''}" for s in p))
    av = m.validar()
    for v in av:
        print('  aviso:', v)
    if not av:
        print('  sem avisos')
    if imagem:
        grava(desenha_mapa(m), imagem)
    return m


def cmd_monta(a):
    d = json.load(open(arq(a.nome, 'descricao.json'), encoding='utf-8'))
    m = monta_dict(d)
    saida = a.saida or os.path.join(RAIZ, 'mapas', d['nome'] + '.json')
    try:
        Mapa.de_dict(json.loads(json.dumps(m)))
    except (ValueError, KeyError) as e:
        sys.exit(f'descricao.json com erro: {e}')
    json.dump(m, open(saida, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('mapa gravado:', saida)
    confere(saida, arq(a.nome, 'mapa.png'))


def cmd_confere(a):
    confere(a.mapa, a.imagem or os.path.splitext(a.mapa)[0] + '_desenho.png')
    if a.janela:
        captura_janela(a.mapa, a.janela)


def captura_janela(mapa, saida):
    """O mapa desenhado pela janela do próprio simulador (sem abrir janela)."""
    import pygame
    from sim.app import Simulacao, carregar_cfg
    from sim.gui import Interface
    os.chdir(RAIZ)
    cfg = carregar_cfg('robo_4x4_camera.json')
    cfg['_arquivo'] = os.path.abspath('robo_4x4_camera.json')
    sim = Simulacao(Mapa.carregar(mapa), cfg, None, 0, 1)
    ui = Interface(sim, os.path.join(RAIZ, 'mapas'), RAIZ)
    ui.tela = pygame.display.set_mode((1700, 1250))
    ui.brick.visivel = False
    ui.sujo = True
    ui.rodar(quadros=4)
    pygame.image.save(ui.tela.subsurface(ui._area()), saida)
    sim.encerrar()
    print('imagem:', saida)


def cmd_compara(a):
    proj = le_projeto(a.nome)
    d = json.load(open(arq(a.nome, 'descricao.json'), encoding='utf-8'))
    mapa = a.mapa or os.path.join(RAIZ, 'mapas', d['nome'] + '.json')
    m = Mapa.carregar(mapa)
    px = max(60, min(150, MAX_LADO // (2 * m.largura)))
    foto = foto_de_cima(a.nome, proj, m.largura, m.altura, px)
    grade_ladrilhos(foto, 0, 0, px / T)
    sim = desenha_mapa(m, px)
    out = np.full((m.altura * px + 30, 2 * m.largura * px + 20, 3), 30, np.uint8)
    out[:m.altura * px, :m.largura * px] = foto
    out[:m.altura * px, m.largura * px + 20:] = sim
    texto(out, 'foto vista de cima, na grade do mapa', (8, m.altura * px + 21), 0.55, (255, 255, 255))
    texto(out, os.path.basename(mapa), (m.largura * px + 28, m.altura * px + 21), 0.55, (255, 255, 255))
    grava(out, a.saida or arq(a.nome, 'comparacao.png'), max_lado=1800)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    sp = ap.add_subparsers(dest='cmd', required=True)
    p = sp.add_parser('novo', help='cria a pasta de trabalho com a foto')
    p.add_argument('nome'); p.add_argument('foto')
    p = sp.add_parser('recorta', help='pedaço da foto ampliado, com régua')
    p.add_argument('nome'); [p.add_argument(k, type=int) for k in ('x0', 'y0', 'x1', 'y1')]
    p.add_argument('--zoom', type=float); p.add_argument('--emendas', action='store_true'); p.add_argument('--saida')
    p = sp.add_parser('calibra', help='grava uma calibração (pontos foto -> chão) e mostra a vista de cima')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('pontos', nargs='+')
    p.add_argument('--ladrilhos', help='região do mapa em que ela vale: x0,y0,x1,y1')
    p.add_argument('--area', help='região da vista: x0,y0,x1,y1'); p.add_argument('--obs')
    p.add_argument('--saida')
    p = sp.add_parser('vista', help='vista de cima com a grade dos ladrilhos')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('--area'); p.add_argument('--ppm', type=float)
    p.add_argument('--emendas', action='store_true'); p.add_argument('--preto', action='store_true')
    p.add_argument('--saida')
    p = sp.add_parser('ponto', help='ponto da foto -> mm no chão, ladrilho e u, v')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('pontos', nargs='+'); p.add_argument('--zona')
    p = sp.add_parser('casa', help='compara cada quadrado com os ladrilhos oficiais')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('area'); p.add_argument('--limiar', default='105,110')
    p = sp.add_parser('ladrilho', help='um ladrilho de perto com régua u/v')
    p.add_argument('nome'); p.add_argument('calib'); p.add_argument('x', type=int); p.add_argument('y', type=int)
    p.add_argument('--margem', type=int, default=60); p.add_argument('--saida')
    p = sp.add_parser('catalogo', help='folha com todos os ladrilhos')
    p.add_argument('--saida')
    p = sp.add_parser('candidatos', help='ladrilhos grandes com rotação e ligações')
    p.add_argument('ladrilhos', nargs='+'); p.add_argument('--saida')
    p = sp.add_parser('inclinacao', help='estima os graus de um tabuleiro inclinado')
    p.add_argument('nome'); p.add_argument('calib')
    p.add_argument('--sobe', required=True, choices='NSLO')
    p.add_argument('--dobra', type=float, required=True, help='mm da linha em que o tabuleiro sai do chão')
    p.add_argument('--em', type=float, required=True, help='mm da outra coordenada, onde se mede o topo')
    p.add_argument('--topo', required=True, help='fx,fy da borda de cima do tabuleiro na foto')
    p.add_argument('--comprimento', type=float, required=True, help='mm da dobra até a borda de cima')
    p = sp.add_parser('monta', help='descricao.json -> mapa (e confere)')
    p.add_argument('nome'); p.add_argument('--saida')
    p = sp.add_parser('confere', help='caminho, avisos e desenho de um mapa')
    p.add_argument('mapa'); p.add_argument('--imagem'); p.add_argument('--janela', help='também a imagem da janela')
    p = sp.add_parser('compara', help='foto de cima | mapa, lado a lado')
    p.add_argument('nome'); p.add_argument('mapa', nargs='?'); p.add_argument('--saida')
    a = ap.parse_args()
    globals()['cmd_' + a.cmd](a)


if __name__ == '__main__':
    main()
