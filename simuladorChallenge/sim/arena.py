"""Arena da RCB Challenge 2026 (regra V1.0, seção 4) e o cenário de cada partida (cubos e plataformas).

Unidades em mm. Origem no canto de baixo à esquerda da lona, x para a direita, y para cima.
A lona é 2840 x 1500 e é simétrica por rotação de 180° em volta do centro (1420, 750): o lado
direito é o esquerdo girado (os nomes dos quadrados do lado direito aparecem de cabeça para baixo
na figura da regra). Medidas que a regra não dá foram tiradas da figura 1 (2,1 mm por pixel), e
batem com as do texto: grade de linhas pretas com 300 mm entre centros.

Lado 'esq' = equipe que começa na área verde da esquerda; 'dir' = a outra.
Nomes do lado direito levam apóstrofo: A1 (esquerda) e A1' (direita). O C3 fica no centro
da pista e é o mesmo para os dois lados.
"""

import json
import math
import random

LARGURA = 2840.0
ALTURA = 1500.0
CX, CY = LARGURA / 2, ALTURA / 2

BORDA = 20.0                      # linha vermelha (limite da cidade)
LINHA = 20.0                      # linhas pretas, azuis e vermelhas
X_ECOPONTO = (BORDA, BORDA + 220.0)               # amarelo, 220 x 1460
X_VERDE = (X_ECOPONTO[1], X_ECOPONTO[1] + 280.0)  # área livre, 280 x 1460
X_AZUL = (X_VERDE[1], X_VERDE[1] + LINHA)         # divisa entre a área livre e a cidade
X_CIDADE = (X_AZUL[1], LARGURA - X_AZUL[1])       # 540 a 2300
VERTICAIS = [670.0, 970.0, 1270.0, 1570.0, 1870.0, 2170.0]   # centros das linhas pretas "em pé"
HORIZONTAIS = [150.0, 450.0, 750.0, 1050.0, 1350.0]         # centros das linhas pretas "deitadas"
QUADRADO = 50.0                   # quadrados cinza (só o contorno) e marrons (cheios)
CONTORNO_CINZA = 2.0              # espessura do contorno cinza-claro (estimada)

# local de descarte: 5 retângulos brancos de 160 x 50 por lado, centrados na altura,
# a 50 mm da linha vermelha e 100 mm um do outro
DESCARTE_X = (BORDA + 50.0, BORDA + 100.0)
DESCARTE_Y = [150.0 + k * 260.0 for k in range(5)]    # começo de cada retângulo (160 de altura)
DESCARTE_ALT = 160.0

CORES_CUBO = ['azul', 'vermelho', 'verde', 'amarelo', 'preto', 'marrom', 'branco']
CORES_PLATAFORMA = ['azul', 'vermelho', 'verde', 'amarelo', 'preto', 'marrom']
ESTOQUE_CUBOS = {c: 5 for c in CORES_PLATAFORMA}       # por pista (seção 5.1)
ESTOQUE_CUBOS['branco'] = 6

# cor de desenho (RGB) de cada coisa
RGB = {
    'branco': (245, 245, 242), 'preto': (20, 20, 20), 'vermelho': (225, 30, 30),
    'azul': (20, 60, 230), 'verde': (0, 128, 0), 'amarelo': (250, 235, 20),
    'marrom': (125, 60, 10), 'cinza': (215, 215, 215), 'fora': (70, 70, 74),
}


def gira(x, y):
    """Ponto equivalente do outro lado (rotação de 180° em volta do centro)."""
    return LARGURA - x, ALTURA - y


def _quadrados_lado_esq():
    """Posições dos quadrados do lado esquerdo: cinza (cubos a coletar) e marrons (obstáculos)."""
    cinza = {}
    # A, B, C: sobre as linhas deitadas, no meio entre duas linhas em pé (de baixo para cima)
    for letra, x, n in (('A', 820.0, 5), ('B', 1120.0, 5), ('C', 1420.0, 3)):
        for k in range(n):
            cinza[f'{letra}{k + 1}'] = (x, HORIZONTAIS[k])
    # D a G: sobre as linhas em pé, no meio entre duas deitadas (D em cima, G embaixo),
    # numerados da área livre para o centro
    for letra, y in (('D', 1200.0), ('E', 900.0), ('F', 600.0), ('G', 300.0)):
        for k in range(3):
            cinza[f'{letra}{k + 1}'] = (VERTICAIS[k], y)
    marrom = {}
    for letra, x, n in (('X', 820.0, 4), ('Y', 1120.0, 4), ('Z', 1420.0, 2)):
        for k in range(n):
            marrom[f'{letra}{k + 1}'] = (x, 300.0 + 300.0 * k)
    return cinza, marrom


def _monta_posicoes():
    cinza_e, marrom_e = _quadrados_lado_esq()
    pos = {}
    for nome, p in cinza_e.items():
        pos[nome] = {'tipo': 'cinza', 'lado': 'esq', 'x': p[0], 'y': p[1]}
        if nome != 'C3':                       # o C3 é o centro da pista: um só para os dois
            q = gira(*p)
            pos[nome + "'"] = {'tipo': 'cinza', 'lado': 'dir', 'x': q[0], 'y': q[1]}
    pos['C3']['lado'] = 'centro'
    for nome, p in marrom_e.items():
        pos[nome] = {'tipo': 'marrom', 'lado': 'esq', 'x': p[0], 'y': p[1]}
        q = gira(*p)
        pos[nome + "'"] = {'tipo': 'marrom', 'lado': 'dir', 'x': q[0], 'y': q[1]}
    # locais de descarte (onde vão as plataformas): P1 embaixo ... P5 em cima, do lado esquerdo
    for k, y0 in enumerate(DESCARTE_Y):
        x = (DESCARTE_X[0] + DESCARTE_X[1]) / 2
        y = y0 + DESCARTE_ALT / 2
        pos[f'P{k + 1}'] = {'tipo': 'descarte', 'lado': 'esq', 'x': x, 'y': y}
        q = gira(x, y)
        pos[f"P{k + 1}'"] = {'tipo': 'descarte', 'lado': 'dir', 'x': q[0], 'y': q[1]}
    return pos


POSICOES = _monta_posicoes()


def par(nome):
    """Nome da mesma posição do outro lado (A1 <-> A1'); o C3 é par dele mesmo."""
    if nome.endswith("'"):
        return nome[:-1]
    return nome if nome == 'C3' else nome + "'"


# --------------------------------------------------------------------------- piso
def piso(x, y):
    """Material do chão no ponto (x, y): o que o sensor de linha vê."""
    if x < 0 or y < 0 or x > LARGURA or y > ALTURA:
        return 'fora'
    if x < BORDA or y < BORDA or x > LARGURA - BORDA or y > ALTURA - BORDA:
        return 'vermelho'
    xe, ye = gira(x, y) if x > CX else (x, y)        # faixas laterais: as do lado esquerdo
    if xe < X_ECOPONTO[1]:
        if DESCARTE_X[0] <= xe <= DESCARTE_X[1]:
            for y0 in DESCARTE_Y:
                if y0 <= ye <= y0 + DESCARTE_ALT:
                    return 'branco'
        return 'amarelo'
    if xe < X_VERDE[1]:
        return 'verde'
    if xe < X_AZUL[1]:
        return 'azul'
    meia = LINHA / 2
    for v in VERTICAIS:
        if abs(x - v) <= meia:
            return 'preto'
    for h in HORIZONTAIS:
        if abs(y - h) <= meia:
            return 'preto'
    q = QUADRADO / 2
    for p in POSICOES.values():
        dx, dy = abs(x - p['x']), abs(y - p['y'])
        if p['tipo'] == 'marrom' and dx <= q and dy <= q:
            return 'marrom'
        if p['tipo'] == 'cinza' and max(dx, dy) <= q and max(dx, dy) >= q - CONTORNO_CINZA:
            return 'cinza'
    return 'branco'


def area_livre(lado):
    """Retângulo (x0, y0, x1, y1) da área verde de um lado."""
    if lado == 'esq':
        return (X_VERDE[0], BORDA, X_VERDE[1], ALTURA - BORDA)
    return (LARGURA - X_VERDE[1], BORDA, LARGURA - X_VERDE[0], ALTURA - BORDA)


# --------------------------------------------------------------------------- cenário
class Cenario:
    """O que o árbitro põe na pista: plataformas (nos locais de descarte), cubos (nos quadrados)
    e onde cada robô começa (na área verde)."""

    def __init__(self):
        self.nome = 'vazio'
        self.caminho = None
        self.plataformas = {}     # 'P1' -> cor
        self.cubos = {}           # 'A2' -> cor
        self.inicio = {'esq': [380.0, 750.0, 0.0], 'dir': [LARGURA - 380.0, 750.0, 180.0]}

    def para_dict(self):
        return {'formato': 'rcb_challenge_cenario_1', 'nome': self.nome,
                'plataformas': dict(sorted(self.plataformas.items())),
                'cubos': dict(sorted(self.cubos.items())), 'inicio': self.inicio}

    @classmethod
    def de_dict(cls, d):
        c = cls()
        c.nome = d.get('nome', 'cenario')
        c.plataformas = {k: v for k, v in d.get('plataformas', {}).items() if v}
        c.cubos = {k: v for k, v in d.get('cubos', {}).items() if v}
        ini = d.get('inicio')
        if ini:
            c.inicio.update({k: [float(a) for a in v] for k, v in ini.items()})
        return c

    @classmethod
    def carregar(cls, caminho):
        with open(caminho, 'r', encoding='utf-8') as f:
            c = cls.de_dict(json.load(f))
        c.caminho = caminho
        return c

    def salvar(self, caminho):
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(self.para_dict(), f, ensure_ascii=False, indent=1)
        self.caminho = caminho

    def validar(self):
        """Avisos de coisas que a regra não deixa (o simulador roda mesmo assim)."""
        av = []
        for k in list(self.plataformas) + list(self.cubos):
            if k not in POSICOES:
                av.append(f'posição desconhecida: {k}')
        for lado in ('esq', 'dir'):
            cores = [c for k, c in self.plataformas.items() if POSICOES.get(k, {}).get('lado') == lado]
            if len(cores) != len(set(cores)):
                av.append(f'lado {lado}: duas plataformas da mesma cor')
        plat = {}
        for c in self.plataformas.values():
            plat[c] = plat.get(c, 0) + 1
        for c, n in plat.items():
            if n > 2:
                av.append(f'{n} plataformas {c} (a pista tem 2 de cada cor)')
        usados = {}
        for c in self.cubos.values():
            usados[c] = usados.get(c, 0) + 1
        for c, n in usados.items():
            if n > ESTOQUE_CUBOS.get(c, 0):
                av.append(f'{n} cubos {c} (a pista tem {ESTOQUE_CUBOS.get(c, 0)})')
        for k, c in self.cubos.items():
            p = POSICOES.get(k)
            if p and p['tipo'] == 'descarte':
                av.append(f'cubo em {k}: os locais de descarte são das plataformas')
        for k in self.plataformas:
            p = POSICOES.get(k)
            if p and p['tipo'] != 'descarte':
                av.append(f'plataforma em {k}: plataforma só vai nos locais de descarte (P1-P5)')
        return av


def sorteia(rng=None, n_plataformas=5, pares_coloridos=4, pares_brancos=1, pares_obstaculo=2,
            sem_plataforma=0):
    """Sorteia um cenário dentro da regra e simétrico entre os lados (o mesmo arranjo girado).

    n_plataformas: 1 a 5 por lado, cores distintas (as mesmas nos dois lados)
    pares_coloridos: cubos de cor com plataforma nos quadrados cinza (por lado)
    pares_brancos: cubos brancos nos quadrados cinza (por lado)
    pares_obstaculo: cubos de qualquer cor nos quadrados marrons (por lado)
    sem_plataforma: cubos de cor SEM plataforma (contam como branco) nos quadrados cinza (por lado)
    """
    rng = rng or random.Random()
    c = Cenario()
    c.nome = 'sorteado'
    n_plataformas = max(1, min(5, int(n_plataformas)))
    cores_plat = rng.sample(CORES_PLATAFORMA, n_plataformas)
    vagas = rng.sample(range(5), n_plataformas)
    for cor, k in zip(cores_plat, vagas):
        c.plataformas[f'P{k + 1}'] = cor
        c.plataformas[f"P{k + 1}'"] = cor
    estoque = dict(ESTOQUE_CUBOS)

    def tira(cores):
        ok = [x for x in cores if estoque[x] >= 2]
        if not ok:
            return None
        x = rng.choice(ok)
        estoque[x] -= 2
        return x

    cinza = [k for k, p in POSICOES.items() if p['tipo'] == 'cinza' and p['lado'] == 'esq']
    marrom = [k for k, p in POSICOES.items() if p['tipo'] == 'marrom' and p['lado'] == 'esq']
    rng.shuffle(cinza)
    rng.shuffle(marrom)
    sem = [x for x in CORES_PLATAFORMA if x not in cores_plat]
    pedidos = ([cores_plat] * pares_coloridos + [['branco']] * pares_brancos
               + [sem or ['branco']] * sem_plataforma)
    for cores in pedidos:
        if not cinza:
            break
        cor = tira(cores)
        if cor is None:
            continue
        k = cinza.pop()
        c.cubos[k] = cor
        c.cubos[par(k)] = cor
    for _ in range(pares_obstaculo):
        if not marrom:
            break
        cor = tira(CORES_CUBO)
        if cor is None:
            continue
        k = marrom.pop()
        c.cubos[k] = cor
        c.cubos[par(k)] = cor
    # robô em algum lugar da área verde (o árbitro escolhe; aqui, a altura sorteada)
    y = rng.choice([450.0, 600.0, 750.0, 900.0, 1050.0])
    ang = rng.choice([0.0, 90.0, -90.0])
    c.inicio = {'esq': [380.0, y, ang], 'dir': [LARGURA - 380.0, ALTURA - y, ang + 180.0]}
    return c


def nome_perto(x, y, raio=40.0, tipos=('cinza', 'marrom', 'descarte')):
    """Posição nomeada mais perto do ponto (para o editor), ou None."""
    melhor, dmin = None, math.inf
    for k, p in POSICOES.items():
        if p['tipo'] not in tipos:
            continue
        dx, dy = abs(x - p['x']), abs(y - p['y'])
        if p['tipo'] == 'descarte':
            dentro = dx <= 40 and dy <= DESCARTE_ALT / 2 + 10   # o retângulo é comprido em y
        else:
            dentro = math.hypot(dx, dy) <= raio
        if dentro and math.hypot(dx, dy) < dmin:
            melhor, dmin = k, math.hypot(dx, dy)
    return melhor
