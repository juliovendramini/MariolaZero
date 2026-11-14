"""O mapa da casa que o robô carrega: a mesma planta em JSON do simulador (casas/*.json).

Com ele o robô sabe três coisas:

* o que os VL53 deveriam ler num lugar e num rumo (raios(), para a localização);
* por onde dá para passar (rota(), um A* numa grade com folga das paredes e dos móveis);
* o nome do cômodo de um ponto e o ponto de um cômodo (comodo(), lugar()).

Tudo em mm, origem no canto de baixo à esquerda da planta, x para a direita, y para cima, ângulos em
graus no sentido anti-horário a partir do x (os mesmos do arquivo da casa).

Roda igual no robô e no simulador: só usa numpy e OpenCV. O arquivo vem da variável de ambiente
CASA_MAPA (o simulador põe nela a casa que está aberta) ou de casa.json ao lado do programa.
"""

import heapq
import json
import math
import os
import unicodedata

import cv2
import numpy as np

CEL = 25.0                 # mm por célula da grade fina (raios e folga)
FATOR_ROTA = 2             # a grade das rotas tem células de CEL * FATOR_ROTA
ALTURA_VL53 = 45.0         # os VL53 ficam de 19 a 44 mm do chão: veem o que começa abaixo disso
ALTURA_ROBO = 255.0        # o robô não passa por baixo de nada mais baixo que isso
RAIO_ROBO = 200.0          # folga mínima do centro do robô até um obstáculo numa rota
CONFORTO = 450.0           # a rota prefere ficar a pelo menos isso dos obstáculos


def arquivo_padrao():
    """O mapa a usar: CASA_MAPA, casa.json ao lado do programa ou a planta do Julio."""
    aqui = os.path.dirname(os.path.abspath(__file__))
    for c in (os.environ.get('CASA_MAPA'), os.path.join(aqui, 'casa.json'),
              os.path.join(aqui, '..', 'casas', 'casa_julio.json')):
        if c and os.path.exists(c):
            return c
    raise FileNotFoundError('não achei o mapa da casa (CASA_MAPA ou casa.json ao lado do programa)')


def _sem_acento(s):
    return ''.join(c for c in unicodedata.normalize('NFD', str(s).lower()) if unicodedata.category(c) != 'Mn').strip()


class Mapa:
    def __init__(self, caminho=None, com_caixa=True):
        caminho = caminho or arquivo_padrao()
        with open(caminho, 'r', encoding='utf-8') as f:
            d = json.load(f)
        self.caminho = os.path.abspath(caminho)
        self.nome = d.get('nome', os.path.splitext(os.path.basename(caminho))[0])
        self.largura = float(d['largura'])
        self.altura = float(d['altura'])
        self.inicio = tuple(float(v) for v in d.get('inicio', [500, 500, 0]))
        self.caixa = d.get('caixa')
        self.pisos = [p for p in d.get('pisos', []) if p.get('nome')]
        self.rotulos = list(d.get('rotulos', []))

        pa = {'esp': 100.0, 'alt': 2500.0}
        pa.update(d.get('parede', {}))
        e = float(pa['esp'])
        borda = e + 200.0
        self.x0 = self.y0 = -borda
        self.nx = int(math.ceil((self.largura + 2 * borda) / CEL / FATOR_ROTA)) * FATOR_ROTA
        self.ny = int(math.ceil((self.altura + 2 * borda) / CEL / FATOR_ROTA)) * FATOR_ROTA

        # sólidos: (cx, cy, ângulo em rad, sx, sy, z de baixo, z de cima), como no sim/casa.py
        sol = []
        L, A = self.largura, self.altura
        if pa.get('externas', True):
            for r in ([-e, -e, L + e, 0], [-e, A, L + e, A + e], [-e, 0, 0, A], [L, 0, L + e, A]):
                sol.append(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, 0.0, r[2] - r[0], r[3] - r[1], 0.0, float(pa['alt'])))
        for p in d.get('paredes', []):
            alt = float(p.get('alt', pa['alt']))
            if 'ret' in p:
                r = p['ret']
                sol.append(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, 0.0, r[2] - r[0], r[3] - r[1], 0.0, alt))
            else:
                (xa, ya), (xb, yb) = p['de'], p['ate']
                esp = float(p.get('esp', 20.0))
                sol.append(((xa + xb) / 2, (ya + yb) / 2, math.atan2(yb - ya, xb - xa),
                            math.hypot(xb - xa, yb - ya) + esp, esp, 0.0, alt))
        for m in d.get('moveis', []):
            r = m['ret']
            base = float(m.get('base', 0))
            sol.append(((r[0] + r[2]) / 2, (r[1] + r[3]) / 2, math.radians(float(m.get('ang', 0))),
                        r[2] - r[0], r[3] - r[1], base, base + float(m['alt'])))
        if self.caixa and com_caixa:
            c = self.caixa
            sol.append((float(c['x']), float(c['y']), math.radians(float(c.get('ang', 0))),
                        float(c['tam'][0]), float(c['tam'][1]), 0.0, float(c.get('alt', 100))))

        self.vista = np.zeros((self.ny, self.nx), np.uint8)       # o que os VL53 veem
        ocupada = np.zeros((self.ny, self.nx), np.uint8)          # onde o robô não passa
        for (cx, cy, ang, sx, sy, z0, z1) in sol:
            ca, sa = math.cos(ang), math.sin(ang)
            pts = np.array([[(cx + lx * ca - ly * sa - self.x0) / CEL - 0.5, (cy + lx * sa + ly * ca - self.y0) / CEL - 0.5]
                            for lx, ly in ((sx / 2, sy / 2), (-sx / 2, sy / 2), (-sx / 2, -sy / 2), (sx / 2, -sy / 2))])
            pts = np.round(pts).astype(np.int32)
            if z0 <= ALTURA_VL53 <= z1:
                cv2.fillPoly(self.vista, [pts], 1)
            if z0 < ALTURA_ROBO:
                cv2.fillPoly(ocupada, [pts], 1)
        ocupada[0, :] = ocupada[-1, :] = ocupada[:, 0] = ocupada[:, -1] = 1
        self._ocupada = ocupada
        self.obstaculos = []                 # coisas no chão que não estão na planta: [(x, y, raio)]
        self._calcula_folga()
        self.folga_planta = self.folga_mm    # só a planta, sem os obstáculos de agora

    def _calcula_folga(self):
        """folga: distância (mm) de cada célula até o obstáculo mais perto (planta + obstáculos)."""
        ocupada = self._ocupada
        if self.obstaculos:
            ocupada = ocupada.copy()
            for (x, y, raio) in self.obstaculos:
                c = (int(round((x - self.x0) / CEL - 0.5)), int(round((y - self.y0) / CEL - 0.5)))
                cv2.circle(ocupada, c, max(1, int(round(raio / CEL))), 1, -1)
        self.folga_mm = cv2.distanceTransform((ocupada == 0).astype(np.uint8), cv2.DIST_L2, 5).astype(np.float32) * CEL
        f = FATOR_ROTA
        self.folga_rota = self.folga_mm.reshape(self.ny // f, f, self.nx // f, f).min(axis=(1, 3))

    def fechado_por_obstaculo(self, de, ate):
        """Não há rota de 'de' até 'ate' por causa dos obstáculos de poe_obstaculos (só pela planta haveria)?"""
        if not self.obstaculos or self.rota(de, ate) is not None:
            return False
        guardados = self.obstaculos
        self.poe_obstaculos([])
        livre = self.rota(de, ate) is not None
        self.poe_obstaculos(guardados)
        return livre

    def poe_obstaculos(self, lista):
        """Coisas no chão que o robô não pode atropelar e que não estão na planta (uma camiseta, um
        brinquedo grande): [(x, y, raio em mm)]. As rotas passam a desviar delas. Lista vazia = só a planta."""
        lista = [tuple(float(v) for v in o) for o in lista]
        if lista != self.obstaculos:
            self.obstaculos = lista
            self._calcula_folga()

    # ------------------------------------------------------------------ células
    def _celula(self, x, y):
        i = min(self.nx - 1, max(0, int((x - self.x0) / CEL)))
        j = min(self.ny - 1, max(0, int((y - self.y0) / CEL)))
        return i, j

    def folga(self, x, y, so_planta=False):
        """Distância (mm) do ponto até o obstáculo mais perto (parede, móvel ou, sem so_planta, uma das
        coisas grandes do chão postas em poe_obstaculos)."""
        i, j = self._celula(x, y)
        return float((self.folga_planta if so_planta else self.folga_mm)[j, i])

    # ------------------------------------------------------------------ raios (VL53)
    def raios(self, ox, oy, ang, alcance=1300.0):
        """Distância (mm) até a primeira coisa do mapa a partir de (ox, oy) no rumo ang (radianos).
        Aceita vetores do numpy (o resultado tem o formato deles). np.inf = nada até o alcance."""
        ox, oy, ang = np.broadcast_arrays(np.asarray(ox, float), np.asarray(oy, float), np.asarray(ang, float))
        passo = CEL * 0.8
        s = np.arange(passo, alcance + passo, passo, dtype=np.float32)
        ix = ((ox[..., None] - self.x0 + np.cos(ang)[..., None] * s) / CEL).astype(np.int32)
        iy = ((oy[..., None] - self.y0 + np.sin(ang)[..., None] * s) / CEL).astype(np.int32)
        np.clip(ix, 0, self.nx - 1, out=ix)
        np.clip(iy, 0, self.ny - 1, out=iy)
        bate = self.vista[iy, ix] > 0
        k = bate.argmax(axis=-1)
        d = s[k] - passo / 2
        return np.where(bate.any(axis=-1), d, np.inf)

    # ------------------------------------------------------------------ cômodos
    def lugares(self):
        """Nomes dos cômodos do mapa."""
        return [r['nome'] for r in self.rotulos] or [p['nome'] for p in self.pisos]

    def comodo(self, x, y):
        """Nome do cômodo em (x, y): o rótulo mais perto (até 2,5 m) ou o piso."""
        if self.rotulos:
            dist, nome = min((math.hypot(x - r['x'], y - r['y']), r['nome']) for r in self.rotulos)
            if dist < 2500:
                return nome
        for p in self.pisos:
            r = p['ret']
            if r[0] <= x <= r[2] and r[1] <= y <= r[3]:
                return p['nome']
        return 'fora'

    def lugar(self, nome):
        """(x, y) de um ponto livre do cômodo: o mais perto do rótulo (ou do meio do piso) em que o
        robô cabe. None se o cômodo não existe ou o robô não cabe perto dele."""
        alvo = _sem_acento(nome)
        ponto = None
        for r in self.rotulos:
            if _sem_acento(r['nome']) == alvo:
                ponto = (float(r['x']), float(r['y']))
        if ponto is None:
            for p in self.pisos:
                if _sem_acento(p['nome']) == alvo:
                    ponto = ((p['ret'][0] + p['ret'][2]) / 2, (p['ret'][1] + p['ret'][3]) / 2)
        if ponto is None:
            return None
        c = self._livre_perto(ponto, RAIO_ROBO + 80.0, 1500.0)
        return None if c is None else self._centro_rota(*c)

    # ------------------------------------------------------------------ rotas
    def _cel_rota(self, x, y):
        c = CEL * FATOR_ROTA
        ny, nx = self.folga_rota.shape
        return (min(nx - 1, max(0, int((x - self.x0) / c))), min(ny - 1, max(0, int((y - self.y0) / c))))

    def _centro_rota(self, i, j):
        c = CEL * FATOR_ROTA
        return (self.x0 + (i + 0.5) * c, self.y0 + (j + 0.5) * c)

    def _livre_perto(self, p, raio, alcance=700.0):
        """Célula de rota com folga >= raio mais perto do ponto p (até 'alcance' mm), ou None."""
        i, j = self._cel_rota(*p)
        if self.folga_rota[j, i] >= raio:
            return i, j
        c = CEL * FATOR_ROTA
        n = int(alcance / c)
        ny, nx = self.folga_rota.shape
        i0, i1, j0, j1 = max(0, i - n), min(nx, i + n + 1), max(0, j - n), min(ny, j + n + 1)
        jj, ii = np.nonzero(self.folga_rota[j0:j1, i0:i1] >= raio)
        if len(ii) == 0:
            return None
        k = np.argmin((ii + i0 - i) ** 2 + (jj + j0 - j) ** 2)
        return int(ii[k] + i0), int(jj[k] + j0)

    def rota(self, de, ate, raio=RAIO_ROBO, conforto=CONFORTO):
        """Caminho de 'de' = (x, y) até 'ate' = (x, y) desviando de paredes e móveis: lista de pontos
        [(x, y), ...] começando em 'de', ou None se não existe. O centro do robô fica a pelo menos
        'raio' dos obstáculos e, quando dá, a 'conforto'."""
        ini = self._livre_perto(de, raio)
        fim = self._livre_perto(ate, raio)
        if ini is None or fim is None:
            return None
        ny, nx = self.folga_rota.shape
        livre = (self.folga_rota >= raio)
        pen = np.clip((conforto - self.folga_rota) / max(1.0, conforto - raio), 0.0, 1.0) ** 2 * 3.0 + 1.0
        livre_l = livre.ravel().tolist()
        pen_l = pen.ravel().tolist()
        a, b = ini[1] * nx + ini[0], fim[1] * nx + fim[0]
        bi, bj = fim
        R2 = math.sqrt(2.0)
        viz = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0), (1, 1, R2), (1, -1, R2), (-1, 1, R2), (-1, -1, R2))
        g = {a: 0.0}
        pai = {}
        fila = [(0.0, a)]
        fechado = set()
        while fila:
            _, n = heapq.heappop(fila)
            if n in fechado:
                continue
            if n == b:
                break
            fechado.add(n)
            j, i = divmod(n, nx)
            gn = g[n]
            for di, dj, custo in viz:
                i2, j2 = i + di, j + dj
                if not (0 <= i2 < nx and 0 <= j2 < ny):
                    continue
                m = j2 * nx + i2
                if not livre_l[m] or m in fechado:
                    continue
                if di and dj and not (livre_l[j * nx + i2] and livre_l[j2 * nx + i]):
                    continue                       # não corta quina
                gm = gn + custo * pen_l[m]
                if gm < g.get(m, 1e18):
                    g[m] = gm
                    pai[m] = n
                    dx, dy = abs(i2 - bi), abs(j2 - bj)
                    heapq.heappush(fila, (gm + (dx + dy) + (R2 - 2.0) * min(dx, dy), m))
        if b not in pai and a != b:
            return None
        cels = [b]
        while cels[-1] != a:
            cels.append(pai[cels[-1]])
        cels.reverse()
        pts = [self._centro_rota(n % nx, n // nx) for n in cels]
        pts[0] = (float(de[0]), float(de[1])) if self.folga(*de) >= raio * 0.6 else pts[0]
        if self.folga(*ate) >= raio:
            pts.append((float(ate[0]), float(ate[1])))
        return self._encurta(pts, raio)

    def _visivel(self, p, q, folga):
        """O segmento p-q passa todo a pelo menos 'folga' dos obstáculos?"""
        n = max(2, int(math.hypot(q[0] - p[0], q[1] - p[1]) / CEL) + 1)
        xs = np.linspace(p[0], q[0], n)
        ys = np.linspace(p[1], q[1], n)
        ix = np.clip(((xs - self.x0) / CEL).astype(int), 0, self.nx - 1)
        iy = np.clip(((ys - self.y0) / CEL).astype(int), 0, self.ny - 1)
        return bool(self.folga_mm[iy, ix].min() >= folga)

    def _encurta(self, pts, raio):
        """Troca a escadinha das células por poucos trechos retos. Um trecho só vale se passa com
        quase a mesma folga das pontas dele (e nunca a menos de 'raio' dos obstáculos)."""
        if len(pts) <= 2:
            return pts
        folgas = [self.folga(*p) for p in pts]
        res = [pts[0]]
        i = 0
        while i < len(pts) - 1:
            j = len(pts) - 1
            while j > i + 1:
                minimo = max(raio, min(folgas[i], folgas[j], 280.0) - 40.0)
                if self._visivel(pts[i], pts[j], minimo):
                    break
                j = i + max(1, int((j - i) * 0.75))
            res.append(pts[j])
            i = j
        return res

    @staticmethod
    def comprimento(pts):
        return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(pts, pts[1:]))
