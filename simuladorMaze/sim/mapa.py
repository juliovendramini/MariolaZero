"""Modelo do mapa da RoboCupJunior Rescue Maze.

Convenções
----------
* Ladrilho (linha, coluna): linha 0 fica no topo (norte), coluna 0 à esquerda (oeste).
* Coordenadas do mundo em milímetros: x cresce para leste, y cresce para norte.
* Direções: 'N', 'S', 'L' (leste), 'O' (oeste).
* paredes_h[l][c] -> parede na borda NORTE do ladrilho (l, c). l vai de 0 até linhas
  (a linha "linhas" é a borda sul da última fileira).
* paredes_v[l][c] -> parede na borda OESTE do ladrilho (l, c). c vai de 0 até colunas.
"""

import json
import math
import random

TAM = 300.0            # tamanho do ladrilho (mm)
MEIA_PAREDE = 10.0     # metade da espessura da parede -> corredor de 280 mm

DIRECOES = ('N', 'L', 'S', 'O')
DELTA = {'N': (-1, 0), 'S': (1, 0), 'L': (0, 1), 'O': (0, -1)}
OPOSTA = {'N': 'S', 'S': 'N', 'L': 'O', 'O': 'L'}
ESQUERDA_DE = {'N': 'O', 'O': 'S', 'S': 'L', 'L': 'N'}
DIREITA_DE = {v: k for k, v in ESQUERDA_DE.items()}
# ângulo (rad, anti-horário a partir do leste) de cada direção
ANGULO_DIR = {'L': 0.0, 'N': math.pi / 2, 'O': math.pi, 'S': -math.pi / 2}

PISOS = ('branco', 'preto', 'prata', 'azul', 'vermelho')
TERRENOS = ('', 'lombada', 'escada', 'detritos')

# cores dos anéis dos alvos cognitivos e seus valores
VALOR_ANEL = {'preto': -2, 'vermelho': -1, 'amarelo': 0, 'verde': 1, 'azul': 2}
STATUS_LETRA = {'H': 'ferida', 'S': 'estavel', 'U': 'ilesa'}
STATUS_SOMA = {2: 'ferida', 1: 'estavel', 0: 'ilesa'}
KITS_STATUS = {'ferida': 2, 'estavel': 1, 'ilesa': 0}
SIMBOLO_LETRA = {'H': 'Φ', 'S': 'Ψ', 'U': 'Ω'}


def status_vitima(v):
    """Retorna 'ferida' | 'estavel' | 'ilesa' ou None (vítima falsa)."""
    if v.get('tipo') == 'letra':
        return STATUS_LETRA.get(v.get('letra'))
    if v.get('tipo') == 'cognitivo':
        aneis = v.get('aneis', [])
        if len(aneis) != 5 or any(a not in VALOR_ANEL for a in aneis):
            return None
        return STATUS_SOMA.get(sum(VALOR_ANEL[a] for a in aneis))
    return None


def gera_aneis(status, rng=None):
    """Gera 5 anéis aleatórios cuja soma corresponde ao status (ou falsa se status=None)."""
    rng = rng or random.Random()
    cores = list(VALOR_ANEL)
    alvo = {'ferida': 2, 'estavel': 1, 'ilesa': 0}.get(status)
    for _ in range(5000):
        aneis = [rng.choice(cores) for _ in range(5)]
        soma = sum(VALOR_ANEL[a] for a in aneis)
        if alvo is None:
            if soma not in (0, 1, 2):
                return aneis
        elif soma == alvo:
            return aneis
    return ['amarelo'] * 5


class Mapa:
    def __init__(self, linhas=6, colunas=8, nome='novo'):
        self.nome = nome
        self.linhas = linhas
        self.colunas = colunas
        self.inicio = (0, 0)
        self.inicio_dir = 'L'
        self.paredes_h = [[False] * colunas for _ in range(linhas + 1)]
        self.paredes_v = [[False] * (colunas + 1) for _ in range(linhas)]
        self.ladrilhos = {}   # (l, c) -> {'piso':..., 'terreno':..., 'direcao':..., 'zona':bool}
        self.vitimas = []     # dicts
        self.semente = 1
        self.caminho = None
        self.cerca_perimetro()

    # ------------------------------------------------------------------ básicos
    def cerca_perimetro(self):
        for c in range(self.colunas):
            self.paredes_h[0][c] = True
            self.paredes_h[self.linhas][c] = True
        for l in range(self.linhas):
            self.paredes_v[l][0] = True
            self.paredes_v[l][self.colunas] = True

    def dentro(self, l, c):
        return 0 <= l < self.linhas and 0 <= c < self.colunas

    def lad(self, l, c):
        return self.ladrilhos.get((l, c), {})

    def piso(self, l, c):
        return self.lad(l, c).get('piso', 'branco')

    def terreno(self, l, c):
        return self.lad(l, c).get('terreno', '')

    def zona(self, l, c):
        return bool(self.lad(l, c).get('zona', False))

    def set_lad(self, l, c, **kw):
        d = dict(self.ladrilhos.get((l, c), {}))
        d.update(kw)
        d = {k: v for k, v in d.items() if v not in (None, '', False, 'branco')}
        if d:
            self.ladrilhos[(l, c)] = d
        else:
            self.ladrilhos.pop((l, c), None)

    def parede(self, l, c, d):
        if d == 'N':
            return self.paredes_h[l][c]
        if d == 'S':
            return self.paredes_h[l + 1][c]
        if d == 'O':
            return self.paredes_v[l][c]
        return self.paredes_v[l][c + 1]

    def set_parede(self, l, c, d, valor):
        if d == 'N':
            self.paredes_h[l][c] = valor
        elif d == 'S':
            self.paredes_h[l + 1][c] = valor
        elif d == 'O':
            self.paredes_v[l][c] = valor
        else:
            self.paredes_v[l][c + 1] = valor

    # --------------------------------------------------------------- geometria
    @property
    def largura_mm(self):
        return self.colunas * TAM

    @property
    def altura_mm(self):
        return self.linhas * TAM

    def centro(self, l, c):
        return ((c + 0.5) * TAM, (self.linhas - l - 0.5) * TAM)

    def ladrilho_em(self, x, y):
        c = int(math.floor(x / TAM))
        l = int(math.floor((self.altura_mm - y) / TAM))
        if self.dentro(l, c):
            return (l, c)
        return None

    def segmentos_parede(self):
        """Lista de segmentos (x1, y1, x2, y2) no eixo central de cada parede.
        Paredes colineares contíguas são unidas."""
        segs = []
        H = self.altura_mm
        for l in range(self.linhas + 1):
            y = H - l * TAM
            c = 0
            while c < self.colunas:
                if self.paredes_h[l][c]:
                    c0 = c
                    while c < self.colunas and self.paredes_h[l][c]:
                        c += 1
                    segs.append((c0 * TAM, y, c * TAM, y))
                else:
                    c += 1
        for c in range(self.colunas + 1):
            x = c * TAM
            l = 0
            while l < self.linhas:
                if self.paredes_v[l][c]:
                    l0 = l
                    while l < self.linhas and self.paredes_v[l][c]:
                        l += 1
                    segs.append((x, H - l0 * TAM, x, H - l * TAM))
                else:
                    l += 1
        return segs

    def ponto_vitima(self, v):
        """Ponto (x, y) da vítima na face da parede e normal apontando para dentro do ladrilho."""
        l, c, d = v['linha'], v['coluna'], v['parede']
        p = min(max(float(v.get('posicao', 0.5)), 0.1), 0.9)
        x0, y0 = c * TAM, self.altura_mm - (l + 1) * TAM   # canto sudoeste
        if d == 'N':
            return (x0 + p * TAM, y0 + TAM - MEIA_PAREDE), (0.0, -1.0)
        if d == 'S':
            return (x0 + p * TAM, y0 + MEIA_PAREDE), (0.0, 1.0)
        if d == 'O':
            return (x0 + MEIA_PAREDE, y0 + p * TAM), (1.0, 0.0)
        return (x0 + TAM - MEIA_PAREDE, y0 + p * TAM), (-1.0, 0.0)

    def perfil_escada(self, l, c, x, y):
        """Altura (mm) do piso dentro de um ladrilho de escada no ponto (x, y)."""
        lad = self.lad(l, c)
        x0, y0 = c * TAM, self.altura_mm - (l + 1) * TAM
        s = (y - y0) if lad.get('direcao', 'NS') == 'NS' else (x - x0)
        s = min(max(s, 0.0), TAM)
        if s > TAM / 2:
            s = TAM - s
        # zona de perigo: degraus mais curtos (rampa mais íngreme)
        comp = 40.0 if self.zona(l, c) else 70.0
        n_degraus = 2
        altura = 20.0
        if s >= comp:
            return altura
        degrau = int(s / (comp / n_degraus)) + (1 if s > 0 else 0)
        return min(degrau, n_degraus) * altura / n_degraus

    def linhas_lombada(self, l, c):
        """Segmentos de lombada dentro do ladrilho."""
        lad = self.lad(l, c)
        x0, y0 = c * TAM, self.altura_mm - (l + 1) * TAM
        segs = []
        for f in (0.3, 0.7):
            if lad.get('direcao', 'NS') == 'NS':   # robô anda norte-sul: lombadas horizontais
                yy = y0 + f * TAM
                segs.append((x0 + 10, yy, x0 + TAM - 10, yy))
            else:
                xx = x0 + f * TAM
                segs.append((xx, y0 + 10, xx, y0 + TAM - 10))
        return segs

    def detritos_iniciais(self, l, c):
        rng = random.Random(hash((self.semente, l, c)) & 0xFFFFFFFF)
        x0, y0 = c * TAM, self.altura_mm - (l + 1) * TAM
        return [[x0 + rng.uniform(40, TAM - 40), y0 + rng.uniform(40, TAM - 40)] for _ in range(6)]

    # ------------------------------------------------------------- navegação
    def pode_passar(self, l, c, d, preto_bloqueia=True):
        if self.parede(l, c, d):
            return False
        dl, dc = DELTA[d]
        nl, nc = l + dl, c + dc
        if not self.dentro(nl, nc):
            return False
        if preto_bloqueia and self.piso(nl, nc) == 'preto':
            return False
        return True

    def ladrilhos_lineares(self):
        """Ladrilhos alcançados seguindo a parede da esquerda ou da direita a partir do início."""
        lineares = set()
        l0, c0 = self.inicio
        for mao in ('esq', 'dir'):
            for d0 in DIRECOES:
                estado = (l0, c0, d0)
                vistos = set()
                while estado not in vistos and len(vistos) < 40000:
                    vistos.add(estado)
                    l, c, d = estado
                    lineares.add((l, c))
                    if mao == 'esq':
                        ordem = (ESQUERDA_DE[d], d, DIREITA_DE[d], OPOSTA[d])
                    else:
                        ordem = (DIREITA_DE[d], d, ESQUERDA_DE[d], OPOSTA[d])
                    for nd in ordem:
                        if self.pode_passar(l, c, nd):
                            dl, dc = DELTA[nd]
                            estado = (l + dl, c + dc, nd)
                            break
                    else:
                        break
        return lineares

    def validar(self):
        """Avisos simples sobre o mapa (não impede salvar)."""
        avisos = []
        for v in self.vitimas:
            l, c, d = v['linha'], v['coluna'], v['parede']
            if not self.dentro(l, c):
                avisos.append(f'vítima fora do mapa em {l},{c}')
                continue
            if not self.parede(l, c, d):
                avisos.append(f'vítima em ({l},{c}) {d} sem parede')
            if self.piso(l, c) in ('preto', 'prata', 'azul', 'vermelho') or self.terreno(l, c) in ('lombada', 'escada'):
                avisos.append(f'vítima em ({l},{c}) voltada para ladrilho especial (proibido pela regra 3.6.3)')
        if self.piso(*self.inicio) != 'branco':
            avisos.append('o ladrilho de início deve ser comum')
        alcancados = {tuple(self.inicio)}
        pilha = [tuple(self.inicio)]
        while pilha:
            l, c = pilha.pop()
            for d in DIRECOES:
                if self.pode_passar(l, c, d):
                    n = (l + DELTA[d][0], c + DELTA[d][1])
                    if n not in alcancados:
                        alcancados.add(n)
                        pilha.append(n)
        fora = [(l, c) for l in range(self.linhas) for c in range(self.colunas)
                if (l, c) not in alcancados and self.piso(l, c) != 'preto']
        if fora:
            avisos.append(f'{len(fora)} ladrilho(s) inalcançável(is) sem passar por preto: '
                          + ', '.join(f'({l},{c})' for l, c in fora[:6]) + (' ...' if len(fora) > 6 else ''))
        return avisos

    # ------------------------------------------------------------ persistência
    def para_dict(self):
        lads = []
        for (l, c), d in sorted(self.ladrilhos.items()):
            e = {'linha': l, 'coluna': c}
            e.update(d)
            lads.append(e)
        return {
            'formato': 'maze-sim-1',
            'nome': self.nome,
            'linhas': self.linhas,
            'colunas': self.colunas,
            'inicio': {'linha': self.inicio[0], 'coluna': self.inicio[1], 'direcao': self.inicio_dir},
            'semente': self.semente,
            'paredes_h': [''.join('1' if p else '0' for p in linha) for linha in self.paredes_h],
            'paredes_v': [''.join('1' if p else '0' for p in linha) for linha in self.paredes_v],
            'ladrilhos': lads,
            'vitimas': self.vitimas,
        }

    @classmethod
    def de_dict(cls, d):
        m = cls(d['linhas'], d['colunas'], d.get('nome', 'mapa'))
        ini = d.get('inicio', {})
        m.inicio = (ini.get('linha', 0), ini.get('coluna', 0))
        m.inicio_dir = ini.get('direcao', 'L')
        m.semente = d.get('semente', 1)
        m.paredes_h = [[ch == '1' for ch in s] for s in d['paredes_h']]
        m.paredes_v = [[ch == '1' for ch in s] for s in d['paredes_v']]
        m.ladrilhos = {}
        for e in d.get('ladrilhos', []):
            e = dict(e)
            l, c = e.pop('linha'), e.pop('coluna')
            m.ladrilhos[(l, c)] = e
        m.vitimas = [dict(v) for v in d.get('vitimas', [])]
        return m

    def salvar(self, caminho):
        d = self.para_dict()
        partes = []
        for k, v in d.items():
            if k in ('paredes_h', 'paredes_v', 'ladrilhos', 'vitimas'):
                itens = ',\n    '.join(json.dumps(x, ensure_ascii=False) for x in v)
                partes.append(f'  {json.dumps(k)}: [\n    {itens}\n  ]' if v else f'  {json.dumps(k)}: []')
            else:
                partes.append(f'  {json.dumps(k)}: {json.dumps(v, ensure_ascii=False)}')
        with open(caminho, 'w', encoding='utf-8') as f:
            f.write('{\n' + ',\n'.join(partes) + '\n}\n')
        self.caminho = caminho

    @classmethod
    def carregar(cls, caminho):
        with open(caminho, 'r', encoding='utf-8') as f:
            m = cls.de_dict(json.load(f))
        m.caminho = caminho
        return m

    # ------------------------------------------------------------ edição
    def redimensiona(self, linhas, colunas):
        linhas, colunas = max(1, linhas), max(1, colunas)
        novo = Mapa(linhas, colunas, self.nome)
        novo.paredes_h = [[False] * colunas for _ in range(linhas + 1)]
        novo.paredes_v = [[False] * (colunas + 1) for _ in range(linhas)]
        for l in range(min(linhas + 1, self.linhas + 1)):
            for c in range(min(colunas, self.colunas)):
                novo.paredes_h[l][c] = self.paredes_h[l][c]
        for l in range(min(linhas, self.linhas)):
            for c in range(min(colunas + 1, self.colunas + 1)):
                novo.paredes_v[l][c] = self.paredes_v[l][c]
        novo.cerca_perimetro()
        novo.ladrilhos = {k: v for k, v in self.ladrilhos.items() if novo.dentro(*k)}
        novo.vitimas = [v for v in self.vitimas if novo.dentro(v['linha'], v['coluna'])]
        novo.inicio = self.inicio if novo.dentro(*self.inicio) else (0, 0)
        novo.inicio_dir = self.inicio_dir
        novo.semente = self.semente
        novo.caminho = self.caminho
        self.__dict__.update(novo.__dict__)
