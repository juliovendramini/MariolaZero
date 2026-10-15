"""Exemplo de explorador para a Rescue Maze (ponto de partida para a equipe).

Estratégia simples: busca em profundidade ladrilho a ladrilho, paredes pelos VL53,
alinhamento pelo para-choque e pelos VL53 laterais, vítimas pelas câmeras laterais,
checkpoint salvo em arquivo, volta ao início no fim (ou quando o tempo aperta).

Roda no robô real e no simulador (python simulador.py --programa exemplo_aluno/main.py).
"""

import time

from navegacao import (Mapa, carrega_checkpoint, salva_checkpoint, vizinho)
from robo import FOLGA_FRENTE, LADRILHO, Robo

try:
    import simdebug          # só desenha no simulador; no robô use o simdebug.py vazio
except ImportError:
    simdebug = None

TEMPO_VOLTAR = 6.5 * 60     # depois disso, volta para o início
LADO_CAMERA = {'esquerda': 1, 'direita': 3}   # direção relativa de cada câmera


class Explorador:
    def __init__(self, robo):
        self.r = robo
        self.mapa = Mapa()
        self.pos = (0, 0)
        self.dir = 0
        self.inicio_rodada = time.time()
        cp = carrega_checkpoint()
        if cp:
            self.mapa, self.pos, self.dir, self.inicio_rodada = cp
            print(f'Retomando do checkpoint {self.pos} direção {self.dir}')
        # z_alvo do giroscópio para cada direção absoluta: z = (dir - dir_inicial) * 90
        self.dir_giro0 = self.dir
        self.r.z_alvo = 0.0

    # ------------------------------------------------------------------ utilidades
    def debug(self, txt=''):
        if simdebug:
            simdebug.pose(self.pos[0] * LADRILHO, self.pos[1] * LADRILHO, self.dir * 90)
            if txt:
                simdebug.texto(txt)

    def tempo(self):
        return time.time() - self.inicio_rodada

    def vira_para(self, d):
        giro = (d - self.dir) % 4
        if giro == 0:
            return
        graus = {1: 90, 2: 180, 3: -90}[giro]
        if giro == 2:
            self.r.gira(90)
            self.dir = (self.dir + 1) % 4
            self.procura_vitimas()
            self.r.gira(90)
        else:
            self.r.gira(graus)
        self.dir = d
        self.debug()
        self.procura_vitimas()

    # ------------------------------------------------------------------ percepção
    def le_paredes(self):
        d = self.r.le_distancias()
        esq = min(d['esq_frente'], d['esq_tras']) < 160
        dir_ = min(d['dir_frente'], d['dir_tras']) < 160
        frente = d['frente'] < 200
        self.mapa.set_parede(self.pos, self.dir, frente)
        self.mapa.set_parede(self.pos, (self.dir + 1) % 4, esq)
        self.mapa.set_parede(self.pos, (self.dir + 3) % 4, dir_)
        return frente, esq, dir_

    def centraliza(self, frente):
        """Corrige posição e ângulo usando paredes (reduz o erro acumulado)."""
        r = self.r
        if frente:
            if r.encosta_na_frente():
                # os dois botões apertados: robô está paralelo à parede -> corrige o giroscópio
                r.z_alvo = float(r.z())
            r.anda_mm(-FOLGA_FRENTE, vel=25)
        ang = r.alinha_parede_lateral()
        if ang is not None and abs(ang) < 20:
            # o robô está girado 'ang' graus em relação à parede: a direção "reta"
            # do labirinto, em graus do giroscópio, é z - ang (isso cancela a deriva)
            r.z_alvo = r.z() - ang
            if abs(ang) > 1.5:
                r.gira_para(r.z_alvo)

    def procura_vitimas(self):
        for v in self.r.camera.detecta_todas():
            parede = (self.dir + LADO_CAMERA[v['camera']]) % 4
            chave = (self.pos, parede)
            if chave in self.mapa.vitimas:
                continue
            self.mapa.vitimas.add(chave)
            print(f"Vítima {v.get('letra', v['tipo'])} ({v['status']}) na {v['camera']} em {self.pos}")
            self.debug(f"vítima {v['status']} em {self.pos}")
            self.r.pisca(5.6, 0.5)
            if v['kits'] > 0:
                self.r.kits.deposita(v['kits'], v['camera'])

    # ------------------------------------------------------------------ movimento
    def avanca(self):
        """Anda um ladrilho na direção atual. Retorna False se achou preto."""
        destino = vizinho(self.pos, self.dir)
        # se há parede à frente ao alcance, ela é uma referência melhor que o encoder
        f0 = self.r.le_distancias()['frente']
        if f0 < 700:
            alvo_frente = max(FOLGA_FRENTE, f0 - LADRILHO)
            motivo, andado = self.r.anda_mm(LADRILHO + 25, olha_preto=True, parar_frente=alvo_frente)
        else:
            motivo, andado = self.r.anda_mm(LADRILHO, olha_preto=True, parar_frente=FOLGA_FRENTE)
        if motivo == 'preto':
            print(f'Preto em {destino}: voltando')
            self.mapa.pisos[destino] = 'preto'
            self.mapa.visitados.add(destino)
            self.r.anda_mm(-andado, vel=35)
            return False
        self.pos = destino
        self.debug()
        return True

    def chegou(self):
        """Tarefas ao chegar no centro de um ladrilho."""
        self.mapa.visitados.add(self.pos)
        piso = self.r.piso()
        if piso == 'preto':
            # o robô nunca para em cima do preto: o sensor (na frente) está vendo o
            # próximo ladrilho porque o robô passou do centro
            piso = 'branco'
        if piso != 'branco':
            self.mapa.pisos[self.pos] = piso
        if piso == 'prata':
            # salva logo ao chegar: se houver LoP agora, o robô volta para cá
            salva_checkpoint(self.mapa, self.pos, self.dir, self.inicio_rodada)
            print(f'Checkpoint salvo em {self.pos}')
        if piso == 'vermelho':
            # exemplo: não entra na zona de perigo (troque se a equipe quiser arriscar)
            print('Entrada da zona de perigo: voltando')
            self.mapa.pisos[self.pos] = 'vermelho'
            self.vira_para((self.dir + 2) % 4)
            self.avanca()
            return
        frente, _, _ = self.le_paredes()
        self.centraliza(frente)
        if piso == 'azul':
            print('Azul: parado 5 s')
            self.r.para()
            self.r.espera(5.3)      # não use time.sleep longo: o Mariola desliga após 5 s sem comando
        self.procura_vitimas()
        self.debug(f'pos {self.pos} dir {self.dir} t={self.tempo():.0f}s')

    def segue_rota(self, rota):
        for d in rota:
            self.vira_para(d)
            if not self.avanca():
                return False
            self.chegou()
        return True

    # ------------------------------------------------------------------ estratégia
    def explora(self):
        self.chegou()
        while self.tempo() < TEMPO_VOLTAR:
            abertas = self.mapa.fronteira(self.pos)
            if abertas:
                pref = [self.dir, (self.dir + 1) % 4, (self.dir + 3) % 4, (self.dir + 2) % 4]
                d = next(x for x in pref if x in abertas)
                self.vira_para(d)
                if self.avanca():
                    self.chegou()
                continue
            rota = self.mapa.caminho(self.pos, lambda p: p in self.mapa.visitados and self.mapa.fronteira(p))
            if rota is None:
                print('Mapa todo explorado!')
                break
            self.segue_rota(rota)
        self.volta_ao_inicio()

    def volta_ao_inicio(self):
        print('Voltando ao início...')
        if self.pos != (0, 0):
            rota = self.mapa.caminho(self.pos, lambda p: p == (0, 0))
            if rota is None:
                print('Sem caminho conhecido para o início')
                return
            self.segue_rota(rota)
        if self.pos == (0, 0):
            print('No início: sinal de saída')
            self.r.pisca(11, 1.0)


def main():
    robo = Robo()
    robo.led(False)
    robo.espera_botao()
    # acende a iluminação DEPOIS do botão: enquanto espera, o Mariola fica sem comando e,
    # após 5 s, o firmware apaga todos os LEDs
    robo.ilumina_cameras(True)      # sem luz as câmeras não enxergam as vítimas
    robo.giro.reseta_z()
    time.sleep(0.1)
    ex = Explorador(robo)
    try:
        ex.explora()
    finally:
        try:
            robo.para()
            robo.led(False)
            robo.ilumina_cameras(False)
        except Exception:
            pass     # interrompido no meio de uma transação serial: só garante a saída


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Interrompido.')
