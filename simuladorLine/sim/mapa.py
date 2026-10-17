"""Mapa da Rescue Line: grade de ladrilhos de 30 cm com camadas (pontes), rampas, gangorra,
lombadas, obstáculos, detritos e checkpoints.

Coordenadas
-----------
* Grade: x = coluna (para a direita), y = linha (para baixo, linha 0 no topo/norte),
  z = camada (0 = chão; ladrilhos de uma ponte ficam numa camada de cima).
* Mundo: mm, X para a direita (leste), Y para cima (norte). A célula (x, y) ocupa
  X em [300x, 300x + 300] e Y em [300(altura-1-y), 300(altura-y)].
* Local do ladrilho: u a partir da borda oeste, v a partir da borda sul (mm).

Rampas: o ladrilho de rampa fica na camada de baixo e sobe para a direção `sobe`. A borda
de cima conecta com a camada z+1. A altura de cada ladrilho é calculada seguindo o caminho a
partir do início (como o pathFinder do sistema oficial).
"""

import json
import math
import os
import random

import numpy as np

from . import ladrilhos as LT
from .ladrilhos import DIRS, OPOSTA, PASSO, TAM

TEMPO_RODADA = 480.0
ALTURA_CAMADA = 250.0       # mm, só para ladrilhos fora do caminho (sem altura propagada)

ITENS_PONTOS = {'intersecao': 10, 'gap': 10, 'obstaculo': 20, 'lombada': 10, 'rampa': 10, 'gangorra': 20}

OBSTACULO_PADRAO = {'larg': 60, 'comp': 60, 'altura': 150, 'ang': 0, 'fixo': False, 'massa_kg': 1.5}

# ------------------------------------------------------------------ área de resgate (regra 3.9/3.10)
CANTOS = ('NO', 'NE', 'SE', 'SO')
LADO_TRIANGULO = 300.0      # catetos do triângulo (regra: 30 x 30 cm)
ABERTURA = 250.0            # vão na parede na entrada/saída (= comprimento da fita)
FITA_LARG, FITA_COMP = 25.0, 250.0
PAREDE_ALTURA = 100.0       # regra: pelo menos 10 cm
PAREDE_ESPESSURA = 25.0     # parede de 25 mm, por dentro (a área é medida por fora); fitas faceadas nela
TRIANGULO_ALTURA = 60.0     # regra: paredes de 6 cm
ESPESSURA_TRIANGULO = 10.0  # parede do triângulo (não está na regra; medir a do seu campo)


def nova_zona(x, y, larg=4, alt=3):
    """Área de resgate de larg x alt células (120 x 90 cm = 4 x 3 ladrilhos)."""
    return {'x': x, 'y': y, 'larg': larg, 'alt': alt,
            'entrada': {'lado': 'O', 'i': alt - 1}, 'saida': {'lado': 'L', 'i': 0},
            'verde': 'NO', 'vermelho': 'SE',
            'obstaculo': None,              # {'u', 'v'} em mm a partir do canto sudoeste da área
            'cor_parede': [200, 200, 205],  # regra 2026: qualquer cor menos vermelho, verde e preto
            'vitimas': None,                # None = sorteio pela semente; ou [{'tipo','u','v'}]
            'falsas': 0}                    # vítimas falsas (regra 3.10.5)


def novo_ladrilho(x, y, z, tipo, rot=0):
    return {'x': x, 'y': y, 'z': z, 'tipo': tipo, 'rot': rot % 360, 'checkpoint': False,
            'rampa': None, 'lombadas': [], 'obstaculos': [], 'detritos': 0}


class Mapa:
    def __init__(self, largura=6, altura=5, nome='novo'):
        self.nome = nome
        self.caminho = None          # arquivo
        self.largura = largura
        self.altura = altura
        self.ladrilhos = {}          # (x, y, z) -> dict
        self.inicio = None           # (x, y, z)
        self.inicio_dir = None       # direção de saída no início (N/L/S/O); None = automática
        self.tempo = TEMPO_RODADA
        self.cat = LT.catalogo()
        self.versao = 0
        self._cache = None
        self._idx_celula = None
        self.zona = None             # área de resgate (dict) ou None
        self._zona_cels = {}         # (x, y) -> chave do passo da área
        self._zona_ver = 0

    # ------------------------------------------------------------------ edição
    def mudou(self):
        self.versao += 1
        self._cache = None
        self._idx_celula = None

    def lad(self, x, y, z=0):
        return self.ladrilhos.get((x, y, z))

    def celula(self, x, y):
        """Ladrilhos da célula (x, y), da camada de baixo para a de cima."""
        idx = getattr(self, '_idx_celula', None)
        if idx is None:
            idx = {}
            for k in sorted(self.ladrilhos, key=lambda k: k[2]):
                idx.setdefault(k[:2], []).append(self.ladrilhos[k])
            self._idx_celula = idx
        return idx.get((x, y), [])

    def dentro(self, x, y):
        return 0 <= x < self.largura and 0 <= y < self.altura

    def coloca(self, x, y, z, tipo, rot=0):
        antigo = self.lad(x, y, z)
        t = novo_ladrilho(x, y, z, tipo, rot)
        if antigo:   # troca só o desenho, mantém os itens
            for k in ('checkpoint', 'rampa', 'lombadas', 'obstaculos', 'detritos'):
                t[k] = antigo[k]
        if tipo == 'gangorra':
            t['gangorra'] = antigo.get('gangorra', {'graus': 15}) if antigo else {'graus': 15}
        self.ladrilhos[(x, y, z)] = t
        self.mudou()
        return t

    def remove(self, x, y, z):
        self.ladrilhos.pop((x, y, z), None)
        if self.inicio == (x, y, z):
            self.inicio = None
        self.mudou()

    def redimensiona(self, largura, altura, dx=0, dy=0):
        """Muda o tamanho da grade; dx/dy deslocam os ladrilhos (para crescer para cima/esquerda)."""
        largura, altura = max(1, largura), max(1, altura)
        novos = {}
        for (x, y, z), t in self.ladrilhos.items():
            nx, ny = x + dx, y + dy
            if 0 <= nx < largura and 0 <= ny < altura:
                t['x'], t['y'] = nx, ny
                novos[(nx, ny, z)] = t
        self.ladrilhos = {k: t for k, t in novos.items() if not t.get('_zona')}
        if self.inicio:
            x, y, z = self.inicio
            self.inicio = (x + dx, y + dy, z) if (x + dx, y + dy, z) in novos else None
        self.largura, self.altura = largura, altura
        if self.zona:
            z = self.zona
            z['x'] += dx
            z['y'] += dy
            if not (0 <= z['x'] and z['x'] + z['larg'] <= largura and 0 <= z['y'] and z['y'] + z['alt'] <= altura):
                self.zona = None
        self.aplica_zona()
        self.mudou()

    # ------------------------------------------------------------------ geometria
    @property
    def largura_mm(self):
        return self.largura * TAM

    @property
    def altura_mm(self):
        return self.altura * TAM

    def origem(self, x, y):
        """Canto sudoeste da célula no mundo."""
        return x * TAM, (self.altura - 1 - y) * TAM

    def centro(self, x, y):
        X0, Y0 = self.origem(x, y)
        return X0 + TAM / 2, Y0 + TAM / 2

    def celula_de(self, X, Y):
        x = int(math.floor(X / TAM))
        y = self.altura - 1 - int(math.floor(Y / TAM))
        if self.dentro(x, y):
            return x, y
        return None

    def local(self, t, X, Y):
        X0, Y0 = self.origem(t['x'], t['y'])
        return X - X0, Y - Y0

    def mundo(self, t, u, v):
        X0, Y0 = self.origem(t['x'], t['y'])
        return X0 + u, Y0 + v

    # ------------------------------------------------------------------ conexões
    @staticmethod
    def camada_borda(t, d):
        r = t.get('rampa')
        return t['z'] + (1 if r and r.get('sobe') == d else 0)

    def vizinho(self, t, d, h=None):
        """Ladrilho ligado a t pela borda d. Numa célula com ponte (dois ladrilhos), escolhe
        pela altura h da borda (camada z fica a ~z x 250 mm) ou, sem h, pela camada."""
        dx, dy = PASSO[d]
        x, y = t['x'] + dx, t['y'] + dy
        cel = self.celula(x, y)
        if not cel:
            return None
        if len(cel) == 1:
            return cel[0]
        if h is not None:
            return min(cel, key=lambda c: abs(self.camada_borda(c, OPOSTA[d]) * ALTURA_CAMADA - h))
        alvo = self.camada_borda(t, d)
        for c in cel:
            if self.camada_borda(c, OPOSTA[d]) == alvo:
                return c
        return None

    def caminhos(self, t):
        return self.cat.caminhos(t['tipo'], t['rot'])

    def eh_chegada(self, t):
        return bool(self.cat.info(t['tipo']).get('chegada'))

    def eh_gangorra(self, t):
        return bool(self.cat.info(t['tipo']).get('gangorra'))

    @staticmethod
    def chave(t):
        return (t['x'], t['y'], t['z'])

    # ------------------------------------------------------------------ caminho esperado
    def saidas_inicio(self):
        """Direções de saída possíveis no ladrilho de início."""
        t = self.ladrilhos.get(self.inicio) if self.inicio else None
        if not t:
            return []
        return sorted(set(self.caminhos(t).values()), key=DIRS.index)

    def _entrada_inicio(self, t):
        cam = self.caminhos(t)
        if self.inicio_dir:
            for e, s in cam.items():
                if s == self.inicio_dir:
                    return e
        # automático (como o sistema oficial): uma saída que tem ladrilho do outro lado
        escolha = None
        for e, s in cam.items():
            if self.vizinho(t, s) is not None:
                escolha = e
        if escolha is None and cam:
            escolha = next(iter(cam))
        return escolha

    def _calcula(self):
        """Caminho esperado (lista de passos) e altura de cada ladrilho."""
        passos = []
        erro = None
        t = self.ladrilhos.get(self.inicio) if self.inicio else None
        bases = {}
        if t is None:
            erro = 'sem ladrilho de início'
        else:
            entrada = self._entrada_inicio(t)
            h = 0.0
            while True:
                cam = self.caminhos(t)
                if self.eh_chegada(t):
                    passos.append({'k': self.chave(t), 'entrada': entrada, 'saida': None})
                    bases.setdefault(self.chave(t), self._base_entrando(t, entrada, h))
                    break
                saida = cam.get(entrada)
                if saida is None:
                    passos.append({'k': self.chave(t), 'entrada': entrada, 'saida': None})
                    erro = f'o ladrilho {self.chave(t)[:2]} não tem saída para quem entra por {entrada}'
                    bases.setdefault(self.chave(t), self._base_entrando(t, entrada, h))
                    break
                b = bases.setdefault(self.chave(t), self._base_entrando(t, entrada, h))
                passos.append({'k': self.chave(t), 'entrada': entrada, 'saida': saida})
                h = self._altura_borda(t, b, saida)
                prox = self.vizinho(t, saida, h)
                if prox is not None and prox.get('_zona'):
                    # a linha acaba na entrada da área e recomeça na saída
                    z = self.zona
                    if (prox['x'], prox['y']) != self.celula_lado(z['entrada']) or \
                            z['entrada']['lado'] != OPOSTA[saida]:
                        erro = 'o caminho chega na área de resgate fora da entrada'
                        break
                    ks = self.chave_zona()
                    lado_s = z['saida']['lado']
                    passos.append({'k': ks, 'entrada': OPOSTA[saida], 'saida': lado_s, 'zona': True})
                    for c in self._zona_cels:
                        bases[(c[0], c[1], 0)] = h
                    cs = self.celula_lado(z['saida'])
                    prox = self.vizinho(self.ladrilhos[(cs[0], cs[1], 0)], lado_s, h)
                    saida = lado_s
                    if prox is None or prox.get('_zona'):
                        erro = 'não há ladrilho com linha do lado de fora da saída da área'
                        break
                if prox is None:
                    erro = 'o caminho acaba antes do ladrilho de chegada'
                    break
                if len(passos) > 600:
                    erro = 'o caminho entra em laço'
                    break
                t, entrada = prox, OPOSTA[saida]
        # ladrilhos fora do caminho ficam no chão da camada deles (z x 250 mm)
        for k, t in self.ladrilhos.items():
            if k not in bases:
                bases[k] = t['z'] * ALTURA_CAMADA
        indices = {}
        for i, p in enumerate(passos):
            indices.setdefault(p['k'], []).append(i)
        if self.zona:
            ks = self.chave_zona()
            for c in self._zona_cels:
                indices[(c[0], c[1], 0)] = indices.get(ks, [])
        self._cache = {'passos': passos, 'erro': erro, 'bases': bases, 'indices': indices}

    def _sobe_por_mm(self, t):
        r = t.get('rampa')
        return math.tan(math.radians(float(r.get('graus', 20)))) if r else 0.0

    def _base_entrando(self, t, entrada, h):
        r = t.get('rampa')
        if not r:
            return h
        sobe = TAM * self._sobe_por_mm(t)
        if entrada == OPOSTA[r['sobe']]:
            return h
        if entrada == r['sobe']:
            return h - sobe
        return h - sobe / 2

    def _altura_borda(self, t, base, d):
        r = t.get('rampa')
        if not r:
            return base
        sobe = TAM * self._sobe_por_mm(t)
        if d == r['sobe']:
            return base + sobe
        if d == OPOSTA[r['sobe']]:
            return base
        return base + sobe / 2

    def _dados(self):
        if self._cache is None:
            self._calcula()
        return self._cache

    def passos(self):
        return self._dados()['passos']

    def erro_caminho(self):
        return self._dados()['erro']

    def indices(self, k):
        """Índices do caminho em que o ladrilho k aparece."""
        return self._dados()['indices'].get(k, [])

    def base(self, t):
        return self._dados()['bases'].get(self.chave(t), t['z'] * ALTURA_CAMADA)

    # ------------------------------------------------------------------ altura do piso
    def eixo_gangorra(self, t):
        """Direção da ponta 'positiva' da gangorra."""
        return LT.gira_dir('L', t['rot'])

    def graus_gangorra(self, t):
        return float(t.get('gangorra', {}).get('graus', 15))

    def elevacao(self, t, X, Y, ang_gangorra=None):
        """Altura do piso (mm) no ponto X, Y do mundo, dentro do ladrilho t."""
        b = self.base(t)
        u, v = self.local(t, X, Y)
        r = t.get('rampa')
        if r:
            s = {'N': v, 'S': TAM - v, 'L': u, 'O': TAM - u}[r['sobe']]
            return b + max(0.0, min(TAM, s)) * self._sobe_por_mm(t)
        if self.eh_gangorra(t):
            gmax = math.radians(self.graus_gangorra(t))
            phi = math.radians(ang_gangorra if ang_gangorra is not None else self.graus_gangorra(t))
            e = self.eixo_gangorra(t)
            s = {'N': v, 'S': TAM - v, 'L': u, 'O': TAM - u}[e] - TAM / 2
            return b + max(0.0, (TAM / 2) * math.tan(gmax) + s * math.tan(phi))
        return b

    def gradiente(self, t, ang_gangorra=None):
        """(dh/dX, dh/dY) do piso no ladrilho (constante por ladrilho)."""
        r = t.get('rampa')
        if r:
            k = self._sobe_por_mm(t)
            dx, dy = {'N': (0, 1), 'S': (0, -1), 'L': (1, 0), 'O': (-1, 0)}[r['sobe']]
            return dx * k, dy * k
        if self.eh_gangorra(t):
            phi = math.radians(ang_gangorra if ang_gangorra is not None else self.graus_gangorra(t))
            dx, dy = {'N': (0, 1), 'S': (0, -1), 'L': (1, 0), 'O': (-1, 0)}[self.eixo_gangorra(t)]
            k = math.tan(phi)
            return dx * k, dy * k
        return 0.0, 0.0

    def ladrilho_em(self, X, Y, h_ref=0.0, angs=None, tolerancia=70.0):
        """Ladrilho sob o ponto, escolhendo a camada cuja altura está mais perto de h_ref.
        Devolve None fora do campo ou se não há piso perto dessa altura (robô caiu)."""
        c = self.celula_de(X, Y)
        if c is None:
            return None
        melhor, dmin = None, None
        for t in self.celula(*c):
            a = angs.get(self.chave(t)) if angs else None
            d = abs(self.elevacao(t, X, Y, a) - h_ref)
            if dmin is None or d < dmin:
                melhor, dmin = t, d
        if melhor is None or dmin > tolerancia:
            return None
        return melhor

    # ------------------------------------------------------------------ itens
    def itens(self, t):
        """Itens pontuáveis do ladrilho: {item: quantidade}."""
        info = self.cat.info(t['tipo'])
        it = {}
        if info.get('intersecoes'):
            it['intersecao'] = int(info['intersecoes'])
        if info.get('gaps'):
            it['gap'] = 1
        if t.get('obstaculos'):
            it['obstaculo'] = len(t['obstaculos'])
        if t.get('lombadas'):
            it['lombada'] = 1
        if t.get('rampa'):
            it['rampa'] = 1
        if info.get('gangorra'):
            it['gangorra'] = 1
        return it

    def eixo_padrao(self, t):
        """'NS' se o caminho principal do ladrilho é norte-sul, senão 'LO'."""
        for e, s in self.caminhos(t).items():
            if e in ('N', 'S') and s in ('N', 'S'):
                return 'NS'
            if e in ('L', 'O') and s in ('L', 'O'):
                return 'LO'
            return 'NS' if e in ('N', 'S') else 'LO'
        return 'NS'

    def linhas_lombada(self, t):
        """Segmentos (no mundo) de cada lombada do ladrilho."""
        out = []
        for lb in t.get('lombadas', []):
            p = float(lb.get('pos', 0.5)) * TAM
            if lb.get('eixo', 'NS') == 'NS':    # robô anda N-S: lombada atravessada (horizontal)
                a, b = self.mundo(t, 0, p), self.mundo(t, TAM, p)
            else:
                a, b = self.mundo(t, p, 0), self.mundo(t, p, TAM)
            out.append((a[0], a[1], b[0], b[1]))
        return out

    def ponto_na_linha(self, t, u, v, raio=120):
        """Ponto preto do ladrilho mais perto de (u, v) (para pôr obstáculo em cima da linha)."""
        a = self.cat.material_girado(t['tipo'], t['rot'])
        ys, xs = np.nonzero(a == LT.M_PRETO)
        if len(xs) == 0:
            return u, v
        uu = xs + 0.5
        vv = TAM - (ys + 0.5)
        d = (uu - u) ** 2 + (vv - v) ** 2
        i = int(np.argmin(d))
        if d[i] > raio * raio:
            return u, v
        # centro da linha: média dos pixels pretos em volta (repetida para centralizar)
        cu, cv = uu[i], vv[i]
        for _ in range(4):
            perto = (uu - cu) ** 2 + (vv - cv) ** 2 < 14 ** 2
            cu, cv = uu[perto].mean(), vv[perto].mean()
        return float(cu), float(cv)

    def detritos_iniciais(self, t, semente=None):
        """Palitos soltos: lista de [x1, y1, x2, y2] no mundo."""
        n = int(t.get('detritos', 0))
        rng = random.Random(semente if semente is not None else hash((t['x'], t['y'], t['z'])) & 0xffff)
        out = []
        for _ in range(n):
            cu, cv = rng.uniform(40, TAM - 40), rng.uniform(40, TAM - 40)
            a = rng.uniform(0, math.pi)
            L = rng.uniform(30, 60) / 2
            p1 = self.mundo(t, cu - L * math.cos(a), cv - L * math.sin(a))
            p2 = self.mundo(t, cu + L * math.cos(a), cv + L * math.sin(a))
            out.append([p1[0], p1[1], p2[0], p2[1]])
        return out

    # ------------------------------------------------------------------ área de resgate
    def celulas_zona(self, z=None):
        z = z or self.zona
        if not z:
            return []
        return [(z['x'] + i, z['y'] + j) for j in range(z['alt']) for i in range(z['larg'])]

    def celula_lado(self, ab, z=None):
        """Célula da área encostada na abertura ab = {'lado', 'i'}."""
        z = z or self.zona
        lado, i = ab['lado'], int(ab['i'])
        if lado == 'N':
            return z['x'] + i, z['y']
        if lado == 'S':
            return z['x'] + i, z['y'] + z['alt'] - 1
        if lado == 'O':
            return z['x'], z['y'] + i
        return z['x'] + z['larg'] - 1, z['y'] + i

    def n_lado(self, lado, z=None):
        z = z or self.zona
        return z['larg'] if lado in ('N', 'S') else z['alt']

    def chave_zona(self):
        if not self.zona:
            return None
        c = self.celula_lado(self.zona['entrada'])
        return (c[0], c[1], 0)

    def chave_caminho(self, k):
        """Chave usada no caminho: qualquer célula da área vale como o passo da área."""
        if k is not None and self._zona_cels and k[2] == 0 and (k[0], k[1]) in self._zona_cels:
            return self.chave_zona()
        return k

    def eh_zona(self, t):
        return bool(t and t.get('_zona'))

    def retangulo_zona(self):
        """(X0, Y0, X1, Y1) da área no mundo."""
        z = self.zona
        X0 = z['x'] * TAM
        Y1 = (self.altura - z['y']) * TAM
        return X0, Y1 - z['alt'] * TAM, X0 + z['larg'] * TAM, Y1

    def interior_zona(self):
        """(X0, Y0, X1, Y1) do piso livre dentro das paredes (a área é medida por fora)."""
        X0, Y0, X1, Y1 = self.retangulo_zona()
        e = PAREDE_ESPESSURA
        return X0 + e, Y0 + e, X1 - e, Y1 - e

    def canto(self, c):
        """Canto interno (encostado nas duas paredes) e as duas direções ao longo delas."""
        X0, Y0, X1, Y1 = self.interior_zona()
        return {'NO': ((X0, Y1), (1, 0), (0, -1)), 'NE': ((X1, Y1), (-1, 0), (0, -1)),
                'SE': ((X1, Y0), (-1, 0), (0, 1)), 'SO': ((X0, Y0), (1, 0), (0, 1))}[c]

    def triangulo(self, c):
        (x, y), d1, d2 = self.canto(c)
        L = LADO_TRIANGULO
        return [(x, y), (x + d1[0] * L, y + d1[1] * L), (x + d2[0] * L, y + d2[1] * L)]

    def abertura_mundo(self, ab):
        """Centro do vão (no mundo) e direção que aponta para fora da área."""
        X0, Y0, X1, Y1 = self.retangulo_zona()
        lado, i = ab['lado'], int(ab['i'])
        if lado == 'N':
            return (X0 + (i + 0.5) * TAM, Y1), (0, 1)
        if lado == 'S':
            return (X0 + (i + 0.5) * TAM, Y0), (0, -1)
        if lado == 'O':
            return (X0, Y1 - (i + 0.5) * TAM), (-1, 0)
        return (X1, Y1 - (i + 0.5) * TAM), (1, 0)

    def paredes_zona(self):
        """Linhas do meio das paredes (x1, y1, x2, y2), com o vão da entrada e da saída. A parede tem
        PAREDE_ESPESSURA e fica toda para dentro da área: a face de fora é a borda medida."""
        e = PAREDE_ESPESSURA
        X0, Y0, X1, Y1 = self.retangulo_zona()
        X0, Y0, X1, Y1 = X0 + e / 2, Y0 + e / 2, X1 - e / 2, Y1 - e / 2
        z = self.zona
        lados = {'N': ((X0, Y1), (X1, Y1)), 'L': ((X1, Y1), (X1, Y0)),
                 'S': ((X1, Y0), (X0, Y0)), 'O': ((X0, Y0), (X0, Y1))}
        out = []
        for lado, (a, b) in lados.items():
            vaos = []
            for ab in (z['entrada'], z['saida']):
                if ab['lado'] == lado:
                    (cx, cy), _ = self.abertura_mundo(ab)
                    vaos.append((cx, cy))
            L = math.hypot(b[0] - a[0], b[1] - a[1])
            ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
            cortes = sorted(((cx - a[0]) * ux + (cy - a[1]) * uy) for cx, cy in vaos)
            s0 = 0.0
            meio = ABERTURA / 2 + e / 2          # a ponta da parede é arredondada (raio e/2)
            for c in cortes:
                if c - meio > s0:
                    out.append((a[0] + ux * s0, a[1] + uy * s0, a[0] + ux * (c - meio), a[1] + uy * (c - meio)))
                s0 = c + meio
            if s0 < L:
                out.append((a[0] + ux * s0, a[1] + uy * s0, b[0], b[1]))
        return out

    def _textura_zona(self, cx, cy):
        a = np.full((TAM, TAM), LT.M_BRANCO, np.uint8)
        z = self.zona
        m0, m1 = int((TAM - FITA_COMP) / 2), int((TAM + FITA_COMP) / 2)
        f = int(FITA_LARG)
        for ab, mat in ((z['entrada'], LT.M_PRATA), (z['saida'], LT.M_PRETO)):
            if self.celula_lado(ab) != (cx, cy):
                continue
            lado = ab['lado']
            if lado == 'N':
                a[0:f, m0:m1] = mat
            elif lado == 'S':
                a[TAM - f:TAM, m0:m1] = mat
            elif lado == 'O':
                a[m0:m1, 0:f] = mat
            else:
                a[m0:m1, TAM - f:TAM] = mat
        return a

    def aplica_zona(self):
        """(Re)cria os ladrilhos de piso da área (não vão para o arquivo)."""
        for k in [k for k, t in self.ladrilhos.items() if t.get('_zona')]:
            del self.ladrilhos[k]
        self._zona_cels = {}
        z = self.zona
        if not z:
            self.mudou()
            return
        self._zona_ver += 1
        for c in self.celulas_zona():
            for k in [k for k in self.ladrilhos if k[:2] == c]:
                del self.ladrilhos[k]
            nome = f'zona@{c[0]},{c[1]}#{self._zona_ver}'
            self.cat.registra(nome, self._textura_zona(*c), descricao='piso da área de resgate')
            t = novo_ladrilho(c[0], c[1], 0, nome)
            t['_zona'] = True
            self.ladrilhos[(c[0], c[1], 0)] = t
            self._zona_cels[c] = True
        if self.inicio and (self.inicio[0], self.inicio[1]) in self._zona_cels:
            self.inicio = None
        self.mudou()

    def coloca_zona(self, x, y, larg=4, alt=3):
        z = nova_zona(x, y, larg, alt)
        if self.zona:   # mantém o que dá da área anterior
            for k in ('cor_parede', 'falsas', 'vitimas'):
                z[k] = self.zona[k]
        self.zona = z
        self.aplica_zona()

    def remove_zona(self):
        self.zona = None
        self.aplica_zona()

    def cantos_proibidos(self, z=None):
        """Cantos encostados na célula da entrada ou da saída (regra 3.9.9)."""
        z = z or self.zona
        out = set()
        for ab in (z['entrada'], z['saida']):
            c = self.celula_lado(ab, z)
            for canto in CANTOS:
                lados = {'NO': ('N', 'O'), 'NE': ('N', 'L'), 'SE': ('S', 'L'), 'SO': ('S', 'O')}[canto]
                cel = {'NO': (z['x'], z['y']), 'NE': (z['x'] + z['larg'] - 1, z['y']),
                       'SE': (z['x'] + z['larg'] - 1, z['y'] + z['alt'] - 1),
                       'SO': (z['x'], z['y'] + z['alt'] - 1)}[canto]
                if c == cel and ab['lado'] in lados:
                    out.add(canto)
        return out

    def valida_zona(self):
        z = self.zona
        av = []
        if (z['entrada']['lado'], z['entrada']['i']) == (z['saida']['lado'], z['saida']['i']):
            av.append('A entrada e a saída da área estão no mesmo lugar.')
        if z['verde'] == z['vermelho']:
            av.append('Os dois triângulos estão no mesmo canto.')
        proib = self.cantos_proibidos()
        for cor in ('verde', 'vermelho'):
            if z[cor] in proib:
                av.append(f'Triângulo {cor} no canto da entrada/saída (regra 3.9.9).')
        cor = z.get('cor_parede', [200, 200, 205])
        r, g, b = cor
        if max(cor) < 60:
            av.append('Parede da área preta (regra 2026: qualquer cor menos vermelho, verde e preto).')
        elif r > 1.6 * max(g, b) or g > 1.4 * max(r, b):
            av.append('Parede da área vermelha/verde (regra 2026: qualquer cor menos vermelho, verde e preto).')
        return av

    # ------------------------------------------------------------------ validação
    def validar(self):
        av = []
        if not self.inicio or self.inicio not in self.ladrilhos:
            return ['Marque o ladrilho de início (ferramenta Início).']
        passos = self.passos()
        erro = self.erro_caminho()
        if erro:
            av.append('Caminho: ' + erro + '.')
        chaves = [p['k'] for p in passos]
        if passos and not self.eh_chegada(self.ladrilhos[chaves[-1]]):
            av.append('O caminho não termina num ladrilho de chegada (fita vermelha).')
        n = len(set(chaves) - {self.inicio} - ({chaves[-1]} if chaves else set()) - {self.chave_zona()})
        if n < 8:
            av.append(f'A regra pede pelo menos 8 ladrilhos além do início e da chegada (tem {n}).')
        for k, t in self.ladrilhos.items():
            if t.get('_zona'):
                continue
            if t.get('checkpoint') and self.itens(t):
                av.append(f'Checkpoint em {k[:2]} tem item pontuável (a regra não permite).')
            r = t.get('rampa')
            if r and float(r.get('graus', 20)) > 25:
                av.append(f'Rampa em {k[:2]} passa de 25°.')
            if self.eh_gangorra(t) and self.graus_gangorra(t) >= 20:
                av.append(f'Gangorra em {k[:2]} precisa inclinar menos de 20°.')
        if self.zona:
            av.extend(self.valida_zona())
            if not any(p.get('zona') for p in passos):
                av.append('O caminho não passa pela área de resgate (a linha precisa chegar na entrada).')
        fora = [k for k in self.ladrilhos if k not in set(chaves) and self.ladrilhos[k]['tipo'] != 'branco'
                and not self.ladrilhos[k].get('_zona')]
        if fora:
            av.append(f'{len(fora)} ladrilho(s) com linha fora do caminho (ok se for de propósito).')
        return av

    # ------------------------------------------------------------------ arquivos
    def para_dict(self):
        lads = []
        for k in sorted(self.ladrilhos, key=lambda k: (k[2], k[1], k[0])):
            t = self.ladrilhos[k]
            if t.get('_zona'):
                continue
            d = {kk: t[kk] for kk in ('x', 'y', 'z', 'tipo', 'rot')}
            for kk in ('checkpoint', 'rampa', 'lombadas', 'obstaculos', 'detritos', 'gangorra'):
                if t.get(kk):
                    d[kk] = t[kk]
            lads.append(d)
        d = {'formato': 'simuladorLine/1', 'regra': 'RoboCupJunior Rescue Line 2026',
             'nome': self.nome, 'largura': self.largura, 'altura': self.altura,
             'inicio': list(self.inicio) if self.inicio else None, 'inicio_dir': self.inicio_dir,
             'tempo': self.tempo, 'ladrilhos': lads}
        if self.zona:
            d['zona_resgate'] = json.loads(json.dumps(self.zona))
        return d

    def salvar(self, caminho):
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(self.para_dict(), f, indent=1, ensure_ascii=False)
        self.caminho = caminho

    @classmethod
    def de_dict(cls, d):
        if 'tiles' in d and 'formato' not in d:
            return cls.importar_cms(d)
        m = cls(int(d['largura']), int(d['altura']), d.get('nome', 'mapa'))
        for t in d['ladrilhos']:
            if not m.cat.existe(t['tipo']):
                raise ValueError(f"ladrilho desconhecido: {t['tipo']}")
            n = novo_ladrilho(int(t['x']), int(t['y']), int(t.get('z', 0)), t['tipo'], int(t.get('rot', 0)))
            for kk in ('checkpoint', 'rampa', 'lombadas', 'obstaculos', 'detritos', 'gangorra'):
                if kk in t:
                    n[kk] = t[kk]
            if m.cat.info(n['tipo']).get('gangorra') and not n.get('gangorra'):
                n['gangorra'] = {'graus': 15}
            m.ladrilhos[(n['x'], n['y'], n['z'])] = n
        m.inicio = tuple(d['inicio']) if d.get('inicio') else None
        m.inicio_dir = d.get('inicio_dir')
        m.tempo = float(d.get('tempo', TEMPO_RODADA))
        if d.get('zona_resgate'):
            z = nova_zona(0, 0)
            z.update(d['zona_resgate'])
            m.zona = z
        m.aplica_zona()
        m.mudou()
        return m

    @classmethod
    def carregar(cls, caminho):
        with open(caminho, encoding='utf-8') as f:
            d = json.load(f)
        m = cls.de_dict(d)
        m.caminho = caminho
        if 'nome' not in d:
            m.nome = os.path.splitext(os.path.basename(caminho))[0]
        return m

    @classmethod
    def importar_cms(cls, d):
        """Mapa exportado do sistema oficial (rcj-rescue-cms / rcj.cloud)."""
        m = cls(int(d.get('width', 1)), int(d.get('height', 1)), d.get('name', 'importado'))
        avisos = []
        for t in d['tiles']:
            tt = t.get('tileType')
            nome = None
            if isinstance(tt, dict):
                nome = m.cat.por_id_cms.get(tt.get('_id')) or m.cat.por_imagem_cms.get(tt.get('image', ''))
                if nome is None and tt.get('image') == 'exit.png':
                    nome = 'chegada'
                if nome is None and tt.get('image') == 'seesaw.png':
                    nome = 'gangorra'
            else:
                nome = m.cat.por_id_cms.get(tt)
                if tt == '58cfd6549792e9313b1610e0':
                    nome = 'chegada'
                elif tt == '58cfd6549792e9313b1610df':
                    nome = 'gangorra'
            if nome is None:
                avisos.append(f"ladrilho {tt} ignorado (zona de resgate ou desconhecido)")
                continue
            x, y, z = int(t['x']), int(t['y']), int(t.get('z', 0))
            rampa = None
            if t.get('levelUp'):
                rampa = {'sobe': LT.DO_CMS[t['levelUp']], 'graus': 20}
            elif t.get('levelDown'):
                z -= 1
                rampa = {'sobe': OPOSTA[LT.DO_CMS[t['levelDown']]], 'graus': 20}
            n = novo_ladrilho(x, y, z, nome, int(t.get('rot', 0)))
            n['rampa'] = rampa
            n['checkpoint'] = bool(t.get('checkPoint'))
            it = t.get('items', {})
            if nome == 'gangorra':
                n['gangorra'] = {'graus': 15}
            m.ladrilhos[(x, y, z)] = n
            nl = int(it.get('speedbumps', 0) or 0)
            if nl:
                eixo = m.eixo_padrao(n)
                n['lombadas'] = [{'pos': round((i + 1) / (nl + 1), 2), 'eixo': eixo} for i in range(nl)]
            for i in range(int(it.get('obstacles', 0) or 0)):
                u, v = m.ponto_na_linha(n, TAM / 2, TAM / 2)
                ob = dict(OBSTACULO_PADRAO)
                ob.update({'u': round(u), 'v': round(v)})
                n['obstaculos'].append(ob)
        st = d.get('startTile') or {}
        if st and st.get('x', -1) >= 0:
            k = (int(st['x']), int(st['y']), int(st.get('z', 0)))
            if k in m.ladrilhos:
                m.inicio = k
        m.avisos_importacao = avisos
        m.mudou()
        return m
