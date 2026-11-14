"""O robô arruma a casa usando o mapa: percorre os cômodos, acha os objetos pela câmera, pega e leva
até a caixa pela rota do mapa.

    python simulador.py --casa casas/casa_julio.json --programa exemplo_casa/arruma.py
    python simulador.py --casa casas/casa_julio.json --programa exemplo_casa/arruma.py --sem-janela --velocidade 8 --tempo 3000

Diferença para o main.py (que acha tudo pela cor, sem saber onde está): aqui o robô sabe onde está
(localiza.py), onde fica a caixa (o "caixa" do mapa) e como chegar nela de qualquer cômodo (navega.py).

O ciclo:
  1. vai até o cômodo mais perto que ainda não foi olhado;
  2. gira uma volta olhando pela câmera. Cada mancha de cor viva vira um ponto no mapa (pelo pixel em
     que ela encosta no chão) e um tamanho em mm; o que é grande demais para a pinça não é objeto;
  3. vai pela rota até perto do objeto mais próximo, vira para ele, chega pela câmera e pega;
  4. vai pela rota até a frente da caixa, vira para ela e guarda;
  5. volta para o cômodo e olha de novo; sem mais nada à vista, o cômodo está arrumado.

Coisa grande demais para a pinça (uma camiseta, um brinquedo grande) não é pega: vai para o mapa como
obstáculo (as rotas desviam dela, para o robô não se enroscar) e o robô avisa. Se ele olha em volta de
novo e ela não está mais lá, sai do mapa.

Variável de ambiente CASA_ROTA="Sala de estar,Quarto 1": olha só esses cômodos.
"""

import math
import os
import time

import cv2
import numpy as np

from localiza import Localizador
from main import ALTURA, AREA_MIN, CAIXA_H, SAT_MIN, VAL_MIN, aproxima, guarda, pega
from mapa import Mapa
from navega import Navegador
from robo import Robo, ABERTA, BARRAS_CHAO, BARRAS_DESCANSO, FOCO_X, LARGURA

LARGURA_MAX, ALTURA_MAX = 110.0, 130.0     # mm: mancha maior que isso não cabe na pinça (não é objeto)
GRANDE_MAX = 900.0                         # mm: até isso é uma "coisa grande" (camiseta, brinquedo grande);
                                           # maior, não é coisa largada no chão
MESMA_GRANDE = 500.0                       # mm: duas vistas de coisa grande mais perto que isso são a mesma
FOLGA_DA_GRANDE = 40.0                     # mm além da metade do tamanho, no mapa (as rotas desviam disso)
VISAO = 2600.0                             # mm: até onde um objeto na imagem é levado a sério
PERTO_DO_OBJETO = 450.0                    # mm: a rota para aqui e o resto é pela câmera
FRENTE_DA_CAIXA = 430.0                    # mm da parede da caixa até o centro do robô, antes de guardar
INCLINACAO_PROCURA = 15.0
RECUO_ANTES_DE_OLHAR = 250.0               # mm
NO_CAMINHO = (750.0, 170.0)                # mm à frente e para cada lado: objeto aí está no caminho do robô
VIGIA_A_CADA = 4                           # passos da viagem entre duas fotos do chão à frente


def nome_da_cor(h):
    """Nome da cor a partir do matiz do OpenCV (0 a 179)."""
    for limite, nome in ((8, 'vermelho'), (20, 'laranja'), (35, 'amarelo'), (85, 'verde'), (100, 'ciano'),
                         (125, 'azul'), (170, 'roxo')):
        if h < limite:
            return nome
    return 'vermelho'


def objetos_na_imagem(r, img, grandes=False):
    """Manchas de cor viva (fora o roxo da caixa) que cabem na pinça: lista de dicionários com a mancha
    (cx, cy, x, y, w, h, area), o ponto do chão em que ela encosta (frente, lado, em mm, no robô), o
    tamanho estimado (largura, altura, em mm), o nome da cor e 'grande' = False.

    grandes=True: vêm também as coisas grandes demais para a pinça (até GRANDE_MAX), com 'grande' =
    True, 'tamanho' (mm, o maior lado estimado), (frente, lado) = o meio dela no chão e 'inteira' = a
    mancha não encosta na borda da imagem (senão o tamanho e o meio são só um palpite).
    No robô de verdade quem dirá "grande" (e roupa ou brinquedo) será a rede neural da câmera."""
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    colorido = (hsv[:, :, 1] > SAT_MIN) & (hsv[:, :, 2] > VAL_MIN)
    roxo = (hsv[:, :, 0] >= CAIXA_H[0]) & (hsv[:, :, 0] <= CAIXA_H[1])
    n, rot, st, cen = cv2.connectedComponentsWithStats((colorido & ~roxo).astype(np.uint8), connectivity=8)
    res = []
    for i in range(1, n):
        x, y, w, h, a = (int(v) for v in st[i])
        if a < AREA_MIN:
            continue
        pe = r.no_chao(x + w / 2.0, y + h)          # o meio da borda de baixo: onde o objeto pisa no chão
        if pe is None:
            continue
        frente, lado, dist = pe
        mm_px = dist / FOCO_X
        largura, altura = w * mm_px, h * mm_px
        o = {'mancha': (float(cen[i][0]), float(cen[i][1]), x, y, w, h, a),
             'frente': frente, 'lado': lado, 'largura': largura, 'altura': altura, 'grande': False}
        if largura > LARGURA_MAX or altura > ALTURA_MAX:
            if not grandes or largura > GRANDE_MAX:
                continue
            # o comprimento (no sentido em que a câmera olha) sai da borda de cima da mancha. Numa coisa
            # alta a borda de cima "cai" no chão bem atrás dela; por isso o comprimento vai no máximo
            # até a largura para achar o meio e até o dobro dela para o tamanho
            longe = r.no_chao(x + w / 2.0, y)
            comp = max(0.0, longe[0] - frente) if longe is not None else largura
            o.update(grande=True, tamanho=max(largura, min(comp, 2.0 * largura)),
                     frente=frente + min(comp, largura) / 2.0,
                     inteira=x > 0 and y > 0 and x + w < LARGURA and y + h < ALTURA)
        matiz = hsv[y:y + h, x:x + w, 0][rot[y:y + h, x:x + w] == i]
        o['cor'] = nome_da_cor(int(np.median(matiz)))
        res.append(o)
    return res


def ve_objeto(r):
    """A mancha do objeto mais perto (para o aproxima() do main.py), ou None."""
    img = r.foto()
    if img is None:
        return None
    objs = objetos_na_imagem(r, img)
    return min(objs, key=lambda o: o['frente'])['mancha'] if objs else None


def na_caixa(mapa, x, y, folga=180.0):
    """O ponto está em cima da caixa de guardar (ou a menos de 'folga' dela)?"""
    c = mapa.caixa
    if not c:
        return False
    a = math.radians(float(c.get('ang', 0)))
    dx, dy = x - c['x'], y - c['y']
    lx = dx * math.cos(a) + dy * math.sin(a)
    ly = -dx * math.sin(a) + dy * math.cos(a)
    return abs(lx) <= c['tam'][0] / 2 + folga and abs(ly) <= c['tam'][1] / 2 + folga


def olha_em_volta(r, loc, mapa, ignora=(), grandes=None):
    """Gira uma volta olhando pela câmera. Devolve os objetos vistos pelo menos duas vezes, como
    pontos do mapa com a cor [(x, y, cor), ...], do mais perto para o mais longe.
    ignora = pontos (x, y, ...) de objetos que não é para listar.
    grandes = uma lista: recebe as coisas grandes demais para a pinça, [(x, y, cor, tamanho em mm)]."""
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=INCLINACAO_PROCURA, espera=0.4)
    # a câmera só vê o chão a partir de uns 35 cm do meio do robô: um objeto que ele veio empurrando
    # fica escondido embaixo dela. Recuando um pouco (se tem espaço atrás) ele aparece.
    x, y, rumo = loc.pose()
    c, s = math.cos(math.radians(rumo)), math.sin(math.radians(rumo))
    if mapa.folga(x - RECUO_ANTES_DE_OLHAR * c, y - RECUO_ANTES_DE_OLHAR * s) >= 260:
        r.anda(-RECUO_ANTES_DE_OLHAR)
    vistos = []                 # [x, y, quantas vezes, {cor: vezes}]
    gr = []                     # as grandes: [x, y, quantas vezes, {cor: vezes}, tamanho]
    ultimo = loc.pose()[2]
    girado = 0.0
    t0 = time.time()
    while girado < 365.0 and time.time() - t0 < 40:
        img = r.foto()
        x, y, rumo = loc.pose()
        if img is not None:
            c, s = math.cos(math.radians(rumo)), math.sin(math.radians(rumo))
            for o in objetos_na_imagem(r, img, grandes=grandes is not None):
                u = o['mancha'][0]
                if o['frente'] > VISAO or not (LARGURA * 0.06 < u < LARGURA * 0.94):
                    continue
                mx = x + o['frente'] * c - o['lado'] * s
                my = y + o['frente'] * s + o['lado'] * c
                if o['grande']:
                    # o meio dela pode estar no lugar que o mapa já marcou para ela: confere só a planta
                    if not o['inteira'] or na_caixa(mapa, mx, my) or mapa.folga(mx, my, so_planta=True) <= 0:
                        continue
                    for g in gr:
                        if math.hypot(mx - g[0], my - g[1]) < MESMA_GRANDE:
                            g[0] += (mx - g[0]) / (g[2] + 1)
                            g[1] += (my - g[1]) / (g[2] + 1)
                            g[2] += 1
                            g[3][o['cor']] = g[3].get(o['cor'], 0) + 1
                            g[4] = max(g[4], o['tamanho'])
                            break
                    else:
                        gr.append([mx, my, 1, {o['cor']: 1}, o['tamanho']])
                    continue
                if na_caixa(mapa, mx, my) or mapa.folga(mx, my) <= 0:
                    continue                      # já guardado, ou "dentro" de uma parede ou de um móvel
                if any(math.hypot(mx - p[0], my - p[1]) < 250 for p in ignora):
                    continue
                for v in vistos:
                    if math.hypot(mx - v[0], my - v[1]) < 200:
                        v[0] += (mx - v[0]) / (v[2] + 1)
                        v[1] += (my - v[1]) / (v[2] + 1)
                        v[2] += 1
                        v[3][o['cor']] = v[3].get(o['cor'], 0) + 1
                        break
                else:
                    vistos.append([mx, my, 1, {o['cor']: 1}])
        r.move(0, 0, 24)
        girado += abs((rumo - ultimo + 180.0) % 360.0 - 180.0)
        ultimo = rumo
    r.para()
    if grandes is not None:
        grandes.extend((g[0], g[1], max(g[3], key=g[3].get), g[4]) for g in gr if g[2] >= 2)
    x, y, _ = loc.pose()
    return sorted(((v[0], v[1], max(v[3], key=v[3].get)) for v in vistos if v[2] >= 2),
                  key=lambda p: math.hypot(p[0] - x, p[1] - y))


def busca(r, nav, loc, alvo):
    """Vai até o objeto do ponto 'alvo' = (x, y, ...) do mapa e pega. False se não conseguiu."""
    ax, ay = alvo[:2]
    x, y, _ = loc.pose()
    if math.hypot(ax - x, ay - y) > PERTO_DO_OBJETO + 60:
        if not nav.vai_para(ax, ay, tolerancia=PERTO_DO_OBJETO):
            return False
        x, y, _ = loc.pose()
    nav.vira_para(math.degrees(math.atan2(ay - y, ax - x)), tolerancia=6.0)
    perto = math.hypot(ax - x, ay - y)
    if perto < 400:
        r.anda(-(420 - perto))             # perto demais para a câmera ver: recua
    if not aproxima(r, ve_objeto, lambda m, d: m[3] + m[5] > ALTURA * 0.80 or d < 330, tempo=15):
        return False
    if pega(r):
        return True
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=INCLINACAO_PROCURA, espera=0.8)
    r.anda(-150)
    return False


def frentes_da_caixa(mapa):
    """Pontos de onde dá para guardar: na frente de cada lado da caixa, com o rumo que olha para ela."""
    c = mapa.caixa
    a = math.radians(float(c.get('ang', 0)))
    ca, sa = math.cos(a), math.sin(a)
    res = []
    for ux, uy, meio in ((1, 0, c['tam'][0] / 2), (-1, 0, c['tam'][0] / 2), (0, 1, c['tam'][1] / 2), (0, -1, c['tam'][1] / 2)):
        d = meio + FRENTE_DA_CAIXA
        x = c['x'] + (ux * ca - uy * sa) * d
        y = c['y'] + (ux * sa + uy * ca) * d
        if mapa.folga(x, y) >= 230:
            res.append((x, y, math.degrees(math.atan2(c['y'] - y, c['x'] - x))))
    return res


def leva_para_a_caixa(r, nav, loc, mapa):
    """Com um objeto na pinça: vai pela rota até a frente da caixa e guarda."""
    x, y, _ = loc.pose()
    frentes = []
    for (fx, fy, rumo) in frentes_da_caixa(mapa):
        caminho = mapa.rota((x, y), (fx, fy))
        if caminho is not None:
            frentes.append((mapa.comprimento(caminho), fx, fy, rumo))
    for _, fx, fy, rumo in sorted(frentes):
        if nav.vai_para(fx, fy, tolerancia=45, rumo=rumo) and guarda(r):
            return True
        print('não deu por este lado da caixa: tento por outro')
        r.anda(-120)
    return False


def larga_no_chao(r):
    r.garra(barras=BARRAS_CHAO, espera=0.9)
    r.garra(abertura=ABERTA, espera=0.8)
    r.anda(-150)
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=INCLINACAO_PROCURA, espera=0.9)


def mais_perto(mapa, loc, nomes):
    """O cômodo da lista com a rota mais curta a partir de onde o robô está."""
    x, y, _ = loc.pose()
    melhor = None
    for n in nomes:
        caminho = mapa.rota((x, y), mapa.lugar(n))
        if caminho is not None and (melhor is None or mapa.comprimento(caminho) < melhor[0]):
            melhor = (mapa.comprimento(caminho), n)
    return melhor[1] if melhor else None


class Arrumador:
    """Arruma cômodos: olha, pega e guarda. Guarda o que já fez (cores guardadas, objetos de que
    desistiu), para o main() daqui e para as ferramentas do cérebro (habilidades.py)."""

    def __init__(self, r, mapa, loc, nav, avisa=print):
        self.r, self.mapa, self.loc, self.nav = r, mapa, loc, nav
        self.avisa = avisa
        self.guardados = []          # cores dos objetos guardados
        self.desistidos = []         # pontos (x, y) de objetos que não deu para pegar ou guardar
        self.falhas = {}
        self.carregando = None       # cor do objeto que está na pinça a caminho da caixa
        # coisas grandes demais para a pinça vistas no chão (camiseta, brinquedo grande): dicionários com
        # x, y, cor, tamanho (mm) e cômodo. Ficam no mapa como obstáculos (o robô desvia) e são avisadas
        self.grandes = []
        self.grandes_novos = []      # as que apareceram desde a última vez que alguém esvaziou esta lista
        self.fechados = []           # cômodos do último arruma() fechados por uma coisa grande
        self._passos = 0
        self._pega = True            # na viagem, objeto pequeno no caminho é pego (False: só desvia das grandes)

    def anota_grandes(self, vistas, olhou_de=None):
        """vistas = [(x, y, cor, tamanho)]. olhou_de = (x, y) de onde o robô olhou em volta: as já anotadas
        até perto dali que ele não viu de novo saíram do lugar (alguém recolheu) e saem do mapa."""
        if olhou_de is not None:
            px, py = olhou_de
            self.grandes = [g for g in self.grandes if math.hypot(g['x'] - px, g['y'] - py) > VISAO * 0.8
                            or any(math.hypot(g['x'] - v[0], g['y'] - v[1]) < MESMA_GRANDE for v in vistas)]
        for (x, y, cor, tam) in vistas:
            for g in self.grandes:
                if math.hypot(g['x'] - x, g['y'] - y) < MESMA_GRANDE:
                    g.update(x=x, y=y, tamanho=max(g['tamanho'], tam))
                    break
            else:
                g = {'x': x, 'y': y, 'cor': cor, 'tamanho': tam, 'comodo': self.mapa.comodo(x, y)}
                self.grandes.append(g)
                self.grandes_novos.append(g)
                self.avisa(f'coisa grande {cor} no chão de {g["comodo"]} (uns {tam / 10:.0f} cm): não dá para '
                           f'pegar, fica marcada no mapa e eu desvio')
        self.mapa.poe_obstaculos([(g['x'], g['y'], g['tamanho'] / 2 + FOLGA_DA_GRANDE) for g in self.grandes])

    def _sem_caminho(self, nomes):
        """Avisa dos cômodos em que não chegou, separando os fechados por uma coisa grande no chão."""
        x, y, _ = self.loc.pose()
        fechados = [n for n in nomes if self.mapa.fechado_por_obstaculo((x, y), self.mapa.lugar(n))]
        self.fechados.extend(fechados)
        if fechados:
            self.avisa('não chego em ' + ', '.join(fechados) + ': uma coisa grande no chão fecha a passagem')
        resto = [n for n in nomes if n not in fechados]
        if resto:
            self.avisa('não cheguei em: ' + ', '.join(resto))

    def vigia(self):
        """Durante a viagem: tem alguma coisa no chão logo à frente? Objeto pequeno (com a pinça vazia e
        self._pega) = devolve (x, y, cor), para pegar. Coisa grande que o mapa ainda não tinha = anota e
        devolve ('grande', x, y), para refazer a rota desviando."""
        self._passos += 1
        if self._passos % VIGIA_A_CADA:
            return None
        img = self.r.foto()
        if img is None:
            return None
        x, y, rumo = self.loc.pose()
        c, s = math.cos(math.radians(rumo)), math.sin(math.radians(rumo))
        for o in objetos_na_imagem(self.r, img, grandes=True):
            meio = o.get('tamanho', 0.0) / 2.0
            if o['frente'] - meio > NO_CAMINHO[0] or abs(o['lado']) - meio > NO_CAMINHO[1]:
                continue
            mx = x + o['frente'] * c - o['lado'] * s
            my = y + o['frente'] * s + o['lado'] * c
            if o['grande']:
                if (any(math.hypot(mx - g['x'], my - g['y']) < MESMA_GRANDE for g in self.grandes)
                        or self.mapa.folga(mx, my, so_planta=True) <= 0):
                    continue                  # já está no mapa (a rota já desvia) ou é parte de um móvel
                self.anota_grandes([(mx, my, o['cor'], o['tamanho'])])
                return ('grande', mx, my)
            if not self._pega:
                continue
            if na_caixa(self.mapa, mx, my) or any(math.hypot(mx - p[0], my - p[1]) < 250 for p in self.desistidos):
                continue
            return (mx, my, o['cor'])
        return None

    def trata(self, alvo):
        """Pega o objeto do ponto 'alvo' = (x, y, cor) e guarda na caixa. True se guardou."""
        cor = alvo[2] if len(alvo) > 2 else 'colorido'
        if busca(self.r, self.nav, self.loc, alvo):
            self.carregando = cor          # se a tarefa for interrompida daqui em diante, o objeto está na pinça
            if leva_para_a_caixa(self.r, self.nav, self.loc, self.mapa):
                self.carregando = None
                self.guardados.append(cor)
                self.avisa(f'guardei o objeto {cor} ({len(self.guardados)})')
                return True
            self.avisa('não consegui chegar na caixa: deixo o objeto no chão')
            larga_no_chao(self.r)
            self.carregando = None
            x, y, _ = self.loc.pose()
            self.desistidos.append((x, y))
            return False
        chave = (round(alvo[0] / 300), round(alvo[1] / 300))
        self.falhas[chave] = self.falhas.get(chave, 0) + 1
        self.avisa('não consegui pegar')
        if self.falhas[chave] >= 2:
            self.desistidos.append(tuple(alvo[:2]))
        return False

    def viaja(self, x, y, pega=True, **kw):
        """Vai até (x, y) olhando o chão à frente: objeto no caminho é pego e guardado (pega=False: não)
        e a viagem segue; coisa grande no caminho vai para o mapa e a rota é refeita desviando dela."""
        desvios = 0
        while True:
            self._pega = pega
            self.nav.ao_andar = self.vigia if desvios < 6 else (lambda: None)
            ok = self.nav.vai_para(x, y, **kw)
            self.nav.ao_andar = None
            if self.nav.parou_por is None:
                return ok
            alvo = self.nav.parou_por
            if alvo[0] == 'grande':
                desvios += 1
                continue
            self.avisa(f'objeto {alvo[2]} no caminho, em ({alvo[0]:.0f}, {alvo[1]:.0f}), {self.mapa.comodo(alvo[0], alvo[1])}')
            self.trata(alvo)

    def arruma(self, nomes):
        """Olha os cômodos da lista (do mais perto para o mais longe) e guarda o que achar.
        Devolve (cômodos olhados, cômodos em que não chegou)."""
        falta = [n for n in nomes if self.mapa.lugar(n) is not None]
        olhados, sem_chegar = [], []
        self.fechados = []           # cômodos em que não chegou porque uma coisa grande fecha a passagem
        while falta:
            nome = mais_perto(self.mapa, self.loc, falta)
            if nome is None:
                self._sem_caminho(falta)
                sem_chegar.extend(falta)
                break
            falta.remove(nome)
            if not self.viaja(*self.mapa.lugar(nome)):
                self._sem_caminho([nome])
                sem_chegar.append(nome)
                continue
            while True:
                gr = []
                vistos = olha_em_volta(self.r, self.loc, self.mapa, ignora=self.desistidos, grandes=gr)
                self.anota_grandes(gr, olhou_de=self.loc.pose()[:2])
                if not vistos:
                    self.avisa(f'{nome}: nada no chão')
                    break
                alvo = vistos[0]
                self.avisa(f'{nome}: vi {len(vistos)} objeto(s); vou no {alvo[2]}, em ({alvo[0]:.0f}, {alvo[1]:.0f})')
                self.trata(alvo)
                if not self.viaja(*self.mapa.lugar(nome)):
                    break
            olhados.append(nome)
        return olhados, sem_chegar


def main():
    mapa = Mapa()
    if not mapa.caixa:
        print(f'o mapa "{mapa.nome}" não tem a caixa de guardar ("caixa" no JSON da casa)')
        return
    pedido = [n.strip() for n in os.environ.get('CASA_ROTA', '').split(',') if n.strip()]
    nomes = [n for n in (pedido or mapa.lugares()) if mapa.lugar(n) is not None]
    print(f'mapa: {mapa.nome}; caixa em ({mapa.caixa["x"]:.0f}, {mapa.caixa["y"]:.0f}), '
          f'{mapa.comodo(mapa.caixa["x"], mapa.caixa["y"])}; {len(nomes)} cômodos para olhar')

    r = Robo()
    r.espera_botao()
    r.garra(barras=BARRAS_DESCANSO, abertura=0, inclinacao=INCLINACAO_PROCURA, espera=0.8)
    loc = Localizador(r, mapa)
    nav = Navegador(r, mapa, loc)
    a = Arrumador(r, mapa, loc, nav)
    a.arruma(nomes)
    x0, y0, a0 = mapa.inicio
    a.viaja(x0, y0, rumo=a0)
    print(f'fim: {len(a.guardados)} objeto(s) guardado(s), {len(a.desistidos)} deixado(s), {loc.percurso / 1000:.0f} m andados')
    for g in a.grandes:
        print(f'ficou no chão, grande demais: coisa {g["cor"]} em {g["comodo"]} ({g["x"]:.0f}, {g["y"]:.0f}), '
              f'uns {g["tamanho"] / 10:.0f} cm')
    r.para()


if __name__ == '__main__':
    main()
