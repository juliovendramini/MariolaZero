"""Interface gráfica (pygame): a planta da casa, os objetos, o robô, os sensores e a câmera."""

import math
import os
import random
import time

import numpy as np
import pygame

from . import camera_casa as CC
from . import casa as A
from .painel_brick import PainelBrick

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
CORES_DEBUG = {'amarelo': (250, 210, 40), 'verde': (60, 220, 90), 'vermelho': (240, 60, 60),
               'azul': (70, 140, 255), 'branco': (255, 255, 255), 'roxo': (200, 90, 255)}
COR_RAIOS = [(255, 120, 80), (255, 180, 80), (90, 200, 255), (120, 160, 255), (120, 255, 140),
             (255, 100, 200), (200, 200, 200), (255, 255, 120)]


def _fonte(tam, negrito=False):
    return pygame.font.SysFont('dejavusans,arial,liberationsans,freesans,helvetica', tam, bold=negrito)


def _leque(tela, borda, cor):
    """Polígono semitransparente (o leque de um VL53) numa superfície só do tamanho dele. Uma
    superfície do tamanho da janela por sensor e por quadro tirava tanta CPU da física (mesmo
    processo) que a partida andava a metade da velocidade (31/10/2026)."""
    xs = [p[0] for p in borda]
    ys = [p[1] for p in borda]
    x0, y0 = int(min(xs)), int(min(ys))
    larg, alt = int(max(xs)) - x0 + 2, int(max(ys)) - y0 + 2
    if larg < 3 or alt < 3:
        return
    s = pygame.Surface((larg, alt), pygame.SRCALPHA)
    pygame.draw.polygon(s, cor + (70,), [(x - x0, y - y0) for x, y in borda])
    tela.blit(s, (x0, y0))


class Botao:
    def __init__(self, texto, acao, ligado=None, dica=''):
        self.texto = texto
        self.acao = acao
        self.ligado = ligado
        self.rect = pygame.Rect(0, 0, 10, 10)
        self.dica = dica


class Interface:
    def __init__(self, sim, pasta_cenarios):
        pygame.display.init()
        pygame.font.init()
        pygame.display.set_caption('Simulador do robô de casa — Mariola')
        self.tela = pygame.display.set_mode((1360, 820), pygame.RESIZABLE)
        self.sim = sim
        self.pasta_cenarios = pasta_cenarios
        self.f11 = _fonte(11)
        self.f12 = _fonte(12)
        self.f14 = _fonte(14)
        self.f12b = _fonte(12, True)
        self.f16b = _fonte(16, True)
        self.f22b = _fonte(22, True)
        self.f30b = _fonte(30, True)
        self.brick = PainelBrick()
        self.arrasta_robo = None
        self.mostrar_raios = True
        self.mostrar_trilha = True
        self.mostrar_nomes = True
        self.mostrar_camera = True
        self.zoom = 1.0
        self.arrasta_obj = None
        self.texto_entrada = ''        # o que está sendo digitado para o input() do programa
        self.cena_cam = None
        self.sup_camera = None
        self.t_camera = 0
        self.trilha = []
        self.sujo = True
        self.camada = None
        self.leituras = {}
        self.t_leituras = 0
        self.msg = ''
        self.t_msg = 0
        self.semente_sorteio = 0
        self.bot_enter = Botao('⏎ Enter', lambda: self.sim.responde_entrada(), dica='Enter')
        self._monta_botoes()

    # ------------------------------------------------------------------ botões
    def _monta_botoes(self):
        s = self.sim
        self.botoes = [
            [Botao('▶ Iniciar partida', self._iniciar, dica='F5'),
             Botao('■ Parar', lambda: s.parar_programa()),
             Botao('↺ Nova rodada', self._nova_rodada)],
            [Botao('Devolver ao início', s.reinicio),
             Botao('Botão do robô', lambda: s.apertar_botao(), dica='B'),
             Botao('Pausar', self._pausa, ligado=lambda: s.pausado, dica='espaço'),
             Botao('', self._velocidade)],
            [Botao('', self._auto_botao),
             Botao('Abrir', self._abrir),
             Botao('Salvar', self._salvar)],
            [Botao('', self._escolhe_programa)],
        ]

    def _iniciar(self):
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

    def _auto_botao(self):
        self.sim.auto_botao = not self.sim.auto_botao

    def _escolhe_programa(self):
        """Abre o seletor de arquivo e troca o programa do robô (sem fechar o simulador)."""
        atual = self.sim.programa
        pasta = os.path.dirname(atual) if atual else os.path.dirname(self.pasta_cenarios)
        c = self._dialogo(False, pasta, [('Programa Python', '*.py')], 'Escolha o programa do robô')
        if c == 'SEM_TK':
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

    def _aviso(self, s):
        self.msg = s
        self.t_msg = time.time()

    # ------------------------------------------------------------------ cenário
    def _dialogo(self, salvar, pasta, tipos, titulo=None):
        try:
            import tkinter as tk
            from tkinter import filedialog
            raiz = tk.Tk()
            raiz.withdraw()
            raiz.attributes('-topmost', True)
            if salvar:
                c = filedialog.asksaveasfilename(initialdir=pasta, defaultextension='.json', filetypes=tipos)
            else:
                c = filedialog.askopenfilename(initialdir=pasta, filetypes=tipos, title=titulo)
            raiz.destroy()
            return c or None
        except Exception:
            return 'SEM_TK'

    def _pode_editar(self):
        j = self.sim.juiz
        if self.sim.programa_rodando() or (j.ativo and not j.fim):
            self._aviso('pare o programa (■ Parar) e comece uma rodada nova para mexer no cenário')
            return False
        return True

    def _aplica_cenario(self, c):
        self.sim.troca_cenario(c)
        self.trilha = []
        self.cena_cam = None
        self.sujo = True
        for aviso in c.validar():
            self._aviso('casa: ' + aviso)

    def _abrir(self):
        if not self._pode_editar():
            return
        c = self._dialogo(False, self.pasta_cenarios, [('Casas', '*.json')])
        if c == 'SEM_TK':
            arqs = sorted(f for f in os.listdir(self.pasta_cenarios) if f.endswith('.json'))
            if not arqs:
                return
            atual = os.path.basename(self.sim.mundo.cenario.caminho or '')
            i = (arqs.index(atual) + 1) % len(arqs) if atual in arqs else 0
            c = os.path.join(self.pasta_cenarios, arqs[i])
        if c:
            try:
                novo = A.Casa.carregar(c)
            except Exception as e:
                self._aviso(f'erro ao abrir: {e}')
                return
            self._aplica_cenario(novo)
            os.environ['CASA_MAPA'] = os.path.abspath(c)       # o programa do robô carrega o mapa desta casa
            self._aviso(f'aberto {os.path.basename(c)}')

    def _salvar(self):
        cen = self.sim.mundo.cenario
        c = self._dialogo(True, self.pasta_cenarios, [('Casas', '*.json')])
        if c == 'SEM_TK':
            n = 1
            while os.path.exists(os.path.join(self.pasta_cenarios, f'casa{n}.json')):
                n += 1
            c = os.path.join(self.pasta_cenarios, f'casa{n}.json')
        if c:
            cen.nome = os.path.splitext(os.path.basename(c))[0]
            cen.salvar(c)
            self._aviso(f'salvo em {c}')

    # ------------------------------------------------------------------ geometria da tela
    def _area(self):
        lw, lh = self.tela.get_size()
        return pygame.Rect(0, 0, lw - PAINEL, lh - CONSOLE)

    def _casa(self):
        return self.sim.mundo.cenario

    def _calcula_escala(self):
        a = self._area()
        c = self._casa()
        mg = 14
        self.borda = float(c.parede['esp'])
        lw, lh = c.largura + 2 * self.borda, c.altura + 2 * self.borda
        self.esc = min((a.w - 2 * mg) / lw, (a.h - 2 * mg) / lh)
        self.ox = a.x + (a.w - lw * self.esc) / 2 + self.borda * self.esc
        self.oy = a.y + mg + self.borda * self.esc
        self.alt_casa = c.altura
        if self.zoom > 1:
            # zoom: a vista acompanha o robô (tecla Z troca 1x, 2,5x, 5x, 10x)
            self.esc *= self.zoom
            rx, ry, _ = self.sim.robo.pose()
            self.ox = a.centerx - rx * self.esc
            self.oy = a.centery - (self.alt_casa - ry) * self.esc

    def T(self, x, y):
        return (self.ox + x * self.esc, self.oy + (self.alt_casa - y) * self.esc)

    def W(self, px, py):
        return ((px - self.ox) / self.esc, self.alt_casa - (py - self.oy) / self.esc)

    def R(self, x0, y0, x1, y1):
        """Retângulo da tela para o retângulo da casa (x0, y0)-(x1, y1)."""
        a = self.T(x0, y1)
        b = self.T(x1, y0)
        return pygame.Rect(round(a[0]), round(a[1]), max(1, round(b[0]) - round(a[0])),
                           max(1, round(b[1]) - round(a[1])))

    def _pol(self, cx, cy, ang, sx, sy):
        ca, sa = math.cos(ang), math.sin(ang)
        return [self.T(cx + lx * ca - ly * sa, cy + lx * sa + ly * ca)
                for lx, ly in ((sx / 2, sy / 2), (-sx / 2, sy / 2), (-sx / 2, -sy / 2), (sx / 2, -sy / 2))]

    # ------------------------------------------------------------------ desenho da casa
    def _desenha_camada(self):
        a = self._area()
        self._calcula_escala()
        c = self._casa()
        sup = pygame.Surface((a.w, a.h))
        sup.fill(COR_FUNDO)
        for ret, rgb in c.chao():
            pygame.draw.rect(sup, rgb, self.R(*ret))
        for (cx, cy, ang, sx, sy, z0, z1, rgb, nome) in c.solidos():
            pts = self._pol(cx, cy, ang, sx, sy)
            if nome == 'parede':
                pygame.draw.polygon(sup, (70, 72, 80), pts)
            elif nome == 'caixa':
                if z1 > 2.0:
                    pygame.draw.polygon(sup, rgb, pts)
                else:
                    pygame.draw.polygon(sup, tuple(int(v * 0.75 + 60) for v in rgb), pts)
            else:
                cor = rgb if z0 <= 0 else tuple(int(v * 0.5 + 110) for v in rgb)     # tampo no ar: mais claro
                pygame.draw.polygon(sup, cor, pts)
                pygame.draw.polygon(sup, (40, 40, 44), pts, 2 if z0 <= 0 else 1)
        self.camada = sup
        self.sujo = False

    def _desenha_nomes(self):
        c = self._casa()
        for p in c.pisos:
            if not p.get('nome') or c.rotulos:
                continue
            r = p['ret']
            t = self.f12.render(p['nome'], True, (70, 72, 78))
            e = float(c.parede.get('esp', 100))     # para dentro: uma parede interna pode cobrir a borda do piso
            px, py = self.T(r[0] + e, r[3] - e)
            self.tela.blit(t, (px + 4, py + 2))
        for r in c.rotulos:
            t = self.f11.render(r['nome'], True, (40, 60, 110))
            px, py = self.T(r['x'], r['y'])
            self.tela.blit(t, (px - t.get_width() / 2, py - t.get_height() / 2))
        for m in c.moveis:
            if float(m['ret'][2] - m['ret'][0]) * self.esc < 46:
                continue
            r = m['ret']
            t = self.f11.render(m.get('nome', ''), True, (30, 30, 34))
            px, py = self.T((r[0] + r[2]) / 2, (r[1] + r[3]) / 2)
            self.tela.blit(t, (px - t.get_width() / 2, py - t.get_height() / 2))
        if c.caixa:
            t = self.f11.render('caixa', True, (30, 30, 34))
            px, py = self.T(c.caixa['x'], c.caixa['y'])
            self.tela.blit(t, (px - t.get_width() / 2, py - t.get_height() / 2))

    def _desenha_objetos(self, objs):
        for (tipo, cor, cantos, estado, z) in objs:
            pts = [self.T(p[0], p[1]) for p in cantos]
            if estado != 'livre':
                # no alto (garra ou plataforma): sombra deslocada, para ver que não está no chão
                k = max(2, int(z * 0.12 * self.esc * 4))
                sombra = pygame.Surface(self.tela.get_size(), pygame.SRCALPHA)
                pygame.draw.polygon(sombra, (0, 0, 0, 70), [(p[0] + k, p[1] + k) for p in pts])
                self.tela.blit(sombra, (0, 0))
            rgb = cor
            borda = (40, 40, 40) if sum(cor) > 120 else (170, 170, 170)
            cx = sum(p[0] for p in pts) / 4
            cy = sum(p[1] for p in pts) / 4
            pygame.draw.polygon(self.tela, rgb, pts)
            # "tampa" mais clara: o objeto tem altura
            claro = tuple(min(255, int(c * 0.6 + 255 * 0.4)) for c in rgb)
            pygame.draw.polygon(self.tela, claro, [(cx + (p[0] - cx) * 0.55, cy + (p[1] - cy) * 0.55) for p in pts])
            pygame.draw.polygon(self.tela, borda, pts, 2)

    def _desenha_robo(self, snap):
        e = self.esc
        r = self.sim.robo
        if self.mostrar_trilha and len(self.trilha) > 1:
            pygame.draw.lines(self.tela, (255, 160, 40), False, [self.T(x, y) for x, y in self.trilha], 2)
        x, y, a = snap['pose']
        ca, sa = math.cos(a), math.sin(a)

        def L(lx, ly):
            return self.T(x + lx * ca - ly * sa, y + lx * sa + ly * ca)

        hl, hw = r.L / 2, r.W / 2
        corpo = [L(hl, hw), L(hl, -hw), L(-hl, -hw), L(-hl, hw)]
        ov = pygame.Surface(self.tela.get_size(), pygame.SRCALPHA)
        pygame.draw.polygon(ov, (30, 35, 50, 170), corpo)
        self.tela.blit(ov, (0, 0))
        pygame.draw.polygon(self.tela, (200, 210, 230), corpo, 2)
        # rodas (mecanum: traços na direção dos roletes que tocam o chão)
        rr = r.diametro / 2
        lw = r.largura_roda / 2
        for mot in r.motores:
            pts = [L(mot.x + rr, mot.y + lw), L(mot.x + rr, mot.y - lw),
                   L(mot.x - rr, mot.y - lw), L(mot.x - rr, mot.y + lw)]
            pygame.draw.polygon(self.tela, (15, 15, 15), pts)
            if mot.rolete is not None:
                t = math.tan(mot.rolete)
                for k in (-0.6, -0.2, 0.2, 0.6):
                    cxw = mot.x + k * rr
                    pygame.draw.line(self.tela, (150, 150, 150), L(cxw - lw * t * 0.9, mot.y - lw * 0.9),
                                     L(cxw + lw * t * 0.9, mot.y + lw * 0.9), 1)
        # sensor de linha
        for cc in r.linhas:
            for s_ in cc['tcs']:
                pygame.draw.circle(self.tela, (255, 255, 255), L(s_['x'], s_['y']), 3)
            for s_ in cc['ir']:
                pygame.draw.circle(self.tela, (255, 80, 80), L(s_['x'], s_['y']), 2)
        # TCS no mux I2C (os da garra andam com a cabeça)
        for lx, ly, ang, _ in snap['tcs_pose']:
            p0 = (lx, ly)
            pygame.draw.line(self.tela, (255, 255, 255), L(*p0),
                             L(p0[0] + 25 * math.cos(ang), p0[1] + 25 * math.sin(ang)), 2)
        pygame.draw.line(self.tela, (255, 255, 255), L(0, 0), L(hl * 0.8, 0), 2)
        # garras (peças claras = no alto, passam por cima dos cubos)
        for g in snap['garras']:
            for a, b, esp, alto in g['desenho']:
                cor = (235, 235, 245) if alto else (150, 160, 180)
                pygame.draw.line(self.tela, cor, L(*a), L(*b), max(1, int(esp * e)))
        # LEDs RGB do Mariola (os 10, numa fileira atrás)
        leds = snap['leds']
        for i, cor in enumerate(leds):
            yy = (i - 4.5) * (r.W * 0.8 / 10)
            pygame.draw.circle(self.tela, cor if any(cor) else (50, 50, 50), L(-hl * 0.6, yy), max(2, int(6 * e)))
        # raios dos VL53
        if self.mostrar_raios:
            for i, sc in enumerate(r.cfg['vl53']):
                rr_ = snap['raios'].get(sc['nome'])
                if rr_ is None:
                    continue
                p0, p1, d, t, a0, meia, pontos = rr_
                cor = COR_RAIOS[i % len(COR_RAIOS)]
                if snap['t'] - t > 0.5:
                    cor = tuple(c // 3 for c in cor)
                # leque do campo de visão (25°): cada raio até onde bateu (ou até a medida)
                alc = min(d, 1200.0) if d is not None else 400.0
                borda = [self.T(p0.x, p0.y)]
                for a, da in pontos:
                    rr = min(da, alc * 1.05) if da is not None else alc
                    borda.append(self.T(p0.x + rr * math.cos(a), p0.y + rr * math.sin(a)))
                _leque(self.tela, borda, cor)
                pygame.draw.line(self.tela, cor, self.T(p0.x, p0.y), self.T(p1.x, p1.y), 1)
                if d is not None:
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

    def _desenha_camera(self, cena):
        """A imagem da câmera do robô, no canto de baixo da área da casa (tecla C)."""
        if cena is None:
            return
        g = self.sim.robo.garra
        if g is None or not g.cam:
            return
        if self.cena_cam is None:
            self.cena_cam = CC.Cena(self._casa())
        if time.time() - self.t_camera > 0.2 or self.sup_camera is None:
            self.t_camera = time.time()
            w, h = 240, 180
            img = self.cena_cam.desenha(cena['cam'], cena['din'], w, h, *CC.campo_de_visao(g.cam), rng=None)
            self.sup_camera = pygame.image.frombuffer(np.ascontiguousarray(img[:, :, ::-1]).tobytes(), (w, h), 'RGB')
        a = self._area()
        r = self.sup_camera.get_rect(bottomleft=(a.x + 8, a.bottom - 8))
        self.tela.blit(self.sup_camera, r)
        pygame.draw.rect(self.tela, (20, 20, 24), r, 2)
        t = self.f11.render('câmera do robô (C)', True, (255, 255, 255))
        pygame.draw.rect(self.tela, (20, 20, 24), (r.x, r.y - t.get_height() - 2, t.get_width() + 8, t.get_height() + 2))
        self.tela.blit(t, (r.x + 4, r.y - t.get_height() - 1))

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
        r = self.sim.robo
        with w.lock:
            # o painel não pode gastar o ruído dos sensores: a partida com e sem janela é a mesma
            rngs = (r.rng_vl53, r.rng_tcs, r.rng_giro, *r.rng_cor)
            estados = [g.getstate() for g in rngs]
            raios = dict(r.raios)
            d = {}
            d['vl53'] = [(sc['nome'], r.vl53(i)) for i, sc in enumerate(r.cfg['vl53'])]
            d['tcs'] = [(sc['nome'], r.tcs(i)) for i, sc in enumerate(r.cfg.get('tcs_i2c', []))]
            d['giro'] = r.giro()
            d['cor'] = [(cc['porta'], r.cor_bytes(i)) for i, cc in enumerate(r.linhas)]
            d['enc'] = [(m.nome, m.contagem_int()) for m in r.motores]
            x, y, _ = r.pose()
            d['piso'] = self._casa().piso(x, y)
            d['comodo'] = self._casa().comodo(x, y)
            for g, st in zip(rngs, estados):
                g.setstate(st)
            if self.sim.programa_rodando():
                r.raios = raios              # com o programa rodando, mostra o que ELE leu
        self.leituras = d

    def _desenha_painel(self, x, y, larg):
        s = self.sim
        j = s.juiz
        total, partes, info = j.placar()
        tp = j.tempo
        self._txt(f'{int(tp // 60):02d}:{int(tp % 60):02d}', x, y, self.f30b, COR_DESTAQUE)
        tt = self.f30b.render(info['guardados'], True, COR_TEXTO)
        self.tela.blit(tt, (x + larg - tt.get_width(), y))
        y += 40
        estado = 'rodada em andamento' if j.ativo and not j.fim else (f'fim: {j.fim}' if j.fim else 'rodada não iniciada')
        prog = 'programa rodando' if s.programa_rodando() else 'programa parado'
        y = self._txt(f'{estado}  •  {prog}', x, y, self.f12, COR_TEXTO2)
        y = self._txt('guardados na caixa  •  ' + '  '.join(f'{k} {v}' for k, v in info.items() if k != 'guardados'),
                      x, y, self.f12)
        y += 4
        for (t, txt, p) in list(j.eventos)[-6:]:
            sp = f'{p:+d} ' if p else ''
            y = self._txt(f'{int(t // 60)}:{int(t % 60):02d} {sp}{txt}'[:62], x, y, self.f12,
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
        y = self._txt(f'Giro  Z {g[2]}', x, y, self.f14)
        y = self._txt('Encoders  ' + '   '.join(f'{_sigla(n)} {c}' for n, c in d['enc']), x, y, self.f12)
        for porta, c in d['cor']:
            nome = f'Linha ({porta})' if len(d['cor']) > 1 else 'Sensor de linha'
            y = self._txt(f'{nome}  IR {c[0]:3d} {c[1]:3d} {c[2]:3d} {c[3]:3d}', x, y, self.f12)
            passo = larg // 3
            for k in range(3):
                rgbc = c[4 + 4 * k: 8 + 4 * k]
                r = pygame.Rect(x + k * passo, y, 14, 14)
                pygame.draw.rect(self.tela, tuple(min(255, 2 * v) for v in rgbc[:3]), r)
                pygame.draw.rect(self.tela, (0, 0, 0), r, 1)
                self._txt(f'{rgbc[0]},{rgbc[1]},{rgbc[2]},{rgbc[3]}', x + k * passo + 17, y + 1, self.f11)
            y += 18
        for n, v in d['tcs']:
            sw = pygame.Rect(x, y, 14, 14)
            k = 255 / max(0.05, max(v[:3]))
            pygame.draw.rect(self.tela, tuple(max(0, min(255, int(c_ * k))) for c_ in v[:3]), sw)
            pygame.draw.rect(self.tela, (0, 0, 0), sw, 1)
            y = self._txt(f'{n}: r {v[0]:.2f} g {v[1]:.2f} b {v[2]:.2f}', x + 18, y, self.f12)
        for g in getattr(self, 'garra_info', None) or []:
            y = self._txt(f'Pinça: abertura {g["abertura"]:.0f} mm, dedos a {g["altura"]:.0f} mm do chão, '
                          f'barras {g["barra"]:+.0f}°', x, y, self.f12)
            y = self._txt(f'Câmera: {abs(g["inclinacao"]):.0f}° para {"baixo" if g["inclinacao"] >= 0 else "cima"}   '
                          f'{"segurando o objeto " + g["preso"] if g["preso"] else "pinça vazia"}', x, y, self.f12)
        px_, py_, pa_ = s.robo.pose()
        y = self._txt(f'Pose real: x {px_:.0f}  y {py_:.0f}  ângulo {math.degrees(pa_) % 360:.0f}°   '
                      f'{d.get("comodo", "")} (piso {d["piso"]})', x, y, self.f12, COR_TEXTO2)
        rb = s.robo
        e = rb.debug.get('erro')
        if e and e['n']:
            y = self._txt(f'Localização: erro {e["mm"]:.0f} mm, {e["graus"]:.1f}°  '
                          f'(médio {e["soma"] / e["n"]:.0f}, máx {e["max"]:.0f} mm)', x, y, self.f12, (220, 90, 255))
        if rb.debug['texto']:
            y += 4
            y = self._txt('Programa (simdebug):', x, y, self.f12, (220, 90, 255))
            for linha in rb.debug['texto'].split('\n')[:4]:
                y = self._txt(linha[:60], x, y, self.f12)
        y += 6
        cen = s.mundo.cenario
        y = self._txt(f'Casa: {cen.nome}', x, y, self.f12, COR_DESTAQUE)
        ajuda = ['Com o programa parado: arraste o robô ou um objeto; Q/E giram o robô 90°, roda do mouse 5°.',
                 'Teclas: espaço pausa, B botão, R raios, T trilha, N nomes, C câmera, Z zoom no robô,',
                 '1–5 velocidade,',
                 'O tela/teclado do brick (F1–F4), Enter responde o input() do programa.',
                 'Roxo = onde o programa acha que está (simdebug.pose).']
        for linha in _quebra(' '.join(ajuda), 58):
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
        if self.texto_entrada or prompt:
            # o programa pergunta algo (um comando para o robô, por exemplo): o teclado escreve aqui
            txt = f'{prompt} {self.texto_entrada}' + ('|' if int(time.time() * 2) % 2 else ' ')
            if not self.texto_entrada:
                txt += '   (digite e aperte Enter)'
        else:
            txt = "O programa está parado no input(''): aperte Enter para continuar"
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

    # ------------------------------------------------------------------ eventos
    def _evento(self, ev):
        s = self.sim
        rb = s.robo
        if ev.type == pygame.VIDEORESIZE:
            self.sujo = True
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1 and s.entrada is not None and self.bot_enter.rect.collidepoint(ev.pos):
                s.responde_entrada(self.texto_entrada)
                self.texto_entrada = ''
                return
            if ev.button == 1 and self.brick.mouse_down(ev.pos, rb, self._area()):
                return
            if ev.button == 1:
                for linha in self.botoes:
                    for b in linha:
                        if b.rect.collidepoint(ev.pos):
                            b.acao()
                            self.sujo = True
                            return
            if self._area().collidepoint(ev.pos) and not s.programa_rodando():
                x, y = self.W(*ev.pos)
                rx, ry, _ = rb.pose()
                if ev.button == 1 and math.hypot(x - rx, y - ry) < max(rb.L, rb.W) / 2:
                    self.arrasta_robo = (x - rx, y - ry)
                elif ev.button == 1:
                    with s.mundo.lock:
                        o = s.mundo.objeto_em(x, y)
                    self.arrasta_obj = o
                elif ev.button in (4, 5):
                    self._gira_robo(5 if ev.button == 4 else -5)
        elif ev.type == pygame.MOUSEBUTTONUP:
            self.brick.mouse_up(rb)
            self.arrasta_robo = None
            self.arrasta_obj = None
        elif ev.type == pygame.MOUSEMOTION:
            if self.arrasta_robo is not None:
                x, y = self.W(*ev.pos)
                with s.mundo.lock:
                    _, _, a = rb.pose()
                    rb.posicionar(x - self.arrasta_robo[0], y - self.arrasta_robo[1], a)
                self.trilha = []
            elif getattr(self, 'arrasta_obj', None) is not None and not s.programa_rodando():
                x, y = self.W(*ev.pos)
                with s.mundo.lock:
                    o = self.arrasta_obj
                    o.muda_estado('livre')
                    o.corpo.position = (x, y)
                    o.x0, o.y0 = x, y
                    s.mundo.space.reindex_shapes_for_body(o.corpo)
        elif ev.type == pygame.TEXTINPUT:
            if s.entrada is not None:
                self.texto_entrada = (self.texto_entrada + ev.text)[:200]
        elif ev.type == pygame.KEYDOWN:
            k = ev.key
            if s.entrada is not None and not (pygame.K_F1 <= k <= pygame.K_F12):
                # o programa espera um texto no input(): o teclado escreve (as teclas de atalho ficam de fora)
                if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    s.responde_entrada(self.texto_entrada)
                    self.texto_entrada = ''
                elif k == pygame.K_BACKSPACE:
                    self.texto_entrada = self.texto_entrada[:-1]
                elif k == pygame.K_ESCAPE:
                    self.texto_entrada = ''
                return
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                s.responde_entrada()         # libera o input() do programa, se houver
            elif k == pygame.K_SPACE:
                self._pausa()
            elif k == pygame.K_b:
                s.apertar_botao()
            elif k == pygame.K_r:
                self.mostrar_raios = not self.mostrar_raios
            elif k == pygame.K_t:
                self.mostrar_trilha = not self.mostrar_trilha
                self.trilha = []
            elif k == pygame.K_n:
                self.mostrar_nomes = not self.mostrar_nomes
            elif k == pygame.K_c:
                self.mostrar_camera = not self.mostrar_camera
            elif k == pygame.K_z:
                niveis = [1.0, 2.5, 5.0, 10.0]
                self.zoom = niveis[(niveis.index(self.zoom) + 1) % len(niveis)] if self.zoom in niveis else 1.0
                self.sujo = True
                self.trilha = self.trilha[-3000:]
            elif k == pygame.K_o:
                self.brick.visivel = not self.brick.visivel
            elif k == pygame.K_F5:
                self._iniciar()
            elif k in (pygame.K_q, pygame.K_e) and not s.programa_rodando():
                self._gira_robo(90 if k == pygame.K_q else -90)
            elif k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5):
                s.set_fator([0.25, 0.5, 1.0, 2.0, 4.0][k - pygame.K_1])
            elif k in (pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4):
                rb.teclas_teclado.add(k - pygame.K_F1 + 1)
            elif k == pygame.K_s and (ev.mod & pygame.KMOD_CTRL):
                self._salvar()
        elif ev.type == pygame.KEYUP:
            if ev.key in (pygame.K_F1, pygame.K_F2, pygame.K_F3, pygame.K_F4):
                rb.teclas_teclado.discard(ev.key - pygame.K_F1 + 1)

    def _gira_robo(self, graus):
        w = self.sim.mundo
        rb = self.sim.robo
        with w.lock:
            x, y, a = rb.pose()
            a = a + math.radians(graus)
            if abs(graus) == 90:
                a = round(a / (math.pi / 2)) * (math.pi / 2)
            rb.posicionar(x, y, a)
            rb.giro_reset_z()

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
            if self.sujo or self.camada is None or self.zoom > 1:
                self._desenha_camada()        # com zoom a vista anda com o robô: redesenha sempre
            self.tela.fill(COR_FUNDO)
            self.tela.blit(self.camada, (0, 0))
            w = self.sim.mundo
            rb = self.sim.robo
            with w.lock:
                snap = {
                    'pose': rb.pose(),
                    'objetos': [(o.tipo, o.rgb, [(p.x, p.y) for p in o.cantos()], o.estado, o.z)
                                for o in w.objetos],
                    'cena': w.cena_camera(rb) if self.mostrar_camera else None,
                    'garras': [dict(g.info(), desenho=g.desenho()) for g in rb.garras],
                    'tcs_pose': [rb.pose_tcs(sc) for sc in rb.cfg.get('tcs_i2c', [])],
                    'leds': list(rb.leds),
                    'raios': dict(rb.raios),
                    't': w.t,
                    'debug': {'pose': rb.debug['pose'], 'marcas': list(rb.debug['marcas'])},
                }
            if self.mostrar_trilha:
                p = snap['pose'][:2]
                if not self.trilha or math.hypot(p[0] - self.trilha[-1][0], p[1] - self.trilha[-1][1]) > 8:
                    self.trilha.append(p)
                    self.trilha = self.trilha[-3000:]
            if self.mostrar_nomes:
                self._desenha_nomes()
            self._desenha_objetos([o for o in snap['objetos'] if o[3] != 'preso'])
            self._desenha_robo(snap)
            self._desenha_objetos([o for o in snap['objetos'] if o[3] == 'preso'])
            self._desenha_camera(snap['cena'])
            self.garra_info = snap['garras']
            self.brick.desenha(self.tela, rb, self._area(), self.f12b, self.f11)
            # painel
            lw, lh = self.tela.get_size()
            pygame.draw.rect(self.tela, COR_PAINEL, (lw - PAINEL, 0, PAINEL, lh))
            x = lw - PAINEL + 14
            larg = PAINEL - 28
            y = 12
            y = self._txt('Robô de casa — simulador Mariola', x, y, self.f16b, COR_DESTAQUE)
            y += 4
            y = self._desenha_botoes(self.botoes, x, y, larg) + 4
            if time.time() - self.t_leituras > 0.15:
                self.t_leituras = time.time()
                self._le_sensores()
            self._desenha_painel(x, y, larg)
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
