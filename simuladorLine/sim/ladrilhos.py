"""Catálogo de ladrilhos da Rescue Line.

Os ladrilhos vêm do rcj-rescue-cms (o sistema oficial do rcj.cloud, licença MIT) e foram
convertidos por ferramentas/importa_ladrilhos.py para 300x300 px (1 mm por pixel) com só
quatro cores: branco, preto, verde e vermelho. A imagem é o que os sensores "enxergam".

Alguns ladrilhos são gerados aqui (branco, gangorra e chegada).

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


def gira_dir(d, rot):
    """Direção d de um ladrilho girado rot graus no sentido horário."""
    if not d:
        return d
    return DIRS[(DIRS.index(d) + int(rot) // 90) % 4]


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
    def __init__(self, pasta=PASTA):
        self.pasta = pasta
        self.tipos = {}
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

    def nomes(self):
        """Ordem da paleta do editor: gerados primeiro, depois os do CMS."""
        return list(GERADOS) + [n for n in self.tipos if n not in GERADOS and not self.tipos[n].get('dinamico')]

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
        return self.tipos[nome]

    def material(self, nome):
        """Matriz uint8 300x300 de materiais, orientação da imagem (linha 0 = norte)."""
        a = self._mat.get(nome)
        if a is None:
            t = self.tipos[nome]
            if 'gerador' in t:
                a = t['gerador']()
            else:
                a = self._le_png(t['imagem'])
            a.setflags(write=False)
            self._mat[nome] = a
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
