"""Converte a planta de uma casa (DXF do AutoCAD) num mapa do simulador (casas/*.json).

    python ferramentas/planta_dxf.py planta.dxf casas/minha_casa.json
    python ferramentas/planta_dxf.py planta.dxf casas/minha_casa.json --unidade cm --ver planta.png

O que ele aproveita, por camada (os nomes mudam com --paredes, --janelas, --moveis):

* PAREDE: cada linha vira uma parede fina (2 cm). A planta desenha o contorno das paredes (duas
  linhas por parede): no simulador ficam duas "cascas" com o miolo vazio, o que dá no mesmo para o
  robô e para os sensores. As portas são os vãos entre as linhas.
* ESQUADRIA: janelas. Viram parede também (o robô anda no chão: abaixo do peitoril é parede).
  Porta de correr desenhada como janela precisa ser tirada à mão do JSON ("tipo": "janela").
* LAY OUT / LAYOUT: retângulos fechados viram móveis de 45 cm de altura, a ajustar. Retângulos
  iguais repetidos muitas vezes (pisantes do quintal) ficam de fora.
* Textos dentro de blocos com nome de cômodo viram rótulos.

A folha costuma ter mais de um desenho (detalhes, legenda): vale o maior grupo de paredes.
Precisa do ezdxf (pip install ezdxf). Com --ver, grava uma imagem para conferir (matplotlib).
"""

import argparse
import collections
import json
import math
import os
import sys

import ezdxf

ESCALA = {'mm': 1.0, 'cm': 10.0, 'm': 1000.0}


def segmentos(e):
    t = e.dxftype()
    if t == 'LINE':
        return [((e.dxf.start.x, e.dxf.start.y), (e.dxf.end.x, e.dxf.end.y))]
    if t == 'LWPOLYLINE':
        pts = [(p[0], p[1]) for p in e.get_points('xy')]
        if e.closed and pts:
            pts.append(pts[0])
        return [(a, b) for a, b in zip(pts, pts[1:]) if a != b]
    return []


def maior_grupo(segs, perto):
    """Índices dos segmentos do maior grupo (segmentos a menos de 'perto' uns dos outros)."""
    n = len(segs)
    pai = list(range(n))

    def acha(i):
        while pai[i] != i:
            pai[i] = pai[pai[i]]
            i = pai[i]
        return i

    def ponto_seg(p, a, b):
        dx, dy = b[0] - a[0], b[1] - a[1]
        d2 = dx * dx + dy * dy
        t = 0.0 if d2 == 0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / d2))
        return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)

    def dist(s, q):
        return min(ponto_seg(s[0], *q), ponto_seg(s[1], *q), ponto_seg(q[0], *s), ponto_seg(q[1], *s))
    for i in range(n):
        for j in range(i + 1, n):
            if dist(segs[i], segs[j]) < perto:
                pai[acha(i)] = acha(j)
    grupos = collections.defaultdict(list)
    for i in range(n):
        grupos[acha(i)].append(i)

    def area(g):
        xs = [p[0] for i in g for p in segs[i]]
        ys = [p[1] for i in g for p in segs[i]]
        return (max(xs) - min(xs)) * (max(ys) - min(ys))
    return max(grupos.values(), key=area)


def main():
    ap = argparse.ArgumentParser(description='Planta em DXF -> mapa do simulador da casa')
    ap.add_argument('dxf')
    ap.add_argument('saida')
    ap.add_argument('--unidade', default='cm', choices=sorted(ESCALA), help='unidade do desenho (padrão cm)')
    ap.add_argument('--paredes', default='PAREDE')
    ap.add_argument('--janelas', default='ESQUADRIA')
    ap.add_argument('--moveis', default='LAY OUT,LAYOUT,LAY')
    ap.add_argument('--altura-movel', type=float, default=450.0)
    ap.add_argument('--nome', default=None)
    ap.add_argument('--nomes', default='', help='blocos com o desenho de cada cômodo: "bloco=Nome do cômodo, ..."')
    ap.add_argument('--moveis-dos-blocos', action='store_true',
                    help='os contornos fechados dentro dos blocos dos cômodos também viram móveis')
    ap.add_argument('--ver', default=None, help='grava uma imagem do mapa para conferir')
    a = ap.parse_args()
    k = ESCALA[a.unidade]

    doc = ezdxf.readfile(a.dxf)
    msp = doc.modelspace()
    por = collections.defaultdict(list)
    fechados = []                                   # retângulos fechados das camadas de móveis
    cam_moveis = [c.strip() for c in a.moveis.split(',')]
    for e in msp:
        cam = e.dxf.layer
        if cam in (a.paredes, a.janelas):
            por[cam].extend(segmentos(e))
        elif cam in cam_moveis and e.dxftype() == 'LWPOLYLINE':
            pts = [(p[0], p[1]) for p in e.get_points('xy')]
            if len(pts) >= 2 and pts[0] == pts[-1]:
                pts = pts[:-1]
            if (e.closed or len(pts) == 4) and len(pts) == 4:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                # só retângulos alinhados com os eixos
                if all(abs(p[0] - min(xs)) < 0.5 or abs(p[0] - max(xs)) < 0.5 for p in pts) and \
                   all(abs(p[1] - min(ys)) < 0.5 or abs(p[1] - max(ys)) < 0.5 for p in pts):
                    fechados.append((min(xs), min(ys), max(xs), max(ys)))
    paredes = por[a.paredes]
    if not paredes:
        sys.exit(f'nenhuma linha na camada {a.paredes!r}. Camadas do desenho: '
                 + ', '.join(sorted({e.dxf.layer for e in msp})))
    # o maior grupo de linhas vizinhas (até 1 m) dá o recorte da planta; vale tudo o que está dentro dele
    g = maior_grupo(paredes, 100.0 * 10.0 / k)
    xs = [p[0] for i in g for p in paredes[i]]
    ys = [p[1] for i in g for p in paredes[i]]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    paredes = [s for s in paredes if all(x0 - 1 <= p[0] <= x1 + 1 and y0 - 1 <= p[1] <= y1 + 1 for p in s)]
    mg = 50.0 / k * 10.0 / 10.0                      # folga de 5 cm em volta

    def dentro(px, py, folga=0.0):
        return x0 - folga <= px <= x1 + folga and y0 - folga <= py <= y1 + folga

    def T(p):
        return [round((p[0] - x0) * k + mg * k, 1), round((p[1] - y0) * k + mg * k, 1)]

    casa = {
        'nome': a.nome or os.path.splitext(os.path.basename(a.saida))[0],
        'largura': round((x1 - x0) * k + 2 * mg * k, 1), 'altura': round((y1 - y0) * k + 2 * mg * k, 1),
        'parede': {'esp': 100, 'alt': 2500, 'rgb': [236, 232, 220], 'externas': False},
        'pisos': [{'nome': '', 'cor': 'cinza', 'ret': [0, 0, round((x1 - x0) * k + 2 * mg * k, 1), round((y1 - y0) * k + 2 * mg * k, 1)],
                   'rgb': [200, 190, 172]}],
        'faixas': [], 'paredes': [], 'moveis': [], 'objetos': [], 'rotulos': [],
    }
    for s in paredes:
        casa['paredes'].append({'de': T(s[0]), 'ate': T(s[1]), 'esp': 20})
    nj = 0
    for s in por[a.janelas]:
        if dentro(*s[0], 5) and dentro(*s[1], 5):
            casa['paredes'].append({'de': T(s[0]), 'ate': T(s[1]), 'esp': 20, 'tipo': 'janela', 'rgb': [170, 200, 222]})
            nj += 1

    # móveis: retângulos de 30 cm a 3 m; tamanhos repetidos 5 vezes ou mais são pisantes/padrões
    tam = collections.Counter((round((r[2] - r[0]) * k / 10), round((r[3] - r[1]) * k / 10)) for r in fechados)
    fora_padrao = 0
    vistos = set()
    for r in fechados:
        w, h = (r[2] - r[0]) * k, (r[3] - r[1]) * k
        chave = (round(w / 10), round(h / 10))
        if not (dentro(r[0], r[1]) and dentro(r[2], r[3])) or not (300 <= max(w, h) <= 3000 and min(w, h) >= 150):
            continue
        if tam[chave] >= 5:
            fora_padrao += 1
            continue
        a0, b0 = T((r[0], r[1])), T((r[2], r[3]))
        ident = (round(a0[0], -1), round(a0[1], -1), round(b0[0], -1), round(b0[1], -1))
        if ident in vistos:
            continue
        vistos.add(ident)
        casa['moveis'].append({'nome': f'móvel {len(casa["moveis"]) + 1}', 'ret': [a0[0], a0[1], b0[0], b0[1]],
                               'alt': a.altura_movel, 'rgb': [150, 118, 84]})

    # rótulos: textos soltos e dentro de blocos
    def texto(e):
        return (e.plain_text() if e.dxftype() == 'MTEXT' else e.dxf.text).strip().replace('\n', ' ')
    cand = []
    for e in msp.query('TEXT MTEXT'):
        cand.append((texto(e), e.dxf.insert.x, e.dxf.insert.y))
    for ins in msp.query('INSERT'):
        try:
            for e in ins.virtual_entities():
                if e.dxftype() in ('TEXT', 'MTEXT'):
                    cand.append((texto(e), e.dxf.insert.x, e.dxf.insert.y))
        except Exception:
            pass
    chaves = ('QUARTO', 'SALA', 'BANH', 'COZINHA', 'CIRCULA', 'GARAGEM', 'CLOSET', 'LAVANDERIA', 'VARANDA',
              'SUÍTE', 'SUITE', 'ÁREA', 'AREA', 'DESPENSA', 'ESCRIT', 'HALL', 'DECK', 'PISCINA', 'JARDIM', 'COPA')
    for s, px, py in cand:
        if dentro(px, py) and any(c in s.upper() for c in chaves) and len(s) < 40 and not s.startswith('-'):
            p = T((px, py))
            casa['rotulos'].append({'nome': s.title() if s.isupper() else s, 'x': p[0], 'y': p[1]})

    # blocos com o desenho de cada cômodo (--nomes "bloco=Nome, ..."): o meio do bloco vira o rótulo e
    # os contornos fechados de dentro dele viram móveis
    nomes = dict(par.split('=', 1) for par in a.nomes.split(',') if '=' in par)
    nomes = {kk.strip(): v.strip() for kk, v in nomes.items()}
    from ezdxf import bbox as _bbox
    for ins in msp.query('INSERT'):
        if ins.dxf.name not in nomes:
            continue
        try:
            ents = list(ins.virtual_entities())
            b = _bbox.extents(ents, fast=True)
        except Exception:
            continue
        if not ents or not b.has_data:
            continue
        cxm, cym = (b.extmin.x + b.extmax.x) / 2, (b.extmin.y + b.extmax.y) / 2
        if not dentro(cxm, cym):
            continue
        p = T((cxm, cym))
        casa['rotulos'].append({'nome': nomes[ins.dxf.name], 'x': p[0], 'y': p[1],
                                'ret': T((b.extmin.x, b.extmin.y)) + T((b.extmax.x, b.extmax.y))})
        if not a.moveis_dos_blocos:
            continue
        for e in ents:
            if e.dxftype() != 'LWPOLYLINE':
                continue
            pts = [(q[0], q[1]) for q in e.get_points('xy')]
            if len(pts) < 4 or not (e.closed or math.hypot(pts[0][0] - pts[-1][0], pts[0][1] - pts[-1][1]) < 0.5):
                continue
            xs_, ys_ = [q[0] for q in pts], [q[1] for q in pts]
            w, h = (max(xs_) - min(xs_)) * k, (max(ys_) - min(ys_)) * k
            if not (300 <= max(w, h) <= 3000 and min(w, h) >= 200):
                continue
            a0, b0 = T((min(xs_), min(ys_))), T((max(xs_), max(ys_)))
            ident = (round(a0[0], -1), round(a0[1], -1), round(b0[0], -1), round(b0[1], -1))
            if ident in vistos:
                continue
            vistos.add(ident)
            casa['moveis'].append({'nome': f'{nomes[ins.dxf.name]} {len(casa["moveis"]) + 1}',
                                   'ret': [a0[0], a0[1], b0[0], b0[1]], 'alt': a.altura_movel, 'rgb': [150, 118, 84]})

    sala = next((r for r in casa['rotulos'] if 'sala de estar' in r['nome'].lower()), None) or \
        next((r for r in casa['rotulos'] if 'sala' in r['nome'].lower()), None)
    casa['inicio'] = [sala['x'], sala['y'], 0] if sala else [casa['largura'] / 2, casa['altura'] / 2, 0]
    # refazendo uma casa que já existe: os objetos e a caixa postos nela (ferramentas/espalha_objetos.py
    # ou a janela do simulador) continuam; a planta não sabe deles
    if os.path.exists(a.saida):
        try:
            with open(a.saida, 'r', encoding='utf-8') as f:
                antiga = json.load(f)
            casa['objetos'] = antiga.get('objetos', [])
            if antiga.get('caixa'):
                casa['caixa'] = antiga['caixa']
        except (OSError, ValueError):
            pass
    with open(a.saida, 'w', encoding='utf-8') as f:
        json.dump(casa, f, ensure_ascii=False, indent=1)
    print(f'{a.saida}: {casa["largura"] / 1000:.2f} x {casa["altura"] / 1000:.2f} m, {len(paredes)} linhas de parede, '
          f'{nj} de janela, {len(casa["moveis"])} móveis ({fora_padrao} retângulos repetidos de fora), '
          f'{len(casa["rotulos"])} rótulos')
    for r in casa['rotulos']:
        print(f'   {r["nome"]:28s} x {r["x"]:7.0f}  y {r["y"]:7.0f}')

    if a.ver:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        from matplotlib.patches import Rectangle
        fig, ax = plt.subplots(figsize=(11, 11 * casa['altura'] / casa['largura']))
        for i, m in enumerate(casa['moveis']):
            r = m['ret']
            ax.add_patch(Rectangle((r[0], r[1]), r[2] - r[0], r[3] - r[1], fc='#d9a066', ec='#7a4a16', lw=0.8))
            ax.text((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, str(i + 1), ha='center', va='center', fontsize=7)
        for p in casa['paredes']:
            cor = '#3d7ab8' if p.get('tipo') == 'janela' else '#111'
            ax.plot([p['de'][0], p['ate'][0]], [p['de'][1], p['ate'][1]], color=cor, lw=2.2 if p.get('tipo') else 1.3)
        for r in casa['rotulos']:
            ax.text(r['x'], r['y'], r['nome'], ha='center', va='center', fontsize=8, color='#1d3f7a')
        ax.plot(casa['inicio'][0], casa['inicio'][1], 'r^', ms=9)
        ax.set_aspect('equal'); ax.grid(alpha=0.3)
        ax.set_xlim(0, casa['largura']); ax.set_ylim(0, casa['altura'])
        ax.set_title(f'{casa["nome"]}: paredes (preto), janelas (azul), móveis numerados (laranja), início (vermelho), mm')
        fig.tight_layout(); fig.savefig(a.ver, dpi=85)
        print('imagem:', a.ver)


if __name__ == '__main__':
    main()
