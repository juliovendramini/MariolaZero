"""Gera os mapas de exemplo (mapas/*.json)."""
import os
import sys

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, RAIZ)
from sim.mapa import Mapa, OBSTACULO_PADRAO  # noqa: E402


def preenche(m):
    for x in range(m.largura):
        for y in range(m.altura):
            if not m.celula(x, y):
                m.coloca(x, y, 0, 'branco')


def treino():
    m = Mapa(6, 4, 'treino')
    L = [
        (0, 3, 'tile-0', 0), (1, 3, 'tile-0', 0), (2, 3, 'tile-13', 0), (3, 3, 'tile-11', 0),
        (4, 3, 'tile-0', 0), (5, 3, 'tile-6', 90), (5, 2, 'tile-0', 90), (5, 1, 'tile-6', 0),
        (4, 1, 'tile-16', 0), (4, 0, 'tile-6', 0), (3, 0, 'tile-0', 0), (2, 0, 'tile-41', 180),
        (1, 0, 'tile-6', 270), (1, 1, 'tile-0', 90), (1, 2, 'chegada', 180),
        (3, 1, 'tile-0', 0), (2, 1, 'tile-6', 180),
    ]
    for x, y, t, r in L:
        m.coloca(x, y, 0, t, r)
    for k in ((5, 2), (1, 1)):
        m.lad(*k)['checkpoint'] = True
    m.inicio = (0, 3, 0)
    m.inicio_dir = 'L'
    preenche(m)
    m.mudou()
    return m


def completo():
    """Rampas (subida e descida), ponte, gangorra, lombadas, gap, obstáculo, detritos e verde."""
    m = Mapa(8, 7, 'completo')
    L = [
        # linha de baixo, para o leste
        (0, 5, 'tile-0', 0), (1, 5, 'tile-0', 0), (2, 5, 'tile-20', 0), (3, 5, 'tile-0', 0),
        (4, 5, 'tile-0', 0), (5, 5, 'tile-0', 0), (6, 5, 'tile-0', 0), (7, 5, 'tile-6', 90),
        # sobe a rampa pela direita
        (7, 4, 'tile-0', 90), (7, 3, 'tile-0', 90), (7, 2, 'tile-6', 0),
        # linha elevada para o oeste, passando pela ponte em (4,2) e descendo a rampa
        (6, 2, 'tile-0', 0), (5, 2, 'tile-0', 0), (3, 2, 'tile-0', 0), (2, 2, 'tile-0', 0),
        (1, 2, 'tile-6', 180),
        # sobe pela esquerda e vai para o leste pela linha de cima (gangorra e verde)
        (1, 1, 'tile-0', 90), (1, 0, 'tile-6', 270), (2, 0, 'gangorra', 0), (3, 0, 'tile-0', 0),
        (4, 0, 'tile-16', 180), (5, 0, 'tile-0', 0),
        # desce pela coluna 4, por baixo da ponte, até a chegada
        (4, 1, 'tile-0', 90), (4, 2, 'tile-0', 90), (4, 3, 'tile-0', 90), (4, 4, 'chegada', 180),
    ]
    for x, y, t, r in L:
        m.coloca(x, y, 0, t, r)
    m.coloca(4, 2, 1, 'tile-0', 0)            # ponte (camada 1) sobre o (4,2) do chão
    m.inicio = (0, 5, 0)
    m.inicio_dir = 'L'
    m.lad(1, 5)['lombadas'] = [{'pos': 0.35, 'eixo': 'LO'}, {'pos': 0.65, 'eixo': 'LO'}]
    m.lad(5, 5)['detritos'] = 5
    m.lad(7, 4)['rampa'] = {'sobe': 'N', 'graus': 25}
    m.lad(7, 3)['rampa'] = {'sobe': 'N', 'graus': 25}
    m.lad(3, 2)['rampa'] = {'sobe': 'L', 'graus': 25}
    m.lad(2, 2)['rampa'] = {'sobe': 'L', 'graus': 25}
    ob = dict(OBSTACULO_PADRAO)
    ob.update({'u': 150, 'v': 150})
    m.lad(3, 5)['obstaculos'] = [ob]
    for k in ((6, 5), (5, 2), (4, 3)):
        m.lad(*k)['checkpoint'] = True
    preenche(m)
    m.mudou()
    return m


def resgate():
    """Linha curta até a área de resgate (entrada embaixo, saída à direita) e chegada depois dela."""
    m = Mapa(8, 6, 'resgate')
    L = [
        (0, 5, 'tile-0', 0), (1, 5, 'tile-0', 0), (2, 5, 'tile-20', 0), (3, 5, 'tile-0', 0),
        (4, 5, 'tile-6', 90), (4, 4, 'tile-0', 90),
        (6, 1, 'tile-0', 0), (7, 1, 'tile-6', 0), (7, 2, 'tile-0', 90), (7, 3, 'chegada', 180),
    ]
    for x, y, t, r in L:
        m.coloca(x, y, 0, t, r)
    m.inicio = (0, 5, 0)
    m.inicio_dir = 'L'
    m.lad(1, 5)['lombadas'] = [{'pos': 0.5, 'eixo': 'LO'}]
    for k in ((4, 4), (6, 1)):
        m.lad(*k)['checkpoint'] = True
    m.coloca_zona(2, 1)
    m.zona['entrada'] = {'lado': 'S', 'i': 2}
    m.zona['saida'] = {'lado': 'L', 'i': 0}
    m.zona['verde'] = 'NO'
    m.zona['vermelho'] = 'SE'
    m.aplica_zona()
    preenche(m)
    m.mudou()
    return m


if __name__ == '__main__':
    for f in (treino, completo, resgate):
        m = f()
        print(m.nome, len(m.passos()), m.erro_caminho(), m.validar())
        m.salvar(os.path.join(RAIZ, 'mapas', m.nome + '.json'))
