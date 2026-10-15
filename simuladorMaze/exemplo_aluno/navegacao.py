"""Mapa interno e planejamento de rota (sem nenhuma dependência de hardware).

Referencial: o robô começa no ladrilho (0, 0) olhando para a direção 0.
Coordenadas (f, e): f cresce "para frente" (direção inicial) e e "para a esquerda".
Direções: 0 = frente, 1 = esquerda, 2 = trás, 3 = direita (giro anti-horário soma 1).
"""

import collections
import json
import os
import time

DELTA = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}


def vizinho(p, d):
    return (p[0] + DELTA[d][0], p[1] + DELTA[d][1])


class Mapa:
    def __init__(self):
        self.paredes = {}       # (ladrilho, direção) -> True/False
        self.visitados = set()
        self.pisos = {}         # ladrilho -> 'preto' | 'azul' | 'prata' | 'vermelho'
        self.vitimas = set()    # (ladrilho, direção da parede)

    def set_parede(self, p, d, tem):
        self.paredes[(p, d)] = tem
        self.paredes[(vizinho(p, d), (d + 2) % 4)] = tem

    def bloqueado(self, p, d):
        """True se não dá para ir de p na direção d (parede ou piso proibido)."""
        if self.paredes.get((p, d), None) is not False:
            return True
        return self.pisos.get(vizinho(p, d)) in ('preto', 'vermelho')

    def fronteira(self, p):
        """Direções abertas de p que levam a ladrilhos ainda não visitados."""
        return [d for d in range(4) if not self.bloqueado(p, d) and vizinho(p, d) not in self.visitados]

    def caminho(self, origem, criterio):
        """Busca em largura: menor caminho (lista de direções) até um ladrilho que satisfaz criterio."""
        fila = collections.deque([origem])
        veio = {origem: None}
        while fila:
            p = fila.popleft()
            if p != origem and criterio(p):
                rota = []
                while veio[p] is not None:
                    q, d = veio[p]
                    rota.append(d)
                    p = q
                return list(reversed(rota))
            if p not in self.visitados:
                continue
            for d in range(4):
                if self.bloqueado(p, d):
                    continue
                q = vizinho(p, d)
                if q not in veio:
                    veio[q] = (p, d)
                    fila.append(q)
        return None

    # ------------------------------------------------------------------ checkpoint
    def para_dict(self):
        return {
            'paredes': [[p[0], p[1], d, t] for (p, d), t in self.paredes.items()],
            'visitados': [list(p) for p in self.visitados],
            'pisos': [[p[0], p[1], v] for p, v in self.pisos.items()],
            'vitimas': [[p[0], p[1], d] for (p, d) in self.vitimas],
        }

    @classmethod
    def de_dict(cls, d):
        m = cls()
        m.paredes = {((a, b), dd): t for a, b, dd, t in d['paredes']}
        m.visitados = {tuple(p) for p in d['visitados']}
        m.pisos = {(a, b): v for a, b, v in d['pisos']}
        m.vitimas = {((a, b), dd) for a, b, dd in d['vitimas']}
        return m


ARQUIVO_CHECKPOINT = 'checkpoint_maze.json'


def salva_checkpoint(mapa, pos, direcao, inicio_rodada):
    dados = {'mapa': mapa.para_dict(), 'pos': list(pos), 'dir': direcao,
             'inicio_rodada': inicio_rodada, 'salvo_em': time.time()}
    tmp = ARQUIVO_CHECKPOINT + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(dados, f)
    os.replace(tmp, ARQUIVO_CHECKPOINT)     # escrita atômica (desligar no meio não corrompe)


def carrega_checkpoint(validade_s=8 * 60):
    try:
        with open(ARQUIVO_CHECKPOINT) as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if time.time() - d.get('inicio_rodada', 0) > validade_s:
        return None
    return Mapa.de_dict(d['mapa']), tuple(d['pos']), d['dir'], d['inicio_rodada']
