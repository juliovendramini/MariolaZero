"""Ladrilhos próprios do simulador (13/11/2026): uma pista de treino que não é ladrilho oficial, feita de uma
foto ou de um desenho, ocupando 1 ou mais ladrilhos (bloco de L x A).

Cada ladrilho próprio fica em simuladorLine/ladrilhos_proprios/:
  NOME.png        o desenho visto de cima, 1 mm por pixel (L*300 x A*300), só com branco, preto, verde e
                  vermelho (e prata, na cor exata do simulador). É o que os sensores "enxergam".
  proprios.json   a lista dos blocos: tamanho, descrição e, por peça ("coluna,linha", 0,0 = noroeste),
                  os caminhos (entrada > saída: N, L, S, O), gaps, interseções e o ponto de início/retorno.
  _conferir/      imagens para conferir (o git ignora)

No simulador, cada peça vira um ladrilho 'NOME@coluna,linha' (bloco 1x1: 'NOME'); na paleta do editor o
bloco aparece inteiro, no fim, e entra de uma vez com o canto noroeste na célula clicada (R gira).

Coordenadas do bloco: mm a partir do canto noroeste do bloco, u para a direita (leste) e v para baixo
(sul), como na imagem. A peça (c, l) vai de u = 300c a 300c + 300 e de v = 300l a 300l + 300.

Comandos (da pasta simuladorLine):
  python ferramentas/ladrilho_proprio.py foto NOME FOTO LxA "fx,fy,u,v" ... [--descricao TEXTO] [--prolonga MM]
        a foto vista de cima: 4 ou mais pontos da foto (pixels) ligados a pontos do bloco (mm). Um quadrado
        de fita, os cantos de um ladrilho ou os verdes (25 mm) servem. --prolonga: linha que para a menos
        de MM mm da borda do bloco (a foto acabou) vai até a borda, para emendar no vizinho.
  python ferramentas/ladrilho_proprio.py desenho NOME IMAGEM LxA [--descricao TEXTO] [--prolonga MM]
        a imagem já vista de cima (Paint, Inkscape, foto já endireitada), esticada para L*300 x A*300
  python ferramentas/ladrilho_proprio.py bordas NOME
        onde as linhas cruzam as bordas de cada peça (para escrever os caminhos)
  python ferramentas/ladrilho_proprio.py pecas NOME [--caminhos "c,l:E>S ..."] [--intersecoes "c,l:N ..."]
        [--gaps "c,l:N ..."] [--ponto "c,l:u,v[:RUMO] ..."] [--limpa]
        escreve as peças no proprios.json (o ponto é na peça: mm do canto noroeste dela)
  python ferramentas/ladrilho_proprio.py confere NOME     imagem com as peças, os caminhos e os pontos
  python ferramentas/ladrilho_proprio.py lista
O passo a passo está em LADRILHO_PROPRIO.md, nesta pasta.
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)                       # simuladorLine
os.environ.setdefault('SDL_VIDEODRIVER', 'dummy')
sys.path.insert(0, RAIZ)
from sim import ladrilhos as LT  # noqa: E402

T = LT.TAM
PASTA = LT.PASTA_PROPRIOS
ARQ = os.path.join(PASTA, LT.ARQ_PROPRIOS)
CONFERIR = os.path.join(PASTA, '_conferir')
MIN_PRETO_MM2 = 300          # mancha preta menor que isso é sujeira (ponto de caneta, poeira)
MIN_VERDE_MM2 = 150
BGR = {m: tuple(int(c) for c in reversed(LT.COR_MATERIAL[m])) for m in LT.COR_MATERIAL}


# ------------------------------------------------------------------ proprios.json
def le_json():
    if not os.path.exists(ARQ):
        return {'_comentario': 'Ladrilhos próprios do simulador da Line. Feito e explicado pela '
                               'ferramentas/ladrilho_proprio.py (LADRILHO_PROPRIO.md).', 'blocos': {}}
    with open(ARQ, encoding='utf-8') as f:
        return json.load(f)


def grava_json(d):
    os.makedirs(PASTA, exist_ok=True)
    with open(ARQ, 'w', encoding='utf-8', newline='\n') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
        f.write('\n')


def tamanho(txt):
    try:
        larg, alt = (int(n) for n in txt.lower().split('x'))
    except ValueError:
        raise SystemExit(f'tamanho {txt!r}: use LxA em ladrilhos, ex. 2x2')
    if not (1 <= larg <= 8 and 1 <= alt <= 8):
        raise SystemExit('tamanho: de 1x1 a 8x8 ladrilhos')
    return larg, alt


def registra(nome, larg, alt, descricao, fonte):
    if LT.Catalogo(pasta_proprios=os.path.join(PASTA, '_nenhum')).existe(nome) or '@' in nome:
        raise SystemExit(f'{nome!r}: escolha outro nome (já é de um ladrilho oficial ou tem @)')
    d = le_json()
    b = d['blocos'].get(nome, {})
    if b and (b.get('largura'), b.get('altura')) != (larg, alt):
        print(f'  o tamanho mudou de {b.get("largura")}x{b.get("altura")} para {larg}x{alt}: as peças foram apagadas')
        b['pecas'] = {}
    b.update({'imagem': f'{nome}.png', 'largura': larg, 'altura': alt})
    if descricao:
        b['descricao'] = descricao
    b.setdefault('descricao', 'ladrilho próprio')
    b['_fonte'] = fonte
    b.setdefault('pecas', {})
    d['blocos'][nome] = b
    grava_json(d)


# ------------------------------------------------------------------ imagem -> materiais
def classifica(bgr, valido=None):
    """Foto (já vista de cima, 1 mm/px) -> matriz de materiais. valido = máscara do que a foto cobre."""
    if valido is None:
        valido = np.ones(bgr.shape[:2], bool)
    cinza = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)
    # fundo (a luz muda ao longo do quadro): fechamento grande tira a fita e fica o branco
    fundo = cv2.morphologyEx(cinza, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (61, 61)))
    fundo = cv2.GaussianBlur(fundo, (0, 0), 15)
    rel = cinza / np.maximum(fundo, 1)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, s, v = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    verde = (h >= 35) & (h <= 95) & (s >= 80) & (v >= 35)
    vermelho = ((h <= 10) | (h >= 170)) & (s >= 100) & (v >= 50)
    preto = (rel < 0.5) & ~verde & ~vermelho
    mat = np.full(bgr.shape[:2], LT.M_BRANCO, np.uint8)
    k3 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    avisos = []
    for m, masc, minimo in ((LT.M_PRETO, preto, MIN_PRETO_MM2), (LT.M_VERDE, verde, MIN_VERDE_MM2),
                            (LT.M_VERMELHO, vermelho, MIN_VERDE_MM2)):
        masc = cv2.morphologyEx((masc & valido).astype(np.uint8), cv2.MORPH_OPEN, k3)
        masc = cv2.morphologyEx(masc, cv2.MORPH_CLOSE, k3)
        n, lab, st, _ = cv2.connectedComponentsWithStats(masc)
        borda_foto = cv2.dilate((~valido).astype(np.uint8), k3, iterations=2).astype(bool)
        for i in range(1, n):
            area = st[i, cv2.CC_STAT_AREA]
            comp = lab == i
            if area < minimo:
                continue
            if m != LT.M_PRETO and (comp & borda_foto).any():
                avisos.append(f'{LT.MATERIAIS[m]} cortado pela borda da foto em u={st[i, 0]}, v={st[i, 1]} '
                              f'({area} mm²): tirado')
                continue
            mat[comp] = m
    return mat, avisos


def prolonga(mat, mm):
    """Linha preta que chega a menos de mm da borda do bloco (a foto acabou antes, a fita foi cortada)
    segue reta até a borda, para emendar no ladrilho vizinho. Só trechos estreitos (linha que cruza a
    borda), não uma linha que corre ao longo dela."""
    if mm <= 0:
        return []
    feitos = []
    A, W = mat.shape
    for nome, faixa, pinta in (
            ('N', lambda: mat[mm], lambda a, b: mat[:mm, a:b + 1]),
            ('S', lambda: mat[A - 1 - mm], lambda a, b: mat[A - mm:, a:b + 1]),
            ('O', lambda: mat[:, mm], lambda a, b: mat[a:b + 1, :mm]),
            ('L', lambda: mat[:, W - 1 - mm], lambda a, b: mat[a:b + 1, W - mm:])):
        for a, b in faixas(faixa() == LT.M_PRETO):
            if 5 <= b - a + 1 <= 40:
                bloco = pinta(a, b)
                if (bloco == LT.M_BRANCO).any():
                    bloco[bloco == LT.M_BRANCO] = LT.M_PRETO
                    feitos.append(f'linha prolongada até a borda {nome} em {(a + b) / 2:.0f} mm')
    return feitos


def grava_png(nome, mat):
    os.makedirs(PASTA, exist_ok=True)
    img = np.zeros(mat.shape + (3,), np.uint8)
    for m, c in BGR.items():
        img[mat == m] = c
    cv2.imwrite(os.path.join(PASTA, f'{nome}.png'), img)
    return img


def medidas(mat):
    """Largura da linha preta e lado dos quadrados verdes, para conferir a escala."""
    txt = []
    preto = (mat == LT.M_PRETO).astype(np.uint8)
    if preto.any():
        dist = cv2.distanceTransform(preto, cv2.DIST_L2, 5)
        esq = cv2.ximgproc.thinning(preto * 255) if hasattr(cv2, 'ximgproc') else None
        vals = dist[esq > 0] if esq is not None else dist[dist >= np.percentile(dist[dist > 0], 90)]
        txt.append(f'linha preta: ~{2 * np.median(vals):.0f} mm de largura (fita da regra: 1 a 2 cm)')
    n, _, st, _ = cv2.connectedComponentsWithStats((mat == LT.M_VERDE).astype(np.uint8))
    lados = [f'{st[i, 2]}x{st[i, 3]}' for i in range(1, n)]
    if lados:
        txt.append(f'verdes (mm): {", ".join(lados)} (o da regra tem 25x25)')
    return txt


# ------------------------------------------------------------------ bordas das peças
def faixas(linha):
    """[(início, fim)] dos trechos verdadeiros de um vetor booleano."""
    d = np.diff(np.concatenate([[0], linha.astype(np.int8), [0]]))
    return list(zip(np.where(d == 1)[0], np.where(d == -1)[0] - 1))


def cruzamentos(mat, larg, alt):
    """{(c, l): {direção: [(posição mm ao longo da borda, largura, material)]}} das linhas nas bordas."""
    res = {}
    for c in range(larg):
        for l in range(alt):
            p = mat[l * T:(l + 1) * T, c * T:(c + 1) * T]
            bordas = {'N': p[1], 'S': p[-2], 'O': p[:, 1], 'L': p[:, -2]}
            r = {}
            for d, faixa in bordas.items():
                itens = []
                for m in (LT.M_PRETO, LT.M_VERDE, LT.M_VERMELHO, LT.M_PRATA):
                    for a, b in faixas(faixa == m):
                        if b - a >= 3:
                            itens.append(((a + b) / 2, b - a + 1, LT.MATERIAIS[m]))
                if itens:
                    r[d] = sorted(itens)
            res[(c, l)] = r
    return res


def relata_bordas(nome, mat, larg, alt):
    nomes_dir = {'N': 'norte (de cima)', 'S': 'sul (de baixo)', 'O': 'oeste (esquerda)', 'L': 'leste (direita)'}
    print(f'Linhas nas bordas das peças de {nome} (posição em mm ao longo da borda: de oeste para leste no N/S, '
          f'de norte para sul no O/L; o centro do ladrilho é 150):')
    for (c, l), r in cruzamentos(mat, larg, alt).items():
        print(f'  peça {c},{l} ({LT.nome_peca(nome, c, l, larg, alt)}):')
        if not r:
            print('    nenhuma linha nas bordas')
        for d in LT.DIRS:
            if d in r:
                vizinho = {'N': (c, l - 1), 'S': (c, l + 1), 'O': (c - 1, l), 'L': (c + 1, l)}[d]
                dentro = 0 <= vizinho[0] < larg and 0 <= vizinho[1] < alt
                onde = f'peça {vizinho[0]},{vizinho[1]}' if dentro else 'fora do bloco'
                itens = ', '.join(f'{mt} em {pos:.0f} (largura {w})' for pos, w, mt in r[d])
                print(f'    {d} {nomes_dir[d]:17s} -> {onde}: {itens}')


# ------------------------------------------------------------------ comandos
def cmd_foto(a):
    larg, alt = tamanho(a.tamanho)
    img = cv2.imread(a.foto)
    if img is None:
        raise SystemExit(f'não consegui abrir {a.foto}')
    src, dst = [], []
    for p in a.pontos:
        try:
            fx, fy, u, v = (float(x) for x in p.split(','))
        except ValueError:
            raise SystemExit(f'ponto {p!r}: use fx,fy,u,v (pixels da foto, mm do bloco)')
        src.append((fx, fy))
        dst.append((u, v))
    if len(src) < 4:
        raise SystemExit('são precisos 4 pontos ou mais')
    H, _ = cv2.findHomography(np.float32(src), np.float32(dst), 0)
    W, A = larg * T, alt * T
    vista = cv2.warpPerspective(img, H, (W, A), flags=cv2.INTER_AREA, borderValue=(255, 255, 255))
    valido = cv2.warpPerspective(np.full(img.shape[:2], 255, np.uint8), H, (W, A), flags=cv2.INTER_NEAREST) > 0
    resto = np.float32(dst) - cv2.perspectiveTransform(np.float32([src]), H)[0]
    mat, avisos = classifica(vista, valido)
    avisos += prolonga(mat, a.prolonga)
    grava_png(a.nome, mat)
    os.makedirs(CONFERIR, exist_ok=True)
    cv2.imwrite(os.path.join(CONFERIR, f'{a.nome}_vista.jpg'), vista)
    fonte = f'foto {os.path.basename(a.foto)}, pontos ' + ' '.join(a.pontos)
    registra(a.nome, larg, alt, a.descricao, fonte)
    print(f'{a.nome}: bloco {larg}x{alt} ({W}x{A} mm) gravado em ladrilhos_proprios/{a.nome}.png')
    print(f'  erro dos pontos: até {np.abs(resto).max():.1f} mm')
    print(f'  a foto cobre {100 * valido.mean():.0f}% do bloco (o resto ficou branco)')
    for t in medidas(mat) + avisos:
        print('  ' + t)
    print(f'  foto endireitada: ladrilhos_proprios/_conferir/{a.nome}_vista.jpg')
    relata_bordas(a.nome, mat, larg, alt)


def cmd_desenho(a):
    larg, alt = tamanho(a.tamanho)
    img = cv2.imread(a.imagem)
    if img is None:
        raise SystemExit(f'não consegui abrir {a.imagem}')
    W, A = larg * T, alt * T
    r = img.shape[1] / img.shape[0]
    if abs(r / (W / A) - 1) > 0.03:
        print(f'  aviso: a imagem tem proporção {r:.2f} e o bloco {W / A:.2f}: ela foi esticada')
    vista = cv2.resize(img, (W, A), interpolation=cv2.INTER_AREA)
    mat, avisos = classifica(vista)
    avisos += prolonga(mat, a.prolonga)
    grava_png(a.nome, mat)
    registra(a.nome, larg, alt, a.descricao, f'desenho {os.path.basename(a.imagem)}')
    print(f'{a.nome}: bloco {larg}x{alt} gravado em ladrilhos_proprios/{a.nome}.png')
    for t in medidas(mat) + avisos:
        print('  ' + t)
    relata_bordas(a.nome, mat, larg, alt)


def bloco(nome):
    d = le_json()
    if nome not in d['blocos']:
        raise SystemExit(f'{nome!r} não está no proprios.json (lista: {", ".join(d["blocos"]) or "vazia"})')
    b = d['blocos'][nome]
    cat = LT.catalogo()
    return d, b, cat._material_bloco(nome)


def cmd_bordas(a):
    _, b, mat = bloco(a.nome)
    relata_bordas(a.nome, mat, b['largura'], b['altura'])


def _por_peca(txt, b):
    """'c,l:resto c,l:resto' -> [((c, l), resto)]."""
    res = []
    for item in txt.split():
        try:
            cl, resto = item.split(':', 1)
            c, l = (int(n) for n in cl.split(','))
        except ValueError:
            raise SystemExit(f'{item!r}: use coluna,linha:valor')
        if not (0 <= c < b['largura'] and 0 <= l < b['altura']):
            raise SystemExit(f'{item!r}: o bloco tem {b["largura"]}x{b["altura"]} peças (0,0 a '
                             f'{b["largura"] - 1},{b["altura"] - 1})')
        res.append((f'{c},{l}', resto))
    return res


def cmd_pecas(a):
    d, b, _ = bloco(a.nome)
    pecas = {} if a.limpa else b.setdefault('pecas', {})
    if a.caminhos:
        novos = {}
        for k, resto in _por_peca(a.caminhos, b):
            for par in resto.split('/'):
                e, s = (LT._dir(x.strip().upper()) for x in par.split('>'))
                novos.setdefault(k, {})[e] = s
        for k, cam in novos.items():
            pecas.setdefault(k, {})['caminhos'] = cam
    for campo, txt in (('intersecoes', a.intersecoes), ('gaps', a.gaps)):
        for k, resto in _por_peca(txt or '', b):
            pecas.setdefault(k, {})[campo] = int(resto)
    for k, resto in _por_peca(a.ponto or '', b):
        partes = resto.split(':')
        u, v = (float(x) for x in partes[0].split(','))
        pecas.setdefault(k, {})['ponto'] = [u, v]
        if len(partes) > 1:
            pecas[k]['rumo'] = LT._dir(partes[1].upper())
    b['pecas'] = {k: pecas[k] for k in sorted(pecas)}
    d['blocos'][a.nome] = b
    grava_json(d)
    print(json.dumps(b['pecas'], ensure_ascii=False, indent=1))
    cmd_confere(a)


def cmd_confere(a):
    _, b, mat = bloco(a.nome)
    larg, alt = b['largura'], b['altura']
    img = np.zeros(mat.shape + (3,), np.uint8)
    for m, c in BGR.items():
        img[mat == m] = c
    img = cv2.resize(img, None, fx=2, fy=2, interpolation=cv2.INTER_NEAREST)
    AZUL, LARANJA = (220, 120, 0), (0, 140, 255)
    for c in range(larg + 1):
        cv2.line(img, (2 * c * T, 0), (2 * c * T, 2 * alt * T), AZUL, 2)
    for l in range(alt + 1):
        cv2.line(img, (0, 2 * l * T), (2 * larg * T, 2 * l * T), AZUL, 2)
    pontas = {'N': (150, 20), 'S': (150, 280), 'O': (20, 150), 'L': (280, 150)}
    for c in range(larg):
        for l in range(alt):
            ox, oy = 2 * c * T, 2 * l * T
            p = b.get('pecas', {}).get(f'{c},{l}', {})
            txt = f'{c},{l}'
            if p.get('intersecoes'):
                txt += f' int {p["intersecoes"]}'
            if p.get('gaps'):
                txt += f' gap {p["gaps"]}'
            cv2.putText(img, txt, (ox + 10, oy + 34), cv2.FONT_HERSHEY_SIMPLEX, 0.9, AZUL, 2)
            for e, s in p.get('caminhos', {}).items():
                e, s = LT._dir(e), LT._dir(s)
                pe = (ox + 2 * pontas[e][0], oy + 2 * pontas[e][1])
                ps = (ox + 2 * pontas[s][0], oy + 2 * pontas[s][1])
                cv2.arrowedLine(img, pe, ps, LARANJA, 4, tipLength=0.08)
            if p.get('ponto'):
                pc = (int(ox + 2 * p['ponto'][0]), int(oy + 2 * p['ponto'][1]))
                cv2.circle(img, pc, 12, (255, 0, 255), 4)
                if p.get('rumo'):
                    dx, dy = {'N': (0, -1), 'S': (0, 1), 'L': (1, 0), 'O': (-1, 0)}[LT._dir(p['rumo'])]
                    cv2.arrowedLine(img, pc, (pc[0] + 60 * dx, pc[1] + 60 * dy), (255, 0, 255), 4)
    os.makedirs(CONFERIR, exist_ok=True)
    arq = os.path.join(CONFERIR, f'{a.nome}_conferir.png')
    cv2.imwrite(arq, img)
    print(f'imagem: {os.path.relpath(arq, RAIZ)} (azul: peças; laranja: caminhos entrada -> saída; '
          f'magenta: ponto de início/retorno)')


def cmd_lista(a):
    d = le_json()
    if not d['blocos']:
        print('nenhum ladrilho próprio ainda')
    for n, b in d['blocos'].items():
        com = sum(1 for p in b.get('pecas', {}).values() if p.get('caminhos'))
        print(f'{n}: {b["largura"]}x{b["altura"]}, {com} peça(s) com caminho; {b.get("descricao", "")}')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('foto')
    p.add_argument('nome')
    p.add_argument('foto')
    p.add_argument('tamanho')
    p.add_argument('pontos', nargs='+')
    p.add_argument('--descricao')
    p.add_argument('--prolonga', type=int, default=0, metavar='MM',
                   help='linha que chega a menos de MM mm da borda do bloco vai até a borda')
    p = sub.add_parser('desenho')
    p.add_argument('nome')
    p.add_argument('imagem')
    p.add_argument('tamanho')
    p.add_argument('--descricao')
    p.add_argument('--prolonga', type=int, default=0, metavar='MM')
    for c in ('bordas', 'confere'):
        sub.add_parser(c).add_argument('nome')
    p = sub.add_parser('pecas')
    p.add_argument('nome')
    p.add_argument('--caminhos', help='"c,l:E>S c,l:E>S/E>S ..." (N, L, S, O)')
    p.add_argument('--intersecoes')
    p.add_argument('--gaps')
    p.add_argument('--ponto', help='"c,l:u,v[:RUMO]" (mm a partir do canto noroeste da peça)')
    p.add_argument('--limpa', action='store_true', help='apaga as peças antes')
    sub.add_parser('lista')
    a = ap.parse_args()
    {'foto': cmd_foto, 'desenho': cmd_desenho, 'bordas': cmd_bordas, 'pecas': cmd_pecas,
     'confere': cmd_confere, 'lista': cmd_lista}[a.cmd](a)


if __name__ == '__main__':
    main()
