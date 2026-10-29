"""Interface gráfica (pygame): visualização da simulação e editor de mapas."""

import math
import os
import time

import pygame

from .painel_brick import PainelBrick

from . import mapa as M
from .fisica import pino_num

PAINEL = 400
CONSOLE = 150
FAIXA_ENTRADA = 40   # aviso do input() no alto do console

COR_FUNDO = (32, 34, 40)
COR_PAINEL = (24, 26, 31)
COR_TEXTO = (225, 228, 235)
COR_TEXTO2 = (150, 156, 170)
COR_DESTAQUE = (255, 196, 61)
COR_BOTAO = (52, 56, 66)
COR_BOTAO_ON = (40, 120, 90)
COR_PAREDE = (52, 64, 92)
COR_PISO = {
    'branco': (238, 238, 232), 'preto': (18, 18, 18), 'prata': (176, 184, 198),
    'azul': (60, 110, 225), 'vermelho': (215, 52, 52),
}
COR_ANEL = {'preto': (15, 15, 15), 'vermelho': (220, 40, 40), 'amarelo': (240, 210, 30),
            'verde': (40, 170, 70), 'azul': (40, 90, 220)}
CORES_DEBUG = {'amarelo': (250, 210, 40), 'verde': (60, 220, 90), 'vermelho': (240, 60, 60),
               'azul': (70, 140, 255), 'branco': (255, 255, 255), 'roxo': (200, 90, 255)}
COR_RAIOS = [(255, 120, 80), (255, 180, 80), (90, 200, 255), (120, 160, 255), (120, 255, 140),
             (255, 100, 200), (200, 200, 200), (255, 255, 120)]

CICLO_TERRENO = [('', None), ('lombada', 'NS'), ('lombada', 'LO'), ('escada', 'NS'),
                 ('escada', 'LO'), ('detritos', None)]
CICLO_VITIMA = [
    ('letra', 'H'), ('letra', 'S'), ('letra', 'U'),
    ('cognitivo', 'ferida'), ('cognitivo', 'estavel'), ('cognitivo', 'ilesa'),
    ('letra', 'X'), ('cognitivo', None), (None, None),
]
FERRAMENTAS = [
    ('parede', 'Parede', 'Clique perto da borda de um ladrilho para pôr/tirar parede. Arraste para desenhar.'),
    ('piso', 'Piso', 'Clique: branco > preto > prata > azul > vermelho. Botão direito: volta a branco.'),
    ('terreno', 'Terreno', 'Clique: lombada (NS/LO) > escada (NS/LO) > detritos > nada. NS = robô anda norte-sul.'),
    ('zona', 'Zona perigo', 'Marca os ladrilhos da zona de perigo (arraste). A entrada é um piso vermelho.'),
    ('vitima', 'Vítima', 'Clique junto a uma parede: Φ > Ψ > Ω > cognitivas (ferida/estável/ilesa) > falsas > nada.'),
    ('inicio', 'Início', 'Clique para pôr o início; clique de novo no mesmo ladrilho para girar a direção.'),
]


def _fonte(tam, negrito=False):
    return pygame.font.SysFont('dejavusans,arial,liberationsans,freesans,helvetica', tam, bold=negrito)


class Botao:
    def __init__(self, texto, acao, ligado=None, dica=''):
        self.texto = texto
        self.acao = acao
        self.ligado = ligado
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.dica = dica


class Interface:
    def __init__(self, sim, pasta_mapas):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption('Simulador RoboCupJunior Rescue Maze — Mariola')
        self.tela = pygame.display.set_mode((1360, 860), pygame.RESIZABLE)
        self.sim = sim
        self.pasta_mapas = pasta_mapas
        self.f12 = _fonte(12)
        self.f14 = _fonte(14)
        self.f12b = _fonte(12, True)
        self.f11 = _fonte(11)
        self.f16b = _fonte(16, True)
        self.f22b = _fonte(22, True)
        self.f30b = _fonte(30, True)
        self.brick = PainelBrick()
        self.modo = 'simular'
        self.ferramenta = 'parede'
        self.arrasto = None
        self.arrasta_robo = None
        self.mostrar_raios = True
        self.mostrar_trilha = True
        self.mostrar_flutuantes = False
        self.mostrar_cameras = True
        self.trilha = []
        self.sujo = True
        self.camada = None
        self.leituras = {}
        self.t_leituras = 0
        self.msg = ''
        self.t_msg = 0
        self.fontes_vitima = {}
        self.bot_enter = Botao('⏎ Enter', lambda: self.sim.responde_entrada(), dica='Enter')
        self._monta_botoes()

    # ------------------------------------------------------------------ botões
    def _monta_botoes(self):
        s = self.sim
        self.bot_sim = [
            [Botao('▶ Iniciar rodada', self._iniciar, dica='F5'),
             Botao('■ Parar', lambda: s.parar_programa()),
             Botao('↺ Nova rodada', self._nova_rodada)],
            [Botao('LoP', s.lop_manual, dica='L'),
             Botao('Botão do robô', lambda: s.apertar_botao(), dica='B'),
             Botao('Pausar', self._pausa, ligado=lambda: s.pausado, dica='espaço'),
             Botao('', self._velocidade)],
            [Botao('', self._modo_lop),
             Botao('', self._auto_botao),
             Botao('Editar mapa', lambda: self._muda_modo('editar'))],
            [Botao('', self._escolhe_programa)],
        ]
        self.bot_ed = [
            [Botao(n, (lambda k=k: self._set_ferramenta(k)), ligado=(lambda k=k: self.ferramenta == k))
             for k, n, _ in FERRAMENTAS[:3]],
            [Botao(n, (lambda k=k: self._set_ferramenta(k)), ligado=(lambda k=k: self.ferramenta == k))
             for k, n, _ in FERRAMENTAS[3:]],
            [Botao('Linha +', lambda: self._redim(1, 0)), Botao('Linha −', lambda: self._redim(-1, 0)),
             Botao('Coluna +', lambda: self._redim(0, 1)), Botao('Coluna −', lambda: self._redim(0, -1))],
            [Botao('Novo', self._novo), Botao('Abrir', self._abrir), Botao('Salvar', self._salvar),
             Botao('Salvar como', lambda: self._salvar(True))],
            [Botao('Sortear pisos', self._sortear), Botao('Voltar a simular', lambda: self._muda_modo('simular'))],
        ]

    def _iniciar(self):
        if self.modo != 'simular':
            self._muda_modo('simular')
        if self.sim.juiz.ativo and not self.sim.juiz.fim:
            self.sim.iniciar_programa()
        else:
            self.sim.nova_rodada()
            self.trilha = []
            self.sim.iniciar_rodada()

    def _nova_rodada(self):
        self.sim.nova_rodada()
        self.trilha = []

    def _pausa(self):
        self.sim.set_pausa(not self.sim.pausado)

    def _velocidade(self):
        opcoes = [0.25, 0.5, 1.0, 2.0, 4.0]
        i = opcoes.index(self.sim.fator) if self.sim.fator in opcoes else 2
        self.sim.set_fator(opcoes[(i + 1) % len(opcoes)])

    def _modo_lop(self):
        self.sim.modo_lop = 'botao' if self.sim.modo_lop == 'reiniciar' else 'reiniciar'

    def _auto_botao(self):
        self.sim.auto_botao = not self.sim.auto_botao

    def _escolhe_programa(self):
        """Abre o seletor de arquivo e troca o programa do robô (sem fechar o simulador)."""
        atual = self.sim.programa
        pasta = os.path.dirname(atual) if atual else os.path.dirname(self.pasta_mapas)
        try:
            import tkinter as tk
            from tkinter import filedialog
            raiz = tk.Tk()
            raiz.withdraw()
            raiz.attributes('-topmost', True)
            c = filedialog.askopenfilename(initialdir=pasta, filetypes=[('Programa Python', '*.py')],
                                           title='Escolha o programa do robô')
            raiz.destroy()
        except Exception:
            self._aviso('sem tkinter: use --programa ao abrir o simulador')
            return
        if not c:
            return
        if not c.lower().endswith('.py'):
            self._aviso(f'{os.path.basename(c)}: o programa tem de ser um .py')
            return
        self.sim.troca_programa(c)
        self.trilha = []
        self._aviso(f'programa: {self._nome_programa()}')

    def _nome_programa(self):
        """'pasta/arquivo' do programa atual (a pasta ajuda quando todos se chamam main.py)."""
        p = self.sim.programa
        if not p:
            return 'nenhum'
        return f'{os.path.basename(os.path.dirname(p))}/{os.path.basename(p)}'

    def _set_ferramenta(self, k):
        self.ferramenta = k

    def _aviso(self, s):
        self.msg = s
        self.t_msg = time.time()

    # ------------------------------------------------------------------ modos / arquivos
    def _muda_modo(self, modo):
        if modo == self.modo:
            return
        if modo == 'editar':
            self.sim.parar_programa()
            with self.sim.mundo.lock:
                self.sim.juiz.reset()
        else:
            self._aplica_mapa()
        self.modo = modo
        self.sujo = True

    def _aplica_mapa(self):
        w = self.sim.mundo
        with w.lock:
            w.corpo = None
            w.construir()
            self.sim.juiz.reset()
            w.reset_rodada()
        self.trilha = []
        self.sujo = True

    def _redim(self, dl, dc):
        m = self.sim.mundo.mapa
        m.redimensiona(m.linhas + dl, m.colunas + dc)
        self.sujo = True

    def _novo(self):
        m = self.sim.mundo.mapa
        novo = M.Mapa(6, 8, 'novo')
        m.__dict__.update(novo.__dict__)
        self.sujo = True

    def _dialogo(self, salvar):
        try:
            import tkinter as tk
            from tkinter import filedialog
            raiz = tk.Tk()
            raiz.withdraw()
            raiz.attributes('-topmost', True)
            tipos = [('Mapas Maze', '*.json')]
            if salvar:
                c = filedialog.asksaveasfilename(initialdir=self.pasta_mapas, defaultextension='.json', filetypes=tipos)
            else:
                c = filedialog.askopenfilename(initialdir=self.pasta_mapas, filetypes=tipos)
            raiz.destroy()
            return c or None
        except Exception:
            return 'SEM_TK'

    def _abrir(self):
        c = self._dialogo(False)
        if c == 'SEM_TK':
            arqs = sorted(f for f in os.listdir(self.pasta_mapas) if f.endswith('.json'))
            if not arqs:
                return
            atual = os.path.basename(self.sim.mundo.mapa.caminho or '')
            i = (arqs.index(atual) + 1) % len(arqs) if atual in arqs else 0
            c = os.path.join(self.pasta_mapas, arqs[i])
        if c:
            try:
                novo = M.Mapa.carregar(c)
            except Exception as e:
                self._aviso(f'erro ao abrir: {e}')
                return
            self.sim.mundo.mapa.__dict__.update(novo.__dict__)
            self._aplica_mapa()
            self._aviso(f'aberto {os.path.basename(c)}')

    def _salvar(self, como=False):
        m = self.sim.mundo.mapa
        c = m.caminho
        if como or not c:
            c = self._dialogo(True)
            if c == 'SEM_TK':
                n = 1
                while os.path.exists(os.path.join(self.pasta_mapas, f'mapa{n}.json')):
                    n += 1
                c = os.path.join(self.pasta_mapas, f'mapa{n}.json')
        if c:
            m.nome = os.path.splitext(os.path.basename(c))[0]
            m.salvar(c)
            self._aviso(f'salvo em {c}')

    def _sortear(self):
        """Sorteia de novo a posição dos ladrilhos preto/azul/prata (como o dado do juiz)."""
        import random
        m = self.sim.mundo.mapa
        especiais = [(k, v['piso']) for k, v in m.ladrilhos.items() if v.get('piso') in ('preto', 'azul', 'prata')]
        livres = [(l, c) for l in range(m.linhas) for c in range(m.colunas)
                  if m.piso(l, c) == 'branco' and not m.terreno(l, c) and not m.zona(l, c)
                  and (l, c) != tuple(m.inicio)
                  and not any(v['linha'] == l and v['coluna'] == c for v in m.vitimas)]
        for k, _ in especiais:
            m.set_lad(*k, piso=None)
            livres.append(k)
        random.shuffle(livres)
        for (k, p), novo in zip(especiais, livres):
            m.set_lad(*novo, piso=p)
        self.sujo = True
        self._aviso('pisos especiais sorteados')

    # ------------------------------------------------------------------ geometria da tela
    def _area(self):
        lw, lh = self.tela.get_size()
        return pygame.Rect(0, 0, lw - PAINEL, lh - CONSOLE)

    def _calcula_escala(self):
        a = self._area()
        m = self.sim.mundo.mapa
        mg = 30
        self.esc = min((a.w - 2 * mg) / m.largura_mm, (a.h - 2 * mg) / m.altura_mm)
        self.ox = a.x + (a.w - m.largura_mm * self.esc) / 2
        self.oy = a.y + (a.h - m.altura_mm * self.esc) / 2
        self.H = m.altura_mm

    def T(self, x, y):
        return (self.ox + x * self.esc, self.oy + (self.H - y) * self.esc)

    def W(self, px, py):
        return ((px - self.ox) / self.esc, self.H - (py - self.oy) / self.esc)

    # ------------------------------------------------------------------ desenho do mapa
    def _desenha_camada(self):
        a = self._area()
        self._calcula_escala()
        sup = pygame.Surface((a.w, a.h))
        sup.fill(COR_FUNDO)
        m = self.sim.mundo.mapa
        e = self.esc
        T = M.TAM
        flut = set()
        if self.mostrar_flutuantes:
            lin = m.ladrilhos_lineares()
            flut = {(l, c) for l in range(m.linhas) for c in range(m.colunas)} - lin
        for l in range(m.linhas):
            for c in range(m.colunas):
                x0, y0 = self.T(c * T, m.altura_mm - l * T)
                r = pygame.Rect(round(x0), round(y0), math.ceil(T * e), math.ceil(T * e))
                piso = m.piso(l, c)
                pygame.draw.rect(sup, COR_PISO.get(piso, (200, 200, 200)), r)
                if piso == 'prata':
                    sup.set_clip(r)
                    for k in range(0, r.w * 2, max(4, int(e * 25))):
                        pygame.draw.line(sup, (215, 222, 232), (r.x + k, r.y), (r.x + k - r.h, r.bottom), 2)
                    sup.set_clip(None)
                    pygame.draw.rect(sup, COR_PISO['prata'], r, 3)
                if m.zona(l, c):
                    s = pygame.Surface(r.size, pygame.SRCALPHA)
                    s.fill((255, 120, 0, 55))
                    sup.blit(s, r)
                if (l, c) in flut:
                    s = pygame.Surface(r.size, pygame.SRCALPHA)
                    s.fill((150, 80, 255, 50))
                    sup.blit(s, r)
                pygame.draw.rect(sup, (200, 200, 195) if piso != 'preto' else (60, 60, 60), r, 1)
                ter = m.terreno(l, c)
                if ter == 'lombada':
                    for (x1, y1, x2, y2) in m.linhas_lombada(l, c):
                        pygame.draw.line(sup, (150, 100, 50), self.T(x1, y1), self.T(x2, y2), max(2, int(14 * e)))
                elif ter == 'escada':
                    self._desenha_escada(sup, m, l, c)
                elif ter == 'detritos':
                    txt = self.f12.render('detritos', True, (120, 90, 60))
                    sup.blit(txt, (r.x + 3, r.bottom - 15))
        # início
        l, c = m.inicio
        cx, cy = self.T(*m.centro(l, c))
        r = pygame.Rect(0, 0, T * e - 8, T * e - 8)
        r.center = (cx, cy)
        pygame.draw.rect(sup, (40, 170, 90), r, 3)
        ang = M.ANGULO_DIR[m.inicio_dir]
        p2 = (cx + math.cos(ang) * T * e * 0.3, cy - math.sin(ang) * T * e * 0.3)
        pygame.draw.line(sup, (40, 170, 90), (cx, cy), p2, 3)
        pygame.draw.circle(sup, (40, 170, 90), (int(p2[0]), int(p2[1])), 5)
        # paredes
        lw = max(2, int(2 * M.MEIA_PAREDE * e))
        for (x1, y1, x2, y2) in m.segmentos_parede():
            p1, p2 = self.T(x1, y1), self.T(x2, y2)
            pygame.draw.line(sup, COR_PAREDE, p1, p2, lw)
            pygame.draw.circle(sup, COR_PAREDE, (int(p1[0]), int(p1[1])), lw // 2)
            pygame.draw.circle(sup, COR_PAREDE, (int(p2[0]), int(p2[1])), lw // 2)
        # coordenadas
        for c in range(m.colunas):
            t = self.f12.render(str(c), True, COR_TEXTO2)
            x, y = self.T((c + 0.5) * T, m.altura_mm)
            sup.blit(t, (x - t.get_width() / 2, y - 22))
        for l in range(m.linhas):
            t = self.f12.render(str(l), True, COR_TEXTO2)
            x, y = self.T(0, m.altura_mm - (l + 0.5) * T)
            sup.blit(t, (x - 20, y - t.get_height() / 2))
        self.camada = sup
        self.sujo = False

    def _desenha_escada(self, sup, m, l, c):
        T = M.TAM
        x0, y0 = c * T, m.altura_mm - (l + 1) * T
        ns = m.lad(l, c).get('direcao', 'NS') == 'NS'
        for k in range(0, 31):
            s = k * 10.0
            if ns:
                h = m.perfil_escada(l, c, x0 + T / 2, y0 + s)
                a, b = self.T(x0 + 8, y0 + s), self.T(x0 + T - 8, y0 + s + 10)
            else:
                h = m.perfil_escada(l, c, x0 + s, y0 + T / 2)
                a, b = self.T(x0 + s, y0 + 8), self.T(x0 + s + 10, y0 + T - 8)
            tom = int(215 - h * 3.5)
            r = pygame.Rect(min(a[0], b[0]), min(a[1], b[1]), abs(b[0] - a[0]) + 1, abs(b[1] - a[1]) + 1)
            pygame.draw.rect(sup, (tom, tom - 5, tom - 15), r)

    def _desenha_vitimas(self):
        w = self.sim.mundo
        m = w.mapa
        e = self.esc
        ident = self.sim.juiz.identificadas
        for idx, v in enumerate(m.vitimas):
            if not m.dentro(v['linha'], v['coluna']):
                continue
            (vx, vy), (nx, ny) = m.ponto_vitima(v)
            px, py = self.T(vx + nx * 6, vy + ny * 6)
            raio = max(6, int(28 * e))
            st = M.status_vitima(v)
            if v['tipo'] == 'cognitivo':
                aneis = v.get('aneis') or ['amarelo'] * 5
                for k in range(4, -1, -1):
                    pygame.draw.circle(self.tela, COR_ANEL.get(aneis[k], (128, 128, 128)), (int(px), int(py)),
                                       max(2, int(raio * (k + 1) / 5)))
            else:
                r = pygame.Rect(0, 0, raio * 2, raio * 2)
                r.center = (px, py)
                pygame.draw.rect(self.tela, (255, 255, 255), r, border_radius=3)
                pygame.draw.rect(self.tela, (0, 0, 0), r, 1, border_radius=3)
                tam = max(10, int(raio * 1.6))
                f = self.fontes_vitima.get(tam)
                if f is None:
                    f = self.fontes_vitima[tam] = _fonte(tam, True)
                t = f.render(M.SIMBOLO_LETRA.get(v['letra'], v['letra']), True, (0, 0, 0))
                self.tela.blit(t, (px - t.get_width() / 2, py - t.get_height() / 2))
            if st is None:
                pygame.draw.line(self.tela, (120, 120, 120), (px - raio, py + raio + 3), (px + raio, py + raio + 3), 2)
            if idx in ident:
                pygame.draw.circle(self.tela, (60, 230, 90), (int(px), int(py)), raio + 4, 3)

    def _desenha_robo(self, snap):
        e = self.esc
        w = self.sim.mundo
        # trilha
        if self.mostrar_trilha and len(self.trilha) > 1:
            pygame.draw.lines(self.tela, (255, 160, 40), False, [self.T(x, y) for x, y in self.trilha], 2)
        # kits
        for k in snap['kits']:
            px, py = self.T(k['x'], k['y'])
            r = pygame.Rect(0, 0, max(7, int(20 * e)), max(7, int(20 * e)))
            r.center = (px, py)
            pygame.draw.rect(self.tela, (255, 140, 0), r)
            pygame.draw.rect(self.tela, (0, 0, 0), r, 1)
        # detritos
        for pts in snap['detritos']:
            for (dx, dy) in pts:
                pygame.draw.circle(self.tela, (90, 70, 50), self.T(dx, dy), max(2, int(6 * e)))
        x, y, a = snap['pose']
        ca, sa = math.cos(a), math.sin(a)

        def L(lx, ly):
            return self.T(x + lx * ca - ly * sa, y + lx * sa + ly * ca)

        ov = pygame.Surface(self.tela.get_size(), pygame.SRCALPHA)
        # câmeras
        if self.mostrar_cameras:
            for cam in w.cfg['cameras']:
                ang = math.radians(cam['angulo'])
                fov = math.radians(cam['fov']) / 2
                r = cam['alcance_mm']
                p0 = (cam['x'], cam['y'])
                pts = [L(*p0)]
                for k in range(9):
                    t = ang - fov + 2 * fov * k / 8
                    pts.append(L(p0[0] + r * math.cos(t), p0[1] + r * math.sin(t)))
                pygame.draw.polygon(ov, (120, 200, 255, 30), pts)
        hl, hw = w.L / 2, w.W / 2
        corpo = [L(hl, hw), L(hl, -hw), L(-hl, -hw), L(-hl, hw)]
        pygame.draw.polygon(ov, (30, 35, 50, 190), corpo)
        self.tela.blit(ov, (0, 0))
        pygame.draw.polygon(self.tela, (200, 210, 230), corpo, 2)
        # rodas
        rr = w.diametro / 2
        for mot in w.motores:
            lado = 1 if mot.y > 0 else -1
            pts = [L(mot.x + rr, mot.y + lado * 6), L(mot.x + rr, mot.y - lado * 12),
                   L(mot.x - rr, mot.y - lado * 12), L(mot.x - rr, mot.y + lado * 6)]
            pygame.draw.polygon(self.tela, (10, 10, 10), pts)
        # para-choque
        pc = w.cfg['para_choque']
        for lado in ('esquerdo', 'direito'):
            c = pc[lado]
            on = snap['pc'].get(pino_num(c['pino']))
            pygame.draw.line(self.tela, (255, 60, 60) if on else (160, 170, 190),
                             L(hl + 2, c['y_min']), L(hl + 2, c['y_max']), 4)
        # sensores de cor
        cc = w.cfg['cor_reflexao']
        for s_ in cc['tcs']:
            pygame.draw.circle(self.tela, (255, 255, 255), L(s_['x'], s_['y']), 3)
        for s_ in cc['ir']:
            pygame.draw.circle(self.tela, (255, 80, 80), L(s_['x'], s_['y']), 2)
        # seta de direção
        pygame.draw.line(self.tela, (255, 255, 255), L(0, 0), L(hl * 0.8, 0), 2)
        # LEDs: indicação de vítima (no meio, atrás) e iluminação de cada câmera
        leds = snap['leds']
        grupos = w.cfg.get('leds', {})
        vit = [i for i in grupos.get('vitima', []) if i < len(leds)]
        for k, i in enumerate(vit):
            yy = (k - (len(vit) - 1) / 2) * 26
            cor = leds[i] if any(leds[i]) else (50, 50, 50)
            pygame.draw.circle(self.tela, cor, L(-hl * 0.45, yy), max(5, int(11 * e)))
            pygame.draw.circle(self.tela, (0, 0, 0), L(-hl * 0.45, yy), max(5, int(11 * e)), 1)
        for cam in w.cfg['cameras']:
            idx = [i for i in grupos.get('camera_' + cam['nome'], []) if i < len(leds)]
            lado = 1 if cam['y'] > 0 else -1
            for k, i in enumerate(idx):
                xx = cam['x'] + (k - (len(idx) - 1) / 2) * 16
                cor = leds[i] if any(leds[i]) else (60, 60, 60)
                pygame.draw.circle(self.tela, cor, L(xx, cam['y'] + lado * 12), max(2, int(5 * e)))
        # raios dos VL53
        if self.mostrar_raios:
            for i, sc in enumerate(w.cfg['vl53']):
                r = snap['raios'].get(sc['nome'])
                if r is None:
                    continue
                p0, p1, d, t = r
                cor = COR_RAIOS[i % len(COR_RAIOS)]
                if snap['t'] - t > 0.5:
                    cor = tuple(c // 3 for c in cor)
                pygame.draw.line(self.tela, cor, self.T(p0.x, p0.y), self.T(p1.x, p1.y), 1)
                pygame.draw.circle(self.tela, cor, self.T(p1.x, p1.y), 3)
        # pose estimada pelo programa (simdebug)
        dbg = snap['debug']
        for (mx, my, cn) in dbg['marcas']:
            pygame.draw.circle(self.tela, CORES_DEBUG.get(cn, (250, 210, 40)), self.T(mx, my), 4)
        if dbg['pose']:
            dx, dy, da = dbg['pose']
            c2, s2 = math.cos(da), math.sin(da)

            def L2(lx, ly):
                return self.T(dx + lx * c2 - ly * s2, dy + lx * s2 + ly * c2)
            pts = [L2(hl, hw), L2(hl, -hw), L2(-hl, -hw), L2(-hl, hw)]
            pygame.draw.polygon(self.tela, (220, 90, 255), pts, 2)
            pygame.draw.line(self.tela, (220, 90, 255), L2(0, 0), L2(hl, 0), 2)

    # ------------------------------------------------------------------ painel
    def _desenha_botoes(self, linhas, x, y, larg):
        for linha in linhas:
            n = len(linha)
            bw = (larg - 6 * (n - 1)) / n
            for i, b in enumerate(linha):
                if b.acao == self._velocidade:
                    b.texto = f'Vel. {self.sim.fator:g}x'
                    vr = self.sim.vel_real
                    if (self.sim.programa_rodando() and not self.sim.pausado and
                            vr > 0.05 and vr < self.sim.fator * 0.85):
                        b.texto += f' (PC: {vr:.1f}x)'
                elif b.acao == self._modo_lop:
                    b.texto = 'LoP: reinicia prog.' if self.sim.modo_lop == 'reiniciar' else 'LoP: só botão'
                elif b.acao == self._auto_botao:
                    b.texto = 'Auto-botão: ' + ('sim' if self.sim.auto_botao else 'não')
                elif b.acao == self._escolhe_programa:
                    b.texto = 'Programa: ' + self._nome_programa() + '  (trocar)'
                b.rect = pygame.Rect(int(x + i * (bw + 6)), y, int(bw), 30)
                on = b.ligado() if b.ligado else False
                hover = b.rect.collidepoint(pygame.mouse.get_pos())
                cor = COR_BOTAO_ON if on else COR_BOTAO
                if hover:
                    cor = tuple(min(255, c + 20) for c in cor)
                pygame.draw.rect(self.tela, cor, b.rect, border_radius=6)
                t = self.f14.render(b.texto, True, COR_TEXTO)
                if t.get_width() > b.rect.w - 6:
                    t = self.f12.render(b.texto, True, COR_TEXTO)
                self.tela.blit(t, (b.rect.centerx - t.get_width() / 2, b.rect.centery - t.get_height() / 2))
            y += 36
        return y

    def _txt(self, s, x, y, fonte=None, cor=COR_TEXTO):
        t = (fonte or self.f14).render(s, True, cor)
        self.tela.blit(t, (x, y))
        return y + t.get_height() + 2

    def _le_sensores(self):
        w = self.sim.mundo
        with w.lock:
            d = {}
            d['vl53'] = [(sc['nome'], w.vl53(i)) for i, sc in enumerate(w.cfg['vl53'])]
            d['giro'] = w.giro()
            d['cor'] = w.cor_bytes()
            d['enc'] = [(m.nome, m.contagem_int()) for m in w.motores]
            d['cams'] = [(cam, v) for _, cam, _, v in w.vitimas_visiveis()]
            d['kits'] = w.kits_restantes
            d['pc'] = []
            for lado in ('esquerdo', 'direito'):
                p = pino_num(w.cfg['para_choque'][lado]['pino'])
                d['pc'].append(f"{lado} {'APERTADO' if w.gpio_nivel(p) == 0 else 'solto'}")
            d['led'] = w.led
            d['ilum'] = [c['nome'] for c in w.cfg['cameras'] if w.camera_iluminada(c['nome'])]
        self.leituras = d

    def _desenha_painel_sim(self, x, y, larg):
        s = self.sim
        j = s.juiz
        total, partes, info = j.placar()
        rest = max(0.0, 480.0 - j.tempo) if (j.ativo or j.fim) else 480.0
        cor_t = COR_DESTAQUE if rest > 60 else (255, 90, 90)
        self._txt(f'{int(rest // 60):02d}:{int(rest % 60):02d}', x, y, self.f30b, cor_t)
        tt = self.f30b.render(f'{total} pts', True, COR_TEXTO)
        self.tela.blit(tt, (x + larg - tt.get_width(), y))
        y += 40
        estado = 'rodada em andamento' if j.ativo and not j.fim else (f'fim: {j.fim}' if j.fim else 'rodada não iniciada')
        prog = 'programa rodando' if s.programa_rodando() else 'programa parado'
        y = self._txt(f'{estado}  •  {prog}', x, y, self.f12, COR_TEXTO2)
        partes_txt = '  '.join(f'{k} {v}' for k, v in partes.items() if v)
        y = self._txt(partes_txt or 'sem pontos ainda', x, y, self.f12)
        y = self._txt('  '.join(f'{k}={v}' for k, v in info.items()), x, y, self.f12, COR_TEXTO2)
        y += 4
        for (t, txt, p) in list(j.eventos)[-6:]:
            sp = f'{p:+d} ' if p else ''
            y = self._txt(f'{int(t // 60)}:{int(t % 60):02d} {sp}{txt}', x, y, self.f12,
                          (140, 230, 150) if p > 0 else (255, 130, 130) if p < 0 else COR_TEXTO2)
        y += 6
        pygame.draw.line(self.tela, (60, 64, 74), (x, y), (x + larg, y))
        y += 6
        d = self.leituras
        if not d:
            return
        y = self._txt('Sensores (leitura atual)', x, y, self.f16b)
        col = larg // 2
        yy = y
        for i, (n, v) in enumerate(d['vl53']):
            cor = COR_RAIOS[i % len(COR_RAIOS)]
            self._txt(f'{n}: {v} mm', x + (i % 2) * col, yy, self.f12, cor)
            if i % 2:
                yy += 16
        y = yy + (16 if len(d['vl53']) % 2 else 0) + 2
        g = d['giro']
        y = self._txt(f'Giro  X {g[0]}   Y {g[1]}   Z {g[2]}', x, y, self.f14)
        y = self._txt('Encoders  ' + '   '.join(f'{_sigla(n)} {c}' for n, c in d['enc']), x, y, self.f12)
        c = d['cor']
        y = self._txt(f'IR {c[0]:3d} {c[1]:3d} {c[2]:3d} {c[3]:3d}', x, y, self.f12)
        for k in range(3):
            rgbc = c[4 + 4 * k: 8 + 4 * k]
            r = pygame.Rect(x + k * 120, y, 14, 14)
            pygame.draw.rect(self.tela, tuple(rgbc[:3]), r)
            pygame.draw.rect(self.tela, (0, 0, 0), r, 1)
            self._txt(f'{rgbc[0]},{rgbc[1]},{rgbc[2]},{rgbc[3]}', x + k * 120 + 18, y, self.f12)
        y += 18
        w = s.mundo
        y = self._txt('Para-choque: ' + ', '.join(d['pc']), x, y, self.f12)
        y = self._txt(f'Kits restantes: {d["kits"]}   LED vítima: {d["led"]}', x, y, self.f12)
        y = self._txt('Câmeras com luz: ' + (', '.join(d['ilum']) or 'nenhuma (não detectam)'), x, y, self.f12)
        cams = ', '.join(f"{cam}: {M.SIMBOLO_LETRA.get(v.get('letra'), v.get('letra')) if v['tipo'] == 'letra' else 'cog.'} "
                         f"({M.status_vitima(v) or 'falsa'})" for cam, v in d['cams']) or 'nada'
        y = self._txt(f'Câmeras: {cams}', x, y, self.f12)
        if w.debug['texto']:
            y += 4
            y = self._txt('Programa (simdebug):', x, y, self.f12, (220, 90, 255))
            for linha in w.debug['texto'].split('\n')[:4]:
                y = self._txt(linha[:60], x, y, self.f12)
        y += 6
        ajuda = ['Arraste o robô com o mouse (programa parado). Q/E giram 90°, roda do mouse 5°.',
                 'Teclas: espaço pausa, B botão, L LoP, R raios, T trilha, C câmeras,',
                 'F ladrilhos flutuantes, 1–5 velocidade, O tela/teclado do brick (botões: clique ou F1–F4),',
                 'Enter responde o input() do programa.']
        for linha in _quebra(' '.join(ajuda), 64):
            y = self._txt(linha, x, y, self.f12, COR_TEXTO2)

    def _desenha_painel_ed(self, x, y, larg):
        m = self.sim.mundo.mapa
        y = self._txt(f'Mapa: {m.nome}  ({m.linhas} x {m.colunas})', x, y, self.f16b)
        y = self._txt(m.caminho or '(não salvo)', x, y, self.f12, COR_TEXTO2)
        y += 6
        dica = dict((k, d) for k, _, d in FERRAMENTAS)[self.ferramenta]
        for linha in _quebra(dica, 62):
            y = self._txt(linha, x, y, self.f12, COR_DESTAQUE)
        y += 8
        avisos = m.validar()
        if avisos:
            y = self._txt('Avisos:', x, y, self.f14, (255, 140, 140))
            for a in avisos[:8]:
                for linha in _quebra(a, 62):
                    y = self._txt(linha, x, y, self.f12, (255, 170, 170))
        y += 8
        txt = ('Ladrilho roxo (tecla F) = flutuante: vítimas valem mais. Lombadas e escadas: a direção '
               'NS/LO é o sentido em que o robô passa por elas. Pela regra, o robô começa num ladrilho comum '
               'e a zona de perigo é toda murada, com a entrada em piso vermelho. Botão direito apaga. '
               'Ctrl+S salva.')
        for linha in _quebra(txt, 64):
            y = self._txt(linha, x, y, self.f12, COR_TEXTO2)

    def _desenha_entrada(self):
        """Faixa no alto do console enquanto o programa espera o Enter de um input()."""
        prompt = self.sim.entrada
        if prompt is None:
            self.bot_enter.rect = pygame.Rect(0, 0, 0, 0)
            return
        lw, lh = self.tela.get_size()
        r = pygame.Rect(0, lh - CONSOLE, lw - PAINEL, FAIXA_ENTRADA)
        pygame.draw.rect(self.tela, COR_DESTAQUE, r)
        b = self.bot_enter
        b.rect = pygame.Rect(r.right - 130, r.y + 5, 120, 30)
        cor = (30, 30, 30) if b.rect.collidepoint(pygame.mouse.get_pos()) else (0, 0, 0)
        pygame.draw.rect(self.tela, cor, b.rect, border_radius=6)
        t = self.f14.render(b.texto, True, COR_DESTAQUE)
        self.tela.blit(t, (b.rect.centerx - t.get_width() / 2, b.rect.centery - t.get_height() / 2))
        txt = f'O programa está parado no input({prompt!r}): aperte Enter para continuar'
        t = self.f14.render(txt, True, (0, 0, 0))
        if t.get_width() > b.rect.x - 20:
            t = self.f12.render(txt, True, (0, 0, 0))
        self.tela.blit(t, (10, r.centery - t.get_height() / 2))

    def _desenha_console(self):
        lw, lh = self.tela.get_size()
        r = pygame.Rect(0, lh - CONSOLE, lw - PAINEL, CONSOLE)
        pygame.draw.rect(self.tela, (14, 15, 18), r)
        faixa = FAIXA_ENTRADA if self.sim.entrada is not None else 0    # aviso do input()
        linhas = list(self.sim.saida)[-((CONSOLE - 8 - faixa) // 15):]
        y = r.y + 4 + faixa
        for s in linhas:
            cor = (255, 140, 140) if ('Error' in s or 'Traceback' in s or 'Erro' in s) else (190, 200, 190)
            t = self.f12.render(s[:160], True, cor)
            self.tela.blit(t, (6, y))
            y += 15

    # ------------------------------------------------------------------ eventos do editor
    def _borda_mais_proxima(self, x, y):
        m = self.sim.mundo.mapa
        T = M.TAM
        fc = x / T
        fr = (m.altura_mm - y) / T
        dv = abs(fc - round(fc))
        dh = abs(fr - round(fr))
        if dv < dh:
            c, l = round(fc), math.floor(fr)
            if 0 <= l < m.linhas and 0 <= c <= m.colunas:
                return ('v', l, c, dv)
        else:
            l, c = round(fr), math.floor(fc)
            if 0 <= l <= m.linhas and 0 <= c < m.colunas:
                return ('h', l, c, dh)
        return None

    def _clique_editor(self, pos, botao, arrastando=False):
        m = self.sim.mundo.mapa
        x, y = self.W(*pos)
        lc = m.ladrilho_em(x, y)
        f = self.ferramenta
        if f == 'parede':
            b = self._borda_mais_proxima(x, y)
            if b is None or b[3] > 0.22:
                return
            tipo, l, c, _ = b
            grade = m.paredes_v if tipo == 'v' else m.paredes_h
            if not arrastando:
                self.arrasto = not grade[l][c] if botao == 1 else False
            grade[l][c] = self.arrasto
        elif lc is None:
            return
        elif f == 'piso' and not arrastando:
            if botao == 3:
                m.set_lad(*lc, piso=None)
            else:
                i = M.PISOS.index(m.piso(*lc))
                m.set_lad(*lc, piso=M.PISOS[(i + 1) % len(M.PISOS)])
        elif f == 'terreno' and not arrastando:
            atual = (m.terreno(*lc), m.lad(*lc).get('direcao') if m.terreno(*lc) in ('lombada', 'escada') else None)
            i = CICLO_TERRENO.index(atual) if atual in CICLO_TERRENO else 0
            ter, d = CICLO_TERRENO[0] if botao == 3 else CICLO_TERRENO[(i + 1) % len(CICLO_TERRENO)]
            m.set_lad(*lc, terreno=ter or None, direcao=d)
        elif f == 'zona':
            if not arrastando:
                self.arrasto = (not m.zona(*lc)) if botao == 1 else False
            m.set_lad(*lc, zona=self.arrasto)
        elif f == 'vitima' and not arrastando:
            self._clique_vitima(m, lc, x, y, botao)
        elif f == 'inicio' and not arrastando:
            if tuple(m.inicio) == lc:
                ordem = ['N', 'L', 'S', 'O']
                m.inicio_dir = ordem[(ordem.index(m.inicio_dir) + 1) % 4]
            else:
                m.inicio = lc
        self.sujo = True

    def _clique_vitima(self, m, lc, x, y, botao):
        l, c = lc
        T = M.TAM
        x0, y0 = c * T, m.altura_mm - (l + 1) * T
        dists = {'O': x - x0, 'L': x0 + T - x, 'S': y - y0, 'N': y0 + T - y}
        d = min(dists, key=dists.get)
        if dists[d] > T * 0.35:
            return
        pos = ((x - x0) if d in ('N', 'S') else (y - y0)) / T
        pos = round(min(max(pos, 0.15), 0.85), 2)
        existente = None
        for v in m.vitimas:
            if v['linha'] == l and v['coluna'] == c and v['parede'] == d:
                existente = v
        if botao == 3:
            if existente:
                m.vitimas.remove(existente)
            return
        if existente is None:
            i = -1
        else:
            chave = (existente['tipo'], existente.get('letra') if existente['tipo'] == 'letra' else M.status_vitima(existente))
            if existente['tipo'] == 'letra' and existente.get('letra') not in M.STATUS_LETRA:
                chave = ('letra', 'X')
            i = CICLO_VITIMA.index(chave) if chave in CICLO_VITIMA else -1
        tipo, val = CICLO_VITIMA[(i + 1) % len(CICLO_VITIMA)]
        if existente:
            m.vitimas.remove(existente)
        if tipo is None:
            return
        v = {'linha': l, 'coluna': c, 'parede': d, 'posicao': pos, 'tipo': tipo}
        if tipo == 'letra':
            v['letra'] = val
        else:
            v['aneis'] = M.gera_aneis(val)
        m.vitimas.append(v)

    # ------------------------------------------------------------------ eventos gerais
    def _evento(self, ev):
        s = self.sim
        if ev.type == pygame.VIDEORESIZE:
            self.sujo = True
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1 and s.entrada is not None and self.bot_enter.rect.collidepoint(ev.pos):
                self.bot_enter.acao()
                return
            if (self.modo == 'simular' and ev.button == 1
                    and self.brick.mouse_down(ev.pos, s.mundo, self._area())):
                return
            linhas = self.bot_sim if self.modo == 'simular' else self.bot_ed
            if ev.button == 1:
                for linha in linhas:
                    for b in linha:
                        if b.rect.collidepoint(ev.pos):
                            b.acao()
                            self.sujo = True
                            return
            if self._area().collidepoint(ev.pos):
                if self.modo == 'editar' and ev.button in (1, 3):
                    self._clique_editor(ev.pos, ev.button)
                elif self.modo == 'simular' and ev.button == 1 and not s.programa_rodando():
                    x, y = self.W(*ev.pos)
                    rx, ry, _ = s.mundo.pose()
                    if math.hypot(x - rx, y - ry) < 120:
                        self.arrasta_robo = (x - rx, y - ry)
                elif self.modo == 'simular' and ev.button in (4, 5) and not s.programa_rodando():
                    self._gira_robo(5 if ev.button == 4 else -5)
        elif ev.type == pygame.MOUSEBUTTONUP:
            self.brick.mouse_up(s.mundo)
            self.arrasto = None
            self.arrasta_robo = None
        elif ev.type == pygame.MOUSEMOTION:
            if self.modo == 'editar' and self.arrasto is not None and any(ev.buttons):
                if self.ferramenta in ('parede', 'zona'):
                    self._clique_editor(ev.pos, 1, arrastando=True)
            elif self.arrasta_robo is not None:
                x, y = self.W(*ev.pos)
                with s.mundo.lock:
                    _, _, a = s.mundo.pose()
                    s.mundo.posicionar(x - self.arrasta_robo[0], y - self.arrasta_robo[1], a)
                self.trilha = []
        elif ev.type == pygame.KEYDOWN:
            k = ev.key
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                s.responde_entrada()         # libera o input() do programa, se houver
            elif k == pygame.K_SPACE:
                self._pausa()
            elif k == pygame.K_b:
                s.apertar_botao()
            elif k == pygame.K_l:
                s.lop_manual()
            elif k == pygame.K_r:
                self.mostrar_raios = not self.mostrar_raios
            elif k == pygame.K_t:
                self.mostrar_trilha = not self.mostrar_trilha
                self.trilha = []
            elif k == pygame.K_c:
                self.mostrar_cameras = not self.mostrar_cameras
            elif k == pygame.K_f:
                self.mostrar_flutuantes = not self.mostrar_flutuantes
                self.sujo = True
            elif k == pygame.K_o and self.modo == 'simular':
                self.brick.visivel = not self.brick.visivel
            elif k == pygame.K_F5:
                self._iniciar()
            elif k in (pygame.K_q, pygame.K_e) and self.modo == 'simular' and not s.programa_rodando():
                self._gira_robo(90 if k == pygame.K_q else -90)
            elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                s.set_fator([0.25, 0.5, 1.0, 2.0, 4.0][k - pygame.K_1])
            elif k in (pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4):
                s.mundo.teclas_teclado.add(k - pygame.K_F1 + 1)
            elif k == pygame.K_s and (ev.mod & pygame.KMOD_CTRL) and self.modo == 'editar':
                self._salvar()
        elif ev.type == pygame.KEYUP:
            if ev.key in (pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4):
                s.mundo.teclas_teclado.discard(ev.key - pygame.K_F1 + 1)

    def _gira_robo(self, graus):
        w = self.sim.mundo
        with w.lock:
            x, y, a = w.pose()
            a = a + math.radians(graus)
            if abs(graus) == 90:
                a = round(a / (math.pi / 2)) * (math.pi / 2)
            w.posicionar(x, y, a)
            w.giro_reset_z()

    # ------------------------------------------------------------------ laço principal
    def rodar(self, quadros=None, captura=None):
        relogio = pygame.time.Clock()
        tam_ant = None
        n = 0
        while quadros is None or n < quadros:
            n += 1
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.sim.encerrar()
                    pygame.quit()
                    return
                self._evento(ev)
            if self.tela.get_size() != tam_ant:
                tam_ant = self.tela.get_size()
                self.sujo = True
            if self.sujo or self.camada is None:
                self._desenha_camada()
            self.tela.fill(COR_FUNDO)
            self.tela.blit(self.camada, (0, 0))
            w = self.sim.mundo
            with w.lock:
                snap = {
                    'pose': w.pose(),
                    'kits': list(w.kits),
                    'detritos': [list(map(tuple, v)) for v in w.detritos.values()],
                    'pc': {p: w.para_choque(p) for p in w.sensores_pc},
                    'leds': list(w.leds),
                    'raios': dict(w.raios),
                    't': w.t,
                    'debug': {'pose': w.debug['pose'], 'marcas': list(w.debug['marcas'])},
                }
            if self.mostrar_trilha:
                p = snap['pose'][:2]
                if not self.trilha or math.hypot(p[0] - self.trilha[-1][0], p[1] - self.trilha[-1][1]) > 8:
                    self.trilha.append(p)
                    self.trilha = self.trilha[-3000:]
            self._desenha_vitimas()
            self._desenha_robo(snap)
            if self.modo == 'simular':
                self.brick.desenha(self.tela, self.sim.mundo, self._area(), self.f12b, self.f11)
            # painel
            lw, lh = self.tela.get_size()
            pygame.draw.rect(self.tela, COR_PAINEL, (lw - PAINEL, 0, PAINEL, lh))
            x = lw - PAINEL + 14
            larg = PAINEL - 28
            y = 12
            y = self._txt('Rescue Maze — simulador Mariola', x, y, self.f16b, COR_DESTAQUE)
            y += 4
            if self.modo == 'simular':
                y = self._desenha_botoes(self.bot_sim, x, y, larg) + 4
                if time.time() - self.t_leituras > 0.15:
                    self.t_leituras = time.time()
                    self._le_sensores()
                self._desenha_painel_sim(x, y, larg)
            else:
                y = self._desenha_botoes(self.bot_ed, x, y, larg) + 4
                self._desenha_painel_ed(x, y, larg)
            self._desenha_console()
            self._desenha_entrada()
            if self.msg and time.time() - self.t_msg < 4:
                t = self.f14.render(self.msg, True, (0, 0, 0))
                r = t.get_rect(midtop=(self._area().centerx, 8)).inflate(16, 8)
                pygame.draw.rect(self.tela, COR_DESTAQUE, r, border_radius=6)
                self.tela.blit(t, (r.x + 8, r.y + 4))
            if self.sim.pausado:
                t = self.f22b.render('PAUSADO', True, COR_DESTAQUE)
                self.tela.blit(t, (16, 12))
            pygame.display.flip()
            relogio.tick(60)
        if captura:
            pygame.image.save(self.tela, captura)


def _sigla(nome):
    return ''.join(p[0].upper() for p in nome.replace('-', '_').split('_') if p)


def _quebra(s, n):
    palavras = s.split()
    linhas, atual = [], ''
    for p in palavras:
        if len(atual) + len(p) + 1 > n:
            linhas.append(atual)
            atual = p
        else:
            atual = (atual + ' ' + p).strip()
    if atual:
        linhas.append(atual)
    return linhas
