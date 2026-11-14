"""A casa: cômodos, paredes, móveis, objetos (prismas coloridos) e a caixa de guardar.

Tudo em mm, com a origem no canto de baixo à esquerda da planta, x para a direita e y para cima
(ângulos anti-horário a partir do x). O arquivo da casa é um JSON (pasta casas/):

    {
     "nome": "casa 1",
     "largura": 4000, "altura": 3000,            tamanho de dentro (as paredes de fora ficam por fora)
     "parede": {"esp": 100, "alt": 2500, "rgb": [235, 232, 222]},     padrão das paredes
     "pisos":   [{"nome": "sala", "cor": "cinza", "ret": [x0, y0, x1, y1], "rgb": [..]}],
     "faixas":  [{"cor": "preto", "ret": [x0, y0, x1, y1]}],          fita no chão
     "paredes": [{"ret": [x0, y0, x1, y1]}],                          paredes de dentro (portas = vãos)
     "moveis":  [{"nome": "sofá", "ret": [x0, y0, x1, y1], "alt": 800, "base": 0, "rgb": [..]}],
     "objetos": [{"cor": "vermelho", "x": 900, "y": 700, "ang": 20, "tam": [40, 40, 60]}],
     "caixa":   {"x": 3500, "y": 400, "ang": 0, "tam": [300, 220], "alt": 100, "esp": 6, "rgb": [..]},
     "inicio":  [600, 600, 0]
    }

* "cor" do piso e das faixas é o que os sensores de linha leem (nomes de cores_piso do robo.json:
  branco, preto, vermelho, azul, verde, amarelo, marrom, cinza). "rgb" é só a aparência (janela e
  câmera); sem ele vale a cor do nome.
* Móvel com "base" > 0 (tampo de mesa) fica no ar: o robô passa por baixo se couber, e os sensores
  só o veem na altura dele. As pernas entram como móveis pequenos.
* "tam" do objeto: [comprimento, largura, altura].
"""

import json
import math
import os

RGB = {
    'branco': (240, 240, 236), 'preto': (25, 25, 28), 'vermelho': (205, 45, 40), 'azul': (40, 85, 190),
    'verde': (45, 150, 70), 'amarelo': (235, 200, 40), 'marrom': (125, 80, 45), 'cinza': (150, 152, 158),
    'laranja': (240, 130, 30), 'roxo': (140, 70, 180), 'rosa': (235, 120, 170), 'ciano': (60, 190, 200),
    'fora': (60, 60, 64),
}
PAREDE_PADRAO = {'esp': 100.0, 'alt': 2500.0, 'rgb': [235, 232, 222]}
TETO = (246, 246, 242)


def rgb_de(nome, padrao=(200, 200, 200)):
    return tuple(RGB.get(nome, padrao))


class Casa:
    def __init__(self):
        self.nome = 'vazia'
        self.caminho = None
        self.largura = 3000.0
        self.altura = 2000.0
        self.parede = dict(PAREDE_PADRAO)
        self.pisos = []
        self.faixas = []
        self.paredes = []
        self.moveis = []
        self.objetos = []
        self.rotulos = []          # nomes dos cômodos de uma planta importada: [{"nome", "x", "y"}]
        self.caixa = None
        self.inicio = {'esq': (500.0, 500.0, 0.0)}

    # ---------------------------------------------------------------- arquivo
    @classmethod
    def de_dict(cls, d):
        c = cls()
        c.nome = d.get('nome', c.nome)
        c.largura = float(d.get('largura', c.largura))
        c.altura = float(d.get('altura', c.altura))
        c.parede = dict(PAREDE_PADRAO, **d.get('parede', {}))
        c.pisos = [dict(p) for p in d.get('pisos', [])]
        c.faixas = [dict(p) for p in d.get('faixas', [])]
        c.paredes = [dict(p) for p in d.get('paredes', [])]
        c.moveis = [dict(p) for p in d.get('moveis', [])]
        c.objetos = [dict(p) for p in d.get('objetos', [])]
        c.rotulos = [dict(p) for p in d.get('rotulos', [])]
        c.caixa = dict(d['caixa']) if d.get('caixa') else None
        ini = d.get('inicio', [500, 500, 0])
        c.inicio = {'esq': (float(ini[0]), float(ini[1]), float(ini[2]))}
        return c

    def para_dict(self):
        x, y, a = self.inicio['esq']
        d = {'nome': self.nome, 'largura': self.largura, 'altura': self.altura, 'parede': self.parede,
             'pisos': self.pisos, 'faixas': self.faixas, 'paredes': self.paredes, 'moveis': self.moveis,
             'objetos': self.objetos, 'rotulos': self.rotulos, 'inicio': [x, y, a]}
        if self.caixa:
            d['caixa'] = self.caixa
        return d

    @classmethod
    def carregar(cls, caminho):
        with open(caminho, 'r', encoding='utf-8') as f:
            c = cls.de_dict(json.load(f))
        c.caminho = os.path.abspath(caminho)
        if c.nome == 'vazia':
            c.nome = os.path.splitext(os.path.basename(caminho))[0]
        return c

    def salvar(self, caminho):
        with open(caminho, 'w', encoding='utf-8') as f:
            json.dump(self.para_dict(), f, ensure_ascii=False, indent=1)
        self.caminho = os.path.abspath(caminho)

    def validar(self):
        avisos = []
        if not self.pisos:
            avisos.append('a casa não tem nenhum piso: os sensores de linha vão ler "fora"')
        x, y, _ = self.inicio['esq']
        if not (0 < x < self.largura and 0 < y < self.altura):
            avisos.append('o início do robô está fora da casa')
        for o in self.objetos:
            if not (0 < o['x'] < self.largura and 0 < o['y'] < self.altura):
                avisos.append(f'objeto {o.get("cor")} fora da casa')
        return avisos

    # ---------------------------------------------------------------- piso
    @staticmethod
    def _no_ret(r, x, y):
        return r[0] <= x <= r[2] and r[1] <= y <= r[3]

    def piso(self, x, y):
        """Nome da cor do piso em (x, y), como os sensores de linha veem."""
        for f in self.faixas:
            if self._no_ret(f['ret'], x, y):
                return f['cor']
        for p in self.pisos:
            if self._no_ret(p['ret'], x, y):
                return p['cor']
        return 'fora'

    def comodo(self, x, y):
        """Nome do cômodo em (x, y): pelo rótulo mais perto (planta importada, até 2,5 m) ou pelo piso."""
        if self.rotulos:
            d, nome = min((math.hypot(x - r['x'], y - r['y']), r['nome']) for r in self.rotulos)
            if d < 2500:
                return nome
        for p in self.pisos:
            if self._no_ret(p['ret'], x, y):
                return p.get('nome', '?')
        return 'fora'

    # ---------------------------------------------------------------- sólidos
    def paredes_caixas(self):
        """Todas as paredes como caixas [(cx, cy, ang, sx, sy, altura, rgb)]: as quatro de fora (a
        menos que "parede.externas" seja false, quando a planta já traz o contorno) e as de dentro.
        Parede de dentro: {"ret": [x0, y0, x1, y1]} ou um segmento {"de": [x, y], "ate": [x, y],
        "esp": 20}; "alt" e "rgb" próprios são opcionais ("tipo": "janela" é só um nome)."""
        pa = self.parede
        e = float(pa['esp'])
        L, A = self.largura, self.altura
        res = []
        if pa.get('externas', True):
            for r in ([-e, -e, L + e, 0], [-e, A, L + e, A + e], [-e, 0, 0, A], [L, 0, L + e, A]):
                res.append(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, 0.0, r[2] - r[0], r[3] - r[1],
                            float(pa['alt']), tuple(pa['rgb'])))
        for p in self.paredes:
            alt = float(p.get('alt', pa['alt']))
            rgb = tuple(p.get('rgb', pa['rgb']))
            if 'ret' in p:
                r = p['ret']
                res.append(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, 0.0, r[2] - r[0], r[3] - r[1], alt, rgb))
            else:
                (x0, y0), (x1, y1) = p['de'], p['ate']
                esp = float(p.get('esp', 20.0))
                comp = math.hypot(x1 - x0, y1 - y0)
                res.append(((x0 + x1) / 2, (y0 + y1) / 2, math.atan2(y1 - y0, x1 - x0), comp + esp, esp, alt, rgb))
        return res

    def caixa_paredes(self):
        """As quatro paredes da caixa como [(cx, cy, ang, sx, sy)] (no mundo)."""
        c = self.caixa
        if not c:
            return []
        w, l = float(c['tam'][0]), float(c['tam'][1])
        e = float(c.get('esp', 6))
        a = math.radians(float(c.get('ang', 0)))
        ca, sa = math.cos(a), math.sin(a)
        res = []
        for (lx, ly, sx, sy) in ((0, l / 2 - e / 2, w, e), (0, -l / 2 + e / 2, w, e),
                                 (w / 2 - e / 2, 0, e, l - 2 * e), (-w / 2 + e / 2, 0, e, l - 2 * e)):
            res.append((c['x'] + lx * ca - ly * sa, c['y'] + lx * sa + ly * ca, a, sx, sy))
        return res

    def dentro_da_caixa(self, x, y, folga=0.0):
        """O ponto está em cima do vão da caixa (por dentro das paredes dela)?"""
        c = self.caixa
        if not c:
            return False
        a = math.radians(float(c.get('ang', 0)))
        dx, dy = x - c['x'], y - c['y']
        lx = dx * math.cos(a) + dy * math.sin(a)
        ly = -dx * math.sin(a) + dy * math.cos(a)
        e = float(c.get('esp', 6))
        return abs(lx) <= c['tam'][0] / 2 - e - folga and abs(ly) <= c['tam'][1] / 2 - e - folga

    def solidos(self):
        """Tudo o que é fixo, para a câmera e a janela: [(cx, cy, ang_rad, sx, sy, z0, z1, rgb, nome)]."""
        res = []
        for (cx, cy, ang, sx, sy, alt, rgb) in self.paredes_caixas():
            res.append((cx, cy, ang, sx, sy, 0.0, alt, rgb, 'parede'))
        for m in self.moveis:
            r = m['ret']
            res.append(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, math.radians(float(m.get('ang', 0))),
                        r[2] - r[0], r[3] - r[1], float(m.get('base', 0)), float(m.get('base', 0)) + float(m['alt']),
                        tuple(m.get('rgb', (160, 120, 80))), m.get('nome', 'móvel')))
        if self.caixa:
            c = self.caixa
            rgb = tuple(c.get('rgb', RGB['roxo']))
            for (cx, cy, a, sx, sy) in self.caixa_paredes():
                res.append((cx, cy, a, sx, sy, 0.0, float(c['alt']), rgb, 'caixa'))
            # fundo da caixa
            res.append((c['x'], c['y'], math.radians(float(c.get('ang', 0))), c['tam'][0], c['tam'][1], 0.0, 2.0,
                        tuple(int(v * 0.7) for v in rgb), 'caixa'))
        return res

    def chao(self):
        """Retângulos do chão para a câmera e a janela, de baixo para cima: [(ret, rgb)]."""
        res = []
        for p in self.pisos:
            res.append((p['ret'], tuple(p.get('rgb', rgb_de(p['cor'])))))
        for f in self.faixas:
            res.append((f['ret'], tuple(f.get('rgb', rgb_de(f['cor'])))))
        return res
