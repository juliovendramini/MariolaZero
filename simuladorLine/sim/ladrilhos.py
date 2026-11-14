"""Catálogo de ladrilhos da Rescue Line.

Os ladrilhos vêm do rcj-rescue-cms (o sistema oficial do rcj.cloud, licença MIT) e foram
convertidos por ferramentas/importa_ladrilhos.py para 300x300 px (1 mm por pixel) com só
quatro cores: branco, preto, verde e vermelho. A imagem é o que os sensores "enxergam".

Alguns ladrilhos são gerados aqui (branco, gangorra e chegada).

Ladrilhos próprios (ladrilhos_proprios/proprios.json, 13/11/2026): um bloco de L x A ladrilhos desenhado
numa imagem só (L*300 x A*300 px, 1 mm/px; ferramentas/ladrilho_proprio.py faz a imagem a partir de uma
foto ou de um desenho). Cada peça vira um tipo 'nome@coluna,linha' (0,0 = canto noroeste; bloco 1x1 =
só 'nome'), com caminhos, gaps, interseções e, opcional, o ponto da linha onde o robô começa/volta
(ponto = [u, v] em mm a partir do canto noroeste da peça, rumo = direção para onde ele fica virado).
O editor põe o bloco inteiro de uma vez (pecas_bloco()).

Direções: N (cima), L (direita), S (baixo), O (esquerda). Rotação em graus no sentido
horário (igual ao editor oficial): girando 90°, o que era N vai para L.
"""

import json
import os

import numpy as np

TAM = 300                  # mm (e px) por ladrilho
LARGURA_LINHA = 18         # mm, para os ladrilhos gerados aqui

MATERIAIS = ['branco', 'preto', 'verde', 'vermelho', 'prata', 'madeira', 'fora']
M_BRANCO, M_PRETO, M_VERDE, M_VERMELHO, M_PRATA, M_MADEIRA, M_FORA = range(7)
COR_MATERIAL = {
    M_BRANCO: (246, 246, 242), M_PRETO: (22, 22, 22), M_VERDE: (0, 166, 81),
    M_VERMELHO: (200, 20, 20), M_PRATA: (180, 186, 196), M_MADEIRA: (190, 150, 95),
    M_FORA: (120, 120, 120),
}

DIRS = ['N', 'L', 'S', 'O']
OPOSTA = {'N': 'S', 'S': 'N', 'L': 'O', 'O': 'L'}
DO_CMS = {'top': 'N', 'right': 'L', 'bottom': 'S', 'left': 'O'}
PARA_CMS = {v: k for k, v in DO_CMS.items()}
# deslocamento na grade (x para a direita, y para baixo)
PASSO = {'N': (0, -1), 'S': (0, 1), 'L': (1, 0), 'O': (-1, 0)}
# ângulo no mundo (anti-horário a partir do leste, y para cima)
ANGULO = {'L': 0.0, 'N': 90.0, 'O': 180.0, 'S': 270.0}

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PASTA = os.path.join(RAIZ, 'ladrilhos')
PASTA_PROPRIOS = os.path.join(RAIZ, 'ladrilhos_proprios')
ARQ_PROPRIOS = 'proprios.json'


def gira_dir(d, rot):
    """Direção d de um ladrilho girado rot graus no sentido horário."""
    if not d:
        return d
    return DIRS[(DIRS.index(d) + int(rot) // 90) % 4]


def gira_ponto(u, v, rot):
    """Ponto (u, v) da imagem do ladrilho (mm a partir do canto noroeste, v para baixo) depois de girar o
    ladrilho rot graus no sentido horário."""
    for _ in range((int(rot) % 360) // 90):
        u, v = TAM - v, u
    return u, v


def _dir(d):
    """Direção no formato do simulador (N/L/S/O) ou do sistema oficial (top/right/bottom/left)."""
    d = DO_CMS.get(d, d)
    if d not in DIRS:
        raise ValueError(f'direção desconhecida: {d!r} (use N, L, S, O)')
    return d


def nome_peca(bloco, c, l, larg=1, alt=1):
    return bloco if larg == 1 and alt == 1 else f'{bloco}@{c},{l}'


def pos_peca(c, l, larg, alt, rot):
    """Coluna/linha da peça (c, l) de um bloco larg x alt depois de girar o bloco rot graus (horário)."""
    for _ in range((int(rot) % 360) // 90):
        c, l, larg, alt = alt - 1 - l, c, alt, larg
    return c, l


def _ladrilho_vazio():
    return np.full((TAM, TAM), M_BRANCO, np.uint8)


def _faixa(a, x0, y0, x1, y1, mat):
    """Retângulo [x0,x1) x [y0,y1) em pixels (linha 0 = topo)."""
    a[max(0, int(y0)):int(y1), max(0, int(x0)):int(x1)] = mat


def _gera_branco():
    return _ladrilho_vazio()


def _gera_reta():
    a = _ladrilho_vazio()
    m = TAM // 2
    _faixa(a, 0, m - LARGURA_LINHA / 2, TAM, m + LARGURA_LINHA / 2, M_PRETO)
    return a


def _gera_chegada():
    """Linha chegando por baixo e fita vermelha 25 x 300 mm no meio, perpendicular à linha."""
    a = _ladrilho_vazio()
    m = TAM // 2
    _faixa(a, m - LARGURA_LINHA / 2, m, m + LARGURA_LINHA / 2, TAM, M_PRETO)
    _faixa(a, 0, m - 12.5, TAM, m + 12.5, M_VERMELHO)
    return a


GERADOS = {
    'branco': {'gerador': _gera_branco, 'caminhos': {}, 'gaps': 0, 'intersecoes': 0,
               'descricao': 'ladrilho sem linha'},
    'gangorra': {'gerador': _gera_reta, 'caminhos': {'O': 'L', 'L': 'O'}, 'gaps': 0, 'intersecoes': 0,
                 'gangorra': True, 'descricao': 'gangorra (linha reta, gira no meio do ladrilho)'},
    'chegada': {'gerador': _gera_chegada, 'caminhos': {'S': 'N'}, 'gaps': 0, 'intersecoes': 0,
                'chegada': True, 'descricao': 'ladrilho de chegada (fita vermelha)'},
}


class Catalogo:
    def __init__(self, pasta=PASTA, pasta_proprios=PASTA_PROPRIOS):
        self.pasta = pasta
        self.pasta_proprios = pasta_proprios
        self.tipos = {}
        self.blocos = {}             # ladrilhos próprios: nome -> {'imagem', 'larg', 'alt', 'descricao', 'pecas'}
        self._img_bloco = {}
        with open(os.path.join(pasta, 'ladrilhos.json'), encoding='utf-8') as f:
            dados = json.load(f)
        for nome, t in dados['ladrilhos'].items():
            self.tipos[nome] = {
                'imagem': os.path.join(pasta, t['imagem']),
                'caminhos': {DO_CMS[k]: DO_CMS[v] for k, v in t['caminhos'].items() if v},
                'gaps': int(t.get('gaps', 0)),
                'intersecoes': int(t.get('intersecoes', 0)),
                'id_cms': t.get('id_cms'),
            }
        for nome, t in GERADOS.items():
            self.tipos[nome] = dict(t)
        self._mat = {}
        self._rot = {}
        self.por_id_cms = {t['id_cms']: n for n, t in self.tipos.items() if t.get('id_cms')}
        self.por_imagem_cms = {os.path.basename(t['imagem']): n for n, t in self.tipos.items() if t.get('imagem')}
        self.carrega_proprios()

    def carrega_proprios(self):
        """Lê ladrilhos_proprios/proprios.json (se existir) e registra cada peça de cada bloco."""
        velhos = [n for n, t in self.tipos.items() if t.get('proprio')] + list(self.blocos)
        for n in velhos:
            self.tipos.pop(n, None)
            self._mat.pop(n, None)
        self._rot.clear()
        self._img_bloco.clear()
        self.blocos = {}
        arq = os.path.join(self.pasta_proprios, ARQ_PROPRIOS)
        if not os.path.exists(arq):
            return
        with open(arq, encoding='utf-8') as f:
            dados = json.load(f)
        for nome, b in dados.get('blocos', {}).items():
            if nome.startswith('_'):
                continue
            if nome in self.tipos:
                raise ValueError(f'{ARQ_PROPRIOS}: o bloco {nome!r} tem o nome de um ladrilho oficial')
            larg, alt = int(b.get('largura', 1)), int(b.get('altura', 1))
            pecas = {}
            for c in range(larg):
                for l in range(alt):
                    p = b.get('pecas', {}).get(f'{c},{l}', {})
                    pn = nome_peca(nome, c, l, larg, alt)
                    info = {
                        'proprio': True, 'bloco': nome, 'peca': (c, l),
                        'caminhos': {_dir(e): _dir(s) for e, s in p.get('caminhos', {}).items() if s},
                        'gaps': int(p.get('gaps', 0)), 'intersecoes': int(p.get('intersecoes', 0)),
                        'descricao': b.get('descricao', 'ladrilho próprio') + (
                            f' (peça {c},{l} de {larg}x{alt})' if larg * alt > 1 else ''),
                    }
                    if p.get('ponto'):
                        info['ponto'] = [float(p['ponto'][0]), float(p['ponto'][1])]
                    if p.get('rumo'):
                        info['rumo'] = _dir(p['rumo'])
                    self.tipos[pn] = info
                    pecas[(c, l)] = pn
            self.blocos[nome] = {'imagem': os.path.join(self.pasta_proprios, b['imagem']), 'larg': larg,
                                 'alt': alt, 'descricao': b.get('descricao', ''), 'pecas': pecas}

    def nomes(self):
        """Todos os tipos que um ladrilho do mapa pode ter: gerados, os do CMS e as peças dos próprios."""
        return list(GERADOS) + [n for n in self.tipos if n not in GERADOS and not self.tipos[n].get('dinamico')]

    def nomes_paleta(self):
        """Paleta do editor: gerados, os do CMS e cada bloco próprio uma vez (pelo nome do bloco)."""
        return [n for n in self.nomes() if not self.tipos[n].get('proprio')] + list(self.blocos)

    def eh_bloco(self, nome):
        return nome in self.blocos and nome not in self.tipos

    def pecas_bloco(self, bloco, rot=0):
        """[(dx, dy, tipo da peça)] para pôr o bloco girado rot graus com o canto noroeste em (0, 0)."""
        b = self.blocos[bloco]
        return [(*pos_peca(c, l, b['larg'], b['alt'], rot), pn) for (c, l), pn in sorted(b['pecas'].items())]

    def registra(self, nome, material, caminhos=None, **info):
        """Ladrilho criado pelo programa (ex.: piso da área de resgate com as fitas)."""
        a = np.ascontiguousarray(material, dtype=np.uint8)
        a.setflags(write=False)
        self.tipos[nome] = dict({'caminhos': caminhos or {}, 'gaps': 0, 'intersecoes': 0, 'dinamico': True},
                                **info)
        self._mat[nome] = a
        for k in [k for k in self._rot if k[0] == nome]:
            del self._rot[k]

    def existe(self, nome):
        return nome in self.tipos

    def info(self, nome):
        if nome not in self.tipos and nome in self.blocos:
            b = self.blocos[nome]
            return {'caminhos': {}, 'bloco': nome, 'descricao': f"{b['descricao'] or 'ladrilho próprio'} "
                                                                f"({b['larg']}x{b['alt']} ladrilhos)"}
        return self.tipos[nome]

    def material(self, nome):
        """Matriz uint8 300x300 de materiais, orientação da imagem (linha 0 = norte). Para um bloco próprio
        (pelo nome do bloco), a imagem do bloco inteiro."""
        a = self._mat.get(nome)
        if a is None:
            t = self.tipos.get(nome)
            if t is None:                              # bloco inteiro (paleta)
                a = self._material_bloco(nome).copy()
            elif 'gerador' in t:
                a = t['gerador']()
            elif t.get('proprio'):
                c, l = t['peca']
                a = self._material_bloco(t['bloco'])[l * TAM:(l + 1) * TAM, c * TAM:(c + 1) * TAM].copy()
            else:
                a = self._le_png(t['imagem'])
            a.setflags(write=False)
            self._mat[nome] = a
        return a

    def _material_bloco(self, bloco):
        a = self._img_bloco.get(bloco)
        if a is None:
            b = self.blocos[bloco]
            a = self._le_png(b['imagem'])
            if a.shape != (b['alt'] * TAM, b['larg'] * TAM):
                raise ValueError(f"{b['imagem']}: a imagem tem {a.shape[1]}x{a.shape[0]} px; o bloco "
                                 f"{b['larg']}x{b['alt']} pede {b['larg'] * TAM}x{b['alt'] * TAM}")
            self._img_bloco[bloco] = a
        return a

    @staticmethod
    def _le_png(caminho):
        import pygame
        sup = pygame.image.load(caminho)
        rgb = pygame.surfarray.array3d(sup).transpose(1, 0, 2).astype(np.int16)
        a = np.full(rgb.shape[:2], M_BRANCO, np.uint8)
        lum = rgb.mean(-1)
        croma = rgb.max(-1) - rgb.min(-1)
        a[lum < 128] = M_PRETO
        verde = (croma > 70) & (rgb[:, :, 1] > rgb[:, :, 0])
        a[verde] = M_VERDE
        a[(croma > 70) & ~verde] = M_VERMELHO
        # prata (só nos ladrilhos próprios): a cor exata do COR_MATERIAL
        a[(np.abs(rgb - np.array(COR_MATERIAL[M_PRATA])).max(-1) <= 6)] = M_PRATA
        return a

    def material_girado(self, nome, rot):
        """Materiais já girados para a orientação do mapa (linha 0 = norte do mundo)."""
        k = (nome, int(rot) % 360)
        a = self._rot.get(k)
        if a is None:
            a = np.ascontiguousarray(np.rot90(self.material(nome), -(int(rot) % 360) // 90))
            a.setflags(write=False)
            self._rot[k] = a
        return a

    def caminhos(self, nome, rot=0):
        """{entrada: saída} já girados."""
        return {gira_dir(e, rot): gira_dir(s, rot) for e, s in self.tipos[nome]['caminhos'].items()}

    def rgb(self, nome, rot=0):
        """Imagem RGB (altura, largura, 3) girada, para desenhar."""
        a = self.material_girado(nome, rot)
        lut = np.zeros((256, 3), np.uint8)
        for k, c in COR_MATERIAL.items():
            lut[k] = c
        return lut[a]


_catalogo = None


def catalogo():
    global _catalogo
    if _catalogo is None:
        _catalogo = Catalogo()
    return _catalogo
