"""Seguidor de linha de exemplo para a Rescue Line (só a linha, sem zona de resgate).

Ponto de partida, não a solução:
* PID na posição da linha calculada pelos 4 canais de reflexão
* interseções: olha os marcadores verdes nos TCS da esquerda/direita (os dois = meia-volta)
* curva de 90° sem verde: confere se a linha continua reto; se não, gira para o lado do preto
* gap: segue reto pelo giroscópio até achar a linha de novo
* obstáculo: VL53 da frente / para-choque -> contorna pela direita
* área de resgate: fita prata -> resgate.py (vítimas pela câmera + garra, ou só achar a saída)
* chegada: fita vermelha -> para (a regra pede mais de 5 s parado)
"""

import time

try:
    import simdebug                      # no robô, copie robo_real/simdebug.py (não faz nada)
except ImportError:
    simdebug = None

from robo import Robo, Y_CANAIS
from resgate import AreaResgate, entrada_da_area, eh_prata

VEL = 38            # velocidade base (-100..100)
KP = 1.6
KD = 6.0
PRETO = 50          # abaixo disso o canal está vendo preto (0 = preto, 100 = branco)
DIST_OBSTACULO = 70 # mm
GAP_MAX_MM = 260    # gap da regra: até 20 cm


def escuro(v):
    return max(0.0, min(1.0, (100.0 - v) / 100.0))


def posicao_linha(ir):
    """mm da linha em relação ao centro do sensor (+ = esquerda) e 'quanto preto' viu."""
    pesos = [escuro(v) for v in ir]
    soma = sum(pesos)
    if soma < 0.25:
        return None, soma
    return sum(p * y for p, y in zip(pesos, Y_CANAIS)) / soma, soma


def mostra(txt):
    if simdebug:
        simdebug.texto(txt)


class Seguidor:
    def __init__(self, r):
        self.r = r
        self.erro_ant = 0.0
        self.verde_esq = 0.0      # momento em que viu verde em cada lado
        self.verde_dir = 0.0
        self.parado = False
        self.z_reto = None
        self.zona_feita = False

    # ------------------------------------------------------------------ marcadores verdes
    def olha_verde(self):
        c = self.r.cores()
        agora = time.time()
        if c[0] == 'verde':
            self.verde_esq = agora
        if c[2] == 'verde':
            self.verde_dir = agora
        return c

    def verde_recente(self, janela=0.6):
        agora = time.time()
        return agora - self.verde_esq < janela, agora - self.verde_dir < janela

    # ------------------------------------------------------------------ manobras
    def procura_linha_girando(self, sentido, max_graus=120):
        """Gira (sentido +1 = esquerda) até os canais do meio verem a linha."""
        r = self.r
        z0 = r.z()
        while abs(r.z() - z0) < max_graus:
            ir = r.reflexao()
            if ir[1] < PRETO or ir[2] < PRETO:
                break
            r.anda(-28 * sentido, 28 * sentido)
            time.sleep(0.01)
        r.para()

    def intersecao(self, lado_preto):
        """Chamado quando a fileira de reflexão passa por uma faixa preta larga (cruzamento,
        T ou curva de 90°). O centro do robô fica ~80 mm atrás do sensor."""
        r = self.r
        self.olha_verde()
        esq, dir_ = self.verde_recente()
        if esq or dir_:
            r.anda_mm(70, vel=30)            # centro do robô no cruzamento
            if esq and dir_:
                mostra('verde dos dois lados: meia-volta')
                r.gira(150)
                self.procura_linha_girando(+1, max_graus=90)
            elif esq:
                mostra('verde à esquerda')
                r.gira(45)
                self.procura_linha_girando(+1, max_graus=100)
            else:
                mostra('verde à direita')
                r.gira(-45)
                self.procura_linha_girando(-1, max_graus=100)
            self.verde_esq = self.verde_dir = 0.0
            return
        # sem verde: passa a faixa e vê se a linha continua reto
        r.anda_mm(30, vel=30)
        ir = r.reflexao()
        if min(ir[1], ir[2]) < PRETO:
            mostra('interseção sem verde: reto')
            return
        mostra('curva fechada')
        r.anda_mm(40, vel=30)
        sentido = +1 if lado_preto == 'esq' else -1
        self.procura_linha_girando(sentido, max_graus=120)

    def gap(self):
        """Linha sumiu: segue reto pelo giroscópio até achar de novo."""
        r = self.r
        mostra('gap? seguindo reto')

        def achou():
            ir = r.reflexao()
            if eh_prata(ir):
                return True               # fita prata da área de resgate
            pos, soma = posicao_linha(ir)
            return pos is not None
        if not r.anda_mm(GAP_MAX_MM, vel=30, para_se=achou):
            return True
        # não achou: volta e procura girando
        mostra('linha perdida: procurando')
        r.anda_mm(-GAP_MAX_MM, vel=35)
        self.procura_linha_girando(+1, max_graus=60)
        if posicao_linha(r.reflexao())[0] is None:
            self.procura_linha_girando(-1, max_graus=120)
        return False

    def obstaculo(self):
        """Contorna pela direita: gira 90°, anda, volta para o lado da linha até achar."""
        r = self.r
        mostra('obstáculo: contornando')
        r.anda_mm(-30, vel=30)
        r.gira(-90)
        r.anda_mm(170, vel=35)
        r.gira(90)
        r.anda_mm(420, vel=35)          # passa o obstáculo inteiro (robô + obstáculo + folga)
        r.gira(90)

        def achou():
            ir = r.reflexao()
            return min(ir) < PRETO
        r.anda_mm(260, vel=30, para_se=achou)
        r.anda_mm(60, vel=30)
        self.procura_linha_girando(-1, max_graus=120)

    # ------------------------------------------------------------------ laço principal
    def passo(self):
        r = self.r
        ir = r.reflexao()
        if not self.zona_feita and entrada_da_area(r, ir):
            r.para()
            self.zona_feita = True
            AreaResgate(r).executa()
            self.erro_ant = 0.0
            return
        cores = self.olha_verde()
        if cores.count('vermelho') >= 2:
            if not self.parado:
                mostra('fita vermelha: chegada!')
            self.parado = True
            r.para()
            return
        if r.para_choque() or r.frente_mm() < DIST_OBSTACULO:
            self.obstaculo()
            return
        incl = r.inclinacao()
        # pé e topo da rampa, lombada: o sensor sai da altura normal e TUDO fica escuro por
        # igual (ou claro demais). Leitura escura e sem contraste não é linha: segura a direção.
        sem_contraste = max(ir) < 70 and max(ir) - min(ir) < 30
        if sem_contraste:
            if self.z_reto is None:
                self.z_reto = r.z()
            corr = max(-15, min(15, (self.z_reto - r.z()) * 2.0))
            r.anda(VEL - corr, VEL + corr)
            mostra(f'sensor longe/perto do chão (IR {ir}): reto pelo giroscópio')
            return
        self.z_reto = None
        transicao = 3 <= abs(incl) <= 18
        pretos = [v < PRETO for v in ir]
        # faixa larga: um canal da ponta + os dois do meio (curva de 90°, T, cruzamento)
        if not transicao and (pretos[0] or pretos[3]) and pretos[1] and pretos[2]:
            if pretos[0] and not pretos[3]:
                lado = 'esq'
            elif pretos[3] and not pretos[0]:
                lado = 'dir'
            else:
                lado = 'esq' if ir[0] < ir[3] else 'dir'
            self.intersecao(lado)
            self.erro_ant = 0.0
            return
        pos, soma = posicao_linha(ir)
        if pos is None and transicao:
            r.anda(VEL, VEL)
            mostra('transição de rampa: reto')
            return
        if pos is None:
            if abs(self.erro_ant) > 10:
                # a linha estava escapando para um lado: é curva, não gap
                mostra('linha escapou: girando para o lado dela')
                z0 = r.z()
                sentido = 1 if self.erro_ant > 0 else -1
                self.procura_linha_girando(sentido, max_graus=110)
                if posicao_linha(r.reflexao())[0] is not None:
                    self.erro_ant = 0.0
                    return
                r.gira_para(z0)
            self.gap()
            self.erro_ant = 0.0
            return
        erro = pos
        d = erro - self.erro_ant
        self.erro_ant = erro
        corr = KP * erro + KD * d
        vel = VEL - 0.4 * abs(erro)      # mais devagar quando a linha está longe do centro
        if incl > 8:
            vel += 15          # subindo rampa
        elif incl < -8:
            vel -= 12          # descendo
        r.anda(vel - corr, vel + corr)
        mostra(f'linha {erro:+5.1f} mm  IR {ir}  {cores}')


def main():
    r = Robo()
    s = Seguidor(r)
    r.espera_botao()
    print('Começou!')
    try:
        while True:
            s.passo()
            time.sleep(0.01)
    finally:
        r.para()


if __name__ == '__main__':
    main()
