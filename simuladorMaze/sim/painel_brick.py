"""Frente do brick na janela do simulador: a tela OLED 128x64 e o teclado (4 LEDs + 4 botões).

Fica no canto de baixo à direita do mapa. Clique e segure os botões com o mouse (ou F1–F4).
A tecla O esconde/mostra.
"""

import numpy as np
import pygame

NOMES = ['Voltar', 'Baixo', 'Cima', 'Enter']
TECLAS = ['F1', 'F2', 'F3', 'F4']
# cores dos LEDs da esquerda para a direita: aceso, apagado
CORES_LED = [((240, 244, 255), (70, 72, 80)), ((255, 45, 70), (80, 30, 36)),
             ((255, 150, 30), (85, 55, 28)), ((40, 235, 110), (28, 70, 44))]
COR_PIXEL = (225, 240, 255)
COR_FUNDO_OLED = (6, 8, 12)
ESCALA = 2


class PainelBrick:
    def __init__(self):
        self.visivel = True
        self._bits = None
        self._sup = None
        self._rects = []
        self._apertado = None

    def tamanho(self):
        return 128 * ESCALA + 28, 64 * ESCALA + 112

    def rect(self, area):
        w, h = self.tamanho()
        return pygame.Rect(area.right - w - 10, area.bottom - h - 10, w, h)

    def _superficie(self, bits, tam):
        if bits is self._bits and self._sup is not None:
            return self._sup
        w, h = tam
        arr = np.unpackbits(np.frombuffer(bits, dtype=np.uint8))[: w * h].reshape(h, w).astype(bool)
        rgb = np.empty((w, h, 3), dtype=np.uint8)
        rgb[:] = COR_FUNDO_OLED
        rgb[arr.T] = COR_PIXEL
        sup = pygame.surfarray.make_surface(rgb)
        self._sup = pygame.transform.scale(sup, (w * ESCALA, h * ESCALA))
        self._bits = bits
        return self._sup

    def desenha(self, tela, mundo, area, fonte, fonte_peq):
        self._rects = []
        if not self.visivel:
            t = fonte_peq.render('O: mostra a tela e o teclado do brick', True, (150, 156, 170))
            tela.blit(t, (area.right - t.get_width() - 10, area.bottom - t.get_height() - 6))
            return
        r = self.rect(area)
        pygame.draw.rect(tela, (16, 17, 20), r, border_radius=10)
        pygame.draw.rect(tela, (70, 74, 84), r, 1, border_radius=10)
        t = fonte_peq.render('brick: tela + teclado   (O esconde)', True, (150, 156, 170))
        tela.blit(t, (r.x + 12, r.y + 6))
        # tela
        tr = pygame.Rect(r.x + 14, r.y + 24, 128 * ESCALA, 64 * ESCALA)
        pygame.draw.rect(tela, COR_FUNDO_OLED, tr)
        bits = getattr(mundo, 'oled', None)
        tam = getattr(mundo, 'oled_tam', (128, 64))
        if bits:
            sup = self._superficie(bits, tam)
            tela.blit(sup, (tr.x + (tr.w - sup.get_width()) // 2, tr.y + (tr.h - sup.get_height()) // 2))
        pygame.draw.rect(tela, (40, 44, 52), tr.inflate(4, 4), 2)
        # LEDs e botões
        cfg = mundo.cfg.get('teclado') or {}
        acende = int(cfg.get('leds_acendem_com', 0)) if isinstance(cfg, dict) else 0
        leds = getattr(mundo, 'teclado_leds', 0x0F)
        passo = tr.w / 4
        y_led = tr.bottom + 20
        y_bot = y_led + 36
        for i in range(4):
            cx = int(tr.x + passo * (i + 0.5))
            aceso = ((leds >> i) & 1) == acende
            cor = CORES_LED[i][0 if aceso else 1]
            if aceso:
                halo = pygame.Surface((40, 40), pygame.SRCALPHA)
                pygame.draw.circle(halo, cor + (70,), (20, 20), 18)
                tela.blit(halo, (cx - 20, y_led - 20))
            pygame.draw.circle(tela, cor, (cx, y_led), 9)
            apertado = (i + 1) in mundo.teclas_teclado
            br = pygame.Rect(0, 0, 50, 30)
            br.center = (cx, y_bot)
            pygame.draw.rect(tela, (90, 96, 108) if apertado else (44, 47, 54), br, border_radius=8)
            pygame.draw.rect(tela, (110, 116, 130), br, 1, border_radius=8)
            t = fonte.render(NOMES[i], True, (235, 238, 245))
            tela.blit(t, (br.centerx - t.get_width() // 2, br.y + 2))
            t = fonte_peq.render(TECLAS[i], True, (150, 156, 170))
            tela.blit(t, (br.centerx - t.get_width() // 2, br.y + 16))
            self._rects.append((br, i + 1))

    def mouse_down(self, pos, mundo, area):
        """True se o clique foi no painel (aí o mapa não trata o clique)."""
        if not self.contem(pos, area):
            return False
        for br, k in self._rects:
            if br.collidepoint(pos):
                self._apertado = k
                mundo.teclas_teclado.add(k)
        return True

    def mouse_up(self, mundo):
        if self._apertado is not None:
            mundo.teclas_teclado.discard(self._apertado)
            self._apertado = None

    def contem(self, pos, area):
        return self.visivel and self.rect(area).collidepoint(pos)
