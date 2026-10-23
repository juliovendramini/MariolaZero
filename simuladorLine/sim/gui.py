"""Interface gráfica (pygame): simulação da Rescue Line e editor de mapas com a paleta de ladrilhos."""

import glob
import json
import math
import os
import time

import numpy as np
import pygame

from .painel_brick import PainelBrick

from . import camera_linha as CL
from . import ladrilhos as LT
from . import mapa as M
from .app import eh_pacoca
from .fisica import pino_num
from .ladrilhos import TAM

PAINEL = 430
CONSOLE = 140

COR_FUNDO = (32, 34, 40)
COR_PAINEL = (24, 26, 31)
COR_TEXTO = (225, 228, 235)
COR_TEXTO2 = (150, 156, 170)
COR_DESTAQUE = (255, 196, 61)
COR_BOTAO = (52, 56, 66)
COR_BOTAO_ON = (40, 120, 90)
COR_GRADE = (60, 64, 74)
CORES_DEBUG = {'amarelo': (250, 210, 40), 'verde': (60, 220, 90), 'vermelho': (240, 60, 60),
               'azul': (70, 140, 255), 'branco': (255, 255, 255), 'roxo': (200, 90, 255)}
COR_RAIOS = [(255, 120, 80), (255, 180, 80), (90, 200, 255), (120, 160, 255), (120, 255, 140),
             (255, 100, 200), (200, 200, 200), (255, 255, 120)]

FERRAMENTAS = [
    ('ladrilho', 'Ladrilho', 'Clique numa célula para pôr o ladrilho escolhido na paleta (abaixo). '
                             'Clicar de novo no mesmo ladrilho gira 90°. R ou roda do mouse giram o da paleta. '
                             'Botão direito apaga.'),
    ('girar', 'Girar', 'Clique: gira 90° no sentido horário. Botão direito: anti-horário.'),
    ('inicio', 'Início', 'Clique para marcar o ladrilho de início; clique de novo para trocar a direção de saída.'),
    ('checkpoint', 'Checkpoint', 'Clique para marcar/desmarcar checkpoint (não pode ter item pontuável).'),
    ('rampa', 'Rampa', 'Clique: sem rampa > sobe para N > L > S > O. Botão direito troca a inclinação '
                       '(10° a 25°). Depois da rampa o caminho segue na altura nova.'),
    ('lombada', 'Lombada', 'Clique: põe uma lombada (1 cm, atravessada no caminho) onde clicou. '
                           'Botão direito tira a mais perto.'),
    ('obstaculo', 'Obstáculo', 'Clique: põe um obstáculo em cima da linha mais perto. Botão direito tira. '
                               'Shift+clique troca entre solto e fixo; roda do mouse gira.'),
    ('detritos', 'Detritos', 'Clique: +1 palito solto no ladrilho. Botão direito: -1.'),
    ('area', 'Área resgate', 'Clique: põe a área de resgate (4 x 3 ladrilhos) com o canto de cima à esquerda '
                             'na célula. Roda do mouse: 4x3 / 3x4. Shift+clique dentro: põe/tira o obstáculo. '
                             'Botão direito dentro: tira a área.'),
    ('aberturas', 'Entrada/saída', 'Clique perto de uma parede da área: entrada (fita prata) ali. '
                                   'Botão direito: saída (fita preta). A linha precisa chegar/sair por elas.'),
    ('triangulos', 'Triângulos', 'Clique perto de um canto da área: triângulo verde ali. Botão direito: '
                                 'vermelho. Não pode ser no canto da entrada/saída.'),
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
    def __init__(self, sim, pasta_mapas, raiz=None):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption('Simulador RoboCupJunior Rescue Line — Mariola')
        info = pygame.display.Info()
        lw = min(1500, int((info.current_w or 1400) * 0.92))
        lh = min(940, int((info.current_h or 900) * 0.88))
        self.tela = pygame.display.set_mode((max(1000, lw), max(640, lh)), pygame.RESIZABLE)
        self.sim = sim
        self.cat = LT.catalogo()
        self.pasta_mapas = pasta_mapas
        self.raiz = raiz or os.path.dirname(pasta_mapas)
        self.f12 = _fonte(12)
        self.f14 = _fonte(14)
        self.f12b = _fonte(12, True)
        self.f11 = _fonte(11)
        self.f16b = _fonte(16, True)
        self.f22b = _fonte(22, True)
        self.f30b = _fonte(30, True)
        self.brick = PainelBrick()
        self.modo = 'simular'
        self.ferramenta = 'ladrilho'
        self.tipo_paleta = 'tile-0'
        self.rot_paleta = 0
        self.camada_ed = 0
        self.rol_paleta = 0
        self.rects_paleta = []
        self.rect_area_paleta = pygame.Rect(0, 0, 0, 0)
        self.arrasta_robo = None
        self.mostrar_raios = True
        self.mostrar_trilha = True
        self.mostrar_caminho = False
        self.mostrar_cam_linha = True
        self._cam_linha_sup = (None, None)
        self.trilha = []
        self.sujo = True
        self.camada = None
        self.leituras = {}
        self.t_leituras = 0
        self.msg = ''
        self.t_msg = 0
        self.cache_lad = {}
        self.cache_mini = {}
        self.versao_desenhada = -1
        self.hover = None
        self._monta_botoes()

    # ------------------------------------------------------------------ botões
    def _monta_botoes(self):
        s = self.sim
        self.bot_sim = [
            [Botao('▶ Iniciar rodada', self._iniciar, dica='F5'),
             Botao('■ Parar', self._parar),
             Botao('↺ Nova rodada', self._nova_rodada)],
            [Botao('LoP', s.lop_manual, dica='L'),
             Botao('Botão do robô', lambda: s.apertar_botao(), dica='B'),
             Botao('Pausar', self._pausa, ligado=lambda: s.pausado, dica='espaço'),
             Botao('', self._velocidade)],
            [Botao('', self._modo_lop),
             Botao('', self._auto_botao),
             Botao('', self._troca_robo)],
            [Botao('Editar mapa', lambda: self._muda_modo('editar')),
             Botao('Abrir mapa', self._abrir),
             Botao('Caminho (P)', self._alterna_caminho, ligado=lambda: self.mostrar_caminho)],
            [Botao('', self._escolhe_programa)],
        ]
        fer =[Botao(n, (lambda k=k: self._set_ferramenta(k)), ligado=(lambda k=k: self.ferramenta == k))
               for k, n, _ in FERRAMENTAS]
        self.bot_ed = [
            fer[:4], fer[4:8], fer[8:],
            [Botao('Camada −', lambda: self._camada(-1)), Botao('', None),
             Botao('Camada +', lambda: self._camada(1)), Botao('Caminho (P)', self._alterna_caminho,
                                                              ligado=lambda: self.mostrar_caminho)],
            [Botao('+Col esq', lambda: self._redim(1, 0, 1, 0)), Botao('+Col dir', lambda: self._redim(1, 0)),
             Botao('+Lin cima', lambda: self._redim(0, 1, 0, 1)), Botao('+Lin baixo', lambda: self._redim(0, 1))],
            [Botao('−Col esq', lambda: self._redim(-1, 0, -1, 0)), Botao('−Col dir', lambda: self._redim(-1, 0)),
             Botao('−Lin cima', lambda: self._redim(0, -1, 0, -1)), Botao('−Lin baixo', lambda: self._redim(0, -1))],
            [Botao('Novo', self._novo), Botao('Abrir', self._abrir), Botao('Salvar', self._salvar),
             Botao('Salvar como', lambda: self._salvar(True))],
            [Botao('Preencher branco', self._preenche), Botao('Voltar a simular', lambda: self._muda_modo('simular'))],
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

    def _parar(self):
        self.sim.parar_programa()
        with self.sim.mundo.lock:
            if self.sim.juiz.ativo and not self.sim.juiz.fim:
                self.sim.juiz.encerrar('parado pelo usuário')

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

    def _robos(self):
        return sorted(glob.glob(os.path.join(self.raiz, 'robo_*.json')))

    def _troca_robo(self):
        robos = self._robos()
        if not robos:
            return
        atual = self.sim.cfg.get('_arquivo')
        i = (robos.index(atual) + 1) % len(robos) if atual in robos else 0
        with open(robos[i], encoding='utf-8') as f:
            cfg = json.load(f)
        cfg['_arquivo'] = robos[i]
        self.sim.troca_robo(cfg)
        self.trilha = []
        self._aviso(f'robô: {cfg.get("nome", os.path.basename(robos[i]))}')

    def _escolhe_programa(self):
        """Abre o seletor de arquivo e troca o programa do robô (sem fechar o simulador)."""
        pacoca = eh_pacoca(self.sim.cfg)
        ext = '.ino' if pacoca else '.py'
        atual = self.sim.programa
        pasta = os.path.dirname(atual) if atual else self.raiz
        try:
            import tkinter as tk
            from tkinter import filedialog
            raiz = tk.Tk()
            raiz.withdraw()
            raiz.attributes('-topmost', True)
            tipos = [('Programa do Paçoca', '*.ino')] if pacoca else [('Programa Python', '*.py')]
            c = filedialog.askopenfilename(initialdir=pasta, filetypes=tipos,
                                           title='Escolha o programa do robô')
            raiz.destroy()
        except Exception:
            self._aviso('sem tkinter: use --programa ao abrir o simulador')
            return
        if not c:
            return
        if not c.lower().endswith(ext):
            outro = 'o Paçoca roda .ino' if pacoca else 'o Mariola roda .py'
            self._aviso(f'{os.path.basename(c)}: {outro} (troque o robô no botão "Robô")')
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

    def _alterna_caminho(self):
        self.mostrar_caminho = not self.mostrar_caminho
        self.sujo = True

    def _set_ferramenta(self, k):
        self.ferramenta = k

    def _camada(self, d):
        self.camada_ed = max(0, min(4, self.camada_ed + d))
        self.sujo = True

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
            w.mapa.mudou()
            w.corpo = None
            w.lad_centro = None
            w.construir()
            self.sim.juiz.reset()
            w.reset_rodada()
        self.trilha = []
        self.sujo = True

    def _redim(self, dl, da, dx=0, dy=0):
        m = self.sim.mundo.mapa
        m.redimensiona(m.largura + dl, m.altura + da, dx, dy)
        self.sujo = True

    def _novo(self):
        m = self.sim.mundo.mapa
        novo = M.Mapa(6, 5, 'novo')
        m.__dict__.update(novo.__dict__)
        m.mudou()
        self.sujo = True

    def _preenche(self):
        m = self.sim.mundo.mapa
        for x in range(m.largura):
            for y in range(m.altura):
                if not m.celula(x, y):
                    m.coloca(x, y, 0, 'branco')
        self.sujo = True

    def _dialogo(self, salvar):
        try:
            import tkinter as tk
            from tkinter import filedialog
            raiz = tk.Tk()
            raiz.withdraw()
            raiz.attributes('-topmost', True)
            tipos = [('Mapas Rescue Line', '*.json')]
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
            self.sim.parar_programa()
            self.sim.mundo.mapa.__dict__.update(novo.__dict__)
            self._aplica_mapa()
            av = getattr(novo, 'avisos_importacao', None)
            self._aviso(f'aberto {os.path.basename(c)}' + (f' ({len(av)} avisos de importação)' if av else ''))

    def _salvar(self, como=False):
        m = self.sim.mundo.mapa
        c = m.caminho
        if como or not c or os.path.basename(c).startswith('_'):
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

    # ------------------------------------------------------------------ geometria da tela
    def _area(self):
        lw, lh = self.tela.get_size()
        return pygame.Rect(0, 0, lw - PAINEL, lh - CONSOLE)

    def _calcula_escala(self):
        a = self._area()
        m = self.sim.mundo.mapa
        mg = 34
        self.esc = min((a.w - 2 * mg) / m.largura_mm, (a.h - 2 * mg) / m.altura_mm)
        self.ox = a.x + (a.w - m.largura_mm * self.esc) / 2
        self.oy = a.y + (a.h - m.altura_mm * self.esc) / 2
        self.H = m.altura_mm

    def T(self, x, y):
        return (self.ox + x * self.esc, self.oy + (self.H - y) * self.esc)

    def W(self, px, py):
        return ((px - self.ox) / self.esc, self.H - (py - self.oy) / self.esc)

    # ------------------------------------------------------------------ imagens dos ladrilhos
    def _sup_ladrilho(self, tipo, rot, px):
        k = (tipo, rot, px)
        s = self.cache_lad.get(k)
        if s is None:
            rgb = self.cat.rgb(tipo, rot)
            base = pygame.surfarray.make_surface(np.ascontiguousarray(rgb.transpose(1, 0, 2)))
            s = pygame.transform.smoothscale(base, (px, px))
            if len(self.cache_lad) > 600:
                self.cache_lad.clear()
            self.cache_lad[k] = s
        return s

    # ------------------------------------------------------------------ desenho do mapa
    def _desenha_camada(self):
        a = self._area()
        self._calcula_escala()
        sup = pygame.Surface((a.w, a.h))
        sup.fill(COR_FUNDO)
        m = self.sim.mundo.mapa
        e = self.esc
        px = max(4, int(math.ceil(TAM * e)))
        ed = self.modo == 'editar'
        # moldura do campo
        x0, y0 = self.T(0, m.altura_mm)
        pygame.draw.rect(sup, (44, 47, 55), (x0, y0, m.largura_mm * e, m.altura_mm * e))
        for x in range(m.largura + 1):
            pygame.draw.line(sup, COR_GRADE, self.T(x * TAM, 0), self.T(x * TAM, m.altura_mm))
        for y in range(m.altura + 1):
            pygame.draw.line(sup, COR_GRADE, self.T(0, y * TAM), self.T(m.largura_mm, y * TAM))
        ordem = sorted(m.ladrilhos.values(), key=lambda t: (t['z'], m.base(t)))
        for t in ordem:
            X0, Y0 = m.origem(t['x'], t['y'])
            tx, ty = self.T(X0, Y0 + TAM)
            r = pygame.Rect(round(tx), round(ty), px, px)
            img = self._sup_ladrilho(t['tipo'], t['rot'], px)
            outra_camada = ed and t['z'] != self.camada_ed
            em_cima = len(m.celula(t['x'], t['y'])) > 1 and t is not m.celula(t['x'], t['y'])[0]
            if outra_camada or em_cima:
                img = img.copy()
                img.set_alpha(90 if outra_camada else 175)
            if em_cima:
                sh = pygame.Surface(r.size, pygame.SRCALPHA)
                sh.fill((0, 0, 0, 70))
                sup.blit(sh, r.move(5, 5))
            sup.blit(img, r)
            if not t.get('_zona'):
                pygame.draw.rect(sup, (170, 170, 165), r, 1)
            self._desenha_itens(sup, m, t, r, e)
        if m.zona:
            self._desenha_zona(sup, m, ed)
        # início
        if m.inicio and m.inicio in m.ladrilhos:
            t = m.ladrilhos[m.inicio]
            cx, cy = self.T(*m.centro(t['x'], t['y']))
            rr = pygame.Rect(0, 0, px - 6, px - 6)
            rr.center = (cx, cy)
            pygame.draw.rect(sup, (40, 200, 110), rr, 3)
            saida = m.passos()[0]['saida'] if m.passos() and m.passos()[0]['saida'] else (m.inicio_dir or 'N')
            ang = math.radians(LT.ANGULO[saida])
            p2 = (cx + math.cos(ang) * px * 0.32, cy - math.sin(ang) * px * 0.32)
            pygame.draw.line(sup, (40, 200, 110), (cx, cy), p2, 4)
            pygame.draw.circle(sup, (40, 200, 110), (int(p2[0]), int(p2[1])), 6)
            t_ = self.f12.render('INÍCIO', True, (40, 200, 110))
            sup.blit(t_, (rr.x + 4, rr.y + 2))
        if self.mostrar_caminho or ed:
            self._desenha_caminho(sup, m, px)
        # coordenadas
        for c in range(m.largura):
            t_ = self.f12.render(str(c), True, COR_TEXTO2)
            x, y = self.T((c + 0.5) * TAM, m.altura_mm)
            sup.blit(t_, (x - t_.get_width() / 2, y - 18))
        for l_ in range(m.altura):
            t_ = self.f12.render(str(l_), True, COR_TEXTO2)
            x, y = self.T(0, m.altura_mm - (l_ + 0.5) * TAM)
            sup.blit(t_, (x - 16, y - t_.get_height() / 2))
        self.camada = sup
        self.sujo = False
        self.versao_desenhada = m.versao

    def _desenha_zona(self, sup, m, ed):
        """Paredes, triângulos e marcas da área de resgate (parte fixa)."""
        e = self.esc
        z = m.zona
        for nome, cor in (('verde', (0, 166, 81)), ('vermelho', (200, 20, 20))):
            tri = [self.T(*p) for p in m.triangulo(z[nome])]
            ov = pygame.Surface(sup.get_size(), pygame.SRCALPHA)
            pygame.draw.polygon(ov, cor + (70,), tri)
            sup.blit(ov, (0, 0))
            pygame.draw.line(sup, cor, tri[1], tri[2], max(3, int(M.ESPESSURA_TRIANGULO * e)))
        cor_p = tuple(z.get('cor_parede', [200, 200, 205]))
        borda = tuple(max(0, c - 90) for c in cor_p)
        lp = max(3, int(round(M.PAREDE_ESPESSURA * e)))
        for (x1, y1, x2, y2) in m.paredes_zona():
            a, b = self.T(x1, y1), self.T(x2, y2)
            pygame.draw.line(sup, borda, a, b, lp + 2)
            pygame.draw.line(sup, cor_p, a, b, max(1, lp - 2))
            for p in (a, b):
                pygame.draw.circle(sup, cor_p, (int(p[0]), int(p[1])), max(1, (lp - 2) // 2))
        X0, Y0, X1, Y1 = m.retangulo_zona()
        tt = self.f12.render('ÁREA DE RESGATE', True, (150, 150, 160))
        cx, cy = self.T((X0 + X1) / 2, (Y0 + Y1) / 2)
        sup.blit(tt, (cx - tt.get_width() / 2, cy - tt.get_height() / 2))
        if ed:
            for ab, txt, cor in ((z['entrada'], 'ENTRADA', (150, 160, 180)), (z['saida'], 'SAÍDA', (30, 30, 30))):
                (ax, ay), (dx, dy) = m.abertura_mundo(ab)
                p = self.T(ax - dx * 60, ay - dy * 60)
                t_ = self.f12.render(txt, True, cor)
                sup.blit(t_, (p[0] - t_.get_width() / 2, p[1] - t_.get_height() / 2))
            ob = z.get('obstaculo')
            if ob:
                self._desenha_caixa(sup, X0 + float(ob['u']), Y0 + float(ob['v']), 60, 60, 0, False)

    def _desenha_itens(self, sup, m, t, r, e):
        """Lombadas, rampa, checkpoint, detritos e obstáculos (no editor) de um ladrilho."""
        for (x1, y1, x2, y2) in m.linhas_lombada(t):
            pygame.draw.line(sup, (150, 100, 50), self.T(x1, y1), self.T(x2, y2), max(2, int(22 * e)))
            pygame.draw.line(sup, (200, 150, 90), self.T(x1, y1), self.T(x2, y2), max(1, int(6 * e)))
        rp = t.get('rampa')
        if rp:
            cx, cy = r.center
            ang = math.radians(LT.ANGULO[rp['sobe']])
            d = r.w * 0.36
            p1 = (cx - math.cos(ang) * d, cy + math.sin(ang) * d)
            p2 = (cx + math.cos(ang) * d, cy - math.sin(ang) * d)
            ov = pygame.Surface(r.size, pygame.SRCALPHA)
            ov.fill((70, 140, 255, 45))
            sup.blit(ov, r)
            pygame.draw.line(sup, (60, 120, 230), p1, p2, 4)
            for s_ in (-1, 1):
                a2 = ang + math.pi + s_ * 0.5
                pygame.draw.line(sup, (60, 120, 230), p2, (p2[0] + math.cos(a2) * 12, p2[1] - math.sin(a2) * 12), 4)
            tt = self.f12.render(f"rampa {rp.get('graus', 20):g}°", True, (40, 90, 200))
            sup.blit(tt, (r.x + 4, r.bottom - 16))
        if m.eh_gangorra(t):
            ang = self.sim.mundo.angs.get(m.chave(t), m.graus_gangorra(t))
            tt = self.f12.render(f'gangorra {ang:+.0f}°', True, (200, 90, 30))
            sup.blit(tt, (r.x + 4, r.y + 4))
            eixo = m.eixo_gangorra(t)
            a = math.radians(LT.ANGULO[eixo])
            ponta = (r.centerx + math.cos(a) * r.w * 0.45, r.centery - math.sin(a) * r.w * 0.45)
            cor = (230, 120, 40) if ang > 0 else (110, 110, 110)
            pygame.draw.circle(sup, cor, (int(ponta[0]), int(ponta[1])), max(4, int(r.w * 0.05)))
        h = m.base(t)
        if abs(h) > 5 and not rp:
            tt = self.f12.render(f'h {h:.0f} mm', True, (40, 90, 200))
            sup.blit(tt, (r.right - tt.get_width() - 4, r.bottom - 16))
        if t.get('checkpoint'):
            c = (r.x + max(8, int(45 * e)), r.y + max(8, int(45 * e)))
            pygame.draw.circle(sup, (235, 190, 40), c, max(6, int(35 * e)))
            pygame.draw.circle(sup, (120, 90, 10), c, max(6, int(35 * e)), 2)
            tt = self.f12.render('CP', True, (60, 40, 0))
            sup.blit(tt, (c[0] - tt.get_width() / 2, c[1] - tt.get_height() / 2))
        if self.modo == 'editar':
            for d in m.detritos_iniciais(t):
                pygame.draw.line(sup, (150, 110, 60), self.T(d[0], d[1]), self.T(d[2], d[3]), max(2, int(4 * e)))
            for ob in t.get('obstaculos', []):
                X, Y = m.mundo(t, float(ob['u']), float(ob['v']))
                self._desenha_caixa(sup, X, Y, float(ob.get('larg', 60)), float(ob.get('comp', 60)),
                                    math.radians(float(ob.get('ang', 0))), ob.get('fixo'))

    def _desenha_caixa(self, sup, X, Y, lw, lc, ang, fixo):
        c, s = math.cos(ang), math.sin(ang)
        pts = [self.T(X + a * c - b * s, Y + a * s + b * c)
               for a, b in ((-lw / 2, -lc / 2), (lw / 2, -lc / 2), (lw / 2, lc / 2), (-lw / 2, lc / 2))]
        pygame.draw.polygon(sup, (120, 72, 60) if not fixo else (90, 90, 100), pts)
        pygame.draw.polygon(sup, (30, 20, 20), pts, 2)
        pygame.draw.line(sup, (30, 20, 20), pts[0], pts[2], 1)
        pygame.draw.line(sup, (30, 20, 20), pts[1], pts[3], 1)

    def _desenha_caminho(self, sup, m, px):
        passos = m.passos()
        rot = {}
        for i, p in enumerate(passos):
            rot.setdefault(p['k'], []).append(str(i))
        for k, nums in rot.items():
            t = m.ladrilhos[k]
            cx, cy = self.T(*m.centro(t['x'], t['y']))
            txt = ','.join(nums)
            tt = self.f14.render(txt, True, (255, 255, 255))
            rr = tt.get_rect(center=(cx, cy + px * 0.28 * (1 if t['z'] == 0 else -1)))
            pygame.draw.rect(sup, (40, 80, 200) if t['z'] == 0 else (140, 60, 200), rr.inflate(8, 4), border_radius=5)
            sup.blit(tt, rr)

    # ------------------------------------------------------------------ robô
    def _desenha_robo(self, snap):
        e = self.esc
        w = self.sim.mundo
        tela = self.tela
        if self.mostrar_trilha and len(self.trilha) > 1:
            pygame.draw.lines(tela, (255, 160, 40), False, [self.T(x, y) for x, y in self.trilha], 2)
        for pts in snap['detritos']:
            for d in pts:
                pygame.draw.line(tela, (150, 110, 60), self.T(d[0], d[1]), self.T(d[2], d[3]), max(2, int(4 * e)))
        for (X, Y, ang, lw, lc, fixo) in snap['obst']:
            self._desenha_caixa(tela, X, Y, lw, lc, ang, fixo)
        for (X, Y) in snap['pilares']:
            r = pygame.Rect(0, 0, max(3, int(25 * e)), max(3, int(25 * e)))
            r.center = self.T(X, Y)
            pygame.draw.rect(tela, (90, 90, 110), r)
        zs = snap.get('zona')
        if zs:
            if zs['obst']:
                X, Y, ang = zs['obst']
                self._desenha_caixa(tela, X, Y, 60, 60, ang, False)
            for (fx, fy) in zs['falsas']:
                pygame.draw.circle(tela, (150, 150, 150), self.T(fx, fy), max(3, int(22 * e)), 2)
            for (bx, by, tipo) in zs['bolas']:
                self._desenha_bola(tela, self.T(bx, by), tipo, e)
            for (bx, by, tipo) in zs['salvas']:       # resgatadas: ficam desenhadas no triângulo
                self._desenha_bola(tela, self.T(bx, by), tipo, e)
                pygame.draw.circle(tela, (40, 200, 90), self.T(bx, by), max(4, int(26 * e)), 2)
        x, y, a = snap['pose']
        ca, sa = math.cos(a), math.sin(a)

        def L(lx, ly):
            return self.T(x + lx * ca - ly * sa, y + lx * sa + ly * ca)

        hl, hw = w.L / 2, w.W / 2
        corpo = [L(hl, hw), L(hl, -hw), L(-hl, -hw), L(-hl, hw)]
        ov = pygame.Surface(tela.get_size(), pygame.SRCALPHA)
        sombra = 120 if not snap['embaixo'] else 60
        pygame.draw.polygon(ov, (30, 35, 50, sombra), corpo)
        tela.blit(ov, (0, 0))
        pygame.draw.polygon(tela, (60, 140, 255) if not snap['fora'] else (255, 70, 70), corpo, 2)
        # rodas / esteiras
        rr = w.diametro / 2
        if w.esteira:
            for mot in w.motores:
                xs = [c[0] for c in mot.contatos]
                lado = 1 if mot.y > 0 else -1
                x1, x2 = min(xs) - rr, max(xs) + rr
                pts = [L(x1, mot.y + lado * 10), L(x2, mot.y + lado * 10), L(x2, mot.y - lado * 12),
                       L(x1, mot.y - lado * 12)]
                pygame.draw.polygon(tela, (15, 15, 15), pts)
                for k in range(int((x2 - x1) / 15) + 1):
                    xx = x1 + k * 15
                    pygame.draw.line(tela, (70, 70, 70), L(xx, mot.y + lado * 10), L(xx, mot.y - lado * 12), 1)
        else:
            for i, mot in enumerate(w.motores):
                lado = 1 if mot.y > 0 else -1
                pts = [L(mot.x + rr, mot.y + lado * 6), L(mot.x + rr, mot.y - lado * 10),
                       L(mot.x - rr, mot.y - lado * 10), L(mot.x - rr, mot.y + lado * 6)]
                no_ar = i < len(snap['suspenso']) and snap['suspenso'][i]
                pygame.draw.polygon(tela, (10, 10, 10), pts)
                if no_ar:      # roda no ar (o robô se apoiou em outro ponto)
                    pygame.draw.polygon(tela, (255, 170, 40), pts, 2)
        # para-choque
        pc = w.cfg.get('para_choque')
        if pc:
            for lado in ('esquerdo', 'direito'):
                c = pc[lado]
                on = snap['pc'].get(pino_num(c['pino']))
                pygame.draw.line(tela, (255, 60, 60) if on else (160, 170, 190),
                                 L(hl + 2, c['y_min']), L(hl + 2, c['y_max']), 4)
        # sensor de linha: cada ITR8307 (cinza = leitura) e cada TCS (cor = leitura)
        ul = snap['leitura']
        sl = w.sensor
        if ul and sl and len(ul['ir12']) == len(sl.ir):
            for i, (lx, ly) in enumerate(sl.ir):
                v = max(0, min(255, int(ul['ir12'][i] * 2.2)))
                pygame.draw.circle(tela, (v, v, v), L(lx, ly), max(2, int(2.6 * e) + 1))
                pygame.draw.circle(tela, (255, 70, 70), L(lx, ly), max(2, int(2.6 * e) + 1), 1)
            for j, (lx, ly) in enumerate(sl.tcs):
                rgb = tuple(max(0, min(255, int(v * 1.8))) for v in ul['rgbc'][j][:3])
                pygame.draw.circle(tela, rgb, L(lx, ly), max(3, int(4.5 * e) + 1))
                pygame.draw.circle(tela, (255, 255, 255), L(lx, ly), max(3, int(4.5 * e) + 1), 1)
        pygame.draw.line(tela, (255, 255, 255), L(0, 0), L(hl * 0.55, 0), 2)
        if zs and zs.get('mec'):
            self._desenha_mecanismo(tela, L, zs['mec'], e, w)
        if zs and zs.get('cam') is not None:
            self._desenha_camera(tela, L, zs, e, w)
        led = snap['led']
        if any(led):
            pygame.draw.circle(tela, led, L(-hl * 0.5, 0), max(4, int(10 * e)))
        if self.mostrar_raios:
            for i, sc in enumerate(w.cfg['vl53']):
                rv = snap['raios'].get(sc['nome'])
                if rv is None:
                    continue
                p0, p1, d, t = rv
                cor = COR_RAIOS[i % len(COR_RAIOS)]
                if snap['t'] - t > 0.5:
                    cor = tuple(c // 3 for c in cor)
                if d is None:      # nada no alcance: só um toco na direção do feixe
                    p1 = p0 + (p1 - p0).normalized() * 60
                    pygame.draw.line(tela, cor, self.T(p0.x, p0.y), self.T(p1.x, p1.y), 1)
                    continue
                pygame.draw.line(tela, cor, self.T(p0.x, p0.y), self.T(p1.x, p1.y), 1)
                pygame.draw.circle(tela, cor, self.T(p1.x, p1.y), 3)
        dbg = snap['debug']
        for (mx, my, cn) in dbg['marcas']:
            pygame.draw.circle(tela, CORES_DEBUG.get(cn, (250, 210, 40)), self.T(mx, my), 4)
        if dbg['pose']:
            dx, dy, da = dbg['pose']
            c2, s2 = math.cos(da), math.sin(da)

            def L2(lx, ly):
                return self.T(dx + lx * c2 - ly * s2, dy + lx * s2 + ly * c2)
            pts = [L2(hl, hw), L2(hl, -hw), L2(-hl, -hw), L2(-hl, hw)]
            pygame.draw.polygon(tela, (220, 90, 255), pts, 2)

    def _desenha_bola(self, tela, c, tipo, e):
        r = max(3, int(22.5 * e))
        if tipo == 'viva':
            pygame.draw.circle(tela, (175, 182, 192), c, r)
            pygame.draw.circle(tela, (240, 244, 250), (c[0] - r // 3, c[1] - r // 3), max(1, r // 3))
            pygame.draw.circle(tela, (90, 95, 105), c, r, 1)
        else:
            pygame.draw.circle(tela, (25, 25, 25), c, r)
            pygame.draw.circle(tela, (90, 90, 90), c, r, 1)

    def _desenha_mecanismo(self, tela, L, mec, e, w):
        cfg = w.cfg['resgate']
        g = cfg.get('garra', {})
        xb = float(g.get('x_base', w.L / 2))
        comp = float(g.get('comprimento', 60))
        a = max(0.0, min(1.0, mec['braco']))
        # vista de cima: a garra aponta para a frente no chão e "deita" sobre o robô no alto
        ponta = xb + comp * (1.0 - 2.0 * a)
        cor = (255, 150, 40) if a < 0.12 else (240, 200, 110)
        larg = max(2, int(6 * e))
        for lado in ('esq', 'dir'):
            yy = mec['y_' + lado]
            pygame.draw.line(tela, cor, L(xb, yy), L(ponta, yy), larg)
        pygame.draw.line(tela, cor, L(xb, mec['y_esq']), L(xb, mec['y_dir']), max(2, int(4 * e)))
        pygame.draw.circle(tela, (90, 70, 40), L(xb, 0), max(2, int(5 * e)))
        if mec['garra']:
            self._desenha_bola(tela, L((xb + ponta) / 2, mec['yb']), mec['garra'], e)
        # caçamba (dois lados) na traseira
        hl = w.L / 2
        for lado, sinal in (('esq', 1), ('dir', -1)):
            r0 = [L(-hl + 8, sinal * 6), L(-hl + 52, sinal * 6), L(-hl + 52, sinal * 58), L(-hl + 8, sinal * 58)]
            aberto = (mec['porta'] <= -0.6 and lado == 'esq') or (mec['porta'] >= 0.6 and lado == 'dir')
            pygame.draw.polygon(tela, (255, 220, 120) if aberto else (120, 125, 140), r0, 2)
            for k, tipo in enumerate(mec['cacamba'][lado]):
                self._desenha_bola(tela, L(-hl + 30, sinal * (20 + 22 * k)), tipo, e * 0.7)

    def _desenha_camera(self, tela, L, zs, e, w):
        c = w.resgate._cfg_cam()
        cx, cy = float(c['x']), float(c['y'])
        meia = math.radians(float(c['fov_graus'])) / 2
        tapada = zs['mec'] and zs['mec']['braco'] < 0.12
        cor = (255, 80, 80) if tapada else (120, 200, 255)
        Lc = 260
        for s_ in (-1, 1):
            pygame.draw.line(tela, cor, L(cx, cy), L(cx + Lc * math.cos(s_ * meia), cy + Lc * math.sin(s_ * meia)), 1)
        for tipo, (t, dets) in zs['cam'].items():
            if zs['t'] - t > 0.6:
                continue
            for d in dets:
                ang = math.radians(d['angulo'])
                dist = d['distancia']
                p = L(cx + dist * math.cos(ang), cy + dist * math.sin(ang))
                if tipo == 'vitimas':
                    cd = (255, 230, 60) if d['tipo'] == 'viva' else (255, 60, 220)
                    pygame.draw.circle(tela, cd, p, max(4, int(26 * e)), 2)
                else:
                    cd = (0, 220, 100) if d['cor'] == 'verde' else (255, 60, 60)
                    pygame.draw.line(tela, cd, L(cx, cy), p, 1)
                    pygame.draw.circle(tela, cd, p, 4)

    def _desenha_cam_linha(self):
        """Último quadro que o programa leu da câmera de linha (canto de baixo, à esquerda)."""
        q = getattr(self.sim.mundo, 'cam_linha_quadro', None)
        if q is None:
            return
        area = self._area()
        if not self.mostrar_cam_linha:
            t = self.f11.render('C: mostra a câmera de linha', True, COR_TEXTO2)
            self.tela.blit(t, (area.x + 10, area.bottom - t.get_height() - 6))
            return
        if self._cam_linha_sup[0] is not q:
            _, geo, mats = q
            img = CL.compoe(geo, mats)[..., ::-1]          # BGR -> RGB
            sup = pygame.surfarray.make_surface(np.ascontiguousarray(img.transpose(1, 0, 2)))
            esc = 208.0 / max(geo.w, geo.h)
            sup = pygame.transform.smoothscale(sup, (int(geo.w * esc), int(geo.h * esc)))
            self._cam_linha_sup = (q, sup)
        sup = self._cam_linha_sup[1]
        r = pygame.Rect(area.x + 10, area.bottom - sup.get_height() - 30, sup.get_width() + 12,
                        sup.get_height() + 22)
        pygame.draw.rect(self.tela, (16, 17, 20), r, border_radius=8)
        self.tela.blit(self.f11.render('câmera de linha (C esconde)', True, COR_TEXTO2), (r.x + 6, r.y + 3))
        self.tela.blit(sup, (r.x + 6, r.y + 16))

    def _redesenha_pontes(self, snap):
        """Robô passando por baixo de uma ponte: a ponte fica por cima dele (transparente)."""
        m = self.sim.mundo.mapa
        px = max(4, int(math.ceil(TAM * self.esc)))
        x, y, _ = snap['pose']
        c = m.celula_de(x, y)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if c is None:
                    return
                cel = m.celula(c[0] + dx, c[1] + dy)
                for t in cel[1:]:
                    X0, Y0 = m.origem(t['x'], t['y'])
                    tx, ty = self.T(X0, Y0 + TAM)
                    img = self._sup_ladrilho(t['tipo'], t['rot'], px).copy()
                    img.set_alpha(150)
                    self.tela.blit(img, (round(tx), round(ty)))

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
                elif b.acao == self._troca_robo:
                    b.texto = 'Robô: ' + str(self.sim.cfg.get('nome', '?')).split(' ')[0]
                elif b.acao == self._escolhe_programa:
                    b.texto = 'Programa: ' + self._nome_programa() + '  (trocar)'
                elif b.acao is None:
                    b.texto = f'camada {self.camada_ed}'
                b.rect = pygame.Rect(int(x + i * (bw + 6)), y, int(bw), 28)
                on = b.ligado() if b.ligado else False
                hover = b.rect.collidepoint(pygame.mouse.get_pos()) and b.acao is not None
                cor = COR_BOTAO_ON if on else COR_BOTAO
                if b.acao is None:
                    cor = COR_PAINEL
                if hover:
                    cor = tuple(min(255, c + 20) for c in cor)
                pygame.draw.rect(self.tela, cor, b.rect, border_radius=6)
                t = self.f14.render(b.texto, True, COR_TEXTO)
                if t.get_width() > b.rect.w - 6:
                    t = self.f12.render(b.texto, True, COR_TEXTO)
                self.tela.blit(t, (b.rect.centerx - t.get_width() / 2, b.rect.centery - t.get_height() / 2))
            y += 33
        return y

    def _txt(self, s, x, y, fonte=None, cor=COR_TEXTO):
        t = (fonte or self.f14).render(s, True, cor)
        self.tela.blit(t, (x, y))
        return y + t.get_height() + 2

    def _le_sensores(self):
        w = self.sim.mundo
        with w.lock:
            ruido = w.estado_ruido()     # a tela não pode gastar o ruído do programa
            raios = dict(w.raios)
            d = {}
            d['vl53'] = [(sc['nome'], w.vl53(i)) for i, sc in enumerate(w.cfg['vl53'])]
            d['giro'] = w.giro()
            d['linha'] = w.leitura_sensor()
            d['enc'] = [(m.nome, f'{m.dc_coef()[0] * 100:+.0f}%' if m.dc else m.contagem_int()) for m in w.motores]
            d['dc'] = any(m.dc for m in w.motores)
            d['pc'] = []
            pc = w.cfg.get('para_choque')
            if pc:
                for lado in ('esquerdo', 'direito'):
                    p = pino_num(pc[lado]['pino'])
                    d['pc'].append(f"{lado} {'APERTADO' if w.gpio_nivel(p) == 0 else 'solto'}")
            d['tcs'] = [(sc['nome'], w.resgate.tcs(i)) for i, sc in enumerate(w.cfg.get('tcs_i2c', []))]
            d['h'] = w.h_centro
            d['lad'] = (w.lad_centro['x'], w.lad_centro['y'], w.lad_centro['z']) if w.lad_centro else None
            w.restaura_ruido(ruido)
            w.raios = raios
        self.leituras = d

    def _desenha_painel_sim(self, x, y, larg):
        s = self.sim
        j = s.juiz
        total, partes, info = j.placar()
        dur = s.mundo.mapa.tempo
        rest = max(0.0, dur - j.tempo) if (j.ativo or j.fim) else dur
        cor_t = COR_DESTAQUE if rest > 60 else (255, 90, 90)
        self._txt(f'{int(rest // 60):02d}:{int(rest % 60):02d}', x, y, self.f30b, cor_t)
        tt = self.f30b.render(f'{total} pts', True, COR_TEXTO)
        self.tela.blit(tt, (x + larg - tt.get_width(), y))
        y += 40
        estado = 'rodada em andamento' if j.ativo and not j.fim else (f'fim: {j.fim}' if j.fim else 'rodada não iniciada')
        prog = 'programa rodando' if s.programa_rodando() else 'programa parado'
        y = self._txt(f'{estado}  •  {prog}', x, y, self.f12, COR_TEXTO2)
        partes_txt = '  '.join(f'{k} {v}' for k, v in partes.items() if v)
        for linha in _quebra(partes_txt, 66) or ['sem pontos ainda']:
            y = self._txt(linha, x, y, self.f12)
        prox_cp = next((c for c in j.cps if c > j.ultimo_cp), j.idx_chegada)
        y = self._txt(f"LoP {info['LoP']}   passo {info['passo']}   último CP {j.ultimo_cp}   próximo {prox_cp}",
                      x, y, self.f12, COR_TEXTO2)
        y += 2
        for (t, txt, p) in list(j.eventos)[-6:]:
            sp = f'{p:+d} ' if p else ''
            y = self._txt(f'{int(t // 60)}:{int(t % 60):02d} {sp}{txt}'[:70], x, y, self.f12,
                          (140, 230, 150) if p > 0 else (255, 130, 130) if 'LoP' in txt else COR_TEXTO2)
        y += 4
        pygame.draw.line(self.tela, (60, 64, 74), (x, y), (x + larg, y))
        y += 6
        d = self.leituras
        if not d:
            return
        sl = self.sim.mundo.sensor
        ln = d['linha'] if sl else None      # (logo depois de trocar de robô a leitura é do robô antigo)
        if ln:
            y = self._painel_linha(x, y, larg, ln)
        else:
            y = self._txt('Sem sensor de linha' + (' (câmera de linha: tecla C)' if self.sim.cfg.get('camera_linha')
                                                   else ''), x, y, self.f14)
        g = d['giro']
        y = self._txt(f'Giro  X {g[0]}   Y {g[1]}   Z {g[2]}      altura {d["h"]:.0f} mm', x, y, self.f12)
        ds = [v for v in ln.get('distancias', [])[:len(sl.ir)] if v == v] if ln else []
        if ds:
            nom = sl.altura
            cor = COR_TEXTO if max(abs(v - nom) for v in ds) < 1.5 else COR_DESTAQUE
            y = self._txt(f'Sensor IR até o piso: {min(ds):.1f} a {max(ds):.1f} mm (normal {nom:g})',
                          x, y, self.f12, cor)
        rotulo = 'Motores (tensão média)  ' if d.get('dc') else 'Encoders  '
        y = self._txt(rotulo + '   '.join(f'{_sigla(n)} {c}' for n, c in d['enc']), x, y, self.f12)
        col = larg // 2
        yy = y
        for i, (n, v) in enumerate(d['vl53']):
            cor = COR_RAIOS[i % len(COR_RAIOS)]
            self._txt(f'{n}: {v} mm', x + (i % 2) * col, yy, self.f12, cor)
            if i % 2:
                yy += 15
        y = yy + (15 if len(d['vl53']) % 2 else 0)
        if d['pc']:
            y = self._txt('Para-choque: ' + ', '.join(d['pc']), x, y, self.f12)
        if d.get('tcs'):
            y = self._txt('TCS  ' + '   '.join(f'{n}: ' + ','.join(str(int(v * 1000)) for v in rgbc)
                                              for n, rgbc in d['tcs']), x, y, self.f12)
        zs = (getattr(self, '_snap', None) or {}).get('zona')
        if zs:
            y = self._painel_resgate(x, y, zs)
        w = s.mundo
        if w.debug['texto']:
            y += 2
            y = self._txt('Programa (simdebug):', x, y, self.f12, (220, 90, 255))
            for linha in w.debug['texto'].split('\n')[:3]:
                y = self._txt(linha[:66], x, y, self.f12)
        y += 4
        ajuda = ('Arraste o robô com o mouse (programa parado); Q/E giram 90°, roda do mouse 5°. '
                 'Teclas: espaço pausa, B botão, L LoP, R raios, T trilha, P caminho, 1–5 velocidade, F5 inicia, '
                 'O tela/teclado do brick (botões: clique ou F1–F4).')
        for linha in _quebra(ajuda, 70):
            y = self._txt(linha, x, y, self.f12, COR_TEXTO2)

    def _painel_linha(self, x, y, larg, ln):
        y = self._txt('Sensor de linha (bytes do Pro1616)', x, y, self.f16b)
        # 4 canais de reflexão
        bw = (larg - 18) / 4
        for k, v in enumerate(ln['bytes'][:4]):
            r = pygame.Rect(int(x + k * (bw + 6)), y, int(bw), 34)
            pygame.draw.rect(self.tela, (50, 52, 60), r)
            hgt = int(min(1.0, v / 130.0) * 34)
            pygame.draw.rect(self.tela, (210, 210, 210), (r.x, r.bottom - hgt, r.w, hgt))
            t = self.f14.render(f'IR{k} {v}', True, (255, 90, 90) if v < 50 else (20, 20, 20) if hgt > 22 else COR_TEXTO)
            self.tela.blit(t, (r.centerx - t.get_width() / 2, r.y + 2))
        y += 38
        # 12 ITR8307 individuais
        bw2 = (larg - 11 * 2) / 12
        for k, v in enumerate(ln['ir12']):
            r = pygame.Rect(int(x + k * (bw2 + 2)), y, int(bw2), 12)
            c = max(0, min(255, int(v * 2.2)))
            pygame.draw.rect(self.tela, (c, c, c), r)
        y += 15
        for k in range(3):
            rgbc = ln['bytes'][4 + 4 * k: 8 + 4 * k]
            r = pygame.Rect(x + k * 138, y, 16, 16)
            pygame.draw.rect(self.tela, tuple(min(255, int(v * 1.8)) for v in rgbc[:3]), r)
            pygame.draw.rect(self.tela, (0, 0, 0), r, 1)
            self._txt(f'{rgbc[0]},{rgbc[1]},{rgbc[2]},{rgbc[3]}', x + k * 138 + 20, y, self.f12)
        return y + 20

    def _painel_resgate(self, x, y, zs):
        mec = zs.get('mec')
        if zs['resgatadas']:
            y = self._txt('Resgatadas: ' + ', '.join(f'{t} ({tri})' for t, tri in zs['resgatadas']), x, y,
                          self.f12, (140, 230, 150))
        if mec:
            pd = mec['porta']
            porta = 'soltando esq' if pd <= -0.6 else 'soltando dir' if pd >= 0.6 else 'fechada'
            cac = '  '.join(f"{k}: {','.join(v) or '-'}" for k, v in mec['cacamba'].items())
            y = self._txt(f"Braço {max(0.0, min(1.0, mec['braco'])) * 100:.0f}%   garra: {mec['garra'] or 'vazia'}   porta {porta}   "
                          f"caçamba {cac}", x, y, self.f12)
            partes = []
            for n, (pot, alvo, potn, trav, pwm, idp) in mec['servos'].items():
                est = 'TRAVA' if trav else ('on' if pwm else 'off')
                partes.append(f'{n}#{idp} {pot}>{alvo} {est}')
            for linha in _quebra('   '.join(partes), 60):
                y = self._txt(linha, x, y, self.f12, COR_TEXTO2)
        if zs.get('cam') is not None:
            cam = zs['cam']
            txt = []
            for tipo in ('vitimas', 'triangulos'):
                if tipo in cam:
                    t, dets = cam[tipo]
                    if tipo == 'vitimas':
                        txt.append('vítimas ' + (', '.join(f"{d['tipo'][0]}{d['angulo']:+.0f}°/{d['distancia']}"
                                                          for d in dets) or '-'))
                    else:
                        txt.append('triâng. ' + (', '.join(f"{'VD' if d['cor'] == 'verde' else 'VM'}{d['angulo']:+.0f}°/{d['distancia']}"
                                                          for d in dets) or '-'))
            y = self._txt('Câmera: ' + ('   '.join(txt) or 'sem pedidos'), x, y, self.f12, (120, 200, 255))
        return y

    def _desenha_painel_ed(self, x, y, larg):
        m = self.sim.mundo.mapa
        y = self._txt(f'Mapa: {m.nome}  ({m.largura} x {m.altura})  camada {self.camada_ed}', x, y, self.f16b)
        y = self._txt((m.caminho or '(não salvo)')[-70:], x, y, self.f12, COR_TEXTO2)
        dica = dict((k, d) for k, _, d in FERRAMENTAS)[self.ferramenta]
        for linha in _quebra(dica, 70):
            y = self._txt(linha, x, y, self.f12, COR_DESTAQUE)
        if self.hover:
            t = self.hover
            it = m.itens(t)
            s = f"({t['x']},{t['y']},{t['z']}) {t['tipo']} {t['rot']}°  h {m.base(t):.0f}"
            if it:
                s += '  ' + ' '.join(f'{k}{"x" + str(v) if v > 1 else ""}' for k, v in it.items())
            idx = m.indices(m.chave(t))
            if idx:
                s += f'  passo {",".join(map(str, idx))}'
            y = self._txt(s[:74], x, y, self.f12)
        avisos = m.validar()
        if avisos:
            for a in avisos[:4]:
                for linha in _quebra(a, 70):
                    y = self._txt(linha, x, y, self.f12, (255, 170, 170))
        else:
            y = self._txt(f'Caminho ok: {len(m.passos())} passos até a chegada.', x, y, self.f12, (140, 230, 150))
        y += 4
        self._desenha_paleta(x, y, larg)

    def _desenha_paleta(self, x, y, larg):
        lw, lh = self.tela.get_size()
        nomes = self.cat.nomes()
        # ladrilho escolhido (com a rotação)
        img = self._sup_ladrilho(self.tipo_paleta, self.rot_paleta, 64)
        self.tela.blit(img, (x, y))
        pygame.draw.rect(self.tela, COR_DESTAQUE, (x, y, 64, 64), 2)
        info = self.cat.info(self.tipo_paleta)
        y2 = self._txt(f'{self.tipo_paleta}  {self.rot_paleta}°', x + 72, y, self.f14)
        extra = []
        if info.get('intersecoes'):
            extra.append(f"interseção x{info['intersecoes']}")
        if info.get('gaps'):
            extra.append('gap')
        if info.get('descricao'):
            extra.append(info['descricao'])
        y2 = self._txt(', '.join(extra) or 'linha', x + 72, y2, self.f12, COR_TEXTO2)
        self._txt('R / roda do mouse no mapa: girar', x + 72, y2, self.f12, COR_TEXTO2)
        y += 70
        cel = 58
        cols = max(1, int((larg + 4) // cel))
        area = pygame.Rect(x, y, larg, lh - y - 6)
        self.rect_area_paleta = area
        linhas = (len(nomes) + cols - 1) // cols
        max_rol = max(0, linhas * cel - area.h)
        self.rol_paleta = max(0, min(self.rol_paleta, max_rol))
        self.tela.set_clip(area)
        self.rects_paleta = []
        for i, n in enumerate(nomes):
            cx = x + (i % cols) * cel
            cy = y + (i // cols) * cel - self.rol_paleta
            r = pygame.Rect(cx, cy, cel - 4, cel - 4)
            if r.bottom < area.y or r.y > area.bottom:
                continue
            self.tela.blit(self._sup_ladrilho(n, 0, cel - 4), r)
            if n == self.tipo_paleta:
                pygame.draw.rect(self.tela, COR_DESTAQUE, r.inflate(2, 2), 3)
            elif r.collidepoint(pygame.mouse.get_pos()):
                pygame.draw.rect(self.tela, (120, 180, 255), r.inflate(2, 2), 2)
            self.rects_paleta.append((r, n))
        self.tela.set_clip(None)
        if max_rol:
            barra = area.h * area.h / (linhas * cel)
            yb = area.y + (area.h - barra) * self.rol_paleta / max_rol
            pygame.draw.rect(self.tela, (90, 94, 104), (area.right - 4, yb, 4, barra), border_radius=2)

    def _desenha_console(self):
        lw, lh = self.tela.get_size()
        r = pygame.Rect(0, lh - CONSOLE, lw - PAINEL, CONSOLE)
        pygame.draw.rect(self.tela, (14, 15, 18), r)
        linhas = list(self.sim.saida)[-((CONSOLE - 8) // 15):]
        y = r.y + 4
        for s in linhas:
            cor = (255, 140, 140) if ('Error' in s or 'Traceback' in s or 'Erro' in s) else (190, 200, 190)
            t = self.f12.render(s[:170], True, cor)
            self.tela.blit(t, (6, y))
            y += 15

    # ------------------------------------------------------------------ editor
    def _lad_editor(self, pos):
        """(célula, ladrilho da camada atual ou None, X, Y)."""
        m = self.sim.mundo.mapa
        X, Y = self.W(*pos)
        c = m.celula_de(X, Y)
        if c is None:
            return None, None, X, Y
        return c, m.lad(c[0], c[1], self.camada_ed), X, Y

    def _clique_editor(self, pos, botao, mods=0):
        m = self.sim.mundo.mapa
        c, t, X, Y = self._lad_editor(pos)
        if c is None:
            return
        f = self.ferramenta
        z = self.camada_ed
        if f in ('area', 'aberturas', 'triangulos'):
            self._clique_zona(f, c, X, Y, botao, mods)
            m.mudou()
            self.sujo = True
            return
        if m.zona and m.eh_zona(m.lad(c[0], c[1], 0)) and f != 'ladrilho':
            self._aviso('célula da área de resgate (use as ferramentas da área)')
            return
        if f == 'ladrilho' and m.zona and (c[0], c[1]) in m.celulas_zona():
            self._aviso('célula da área de resgate: tire a área antes (botão direito com a ferramenta Área)')
            return
        if f == 'ladrilho':
            if botao == 3:
                if t:
                    m.remove(*c, z)
            elif t and t['tipo'] == self.tipo_paleta:
                t['rot'] = (t['rot'] + 90) % 360
            else:
                m.coloca(c[0], c[1], z, self.tipo_paleta, self.rot_paleta)
        elif t is None:
            self._aviso(f'sem ladrilho na camada {z} aqui')
            return
        elif f == 'girar':
            t['rot'] = (t['rot'] + (90 if botao == 1 else 270)) % 360
        elif f == 'inicio':
            if m.inicio == m.chave(t):
                saidas = list(m.caminhos(t).values())
                ordem = [d for d in LT.DIRS if d in saidas] or LT.DIRS
                atual = m.passos()[0]['saida'] if m.passos() else None
                i = ordem.index(atual) if atual in ordem else -1
                m.inicio_dir = ordem[(i + 1) % len(ordem)]
            else:
                m.inicio = m.chave(t)
                m.inicio_dir = None
        elif f == 'checkpoint':
            t['checkpoint'] = not t.get('checkpoint')
        elif f == 'rampa':
            r = t.get('rampa')
            if botao == 3:
                if r:
                    graus = [10, 15, 18, 20, 25]
                    g = r.get('graus', 20)
                    r['graus'] = graus[(graus.index(g) + 1) % len(graus)] if g in graus else 20
            else:
                ordem = [None, 'N', 'L', 'S', 'O']
                atual = r['sobe'] if r else None
                prox = ordem[(ordem.index(atual) + 1) % len(ordem)]
                t['rampa'] = {'sobe': prox, 'graus': r.get('graus', 20) if r else 20} if prox else None
        elif f == 'lombada':
            u, v = m.local(t, X, Y)
            lbs = t.setdefault('lombadas', [])
            if botao == 3:
                if lbs:
                    def dist(lb):
                        p = lb['pos'] * TAM
                        return abs((v if lb.get('eixo', 'NS') == 'NS' else u) - p)
                    lbs.remove(min(lbs, key=dist))
            else:
                eixo = m.eixo_padrao(t)
                pos = (v if eixo == 'NS' else u) / TAM
                lbs.append({'pos': round(min(0.9, max(0.1, pos)), 2), 'eixo': eixo})
        elif f == 'obstaculo':
            u, v = m.local(t, X, Y)
            obs = t.setdefault('obstaculos', [])
            perto = min(obs, key=lambda o: (o['u'] - u) ** 2 + (o['v'] - v) ** 2) if obs else None
            dperto = math.hypot(perto['u'] - u, perto['v'] - v) if perto else 1e9
            if botao == 3:
                if perto:
                    obs.remove(perto)
            elif mods & pygame.KMOD_SHIFT:
                if perto and dperto < 80:
                    perto['fixo'] = not perto.get('fixo')
            else:
                uu, vv = m.ponto_na_linha(t, u, v)
                ob = dict(M.OBSTACULO_PADRAO)
                ob.update({'u': round(uu), 'v': round(vv)})
                obs.append(ob)
        elif f == 'detritos':
            t['detritos'] = max(0, int(t.get('detritos', 0)) + (1 if botao == 1 else -1))
        m.mudou()
        self.sujo = True

    def _clique_zona(self, f, c, X, Y, botao, mods):
        m = self.sim.mundo.mapa
        z = m.zona
        dentro = bool(z) and (c[0], c[1]) in m.celulas_zona()
        if f == 'area':
            if botao == 3:
                if dentro:
                    m.remove_zona()
                return
            if dentro and mods & pygame.KMOD_SHIFT:
                X0, Y0, X1, Y1 = m.retangulo_zona()
                z['obstaculo'] = None if z.get('obstaculo') else {'u': round(X - X0), 'v': round(Y - Y0)}
                m.aplica_zona()
                return
            larg, alt = (z['larg'], z['alt']) if z else (4, 3)
            if c[0] + larg > m.largura or c[1] + alt > m.altura:
                self._aviso(f'a área ({larg} x {alt}) não cabe aqui: aumente o mapa ou clique mais para cima/esquerda')
                return
            if z:
                ent, sai, ve, vm = z['entrada'], z['saida'], z['verde'], z['vermelho']
                m.coloca_zona(c[0], c[1], larg, alt)
                m.zona.update({'entrada': ent, 'saida': sai, 'verde': ve, 'vermelho': vm})
                m.aplica_zona()
            else:
                m.coloca_zona(c[0], c[1])
            if m.inicio is None:
                self._aviso('a área apagou o ladrilho de início: marque de novo')
            return
        if not dentro:
            self._aviso('clique dentro da área de resgate')
            return
        X0, Y0, X1, Y1 = m.retangulo_zona()
        if f == 'aberturas':
            dist = {'N': Y1 - Y, 'S': Y - Y0, 'O': X - X0, 'L': X1 - X}
            lado = min(dist, key=dist.get)
            if lado in ('N', 'S'):
                i = int((X - X0) // TAM)
            else:
                i = int((Y1 - Y) // TAM)
            i = max(0, min(m.n_lado(lado) - 1, i))
            chave = 'entrada' if botao == 1 else 'saida'
            outra = 'saida' if chave == 'entrada' else 'entrada'
            if (z[outra]['lado'], z[outra]['i']) == (lado, i):
                z[outra] = dict(z[chave])
            z[chave] = {'lado': lado, 'i': i}
        else:
            cantos = {'NO': (X0, Y1), 'NE': (X1, Y1), 'SE': (X1, Y0), 'SO': (X0, Y0)}
            canto = min(cantos, key=lambda k: math.hypot(X - cantos[k][0], Y - cantos[k][1]))
            cor = 'verde' if botao == 1 else 'vermelho'
            outra = 'vermelho' if cor == 'verde' else 'verde'
            if z[outra] == canto:
                z[outra] = z[cor]
            z[cor] = canto
            if canto in m.cantos_proibidos():
                self._aviso('canto da entrada/saída: a regra não permite triângulo aqui')
        m.aplica_zona()

    def _roda_editor(self, pos, d):
        m = self.sim.mundo.mapa
        if self.ferramenta == 'area' and m.zona:
            z = m.zona
            larg, alt = z['alt'], z['larg']
            if z['x'] + larg > m.largura or z['y'] + alt > m.altura:
                self._aviso('girada a área não cabe aqui')
                return
            m.coloca_zona(z['x'], z['y'], larg, alt)
            m.mudou()
            self.sujo = True
            return
        if self.ferramenta == 'obstaculo':
            c, t, X, Y = self._lad_editor(pos)
            if t and t.get('obstaculos'):
                u, v = m.local(t, X, Y)
                ob = min(t['obstaculos'], key=lambda o: (o['u'] - u) ** 2 + (o['v'] - v) ** 2)
                ob['ang'] = (float(ob.get('ang', 0)) + 15 * d) % 180
                m.mudou()
                self.sujo = True
                return
        self.rot_paleta = (self.rot_paleta + (90 if d < 0 else 270)) % 360

    # ------------------------------------------------------------------ eventos
    def _evento(self, ev):
        s = self.sim
        if ev.type == pygame.VIDEORESIZE:
            self.sujo = True
        elif ev.type == pygame.MOUSEWHEEL:
            pos = pygame.mouse.get_pos()
            if self.modo == 'editar' and self.rect_area_paleta.collidepoint(pos):
                self.rol_paleta -= ev.y * 40
            elif self.modo == 'editar' and self._area().collidepoint(pos):
                self._roda_editor(pos, ev.y)
            elif self.modo == 'simular' and self._area().collidepoint(pos) and not s.programa_rodando():
                self._gira_robo(5 if ev.y > 0 else -5)
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if (self.modo == 'simular' and ev.button == 1 and s.cfg.get('brick') != 'pacoca'
                    and self.brick.mouse_down(ev.pos, s.mundo, self._area())):
                return
            if ev.button in (4, 5):
                return
            linhas = self.bot_sim if self.modo == 'simular' else self.bot_ed
            if ev.button == 1:
                for linha in linhas:
                    for b in linha:
                        if b.acao and b.rect.collidepoint(ev.pos):
                            b.acao()
                            self.sujo = True
                            return
                if self.modo == 'editar':
                    for r, n in self.rects_paleta:
                        if r.collidepoint(ev.pos) and self.rect_area_paleta.collidepoint(ev.pos):
                            self.tipo_paleta = n
                            self.ferramenta = 'ladrilho'
                            return
            if self._area().collidepoint(ev.pos):
                if self.modo == 'editar' and ev.button in (1, 3):
                    self._clique_editor(ev.pos, ev.button, pygame.key.get_mods())
                elif self.modo == 'simular' and ev.button == 1 and not s.programa_rodando():
                    x, y = self.W(*ev.pos)
                    rx, ry, _ = s.mundo.pose()
                    if math.hypot(x - rx, y - ry) < 120:
                        self.arrasta_robo = (x - rx, y - ry)
        elif ev.type == pygame.MOUSEBUTTONUP:
            self.brick.mouse_up(s.mundo)
            self.arrasta_robo = None
        elif ev.type == pygame.MOUSEMOTION:
            if self.arrasta_robo is not None:
                x, y = self.W(*ev.pos)
                with s.mundo.lock:
                    _, _, a = s.mundo.pose()
                    s.mundo.lad_centro = None
                    s.mundo.posicionar(x - self.arrasta_robo[0], y - self.arrasta_robo[1], a)
                self.trilha = []
            if self.modo == 'editar' and self._area().collidepoint(ev.pos):
                c, t, X, Y = self._lad_editor(ev.pos)
                self.hover = t
        elif ev.type == pygame.KEYDOWN:
            k = ev.key
            if k == pygame.K_SPACE:
                self._pausa()
            elif k == pygame.K_b:
                s.apertar_botao()
            elif k == pygame.K_l:
                s.lop_manual()
            elif k == pygame.K_r and self.modo == 'editar':
                self.rot_paleta = (self.rot_paleta + 90) % 360
            elif k == pygame.K_r:
                self.mostrar_raios = not self.mostrar_raios
            elif k == pygame.K_p:
                self._alterna_caminho()
            elif k == pygame.K_t:
                self.mostrar_trilha = not self.mostrar_trilha
                self.trilha = []
            elif k == pygame.K_o and self.modo == 'simular':
                self.brick.visivel = not self.brick.visivel
            elif k == pygame.K_c and self.modo == 'simular':
                self.mostrar_cam_linha = not self.mostrar_cam_linha
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
            w.posicionar(x, y, a, w.lad_centro)
            w.giro_reset_z()

    # ------------------------------------------------------------------ laço principal
    def _snapshot(self):
        w = self.sim.mundo
        with w.lock:
            obst = []
            for o in w.obstaculos:
                b = o['corpo']
                obst.append((b.position.x, b.position.y, b.angle, o['larg'], o['comp'], o['ob'].get('fixo')))
            embaixo = any(w.h_centro < p['h'] - 50 for p in w.pilares) if w.pilares else False
            rg = w.resgate
            zona = None
            if rg.ativa or rg.mec:
                zona = {'bolas': [(b['corpo'].position.x, b['corpo'].position.y, b['tipo'])
                                  for b in rg.bolas if b['estado'] == 'chao'],
                        'obst': ((rg.obst['corpo'].position.x, rg.obst['corpo'].position.y,
                                  rg.obst['corpo'].angle) if rg.obst else None),
                        'falsas': [fz['pos'] for fz in rg.falsas], 'mec': None,
                        'cam': dict(rg.ult_cam) if rg.camera_cfg else None, 't': w.t,
                        'resgatadas': [(b['tipo'], b.get('triangulo')) for b in rg.bolas if b['estado'] == 'resgatada'],
                        'salvas': self._posicoes_salvas(rg)}
                mc = rg.mec
                if mc:
                    zona['mec'] = {
                        'braco': mc.braco(), 'y_esq': mc.y_dedo('esq'), 'y_dir': mc.y_dedo('dir'),
                        'porta': mc.porta(), 'garra': mc.na_garra['tipo'] if mc.na_garra else None,
                        'yb': mc.na_garra['local'][1] if mc.na_garra else 0.0,
                        'cacamba': {k: [b['tipo'] for b in v] for k, v in mc.cacamba.items()},
                        'servos': {n: (round(mc.servos[n].pot), fw.alvo, fw.potencia, fw.travado, mc.servos[n].pwm, fw.id)
                                   for n, fw in mc.firmwares.items()},
                    }
            return {
                'zona': zona,
                'pose': w.pose(),
                'detritos': [list(map(list, v)) for v in w.detritos.values()],
                'obst': obst,
                'pilares': [p['pos'] for p in w.pilares],
                'pc': {p: w.para_choque(p) for p in w.sensores_pc},
                'led': w.led,
                'raios': dict(w.raios),
                't': w.t,
                'leitura': w.ultima_leitura or w.leitura_sensor(ruido=False),
                'fora': w.fora_da_pista,
                'suspenso': list(w.suspenso),
                'embaixo': embaixo,
                'angs': dict(w.angs),
                'debug': {'pose': w.debug['pose'], 'marcas': list(w.debug['marcas'])},
            }

    @staticmethod
    def _posicoes_salvas(rg):
        """Onde desenhar as vítimas resgatadas: onde caíram no triângulo, sem uma tapar a outra
        (o juiz tira cada uma do campo, então a próxima pode cair no mesmo lugar)."""
        out = []
        for b in rg.bolas:
            if b['estado'] != 'resgatada' or not b.get('pos_final'):
                continue
            x, y = b['pos_final']
            tri = rg.triangulos.get(b.get('triangulo'))
            if tri:
                cx, cy = tri[0]
                for _ in range(12):
                    if all(math.hypot(x - ox, y - oy) >= 47 for ox, oy, _ in out):
                        break
                    # anda na direção do canto do triângulo (sempre fica dentro dele)
                    dx, dy = cx - x, cy - y
                    d = math.hypot(dx, dy) or 1.0
                    x, y = x + dx / d * 25, y + dy / d * 25
            out.append((x, y, b['tipo']))
        return out

    def quadro(self):
        if self.tela.get_size() != getattr(self, '_tam_ant', None):
            self._tam_ant = self.tela.get_size()
            self.sujo = True
        m = self.sim.mundo.mapa
        if m.versao != self.versao_desenhada:
            self.sujo = True
        self.tela.fill(COR_FUNDO)
        if self.modo == 'simular':
            snap = self._snapshot()
            self._snap = snap
            if snap['angs'] != getattr(self, '_angs_ant', None):
                self._angs_ant = snap['angs']
                self.sujo = True
        if self.sujo or self.camada is None:
            self._desenha_camada()
        self.tela.blit(self.camada, (0, 0))
        if self.modo == 'simular':
            if self.mostrar_trilha:
                p = snap['pose'][:2]
                d = math.hypot(p[0] - self.trilha[-1][0], p[1] - self.trilha[-1][1]) if self.trilha else 1e9
                if d > 120:          # robô foi reposicionado (LoP): começa outra trilha
                    self.trilha = [p]
                elif d > 6:
                    self.trilha.append(p)
                    self.trilha = self.trilha[-4000:]
            self._desenha_robo(snap)
            if snap['embaixo']:
                self._redesenha_pontes(snap)
            if self.sim.cfg.get('brick') != 'pacoca':        # tela + teclado são do brick Mariola
                self.brick.desenha(self.tela, self.sim.mundo, self._area(), self.f12b, self.f11)
            self._desenha_cam_linha()
        lw, lh = self.tela.get_size()
        pygame.draw.rect(self.tela, COR_PAINEL, (lw - PAINEL, 0, PAINEL, lh))
        x = lw - PAINEL + 14
        larg = PAINEL - 28
        y = 10
        y = self._txt('Rescue Line — simulador Mariola', x, y, self.f16b, COR_DESTAQUE)
        y += 2
        if self.modo == 'simular':
            y = self._desenha_botoes(self.bot_sim, x, y, larg) + 2
            if time.time() - self.t_leituras > 0.12:
                self.t_leituras = time.time()
                self._le_sensores()
            self._desenha_painel_sim(x, y, larg)
        else:
            y = self._desenha_botoes(self.bot_ed, x, y, larg) + 2
            self._desenha_painel_ed(x, y, larg)
        self._desenha_console()
        if self.msg and time.time() - self.t_msg < 4:
            t = self.f14.render(self.msg, True, (0, 0, 0))
            r = t.get_rect(midtop=(self._area().centerx, 8)).inflate(16, 8)
            pygame.draw.rect(self.tela, COR_DESTAQUE, r, border_radius=6)
            self.tela.blit(t, (r.x + 8, r.y + 4))
        if self.sim.pausado:
            t = self.f22b.render('PAUSADO', True, COR_DESTAQUE)
            self.tela.blit(t, (16, 12))
        if self.modo == 'editar':
            t = self.f22b.render('EDITOR', True, COR_DESTAQUE)
            self.tela.blit(t, (16, 8))

    def rodar(self, quadros=None, captura=None):
        relogio = pygame.time.Clock()
        n = 0
        while quadros is None or n < quadros:
            n += 1
            for ev in pygame.event.get():
                if ev.type == pygame.QUIT:
                    self.sim.encerrar()
                    pygame.quit()
                    return
                self._evento(ev)
            self.quadro()
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
