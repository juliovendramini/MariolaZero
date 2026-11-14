"""Faz uma cópia "bagunçada" de uma casa, para testar a localização com a casa diferente do mapa.

    python ferramentas/bagunca_casa.py casas/casa_julio.json casas/casa_julio_baguncada.json
    python simulador.py --casa casas/casa_julio_baguncada.json --mapa casas/casa_julio.json --programa exemplo_casa/passeio.py

O simulador abre a casa bagunçada e o robô continua com o mapa original (--mapa). A cópia:

* tira alguns móveis (o mapa do robô tem um móvel que não existe mais);
* desloca os outros um pouco (até --desloca mm);
* põe coisas que não estão no mapa (caixas de 30 a 50 cm, em vermelho escuro, chamadas "fora do
  mapa"), longe o bastante das rotas entre os cômodos para não fechar a passagem.

A mesma --semente faz a mesma bagunça.
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


def rotas_do_passeio(m):
    """Os pontos das rotas do passeio (início > cômodos, do mais perto para o mais longe > início)."""
    x, y, _ = m.inicio
    falta = {n: m.lugar(n) for n in m.lugares()}
    falta = {n: p for n, p in falta.items() if p is not None}
    pts = []
    while falta:
        melhor = None
        for n, p in falta.items():
            c = m.rota((x, y), p)
            if c is not None and (melhor is None or m.comprimento(c) < melhor[0]):
                melhor = (m.comprimento(c), n, c)
        if melhor is None:
            break
        pts.append(melhor[2])
        x, y = falta.pop(melhor[1])
    volta = m.rota((x, y), m.inicio[:2])
    if volta:
        pts.append(volta)
    return pts


def dist_rotas(rotas, x, y):
    d = 1e18
    for c in rotas:
        for (ax, ay), (bx, by) in zip(c, c[1:]):
            L2 = (bx - ax) ** 2 + (by - ay) ** 2
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
            d = min(d, math.hypot(x - (ax + (bx - ax) * t), y - (ay + (by - ay) * t)))
    return d


def main():
    ap = argparse.ArgumentParser(description='Cópia bagunçada de uma casa (teste de localização)')
    ap.add_argument('entrada')
    ap.add_argument('saida')
    ap.add_argument('--semente', type=int, default=1)
    ap.add_argument('--tira', type=int, default=4, help='móveis que somem')
    ap.add_argument('--desloca', type=float, default=150.0, help='mm que os outros móveis podem sair do lugar')
    ap.add_argument('--novos', type=int, default=14, help='coisas fora do mapa')
    ap.add_argument('--folga-rota', type=float, default=650.0, help='mm das coisas novas até as rotas')
    a = ap.parse_args()

    rng = random.Random(a.semente)
    with open(a.entrada, 'r', encoding='utf-8') as f:
        d = json.load(f)
    m = Mapa(a.entrada)
    rotas = rotas_do_passeio(m)

    moveis = d.get('moveis', [])
    for _ in range(min(a.tira, len(moveis))):
        tirado = moveis.pop(rng.randrange(len(moveis)))
        print('tirei', tirado.get('nome', 'móvel'), tirado['ret'])
    for mv in moveis:
        dx, dy = rng.uniform(-a.desloca, a.desloca), rng.uniform(-a.desloca, a.desloca)
        r = mv['ret']
        mv['ret'] = [round(r[0] + dx), round(r[1] + dy), round(r[2] + dx), round(r[3] + dy)]
    postos = 0
    for _ in range(20000):
        if postos >= a.novos:
            break
        lado = rng.uniform(300, 500)
        x, y = rng.uniform(0, m.largura), rng.uniform(0, m.altura)
        if m.folga(x, y) < lado * 0.75 + 60 or m.folga(x, y) > 1200:
            continue                    # nem em cima de parede/móvel, nem no meio do nada
        if dist_rotas(rotas, x, y) < a.folga_rota + lado / 2:
            continue
        if math.hypot(x - m.inicio[0], y - m.inicio[1]) < 900:
            continue
        moveis.append({'nome': 'fora do mapa', 'ret': [round(x - lado / 2), round(y - lado / 2),
                                                       round(x + lado / 2), round(y + lado / 2)],
                       'alt': 450, 'rgb': [150, 60, 50]})
        postos += 1
    d['moveis'] = moveis
    d['nome'] = d.get('nome', 'casa') + ' (bagunçada)'
    with open(a.saida, 'w', encoding='utf-8') as f:
        json.dump(d, f, ensure_ascii=False, indent=1)
    print(f'{a.saida}: {postos} coisas fora do mapa, {len(moveis)} móveis ao todo')


if __name__ == '__main__':
    main()
