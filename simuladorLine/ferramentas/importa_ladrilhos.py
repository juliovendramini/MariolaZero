"""Converte os ladrilhos do rcj-rescue-cms (MIT, github.com/robocup-junior/rcj-rescue-cms)
para o formato do simulador: PNG 300x300 (1 mm/px) só com as cores "puras" do piso
(branco, preto, verde, vermelho) + ladrilhos.json com caminhos, gaps e interseções.

Uso: python ferramentas/importa_ladrilhos.py CAMINHO/rcj-rescue-cms
"""
import json
import os
import re
import subprocess
import sys

import numpy as np
from PIL import Image

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(RAIZ, 'ladrilhos')
TAM = 300

# material -> cor de referência das imagens originais
PALETA = {
    'branco': (255, 255, 255),
    'preto': (35, 31, 32),
    'verde': (0, 166, 81),
    'vermelho': (192, 0, 0),
}
COR_SAIDA = {'branco': (255, 255, 255), 'preto': (20, 20, 20), 'verde': (0, 166, 81), 'vermelho': (200, 16, 16)}
IGNORAR = {'ev1.png', 'ev2.png', 'ev3.png', 'ev-entrance.png', 'ev-exit.png', 'tile-empty.png',
           'seesaw.png', 'exit.png'}


def le_tipos(cms):
    src = open(os.path.join(cms, 'models', 'lineMap.js'), encoding='utf-8').read()
    i = src.index('const tileTypes = [')
    j = src.index('];', i)
    js = 'console.log(JSON.stringify(' + src[i + 18:j + 1] + '))'
    out = subprocess.run(['node', '-e', js], capture_output=True, text=True, check=True).stdout
    return json.loads(out)


LADO_VERDE = 25   # mm: marcador verde da regra (25 x 25 mm)


def _componentes(m):
    """Componentes conectados (4-vizinhança) de uma máscara: lista de (ys, xs)."""
    vis = np.zeros_like(m, dtype=bool)
    out = []
    H, W = m.shape
    for y0, x0 in zip(*np.nonzero(m)):
        if vis[y0, x0]:
            continue
        pilha = [(y0, x0)]
        vis[y0, x0] = True
        ys, xs = [], []
        while pilha:
            y, x = pilha.pop()
            ys.append(y)
            xs.append(x)
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if 0 <= ny < H and 0 <= nx < W and m[ny, nx] and not vis[ny, nx]:
                    vis[ny, nx] = True
                    pilha.append((ny, nx))
        out.append((np.array(ys), np.array(xs)))
    return out


def corrige_verdes(idx, verde, preto, branco):
    """As imagens do CMS têm marcadores de 30, 40 e 64 mm. A regra é 25 x 25 mm: cada
    marcador vira um quadrado de 25 mm no canto dele que encosta na linha (o canto voltado
    para o cruzamento), mantendo a posição em relação à linha."""
    idx = idx.copy()
    m = idx == verde
    for ys, xs in _componentes(m):
        y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
        h, w = y1 - y0 + 1, x1 - x0 + 1
        if abs(h - LADO_VERDE) <= 2 and abs(w - LADO_VERDE) <= 2:
            continue
        idx[ys, xs] = branco
        melhor, canto = -1, (y0, x0)
        faixa = 4
        n = min(LADO_VERDE, h, w)
        for (cy, sy) in ((y0, -1), (y1, 1)):
            for (cx, sx) in ((x0, -1), (x1, 1)):
                # preto logo fora das duas bordas que se encontram neste canto
                ly = slice(min(cy, cy - sy * (n - 1)), max(cy, cy - sy * (n - 1)) + 1)
                lx = slice(min(cx, cx - sx * (n - 1)), max(cx, cx - sx * (n - 1)) + 1)
                fy = slice(max(0, min(cy + sy, cy + sy * faixa)), max(cy + sy, cy + sy * faixa) + 1)
                fx = slice(max(0, min(cx + sx, cx + sx * faixa)), max(cx + sx, cx + sx * faixa) + 1)
                horiz = (idx[fy, lx] == preto).sum()
                vert = (idx[ly, fx] == preto).sum()
                pontos = min(horiz, vert) * 2 + max(horiz, vert)
                if pontos > melhor:
                    melhor, canto = pontos, (cy, cx, sy, sx)
        cy, cx, sy, sx = canto
        ya, yb = sorted((cy, cy - sy * (LADO_VERDE - 1)))
        xa, xb = sorted((cx, cx - sx * (LADO_VERDE - 1)))
        bloco = idx[ya:yb + 1, xa:xb + 1]
        bloco[bloco != preto] = verde
    return idx


def limpa(caminho):
    im = Image.open(caminho).convert('RGBA')
    fundo = Image.new('RGBA', im.size, (255, 255, 255, 255))
    fundo.alpha_composite(im)
    im = fundo.convert('RGB')
    # algumas imagens têm 1 px a mais/menos
    im = im.resize((TAM, TAM), Image.LANCZOS)
    a = np.asarray(im).astype(np.int32)
    nomes = list(PALETA)
    # bordas suavizadas (cinza) não podem virar verde: cor só com croma alto
    croma = a.max(-1) - a.min(-1)
    lum = a.mean(-1)
    idx = np.where(lum < 128, nomes.index('preto'), nomes.index('branco'))
    colorido = croma > 70
    verde = colorido & (a[:, :, 1] > a[:, :, 0])
    idx = np.where(verde, nomes.index('verde'), idx)
    idx = np.where(colorido & ~verde, nomes.index('vermelho'), idx)
    idx = corrige_verdes(idx, nomes.index('verde'), nomes.index('preto'), nomes.index('branco'))
    out = np.zeros((TAM, TAM, 3), np.uint8)
    for k, n in enumerate(nomes):
        out[idx == k] = COR_SAIDA[n]
    return Image.fromarray(out), idx, nomes


def main():
    cms = sys.argv[1]
    os.makedirs(DEST, exist_ok=True)
    tipos = le_tipos(cms)
    catalogo = {}
    for t in tipos:
        img = t['image']
        if img in IGNORAR:
            continue
        nome = os.path.splitext(img)[0]
        im, idx, nomes = limpa(os.path.join(cms, 'public', 'images', 'tiles', img))
        im.save(os.path.join(DEST, nome + '.png'), optimize=True)
        n_verde = int((idx == nomes.index('verde')).sum())
        catalogo[nome] = {
            'imagem': nome + '.png',
            'caminhos': t.get('paths', {}),
            'gaps': int(t.get('gaps', 0)),
            'intersecoes': int(t.get('intersections', 0)),
            'id_cms': t['_id'],
            'tem_verde': n_verde > 50,
        }
    ordem = sorted(catalogo, key=lambda s: [int(x) if x.isdigit() else x for x in re.split(r'(\d+)', s)])
    with open(os.path.join(DEST, 'ladrilhos.json'), 'w', encoding='utf-8') as f:
        json.dump({'_fonte': 'rcj-rescue-cms (MIT) — github.com/robocup-junior/rcj-rescue-cms',
                   'tamanho_mm': TAM, 'mm_por_px': 1.0,
                   'ladrilhos': {k: catalogo[k] for k in ordem}}, f, indent=1, ensure_ascii=False)
    print(len(catalogo), 'ladrilhos')


if __name__ == '__main__':
    main()
