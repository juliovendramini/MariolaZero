"""Gera uma pista surpresa da Rescue Line: caminho sorteado, ladrilhos sorteados.

Na competição a pista só é conhecida no dia. Treinar sempre nos mesmos mapas faz o programa
"decorar" a pista (constantes ajustadas para aquelas curvas). A pista surpresa testa se o
programa funciona em qualquer pista dentro da regra.

Uso:
    python ferramentas/pista_surpresa.py                          # nível médio, semente 1
    python ferramentas/pista_surpresa.py --nivel dificil --semente 7
    python ferramentas/pista_surpresa.py --semente 3 --saida mapas/minha_surpresa.json

A mesma semente e o mesmo nível geram sempre a mesma pista. O avalia.py usa este gerador nos
desafios de pista surpresa.

Níveis:
    facil    retas e curvas simples, 1 interseção com verde
    medio    + retas e curvas desenhadas (ondas, degraus), gap, 2-3 interseções, lombada
    dificil  + ziguezague, cruzamentos, obstáculo, detritos, 3-4 interseções, 2 gaps
"""
import argparse
import os
import random
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from sim.ladrilhos import catalogo, PASSO, OPOSTA  # noqa: E402
from sim.mapa import Mapa, OBSTACULO_PADRAO  # noqa: E402

# Ladrilhos por tipo (nomes do catálogo). Todos atravessam o ladrilho: entram por um lado e
# saem por outro, sem bifurcação. A rotação certa é procurada pelos caminhos do catálogo.
RETAS = {
    'facil': ['tile-0'],
    'medio': ['tile-0', 'tile-8', 'tile-9', 'tile-13', 'tile-14', 'tile-17', '021', '022', 'tile-46',
              'tile-59', 'tile-67', 'tile-70'],
    'dificil': ['tile-0', 'tile-1', 'tile-2', 'tile-18', 'tile-23', 'tile-53', 'tile-60', 'tile-66',
                'tile-68', 'tile-69', '010', '011', '025', 'tile-56', 'tile-62', 'tile-75'],
}
CURVAS = {
    'facil': ['tile-6', 'tile-12'],
    'medio': ['tile-6', 'tile-12', 'tile-21', 'tile-5', 'tile-51', 'tile-71'],
    'dificil': ['tile-6', 'tile-12', 'tile-3', 'tile-10', 'tile-22', 'tile-24', 'tile-26', 'tile-57',
                'tile-61', 'tile-65', '007', '009', 'tile-58'],
}
# interseções com verde (ou sem verde = seguir reto). Só valem as orientações em que o caminho
# certo, segundo o catálogo, leva do lado em que o robô entra ao lado em que ele deve sair.
INTERSECOES = {
    'facil': ['tile-15', 'tile-16'],
    'medio': ['tile-15', 'tile-16', 'tile-41', 'tile-30', 'tile-35'],
    'dificil': ['tile-15', 'tile-16', 'tile-41', 'tile-30', 'tile-32', 'tile-33', 'tile-34', 'tile-35'],
}
GAPS = {'medio': ['tile-20', 'tile-11_2'], 'dificil': ['tile-20', 'tile-11', 'tile-11_2', 'tile-49']}

NIVEIS = {
    #            grade    comprimento  interseções gaps obstáculos lombadas detritos
    'facil':   dict(grade=(6, 4), comp=(11, 15), inter=1, gaps=0, obst=0, lomb=0, detr=0, p_especial=0.0),
    'medio':   dict(grade=(7, 5), comp=(14, 19), inter=(2, 3), gaps=1, obst=0, lomb=1, detr=0, p_especial=0.5),
    'dificil': dict(grade=(8, 5), comp=(17, 23), inter=(3, 4), gaps=2, obst=1, lomb=1, detr=1, p_especial=0.7),
}
NOMES_NIVEL = list(NIVEIS)


def _sorteia(rng, v):
    return rng.randint(*v) if isinstance(v, tuple) else v


def _caminho(rng, larg, alt, comp):
    """Caminho sem cruzar (lista de células) com 'comp' células, por busca com retrocesso."""
    for _ in range(400):
        x0, y0 = rng.randrange(larg), rng.randrange(alt)
        d0 = rng.choice('NLSO')
        dx, dy = PASSO[d0]
        # o ladrilho de início é reto: a célula seguinte vai na mesma direção, e atrás dele
        # (de onde a linha "vem") não pode ter caminho
        x1, y1 = x0 + dx, y0 + dy
        if not (0 <= x1 < larg and 0 <= y1 < alt):
            continue
        cam = [(x0, y0), (x1, y1)]
        atras = (x0 - dx, y0 - dy)
        usados = {cam[0], cam[1], atras}
        if _estende(rng, cam, usados, larg, alt, comp, [0]):
            return cam, d0
    return None, None


def _estende(rng, cam, usados, larg, alt, comp, contador):
    contador[0] += 1
    if contador[0] > 20000:
        return False
    if len(cam) == comp:
        # a chegada é o último: precisa de uma reta antes (os 2 últimos na mesma direção)
        return True
    x, y = cam[-1]
    px, py = cam[-2]
    dir_atual = (x - px, y - py)
    opcoes = []
    for d, (dx, dy) in PASSO.items():
        n = (x + dx, y + dy)
        if not (0 <= n[0] < larg and 0 <= n[1] < alt) or n in usados:
            continue
        # preferir seguir reto às vezes (pistas com trechos retos para gap e obstáculo)
        peso = 2.2 if (dx, dy) == dir_atual else 1.0
        opcoes.append((rng.random() * peso, n))
    opcoes.sort(reverse=True)
    for _, n in opcoes:
        cam.append(n)
        usados.add(n)
        if _estende(rng, cam, usados, larg, alt, comp, contador):
            return True
        cam.pop()
        usados.discard(n)
    return False


def _lado(de, para):
    """Lado da célula 'de' pelo qual se vai para 'para'."""
    dx, dy = para[0] - de[0], para[1] - de[1]
    for d, p in PASSO.items():
        if p == (dx, dy):
            return d
    raise ValueError


def _orienta(cat, nome, entra, sai):
    """Rotações em que o ladrilho leva de 'entra' a 'sai' (lado de entrada e de saída)."""
    out = []
    for rot in (0, 90, 180, 270):
        if cat.caminhos(nome, rot).get(entra) == sai:
            out.append(rot)
    return out


def _lados_com_linha(cat, nome, rot):
    c = cat.caminhos(nome, rot)
    return set(c) | set(c.values())


def gera(semente=1, nivel='medio', nome=None):
    """Devolve um Mapa válido (lança RuntimeError se não conseguir)."""
    if nivel not in NIVEIS:
        raise ValueError(f'nível {nivel!r}: use {", ".join(NIVEIS)}')
    cfg = NIVEIS[nivel]
    cat = catalogo()
    rng = random.Random(f'{nivel}-{semente}')
    larg, alt = cfg['grade']
    for _tentativa in range(400):
        comp = rng.randint(*cfg['comp'])
        cam, d0 = _caminho(rng, larg, alt, comp)
        if not cam:
            continue
        m = _monta(cat, rng, cfg, nivel, cam, d0, larg, alt, nome or f'surpresa_{nivel}_{semente}')
        if m is not None:
            return m
    raise RuntimeError('não consegui gerar a pista (tente outra semente)')


def _monta(cat, rng, cfg, nivel, cam, d0, larg, alt, nome):
    n = len(cam)
    no_caminho = set(cam)
    entra = [None] * n
    sai = [None] * n
    for i in range(n):
        entra[i] = OPOSTA[d0] if i == 0 else _lado(cam[i], cam[i - 1])
        sai[i] = _lado(cam[i], cam[i + 1]) if i < n - 1 else OPOSTA[entra[i]]
    reta = [OPOSTA[entra[i]] == sai[i] for i in range(n)]
    if not reta[-1] or not reta[-2]:
        return None                        # chegada depois de uma reta

    tipo = {}
    # reservados: início (0), o seguinte (1) e a chegada (n-1)
    livres = list(range(2, n - 1))

    # checkpoints a cada 4-5 ladrilhos, em ladrilho simples (sem item pontuável)
    checkpoints = set()
    i = 5
    while i < n - 2:
        checkpoints.add(i)
        i += rng.randint(4, 5)

    # interseções (em reta ou curva), longe uma da outra
    n_inter = _sorteia(rng, cfg['inter'])
    candidatos = [i for i in livres if i not in checkpoints]
    rng.shuffle(candidatos)
    for i in candidatos:
        if n_inter == 0:
            break
        if any(abs(i - j) < 2 for j, (k, _) in tipo.items() if k == 'inter'):
            continue
        opcoes = []
        for t in INTERSECOES[nivel]:
            for rot in _orienta(cat, t, entra[i], sai[i]):
                lados = _lados_com_linha(cat, t, rot) - {entra[i], sai[i]}
                ok = True
                for l in lados:   # o ramo que não se segue não pode encostar no caminho
                    dx, dy = PASSO[l]
                    viz = (cam[i][0] + dx, cam[i][1] + dy)
                    if viz in no_caminho:
                        ok = False
                if ok:
                    opcoes.append((t, rot))
        if opcoes:
            tipo[i] = ('inter', rng.choice(opcoes))
            n_inter -= 1
    if n_inter > 0:
        return None

    # gaps: só em reta, com reta antes e depois (a regra pede o gap num trecho reto)
    if cfg['gaps']:
        cand = [i for i in livres if i not in tipo and i not in checkpoints and reta[i]
                and reta[i - 1] and i + 1 < n and reta[i + 1] and (i - 1) not in tipo]
        rng.shuffle(cand)
        for i in cand[:cfg['gaps']]:
            t = rng.choice(GAPS[nivel])
            rots = _orienta(cat, t, entra[i], sai[i])
            if rots:
                tipo[i] = ('gap', (t, rng.choice(rots)))

    # obstáculo: reta simples, com as duas laterais livres (para contornar)
    obst = set()
    if cfg['obst']:
        cand = []
        for i in livres:
            if i in tipo or i in checkpoints or not reta[i] or not reta[i - 1] or not reta[i + 1]:
                continue
            dx, dy = PASSO[sai[i]]
            laterais = [(cam[i][0] - dy, cam[i][1] + dx), (cam[i][0] + dy, cam[i][1] - dx)]
            if all(0 <= x < larg and 0 <= y < alt and (x, y) not in no_caminho for x, y in laterais):
                cand.append(i)
        rng.shuffle(cand)
        for i in cand[:cfg['obst']]:
            tipo[i] = ('obst', ('tile-0', _orienta(cat, 'tile-0', entra[i], sai[i])[0]))
            obst.add(i)
        if len(obst) < cfg['obst']:
            return None

    # lombadas e detritos: retas simples
    lomb, detr = set(), set()
    cand = [i for i in livres if i not in tipo and i not in checkpoints and reta[i]]
    rng.shuffle(cand)
    for i in cand[:cfg['lomb']]:
        lomb.add(i)
    cand = [i for i in cand if i not in lomb]
    for i in cand[:cfg['detr']]:
        detr.add(i)

    # o resto: retas e curvas, às vezes desenhadas
    for i in range(n):
        if i in tipo:
            continue
        if i == n - 1:
            rots = _orienta(cat, 'chegada', entra[i], sai[i]) or \
                [r for r in (0, 90, 180, 270) if entra[i] in cat.caminhos('chegada', r)]
            tipo[i] = ('chegada', ('chegada', rots[0]))
            continue
        simples = i < 2 or i >= n - 2 or i in checkpoints or i in lomb or i in detr
        especial = (not simples) and rng.random() < cfg['p_especial']
        if reta[i]:
            lista = RETAS[nivel] if especial else ['tile-0']
        else:
            lista = CURVAS[nivel] if especial else ['tile-6']
        lista = list(lista)
        rng.shuffle(lista)
        for t in lista:
            rots = _orienta(cat, t, entra[i], sai[i])
            # a linha do ladrilho não pode sair por um lado que encosta em outro trecho
            rots = [r for r in rots if _lados_com_linha(cat, t, r) <= {entra[i], sai[i]}]
            if rots:
                tipo[i] = ('normal', (t, rng.choice(rots)))
                break
        else:
            return None

    m = Mapa(larg, alt, nome)
    for i, (x, y) in enumerate(cam):
        t, rot = tipo[i][1]
        m.coloca(x, y, 0, t, rot)
    m.inicio = (cam[0][0], cam[0][1], 0)
    m.inicio_dir = d0
    for i in checkpoints:
        m.lad(*cam[i])['checkpoint'] = True
    for i in lomb:
        eixo = 'NS' if sai[i] in ('N', 'S') else 'LO'
        m.lad(*cam[i])['lombadas'] = [{'pos': 0.5, 'eixo': eixo}]
    for i in detr:
        m.lad(*cam[i])['detritos'] = 5
    for i in obst:
        ob = dict(OBSTACULO_PADRAO)
        ob.update({'u': 150, 'v': 150})
        m.lad(*cam[i])['obstaculos'] = [ob]
    for x in range(larg):
        for y in range(alt):
            if not m.celula(x, y):
                m.coloca(x, y, 0, 'branco')
    m.mudou()
    avisos = [a for a in m.validar() if 'fora do caminho' not in a]
    if avisos or len(m.passos()) != n:
        return None
    return m


def main():
    ap = argparse.ArgumentParser(description='Gera uma pista surpresa da Rescue Line')
    ap.add_argument('--semente', type=int, default=1)
    ap.add_argument('--nivel', choices=NOMES_NIVEL, default='medio')
    ap.add_argument('--saida', default=None, help='arquivo (padrão: mapas/surpresa_NIVEL_SEMENTE.json)')
    a = ap.parse_args()
    m = gera(a.semente, a.nivel)
    saida = a.saida or os.path.join(RAIZ, 'mapas', f'{m.nome}.json')
    m.salvar(saida)
    it = {}
    for k in {p['k'] for p in m.passos()}:
        for nome, q in m.itens(m.ladrilhos[k]).items():
            it[nome] = it.get(nome, 0) + q
    print(f'{saida}: {len(m.passos())} ladrilhos no caminho, itens {it}')


if __name__ == '__main__':
    main()
