"""Gera os mapas da trilha de desafios (desafios/mapas/*.json).

Cada pista é descrita pela lista de células do caminho (do início à chegada) e pelos ladrilhos
especiais; a rotação de cada ladrilho é achada sozinha pelos caminhos do catálogo.
"""
import os
import shutil
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
sys.path.insert(0, os.path.join(RAIZ, 'ferramentas'))
from sim.ladrilhos import catalogo, OPOSTA, PASSO  # noqa: E402
from sim.mapa import Mapa, OBSTACULO_PADRAO  # noqa: E402
from pista_surpresa import _lado, _orienta, _lados_com_linha  # noqa: E402

PASTA = os.path.join(RAIZ, 'desafios', 'mapas')


def pista(nome, larg, alt, cam, d0, tipos=None, checkpoints=(), extras=None, ramos_livres=True):
    """cam: células do início à chegada; d0: direção do robô no início;
    tipos: {índice: nome do ladrilho}; extras: {índice: {campo: valor}} (lombadas, rampa...)."""
    cat = catalogo()
    tipos = tipos or {}
    extras = extras or {}
    n = len(cam)
    m = Mapa(larg, alt, nome)
    no_cam = set(cam)
    for i, cel in enumerate(cam):
        entra = OPOSTA[d0] if i == 0 else _lado(cel, cam[i - 1])
        sai = _lado(cel, cam[i + 1]) if i < n - 1 else OPOSTA[entra]
        if i == n - 1:
            t = 'chegada'
            rots = [r for r in (0, 90, 180, 270) if cat.caminhos(t, r).get(entra)]
        else:
            t = tipos.get(i) or ('tile-0' if OPOSTA[entra] == sai else 'tile-6')
            rots = _orienta(cat, t, entra, sai)
            if ramos_livres:
                bons = []
                for r in rots:
                    ramos = _lados_com_linha(cat, t, r) - {entra, sai}
                    if all((cel[0] + PASSO[l][0], cel[1] + PASSO[l][1]) not in no_cam for l in ramos):
                        bons.append(r)
                rots = bons
        if not rots:
            raise RuntimeError(f'{nome}: {t} não serve na posição {i} {cel} ({entra}->{sai})')
        m.coloca(cel[0], cel[1], 0, t, rots[0])
    m.inicio = (cam[0][0], cam[0][1], 0)
    m.inicio_dir = d0
    for i in checkpoints:
        m.lad(*cam[i])['checkpoint'] = True
    for i, ex in extras.items():
        m.lad(*cam[i]).update(ex)
    for x in range(larg):
        for y in range(alt):
            if not m.celula(x, y):
                m.coloca(x, y, 0, 'branco')
    m.mudou()
    return m


def linha(*trechos):
    """Monta a lista de células a partir de trechos (x0, y0, x1, y1) retos e encadeados."""
    cam = []
    for x0, y0, x1, y1 in trechos:
        dx = (x1 > x0) - (x1 < x0)
        dy = (y1 > y0) - (y1 < y0)
        x, y = x0, y0
        while True:
            if not cam or cam[-1] != (x, y):
                cam.append((x, y))
            if (x, y) == (x1, y1):
                break
            x, y = x + dx, y + dy
    return cam


def l02_curvas():
    """Retas e curvas desenhadas: ondas, degraus, ziguezague, arcos (linhas paralelas afastadas)."""
    cam = linha((0, 4, 6, 4), (6, 4, 6, 0), (6, 0, 0, 0), (0, 0, 0, 2), (0, 2, 3, 2))
    tipos = {2: 'tile-13', 4: 'tile-9', 5: 'tile-14', 7: 'tile-62', 9: 'tile-75', 10: 'tile-21',
             11: 'tile-17', 12: 'tile-69', 13: 'tile-46', 14: 'tile-8', 16: 'tile-57', 18: 'tile-51',
             }
    return pista('L02_curvas', 7, 5, cam, 'L', tipos, checkpoints=(8, 15))


def l04_verde():
    """Interseções: verde à esquerda, à direita, nos dois lados de um cruzamento, e sem verde."""
    # uma fileira livre em cima e embaixo: nenhum ramo de interseção aponta para fora do campo
    cam = linha((0, 5, 3, 5), (3, 5, 3, 3), (3, 3, 6, 3), (6, 3, 6, 1), (6, 1, 1, 1), (1, 1, 1, 3))
    tipos = {2: 'tile-35',        # cruzamento sem verde: reto
             3: 'tile-15',        # verde à esquerda: vira à esquerda (para o norte)
             5: 'tile-16',        # verde à direita: vira à direita (para o leste)
             7: 'tile-41',        # T sem verde: reto
             13: 'tile-30',       # cruzamento com verde depois dele (não vale): reto
             15: 'tile-32',       # cruzamento com verde à esquerda: vira à esquerda (para o sul)
             }
    return pista('L04_verde', 7, 7, cam, 'L', tipos, checkpoints=(6, 12))


def l05_gap_obstaculo():
    """Dois gaps em reta e um obstáculo com espaço dos dois lados."""
    cam = linha((0, 3, 6, 3), (6, 3, 6, 1), (6, 1, 0, 1))
    tipos = {2: 'tile-20', 5: 'tile-11'}
    ob = dict(OBSTACULO_PADRAO)
    ob.update({'u': 150, 'v': 150})
    extras = {11: {'obstaculos': [ob]}}
    # o obstáculo fica na linha de cima (y=1): laterais (y=0 e y=2) livres
    return pista('L05_gap_obstaculo', 7, 5, cam, 'L', tipos, checkpoints=(7, 13), extras=extras)


def l06_terreno():
    """Lombadas, detritos, rampa de subida e de descida e gangorra."""
    cam = linha((0, 4, 7, 4), (7, 4, 7, 1), (7, 1, 2, 1), (2, 1, 2, 3))
    tipos = {16: 'gangorra'}
    extras = {
        2: {'lombadas': [{'pos': 0.35, 'eixo': 'LO'}, {'pos': 0.65, 'eixo': 'LO'}]},
        4: {'detritos': 5},
        8: {'rampa': {'sobe': 'N', 'graus': 20}},
        9: {'rampa': {'sobe': 'N', 'graus': 20}},
        12: {'rampa': {'sobe': 'L', 'graus': 20}},
        13: {'rampa': {'sobe': 'L', 'graus': 20}},
    }
    return pista('L06_terreno', 8, 5, cam, 'L', tipos, checkpoints=(6, 11, 15), extras=extras)


def copia(origem, destino):
    shutil.copy(os.path.join(RAIZ, 'mapas', origem), os.path.join(PASTA, destino))


if __name__ == '__main__':
    os.makedirs(PASTA, exist_ok=True)
    for f in (l02_curvas, l04_verde, l05_gap_obstaculo, l06_terreno):
        m = f()
        av = m.validar()
        print(m.nome, len(m.passos()), m.erro_caminho() or 'ok', av)
        m.salvar(os.path.join(PASTA, m.nome + '.json'))
    copia('curso_pista.json', 'L01_pista.json')
    copia('completo.json', 'L07_completo.json')
    copia('resgate.json', 'L08_resgate.json')
    copia('curso_area.json', 'L09_area.json')
