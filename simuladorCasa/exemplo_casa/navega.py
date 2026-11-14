"""Navegação: leva o robô de onde ele está até um ponto ou um cômodo do mapa.

Usa a rota do mapa (Mapa.rota) e a pose da localização (Localizador.pose). O robô segue a rota olhando
para onde vai (a câmera e a garra ficam na frente) e usa as rodas mecanum para corrigir de lado sem
ter de virar.

Não desvia de coisas que não estão no mapa (uma cadeira fora do lugar, uma pessoa): se o robô para de
andar, ele recua, refaz a rota e tenta de novo, e desiste depois de algumas tentativas.
"""

import math
import time

from mapa import Mapa

VEL = 60.0                 # velocidade de cruzeiro (-100 a 100)
VEL_APERTADO = 35.0        # com menos de FOLGA_APERTADO até um obstáculo
FOLGA_APERTADO = 320.0     # mm
ANTECIPA = 230.0           # mm: o robô mira um ponto da rota este tanto à frente dele
VIRA_PARADO = 50.0         # graus: erro de rumo acima disso, gira parado antes de andar
TENTATIVAS = 4


def _dif(a, b):
    """a - b em graus, entre -180 e 180."""
    return (a - b + 180.0) % 360.0 - 180.0


class Navegador:
    def __init__(self, robo, mapa, loc):
        self.r = robo
        self.m = mapa
        self.loc = loc
        # ao_andar: função chamada a cada passo da viagem. Se ela devolve algo (um objeto visto no
        # caminho, por exemplo), o robô para, vai_para() devolve False e o que ela devolveu fica em parou_por.
        self.ao_andar = None
        self.parou_por = None

    # ------------------------------------------------------------------ comandos
    def vai_para_comodo(self, nome, **kw):
        """Vai até o cômodo com esse nome no mapa. False se não chegou."""
        p = self.m.lugar(nome)
        if p is None:
            print(f'não conheço o cômodo "{nome}" (conheço: {", ".join(self.m.lugares())})')
            return False
        return self.vai_para(p[0], p[1], **kw)

    def vai_para(self, x, y, tolerancia=70.0, rumo=None):
        """Vai até (x, y) do mapa pela rota mais folgada. rumo (graus): vira para ele ao chegar.
        False se não existe caminho ou se o robô ficou preso."""
        self.parou_por = None
        for tentativa in range(TENTATIVAS):
            px, py, _ = self.loc.pose()
            caminho = self.m.rota((px, py), (x, y))
            if caminho is None:
                print(f'não existe caminho de ({px:.0f}, {py:.0f}) até ({x:.0f}, {y:.0f})')
                self.r.para()
                return False
            res = self._segue(caminho, tolerancia)
            if res == 'chegou':
                if rumo is not None:
                    self.vira_para(rumo)
                return True
            if res == 'parou':
                return False
            print('fiquei preso: recuo e refaço a rota')
            self.r.anda(-120)
        self.r.para()
        return False

    def vira_para(self, rumo, tolerancia=3.0):
        """Gira parado até o rumo (graus no mapa)."""
        t0 = time.time()
        while time.time() - t0 < 10:
            erro = _dif(rumo, self.loc.pose()[2])
            if abs(erro) < tolerancia:
                break
            self.r.move(0, 0, math.copysign(max(12.0, min(35.0, abs(erro) * 0.9)), erro))
        self.r.para()

    # ------------------------------------------------------------------ seguir a rota
    def _segue(self, pts, tolerancia):
        fim = pts[-1]
        # comprimento acumulado de cada ponto da rota
        acum = [0.0]
        for a, b in zip(pts, pts[1:]):
            acum.append(acum[-1] + math.hypot(b[0] - a[0], b[1] - a[1]))
        total = acum[-1]
        s = 0.0                              # até onde o robô já foi na rota (mm)
        t0 = time.time()
        t_marca, marca = t0, self.loc.pose()
        while time.time() - t0 < 30.0 + total / 60.0:
            x, y, rumo = self.loc.pose()
            falta = math.hypot(fim[0] - x, fim[1] - y)
            if falta <= tolerancia:
                self.r.para()
                return 'chegou'
            if self.ao_andar is not None:
                motivo = self.ao_andar()
                if motivo:
                    self.parou_por = motivo
                    self.r.para()
                    return 'parou'
            s = self._avanco(pts, acum, x, y, s)
            ax, ay = self._ponto(pts, acum, min(total, s + ANTECIPA))
            dx, dy = ax - x, ay - y
            erro = _dif(math.degrees(math.atan2(dy, dx)), rumo)
            if abs(erro) > VIRA_PARADO:
                self.r.move(0, 0, math.copysign(max(14.0, min(40.0, abs(erro) * 0.8)), erro))
            else:
                v = min(VEL, 14.0 + falta * 0.22)
                if self.m.folga(x, y) < FOLGA_APERTADO:
                    v = min(v, VEL_APERTADO)
                e = math.radians(erro)
                self.r.move(v * math.cos(e), v * math.sin(e), max(-35.0, min(35.0, erro * 1.1)))
            # preso? a cada 3 s confere se saiu do lugar
            if time.time() - t_marca > 3.0:
                if math.hypot(x - marca[0], y - marca[1]) < 25.0 and abs(_dif(rumo, marca[2])) < 8.0:
                    self.r.para()
                    return 'preso'
                t_marca, marca = time.time(), (x, y, rumo)
        self.r.para()
        return 'preso'

    @staticmethod
    def _ponto(pts, acum, s):
        """Ponto da rota a 's' mm do começo dela."""
        for k in range(len(pts) - 1):
            if s <= acum[k + 1]:
                t = (s - acum[k]) / max(1e-6, acum[k + 1] - acum[k])
                return (pts[k][0] + (pts[k + 1][0] - pts[k][0]) * t, pts[k][1] + (pts[k + 1][1] - pts[k][1]) * t)
        return pts[-1]

    @staticmethod
    def _avanco(pts, acum, x, y, s_antes):
        """Até onde o robô já foi na rota: a projeção dele no trecho mais perto, sem voltar atrás nem
        pular para um trecho distante (a rota pode passar duas vezes perto do mesmo lugar)."""
        melhor, d_melhor = s_antes, 1e18
        for k in range(len(pts) - 1):
            if acum[k + 1] < s_antes - 1.0 or acum[k] > s_antes + 600.0:
                continue
            ax, ay = pts[k]
            bx, by = pts[k + 1]
            L2 = (bx - ax) ** 2 + (by - ay) ** 2
            t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((x - ax) * (bx - ax) + (y - ay) * (by - ay)) / L2))
            d = math.hypot(x - (ax + (bx - ax) * t), y - (ay + (by - ay) * t))
            s = acum[k] + math.sqrt(L2) * t
            if s >= s_antes and d < d_melhor:
                melhor, d_melhor = s, d
        return melhor
