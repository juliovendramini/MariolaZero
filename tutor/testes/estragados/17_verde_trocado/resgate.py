"""Área de resgate do programa de exemplo (ponto de partida, não a solução).

Com câmera e garra (robô 4x4):
  1. entra (a fita prata da entrada já passou embaixo do sensor de linha);
  2. gira procurando vítimas pela câmera; vai até a mais perto, abaixa a garra aberta (a garra
     abaixada tapa a câmera), avança até o VL53 da garra ver a bolinha, fecha, levanta e joga
     na caçamba: vivas no lado esquerdo, a morta no direito;
  3. procura o triângulo verde, chega de frente, vira e encosta de ré (o TCS de trás confirma),
     solta o lado esquerdo; depois o vermelho com o lado direito (a morta só vale depois das
     duas vivas);
  4. sai: segue a parede pela direita até achar um vão; se embaixo tiver fita preta é a saída.

Só com o sensor de linha (robô de esteira): entra e vai direto para o passo 4.

As paredes da área são paralelas/perpendiculares à direção em que o robô entrou: o giroscópio
guarda essa direção e o robô se alinha por ela (triângulos ficam a 45 graus).
"""

import math
import time

try:
    import simdebug
except ImportError:
    simdebug = None

try:
    from visao import Visao
except ImportError:          # robô sem câmera
    Visao = None

PRETO = 50
PRATA_C = 165        # claridade C do TCS: branco ~127, prata ~200 (os LEDs de 5 mm fazem o prata brilhar)
IR_PRATA = (50, 120)  # no prata o IR lê ~80, MENOS que no branco. Fora disso não é prata:
                      # abaixo = tem linha preta embaixo; acima = sensor perto do chão (lombada)


def eh_prata(r, ir=None):
    """Fita prata embaixo do sensor: os 3 TCS muito claros (C acima do branco) e com a cor 'prata',
    e os 4 canais de IR entre 50 e 120.

    A fita prata da entrada é larga (atravessa o vão todo): os 3 TCS ficam em cima dela ao mesmo
    tempo e não há linha preta embaixo. Em cima da lombada o sensor chega perto do chão e o branco
    também fica muito claro no TCS (~200), mas aí a linha preta continua embaixo do sensor (TCS do
    meio e canais do meio escuros). O IR sozinho não serve para achar o prata: ele lê ~80 no
    prata, menos que no branco."""
    ir = ir if ir is not None else r.reflexao()
    if min(ir) < IR_PRATA[0] or max(ir) > IR_PRATA[1]:
        return False
    for k in (1, 2, 3):
        if r.cor.le_rgbc(k)[3] < PRATA_C or r.cor.cor(k) != 'prata':
            return False
    return True


def entrada_da_area(r, ir):
    """Fita prata de verdade: eh_prata() com o robô nivelado (no pé/topo de rampa o sensor chega
    perto do chão e o branco fica mais claro)."""
    return abs(r.inclinacao()) <= 4 and eh_prata(r, ir)


VEL = 32
DIST_PAREDE = 60     # mm do VL53 da direita até a parede seguida
FRENTE_PAREDE = 60   # mm do VL53 da frente: vira no canto (o robô ainda gira sem raspar)
TEMPO_MAXIMO_AREA = 240.0    # s: depois disso desiste das vítimas e procura a saída


def mostra(txt):
    if simdebug:
        simdebug.texto(txt)


def angulo_dif(a, b):
    return (a - b + 180.0) % 360.0 - 180.0


class AreaResgate:
    def __init__(self, r):
        self.r = r
        self.visao = None
        if Visao is not None and r.garra is not None:
            try:
                self.visao = Visao()
            except Exception as e:
                print('Sem câmera:', e)
        self.z_entrada = 0.0
        self.guardadas = {'esq': [], 'dir': []}
        self.vivas_entregues = 0
        self.t0 = 0.0

    # ------------------------------------------------------------------ sensores
    def prata(self, ir=None):
        return eh_prata(self.r, ir)

    def preto_largo(self, ir=None):
        ir = ir or self.r.reflexao()
        return sum(v < PRETO for v in ir) >= 3

    def vl(self, nome):
        """Leitura nova de um VL53 (as leituras do robo.py são de ~36 ms atrás)."""
        self.r.distancia(nome)
        time.sleep(0.04)
        return self.r.distancia(nome)

    def cor_tras(self):
        """'verde', 'vermelho' ou None pelo TCS de trás (encostado na parede do triângulo)."""
        v = self.r.cor_tcs('tras')
        if v is None:
            return None
        r, g, b, c = v
        if max(r, g, b) < 1500:
            return None
        if g > 1.6 * r and g > 1.2 * b:
            return 'verde'
        if r > 1.8 * g and r > 1.8 * b:
            return 'vermelho'
        return None

    def tempo_esgotado(self):
        return time.time() - self.t0 > TEMPO_MAXIMO_AREA

    # ------------------------------------------------------------------ principal
    def executa(self):
        r = self.r
        self.t0 = time.time()
        self.z_entrada = r.z()
        mostra('área de resgate: entrando')
        r.anda_mm(200, vel=30)
        if self.visao is not None:
            if r.garra:
                r.garra.guarda()
            self.recolhe()
            self.deposita('verde', 'esq')
            if self.vivas_entregues >= 2:          # a morta só vale depois das duas vivas
                self.deposita('vermelho', 'dir')
        ok = self.sai()
        mostra('saiu da área' if ok else 'não achou a saída')
        return ok

    # ------------------------------------------------------------------ vítimas
    def escolhe(self, dets):
        vivas = len(self.guardadas['esq'])
        morta = len(self.guardadas['dir'])
        cand = [d for d in dets if (d.tipo == 'viva' and vivas < 2) or (d.tipo == 'morta' and morta < 1)]
        if not cand:
            return None
        return min(cand, key=lambda d: d.distancia)

    def procura_vitima(self, voltas=1.0):
        """Gira parado olhando pela câmera. Devolve a detecção escolhida ou None."""
        r = self.r
        passos = int(round(360 * voltas / 30))
        for _ in range(passos):
            d = self.escolhe(self.visao.vitimas())
            if d is not None:
                return d
            r.gira(30)
            r.garra.mantem()
        return None

    def recolhe(self):
        r = self.r
        mudancas = 0
        while not self.tempo_esgotado():
            if len(self.guardadas['esq']) >= 2 and len(self.guardadas['dir']) >= 1:
                break
            mostra(f"procurando vítimas (guardadas {self.guardadas})")
            d = self.procura_vitima()
            if d is None:
                mudancas += 1
                if mudancas > 5:
                    break
                # muda de lugar: anda até perto de uma parede e tenta de novo
                r.gira(55)
                self.vl('frente')
                r.anda_mm(350, vel=35, para_se=lambda: r.frente_mm() < 180 or r.para_choque())
                continue
            if self.pega(d):
                mudancas = 0

    def pega(self, d):
        r = self.r
        g = r.garra
        tipo = d.tipo
        # chega perto olhando
        perdidas = 0
        for _ in range(12):
            if abs(d.angulo) > 3:
                r.gira(d.angulo)
            if d.distancia < 260:
                break
            passo = min(d.distancia - 230, 300)
            self.vl('frente')
            r.anda_mm(passo, vel=35, para_se=lambda: r.para_choque() or r.frente_mm() < 120)
            g.mantem()
            dets = [x for x in self.visao.vitimas() if x.tipo == tipo]
            if not dets:
                perdidas += 1
                if perdidas >= 3:
                    return False
                continue
            perdidas = 0
            d = min(dets, key=lambda x: abs(x.angulo) + x.distancia / 50)
        else:
            return False
        # confirma o tipo com mais dois quadros antes de abaixar a garra (a IA também erra)
        votos = [tipo]
        for _ in range(2):
            perto = [x for x in self.visao.vitimas() if abs(x.angulo - d.angulo) < 8]
            if perto:
                votos.append(perto[0].tipo)
        tipo = max(set(votos), key=votos.count)
        lado_cheio = (tipo == 'viva' and len(self.guardadas['esq']) >= 2) or \
                     (tipo == 'morta' and len(self.guardadas['dir']) >= 1)
        if lado_cheio:
            r.anda_mm(-100, vel=30)
            return False
        # abaixa a garra aberta (a câmera fica tapada) e avança até a bolinha entrar
        mostra(f'pegando vítima {tipo}')
        g.abaixa_aberta()
        avanco = d.distancia + 60
        r.anda_mm(avanco, vel=22, para_se=lambda: r.distancia('garra') < 22, tempo_max=6.0)
        g.fecha()
        g.levanta()
        if self.vl('garra') > 120:
            mostra('errou a vítima')
            g.guarda()
            r.anda_mm(-120, vel=30)
            return False
        lado = 'esq' if tipo == 'viva' else 'dir'
        g.joga_na_cacamba(lado)
        self.guardadas[lado].append(tipo)
        g.guarda()
        r.anda_mm(-100, vel=30)
        return True

    # ------------------------------------------------------------------ triângulos
    def diagonal_mais_perto(self, direcao):
        """Direção (graus do giroscópio) perpendicular à parede de um triângulo: 45 graus das paredes."""
        k = round((angulo_dif(direcao, self.z_entrada) - 45.0) / 90.0)
        alvo = self.z_entrada + 45.0 + 90.0 * k
        return direcao + angulo_dif(alvo, direcao)     # o giroscópio acumula voltas: alvo perto do atual

    def procura_triangulo(self, cor):
        r = self.r
        for _ in range(18):
            for t in self.visao.triangulos():
                if t.cor == cor:
                    return t
            r.gira(20)
            r.garra.mantem()
        return None

    def deposita(self, cor, lado):
        r = self.r
        if not self.guardadas[lado]:
            return
        for tentativa in range(3):
            mostra(f'levando {self.guardadas[lado]} para o triângulo {cor} ({tentativa + 1}ª tentativa)')
            t = self.procura_triangulo(cor)
            if t is None:
                mostra(f'não achou o triângulo {cor}')
                return
            r.gira(t.angulo)
            # vai na direção dele até ~50 cm
            for _ in range(6):
                if t.distancia < 500:
                    break
                self.vl('frente')
                r.anda_mm(min(t.distancia - 450, 300), vel=40, para_se=lambda: r.frente_mm() < 200)
                r.garra.mantem()
                ts = [x for x in self.visao.triangulos() if x.cor == cor]
                if not ts:
                    break
                t = ts[0]
                r.gira(t.angulo)
            # fica de frente para a parede do triângulo (45 graus das paredes da área) e corrige o
            # desvio de lado: o centro da parede tem que ficar bem na frente (ângulo ~0)
            diag = self.diagonal_mais_perto(r.z())
            r.gira_para(diag)
            for _ in range(3):
                ts = [x for x in self.visao.triangulos() if x.cor == cor]
                if not ts:
                    break
                t = ts[0]
                lado_mm = t.distancia * math.sin(math.radians(t.angulo))   # + = triângulo à esquerda
                if abs(lado_mm) < 35:
                    break
                r.gira_para(diag + (90 if lado_mm > 0 else -90))
                r.anda_mm(abs(lado_mm), vel=30)
                r.gira_para(diag)
            self.vl('frente')
            r.anda_mm(500, vel=30, para_se=lambda: r.frente_mm() < 150 or r.para_choque())
            # vira de costas e encosta de ré até o TCS de trás ver a cor
            r.gira(180)
            r.anda_mm(-320, vel=22, para_se=lambda: self.cor_tras() == cor, tempo_max=6.0)
            r.anda(-15, -15)              # empurra um pouco contra a parede
            time.sleep(0.3)
            r.para()
            if self.cor_tras() == cor:
                break
            mostra(f'não encostou no {cor}: tentando de novo')
            r.anda_mm(250, vel=35)
        else:
            return
        mostra(f'soltando no {cor}')
        n = len(self.guardadas[lado])
        r.garra.solta(lado, tempo=0.6 + 0.3 * n)
        if cor == 'verde':
            self.vivas_entregues += n
        self.guardadas[lado] = []
        r.anda_mm(200, vel=35)

    # ------------------------------------------------------------------ saída
    def alinhado(self, direcao):
        """Direção de parede (múltiplo de 90 graus a partir da entrada) mais perto de 'direcao'."""
        k = round(angulo_dif(direcao, self.z_entrada) / 90.0)
        alvo = self.z_entrada + 90.0 * k
        return direcao + angulo_dif(alvo, direcao)

    def sai(self):
        """Segue a parede pela direita (rumo pelo giroscópio, alinhado com as paredes) até um vão
        com a fita preta embaixo."""
        r = self.r
        mostra('procurando a saída (parede à direita)')
        self.rumo = self.alinhado(r.z())
        r.gira_para(self.rumo)
        self.renova()
        r.anda_mm(1500, vel=40, para_se=lambda: r.frente_mm() < FRENTE_PAREDE or r.para_choque())
        self.vira(90)
        t0 = time.time()
        prog = None
        longe = 0
        while time.time() - t0 < 180.0:
            # preso (empurrando uma vítima contra a parede, por exemplo): andando reto pela parede
            # os encoders não andam. prog = None depois de cada manobra (giro não mexe os encoders)
            e = r.encoder_mm()
            if prog is None or abs(e - prog[1]) > 30:
                prog = (time.time(), e)
            elif time.time() - prog[0] > 2.5:
                mostra('preso: desviando')
                r.anda_mm(-100, vel=30)
                r.gira(35)
                self.vl('frente')
                r.anda_mm(160, vel=30, para_se=lambda: r.frente_mm() < 110)
                r.gira_para(self.rumo)
                prog = None
                continue
            ir = r.reflexao()
            if self.preto_largo(ir):
                r.anda_mm(40, vel=25)
                return True
            if self.prata(ir):
                self._pula_vao()
                prog = None
                continue
            if prog is None:
                self.renova()
            dir_ = r.distancia('direita')
            frente = r.frente_mm()
            longe = longe + 1 if dir_ > 250 else 0
            if frente < FRENTE_PAREDE or r.para_choque():
                r.para()
                if self.vl('direita') > 250 and self.vl('direita') > 250:
                    longe = 2          # canto com o vão logo antes da parede da frente
                else:
                    if r.para_choque():
                        r.anda_mm(-40, vel=30)
                    self.vira(90)
                    prog = None
                    continue
            if longe >= 2:
                # vão na parede da direita (duas leituras seguidas): entra nele e vê o que tem no chão
                r.anda_mm(120, vel=30, para_se=lambda: self.preto_largo() or self.prata() or r.frente_mm() < 60)
                self.vira(-90)
                r.anda_mm(300, vel=28, para_se=lambda: self.preto_largo() or self.prata() or r.frente_mm() < 100)
                if self.preto_largo():
                    r.anda_mm(40, vel=25)
                    return True
                if self.prata():
                    self._pula_vao()
                    prog = None
                    continue
                # não era a saída (diagonal do triângulo, área aberta...): segue até a próxima
                # parede e continua com ela à direita
                r.anda_mm(900, vel=35, para_se=lambda: self.preto_largo() or self.prata()
                          or r.frente_mm() < FRENTE_PAREDE or r.para_choque())
                if self.preto_largo():
                    r.anda_mm(40, vel=25)
                    return True
                if self.prata():
                    self._pula_vao()
                else:
                    self.vira(90)
                prog = None
                longe = 0
                continue
            # rumo da parede + correção pela distância (positivo = virar à esquerda)
            # longe da parede: aponta até 12 graus para ela (mais que isso o VL53 da direita lê na
            # diagonal e não enxerga o vão da saída)
            desvio = max(-12.0, min(12.0, -0.3 * (min(dir_, 250) - DIST_PAREDE)))
            u = -1.5 * angulo_dif(r.z(), self.rumo + desvio)
            u = max(-16, min(16, u))
            r.anda(VEL - u, VEL + u)
            time.sleep(0.01)
        r.para()
        return False

    def vira(self, graus):
        """Gira 90 graus em relação ao rumo atual (não ao ângulo atual: não acumula erro)."""
        self.rumo += graus
        self.r.gira_para(self.rumo)
        self.renova()

    def renova(self):
        """Depois de girar, a primeira leitura de cada VL53 ainda é a medida pedida antes do giro."""
        for nome in ('direita', 'frente'):
            self.vl(nome)

    def _pula_vao(self):
        """Achou a fita prata (é a entrada): volta e passa reto pelo vão."""
        r = self.r
        mostra('é a entrada: passando reto')
        r.anda_mm(-150, vel=30)
        self.vira(90)
        r.anda_mm(300, vel=35, para_se=lambda: r.frente_mm() < FRENTE_PAREDE)
