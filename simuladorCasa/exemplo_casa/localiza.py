"""Localização do robô na casa: onde ele está no mapa, sabendo de onde saiu.

Um filtro de partículas (localização de Monte Carlo). Cada partícula é um palpite de onde o robô
está: (x, y) no mapa e a diferença entre o rumo de verdade e o que o giroscópio diz.

* Quando o robô anda, cada palpite anda junto pela odometria (os 4 encoders das rodas mecanum dão o
  quanto ele foi para a frente e para o lado; o giroscópio dá o rumo), com um pouco de sorteio, porque
  roda patina e giroscópio deriva.
* Quando os VL53 medem, cada palpite é comparado com o mapa: "se eu estivesse aqui, o sensor da
  esquerda leria 430 mm; ele leu 425". Palpite que combina ganha peso; os que não combinam somem.
  Leitura "nada à vista" também conta: perto de uma parede ela não aconteceria.
* A pose do robô é a média dos palpites; o quanto eles estão espalhados é a incerteza.

Os VL53 alcançam 1,2 m. No meio de um cômodo grande nenhum deles vê nada e a posição segue só pela
odometria (a incerteza cresce); passando perto de uma parede ou de uma porta ela é corrigida.

O que este filtro NÃO faz: descobrir onde está sem saber de onde saiu (o robô "sequestrado"). Ele
acompanha a posição a partir de uma pose inicial conhecida (o "inicio" do mapa: a base do robô).

Uso:
    mapa = Mapa()
    r = Robo()
    loc = Localizador(r, mapa)        # começa no "inicio" do mapa
    ...                               # todo r.move() e toda leitura dos VL53 atualizam o filtro
    x, y, rumo = loc.pose()
"""

import math
import time

import numpy as np

from robo import ALCANCE_VL53, EFICIENCIA_LATERAL, VL53_POSE

try:
    import simdebug                    # no simulador: desenha na janela onde o programa acha que está
except ImportError:                    # no robô, sem o simdebug.py de robo_real/
    simdebug = None

LEQUE = np.radians([-8.0, 0.0, 8.0])   # o feixe do VL53 é um cone de 25°: três raios dentro dele


class Localizador:
    N = 300                    # palpites
    PERIODO_VL53 = 0.15        # s entre duas medidas dos VL53 pedidas pelo próprio filtro
    # odometria: a variância do erro cresce com o que o robô andou (mm² por mm andado)
    RUIDO_FRENTE = 1.5         # 1 m para a frente: desvio de ~39 mm
    RUIDO_LADO = 6.0           # 1 m de lado: ~77 mm (a mecanum patina mais de lado)
    RUIDO_RUMO_PASSO = 0.03    # graus por atualização (deriva do giroscópio)
    RUIDO_RUMO_GIRO = 0.002    # graus² por grau girado (uma volta: ~0,85°)
    # VL53
    SIGMA_MM, SIGMA_PROP = 35.0, 0.03      # desvio aceito entre a leitura e o mapa: 35 mm + 3%
    PISO_CURTO = 0.12          # leitura mais curta que o mapa: algo fora do mapa na frente (comum)
    PISO_LONGO = 0.04          # leitura mais longa que o mapa: "ver através da parede" (raro)
    CONFIANCA = 0.6            # < 1: as medidas seguidas não são independentes

    def __init__(self, robo, mapa, pose=None, semente=1, usa_vl53=True, incerteza=(30.0, 2.0)):
        """pose = (x, y, rumo em graus) no mapa; sem ela vale o "inicio" do mapa.
        incerteza = (mm, graus) do quanto essa pose pode estar errada.
        usa_vl53=False: só odometria e giroscópio (para comparar)."""
        self.r = robo
        self.m = mapa
        self.usa_vl53 = usa_vl53
        self.rng = np.random.default_rng(semente)
        x, y, a = pose if pose is not None else mapa.inicio
        self.gz = robo.z()
        n = self.N
        self.x = x + self.rng.normal(0, incerteza[0], n)
        self.y = y + self.rng.normal(0, incerteza[0], n)
        self.off = (a - self.gz) + self.rng.normal(0, incerteza[1], n)     # rumo = giroscópio + off
        self.w = np.full(n, 1.0 / n)
        self.ultimas_rodas = robo.rodas()
        self.andou = 0.0
        self.girou = 0.0
        self.t_vl53 = 0.0
        self.medidas = 0
        self.percurso = 0.0              # mm andados desde o começo
        self.combina = 1.0               # 0 a 1: o quanto as últimas leituras combinam com o mapa
        self._n_mostra = 0
        robo.loc = self

    # ------------------------------------------------------------------ o robô andou
    def _odometria(self):
        rodas = self.r.rodas()
        gz = self.r.z()
        d = [b - a for a, b in zip(self.ultimas_rodas, rodas)]
        self.ultimas_rodas = rodas
        if max(abs(v) for v in d) > 400.0:
            d = [0.0, 0.0, 0.0, 0.0]         # uma placa não respondeu (a lib devolve 0): passo perdido
        fe, fd, te, td = d
        frente = (fe + fd + te + td) / 4.0
        lado = (-fe + fd + te - td) / 4.0 * EFICIENCIA_LATERAL
        dg = gz - self.gz
        self.gz = gz
        if frente == 0.0 and lado == 0.0 and dg == 0.0:
            return
        n = self.N
        rumo = np.radians(gz - dg / 2.0 + self.off)          # rumo no meio do passo
        f = frente + self.rng.normal(0, math.sqrt(self.RUIDO_FRENTE * abs(frente) + 0.2 * abs(lado)), n)
        la = lado + self.rng.normal(0, math.sqrt(self.RUIDO_LADO * abs(lado) + 0.2 * abs(frente)), n)
        c, s = np.cos(rumo), np.sin(rumo)
        self.x += f * c - la * s
        self.y += f * s + la * c
        self.off += self.rng.normal(0, math.sqrt(self.RUIDO_RUMO_PASSO ** 2 + self.RUIDO_RUMO_GIRO * abs(dg)), n)
        passo = math.hypot(frente, lado)
        self.andou += passo
        self.percurso += passo
        self.girou += abs(dg)

    # ------------------------------------------------------------------ os VL53 mediram
    def mede(self, dist):
        """dist = {'frente': mm, ...} (8190 = nada à vista). Chamado pelo Robo.distancias()."""
        self._odometria()
        self.t_vl53 = time.time()
        if not self.usa_vl53:
            return
        if self.medidas and self.andou < 15.0 and self.girou < 1.5:
            return                 # parado: a mesma medida repetida não é informação nova
        self.andou = self.girou = 0.0
        self.medidas += 1
        rumo = np.radians(self.gz + self.off)
        c, s = np.cos(rumo), np.sin(rumo)
        logw = np.zeros(self.N)
        for nome, (sx, sy, sa) in VL53_POSE.items():
            z = dist.get(nome)
            if z is None:
                continue
            ox = self.x + sx * c - sy * s
            oy = self.y + sx * s + sy * c
            a = rumo + math.radians(sa)
            esperado = self.m.raios(ox[:, None], oy[:, None], a[:, None] + LEQUE[None, :], ALCANCE_VL53 + 100.0)
            if z < ALCANCE_VL53:
                z = max(0.0, float(z))
                sig = self.SIGMA_MM + self.SIGMA_PROP * z
                p = np.exp(-0.5 * ((z - esperado) / sig) ** 2).max(axis=1)        # inf -> 0
                piso = np.where(z < esperado.min(axis=1), self.PISO_CURTO, self.PISO_LONGO)
                p = piso + (1.0 - piso) * p
            else:
                # nada à vista: combina com palpite que não tem nada na frente do sensor
                meio = esperado[:, 1]
                p = np.where(meio > ALCANCE_VL53 * 0.92, 1.0, np.where(meio > 700.0, 0.5, 0.2))
            logw += np.log(p)
        v = np.exp(self.CONFIANCA * logw)
        # o quanto o conjunto dos palpites combina com as leituras (média, com memória)
        self.combina = 0.9 * self.combina + 0.1 * float(np.sum(self.w * np.exp(logw / len(VL53_POSE))))
        self.w *= v
        soma = self.w.sum()
        if soma <= 0.0 or not np.isfinite(soma):
            self.w[:] = 1.0 / self.N
        else:
            self.w /= soma
        if 1.0 / np.sum(self.w ** 2) < self.N / 2.0:
            self._reamostra()

    def _reamostra(self):
        """Sorteia de novo os palpites pelo peso (os bons se repetem, os ruins somem)."""
        n = self.N
        pos = (self.rng.random() + np.arange(n)) / n
        idx = np.minimum(np.searchsorted(np.cumsum(self.w), pos), n - 1)
        self.x = self.x[idx] + self.rng.normal(0, 3.0, n)
        self.y = self.y[idx] + self.rng.normal(0, 3.0, n)
        self.off = self.off[idx] + self.rng.normal(0, 0.05, n)
        self.w = np.full(n, 1.0 / n)

    # ------------------------------------------------------------------ chamado a cada Robo.move()
    def passo(self):
        if self.usa_vl53 and time.time() - self.t_vl53 >= self.PERIODO_VL53:
            self.r.distancias()            # mede e chama o mede() aqui de cima
        else:
            self._odometria()
        self._n_mostra += 1
        if simdebug is not None and self._n_mostra % 3 == 0:
            self.mostra()

    # ------------------------------------------------------------------ resultado
    def pose(self):
        """(x, y, rumo em graus) no mapa: a média dos palpites."""
        x = float(np.sum(self.w * self.x))
        y = float(np.sum(self.w * self.y))
        a = np.radians(self.gz + self.off)
        rumo = math.degrees(math.atan2(float(np.sum(self.w * np.sin(a))), float(np.sum(self.w * np.cos(a)))))
        return x, y, rumo

    def incerteza(self):
        """(mm, graus): o quanto os palpites estão espalhados (desvio padrão)."""
        x = float(np.sum(self.w * self.x))
        y = float(np.sum(self.w * self.y))
        o = float(np.sum(self.w * self.off))
        mm = math.sqrt(float(np.sum(self.w * ((self.x - x) ** 2 + (self.y - y) ** 2))))
        graus = math.sqrt(float(np.sum(self.w * (self.off - o) ** 2)))
        return mm, graus

    def comodo(self):
        x, y, _ = self.pose()
        return self.m.comodo(x, y)

    def mostra(self):
        """No simulador: desenha na janela a pose estimada (o simulador mede o erro dela)."""
        if simdebug is None:
            return
        x, y, a = self.pose()
        x0, y0, a0 = self.m.inicio          # o simdebug quer a pose no referencial do início
        c, s = math.cos(math.radians(a0)), math.sin(math.radians(a0))
        dx, dy = x - x0, y - y0
        simdebug.pose(dx * c + dy * s, -dx * s + dy * c, a - a0)
        if self._n_mostra % 15 == 0:
            mm, graus = self.incerteza()
            simdebug.texto(f'{self.m.comodo(x, y)}: x {x:.0f} y {y:.0f} rumo {a % 360:.0f}°\n'
                           f'incerteza {mm:.0f} mm, {graus:.1f}°   leituras x mapa {self.combina * 100:.0f}%')
