"""Põe a caixa de guardar e espalha prismas coloridos numa casa (para testar o robô arrumando).

    python ferramentas/espalha_objetos.py casas/casa_julio.json --caixa 6400,6000 --comodos "Sala de estar,Quarto 1,Cozinha"
    python ferramentas/espalha_objetos.py casas/casa_julio.json --n 8 --semente 3      (outra disposição)

Cada objeto fica num cômodo, num lugar em que o robô chega (folga de 30 cm das paredes e dos móveis)
e que dá para ver do ponto do cômodo onde o robô para para olhar em volta (até --alcance mm, sem móvel
na frente). Os objetos que a casa já tinha saem. A caixa só muda com --caixa.
A mesma --semente dá a mesma disposição.
"""

import argparse
import json
import math
import os
import random
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(RAIZ, 'exemplo_casa'))
from mapa import Mapa  # noqa: E402

CORES = ['vermelho', 'azul', 'verde', 'amarelo', 'laranja', 'ciano']       # cores vivas (a câmera acha pela cor)
TAMANHOS = [[40, 40, 60], [50, 35, 40], [36, 36, 36], [60, 40, 30], [40, 40, 50], [45, 30, 45]]


def main():
    ap = argparse.ArgumentParser(description='Caixa e prismas coloridos numa casa')
    ap.add_argument('casa')
    ap.add_argument('--saida', default=None, help='arquivo de saída (padrão: a própria casa)')
    ap.add_argument('--n', type=int, default=6, help='quantos objetos')
    ap.add_argument('--semente', type=int, default=1)
    ap.add_argument('--comodos', default='', help='cômodos que recebem objeto, separados por vírgula (padrão: sorteia)')
    ap.add_argument('--caixa', default=None, help='"x,y" ou "x,y,ângulo" do meio da caixa de guardar')
    ap.add_argument('--alcance', type=float, default=1700.0, help='mm do ponto do cômodo até o objeto, no máximo')
    a = ap.parse_args()

    with open(a.casa, 'r', encoding='utf-8') as f:
        d = json.load(f)
    if a.caixa:
        v = [float(x) for x in a.caixa.split(',')]
        d['caixa'] = {'x': v[0], 'y': v[1], 'ang': v[2] if len(v) > 2 else 0, 'tam': [320, 240], 'alt': 100,
                      'esp': 6, 'rgb': [140, 70, 180]}
    d['objetos'] = []
    saida = a.saida or a.casa
    with open(saida, 'w', encoding='utf-8') as f:          # o Mapa lê do arquivo: já com a caixa nova
        json.dump(d, f, ensure_ascii=False, indent=1)
    m = Mapa(saida)
    rng = random.Random(a.semente)
    x0, y0, _ = m.inicio
    nomes = [n.strip() for n in a.comodos.split(',') if n.strip()]
    if not nomes:
        nomes = [n for n in m.lugares() if m.lugar(n) and m.rota((x0, y0), m.lugar(n))]
        rng.shuffle(nomes)
    postos = []
    k = 0
    while len(postos) < a.n and k < 40 * a.n:
        nome = nomes[k % len(nomes)]
        k += 1
        base = m.lugar(nome)
        if base is None:
            print(f'{nome}: o robô não cabe neste cômodo')
            continue
        for _ in range(400):
            dist = rng.uniform(500, a.alcance)
            ang = rng.uniform(0, 2 * math.pi)
            x, y = base[0] + dist * math.cos(ang), base[1] + dist * math.sin(ang)
            if not (300 <= m.folga(x, y) <= 1500):
                continue
            if float(m.raios(base[0], base[1], ang, dist + 100)) < dist + 100:
                continue                    # tem parede ou móvel entre o ponto do cômodo e o objeto
            if math.hypot(x - x0, y - y0) < 500 or any(math.hypot(x - o['x'], y - o['y']) < 500 for o in postos):
                continue
            c = d.get('caixa')
            if c and math.hypot(x - c['x'], y - c['y']) < 900:
                continue
            if m.rota((x0, y0), (x, y)) is None:
                continue
            i = len(postos)
            postos.append({'cor': CORES[i % len(CORES)], 'x': round(x), 'y': round(y), 'ang': rng.randrange(0, 90, 5),
                           'tam': TAMANHOS[i % len(TAMANHOS)]})
            print(f'{CORES[i % len(CORES)]:<9} em {nome} ({x:.0f}, {y:.0f})')
            break
        else:
            print(f'{nome}: não achei lugar para um objeto')
    d['objetos'] = postos
    with open(saida, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(f'{saida}: {len(postos)} objetos' + (f', caixa em ({d["caixa"]["x"]:.0f}, {d["caixa"]["y"]:.0f})' if d.get('caixa') else ', SEM caixa'))


if __name__ == '__main__':
    main()
