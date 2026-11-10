"""Teste da física das pilhas (cubos em cima das plataformas), direto no Mundo, sem programa:

    python testa_pilha.py

em cima, na beirada, em cima de dois (na emenda), empurrado, plataforma andando. Rode depois de mexer
no Mundo.solta, no _apoio ou no _derruba_pilhas (sim/fisica.py).
"""
import json
import os
import sys

SIM = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SIM)
from pymunk import Vec2d  # noqa: E402

from sim import arena as A  # noqa: E402
from sim import fisica as F  # noqa: E402

cfg = json.load(open(os.path.join(SIM, 'robo_bombertinho.json'), encoding='utf-8'))
c = A.Cenario()
c.plataformas = {'P3': 'azul'}
c.cubos = {k: 'azul' for k in ('A1', 'A2', 'A3', 'A4', 'A5')}
ok = True


def novo():
    w = F.Mundo(c, cfg, 1)
    cubos = {o.pos: o for o in w.objetos if o.tipo == 'cubo'}
    return w, cubos


def solta(w, o, x, y, altura):
    o.muda_estado('preso', altura)
    w.solta(w.robo, o, Vec2d(x, y), altura)
    return o.estado, round(o.z), w.eventos_garra[-1][0]


def confere(nome, obtido, esperado):
    global ok
    bom = obtido == esperado
    ok &= bom
    print(f'{"ok " if bom else "ERRO"} {nome}: {obtido}' + ('' if bom else f' (esperado {esperado})'))


w, k = novo()
confere('no meio da plataforma', solta(w, k['A1'], 95, 750, 54), ('plataforma', 50, 'plataforma'))
confere('em cima dele', solta(w, k['A2'], 95, 755, 108), ('plataforma', 100, 'plataforma'))
confere('3º andar, centro fora do de baixo', solta(w, k['A3'], 95, 795, 158), ('livre', 0, 'caiu'))
confere('caiu fora da plataforma', F._penetra(w.objetos[0].forma, k['A3'].forma, -1.0) is None, True)
confere('plataforma, centro fora dela', solta(w, k['A4'], 95, 845, 54), ('livre', 0, 'caiu'))
confere('baixo demais (base 40)', solta(w, k['A5'], 95, 650, 40), ('livre', 0, 'chao'))

w, k = novo()
solta(w, k['A1'], 95, 722, 54)
solta(w, k['A2'], 95, 778, 54)
confere('em cima de dois, centro na emenda', solta(w, k['A3'], 95, 750, 108), ('plataforma', 100, 'plataforma'))
confere('2º andar, centro fora da ponta do de baixo', solta(w, k['A4'], 95, 690, 108), ('livre', 0, 'caiu'))
confere('2º andar, centro 3 mm dentro da ponta', solta(w, k['A5'], 95, 700, 108), ('plataforma', 100, 'plataforma'))

w, k = novo()
solta(w, k['A1'], 95, 750, 54)
solta(w, k['A2'], 95, 750, 108)
w.eventos_garra.clear()
w._empurra(k['A1'], w.robo, Vec2d(0, 10))
confere('empurra o de baixo 10 mm', (k['A1'].estado, k['A2'].estado, round(k['A1'].corpo.position.y)),
        ('plataforma', 'plataforma', 760))
w._empurra(k['A1'], w.robo, Vec2d(0, 20))
confere('mais 20: o de cima perde o apoio', (k['A1'].estado, k['A2'].estado, [e[0] for e in w.eventos_garra]),
        ('plataforma', 'livre', ['derrubado']))
w._empurra(k['A1'], w.robo, Vec2d(0, 60))
confere('mais 60: o de baixo sai da plataforma', (k['A1'].estado, [e[0] for e in w.eventos_garra]),
        ('livre', ['derrubado', 'derrubado']))
# a plataforma andando leva a pilha junto
w, k = novo()
solta(w, k['A1'], 95, 750, 54)
solta(w, k['A2'], 95, 750, 108)
plat = w.objetos[0]
plat.corpo.position += Vec2d(0, 30)
w.space.reindex_shapes_for_body(plat.corpo)
w._segue_plataformas()
confere('plataforma andou 30 mm', (round(k['A1'].corpo.position.y), round(k['A2'].corpo.position.y)), (780, 780))
print('TUDO CERTO' if ok else 'FALHOU')
