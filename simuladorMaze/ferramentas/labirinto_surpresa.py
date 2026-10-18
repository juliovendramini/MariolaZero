"""Gera um labirinto surpresa da Rescue Maze: paredes, pisos e vítimas sorteados.

Na competição o labirinto só é conhecido no dia. Um programa ajustado para um mapa só (por
exemplo, que "sabe" que a primeira curva é à direita) não serve. O labirinto surpresa testa se o
programa explora e se orienta em qualquer labirinto dentro da regra.

Uso:
    python ferramentas/labirinto_surpresa.py                        # nível médio, semente 1
    python ferramentas/labirinto_surpresa.py --nivel dificil --semente 7
    python ferramentas/labirinto_surpresa.py --semente 3 --saida mapas/meu_labirinto.json

A mesma semente e o mesmo nível geram sempre o mesmo labirinto. O avalia.py usa este gerador
nos desafios de labirinto surpresa.

Níveis:
    facil    4x5, corredores (árvore: seguir a parede visita tudo), 1 buraco preto, 4 vítimas
    medio    5x7, alguns ciclos, 2 pretos, azul, lombada, 6 vítimas (1 falsa)
    dificil  6x8, ciclos e salas abertas (seguir a parede NÃO visita tudo), 3 pretos, 8 vítimas
"""
import argparse
import os
import random
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from sim.mapa import Mapa, DELTA, DIRECOES, OPOSTA, gera_aneis  # noqa: E402

NIVEIS = {
    'facil':   dict(tam=(4, 5), ciclos=0.0, salas=0, pretos=1, pratas=1, azuis=0, lombadas=0,
                    detritos=0, vitimas=4, falsas=0),
    'medio':   dict(tam=(5, 7), ciclos=0.12, salas=0, pretos=2, pratas=2, azuis=1, lombadas=1,
                    detritos=1, vitimas=6, falsas=1),
    'dificil': dict(tam=(6, 8), ciclos=0.18, salas=1, pretos=3, pratas=2, azuis=2, lombadas=2,
                    detritos=2, vitimas=8, falsas=1),
}
NOMES_NIVEL = list(NIVEIS)


def _vizinho(l, c, d):
    dl, dc = DELTA[d]
    return l + dl, c + dc


def gera(semente=1, nivel='medio', nome=None):
    """Devolve um Mapa da Maze válido (lança RuntimeError se não conseguir)."""
    if nivel not in NIVEIS:
        raise ValueError(f'nível {nivel!r}: use {", ".join(NIVEIS)}')
    cfg = NIVEIS[nivel]
    rng = random.Random(f'maze-{nivel}-{semente}')
    for _ in range(300):
        m = _tenta(rng, cfg, nome or f'labirinto_{nivel}_{semente}', semente)
        if m is not None:
            return m
    raise RuntimeError('não consegui gerar o labirinto (tente outra semente)')


def _tenta(rng, cfg, nome, semente):
    L, C = cfg['tam']
    m = Mapa(L, C, nome)
    m.semente = semente
    # 1) todas as paredes, depois cava uma árvore (busca em profundidade aleatória)
    for l in range(L + 1):
        for c in range(C):
            m.paredes_h[l][c] = True
    for l in range(L):
        for c in range(C + 1):
            m.paredes_v[l][c] = True
    inicio = (rng.randrange(L), rng.choice((0, C - 1)) if rng.random() < 0.5 else rng.randrange(C))
    visto = {inicio}
    pilha = [inicio]
    while pilha:
        l, c = pilha[-1]
        opcoes = [d for d in DIRECOES if m.dentro(*_vizinho(l, c, d)) and _vizinho(l, c, d) not in visto]
        if not opcoes:
            pilha.pop()
            continue
        d = rng.choice(opcoes)
        m.set_parede(l, c, d, False)
        n = _vizinho(l, c, d)
        visto.add(n)
        pilha.append(n)
    # 2) ciclos: tira algumas paredes internas a mais (ilhas: seguir a parede não visita tudo)
    internas = [(l, c, d) for l in range(L) for c in range(C) for d in ('S', 'L')
                if m.dentro(*_vizinho(l, c, d)) and m.parede(l, c, d)]
    rng.shuffle(internas)
    for l, c, d in internas[:int(len(internas) * cfg['ciclos'])]:
        m.set_parede(l, c, d, False)
    # 3) salas abertas 2x2
    for _ in range(cfg['salas']):
        l, c = rng.randrange(L - 1), rng.randrange(C - 1)
        m.set_parede(l, c, 'L', False)
        m.set_parede(l, c, 'S', False)
        m.set_parede(l + 1, c, 'L', False)
        m.set_parede(l, c + 1, 'S', False)
    m.cerca_perimetro()
    m.inicio = inicio
    abertas = [d for d in DIRECOES if not m.parede(*inicio, d)]
    m.inicio_dir = rng.choice(abertas) if abertas else 'N'

    # 4) pisos e terrenos em células diferentes do início e dos vizinhos dele
    perto = {inicio} | {_vizinho(*inicio, d) for d in DIRECOES}
    livres = [(l, c) for l in range(L) for c in range(C) if (l, c) not in perto]
    rng.shuffle(livres)
    for _ in range(cfg['pretos']):
        for i, cel in enumerate(livres):
            m.set_lad(*cel, piso='preto')
            if any('inalcançável' in a for a in m.validar()):
                m.set_lad(*cel, piso=None)
                continue
            livres.pop(i)
            break
        else:
            return None
    for chave, valor, n in (('piso', 'prata', cfg['pratas']), ('piso', 'azul', cfg['azuis'])):
        for _ in range(n):
            if not livres:
                return None
            m.set_lad(*livres.pop(), **{chave: valor})
    for _ in range(cfg['lombadas']):
        if not livres:
            return None
        m.set_lad(*livres.pop(), terreno='lombada', direcao=rng.choice(('LO', 'NS')))
    for _ in range(cfg['detritos']):
        if not livres:
            return None
        m.set_lad(*livres.pop(), terreno='detritos')

    # 5) vítimas: numa parede de uma célula comum (a regra não deixa vítima de frente para
    #    ladrilho especial), uma por célula
    comuns = [(l, c) for l in range(L) for c in range(C)
              if m.piso(l, c) == 'branco' and m.terreno(l, c) in ('', 'detritos') and (l, c) != inicio]
    rng.shuffle(comuns)
    tipos = []
    n_reais = cfg['vitimas'] - cfg['falsas']
    for k in range(n_reais):
        status = ('ferida', 'estavel', 'ilesa')[k % 3]
        tipos.append(status)
    tipos += [None] * cfg['falsas']
    rng.shuffle(tipos)
    for status in tipos:
        while comuns:
            l, c = comuns.pop()
            paredes = [d for d in DIRECOES if m.parede(l, c, d)]
            if paredes:
                break
        else:
            return None
        v = {'linha': l, 'coluna': c, 'parede': rng.choice(paredes), 'posicao': 0.5}
        if rng.random() < 0.5:
            v['tipo'] = 'letra'
            v['letra'] = {'ferida': 'H', 'estavel': 'S', 'ilesa': 'U', None: 'X'}[status]
        else:
            v['tipo'] = 'cognitivo'
            v['aneis'] = gera_aneis(status, rng)
        m.vitimas.append(v)
    if m.validar():
        return None
    return m


def main():
    ap = argparse.ArgumentParser(description='Gera um labirinto surpresa da Rescue Maze')
    ap.add_argument('--semente', type=int, default=1)
    ap.add_argument('--nivel', choices=NOMES_NIVEL, default='medio')
    ap.add_argument('--saida', default=None, help='arquivo (padrão: mapas/labirinto_NIVEL_SEMENTE.json)')
    a = ap.parse_args()
    m = gera(a.semente, a.nivel)
    saida = a.saida or os.path.join(RAIZ, 'mapas', f'{m.nome}.json')
    m.salvar(saida)
    pisos = {}
    for d in m.ladrilhos.values():
        for k in ('piso', 'terreno'):
            if d.get(k):
                pisos[d[k]] = pisos.get(d[k], 0) + 1
    print(f'{saida}: {m.linhas}x{m.colunas}, {len(m.vitimas)} vítimas, {pisos}')


if __name__ == '__main__':
    main()
