"""Tutorial 4b — seguidor de linha proporcional (P) e proporcional-derivativo (PD).

Troque KD para 0 e veja a diferença. Para na fita vermelha da chegada.
Robô de esteira, pista do curso (só curvas, sem interseção):
    python simulador.py --robo robo_esteira.json --mapa mapas/curso_pista.json --programa CAMINHO/04_linha/seguidor_p.py
"""
import time

from motores import Motores
from portas import Portas
from sensorCorReflexao import CorReflexao

VEL = 35      # velocidade base
KP = 1.4      # quanto corrige por mm de erro
KD = 5.0      # quanto corrige pela VARIAÇÃO do erro (amortece o zigue-zague)

# posição (mm, + = esquerda) de cada um dos 4 canais em relação ao centro do sensor
Y_CANAIS = [26.6, 8.9, -8.9, -26.6]

motores = Motores(False)
motores.direcao_motor(2, Motores.INVERTIDO)
sensor = CorReflexao(Portas.SERIAL6)
sensor.usa_cores(['branco', 'preto', 'verde', 'vermelho', 'prata'])


def anda(ve, vd):
    motores.velocidade_motores(int(max(-100, min(100, ve))), int(max(-100, min(100, vd))))
    motores.atualiza_motores()


def posicao_linha():
    """Onde está a linha (mm, + = à esquerda do centro), ou None se não vê preto."""
    ir = sensor.le_reflexao()
    pesos = [max(0, min(100, 100 - v)) / 100 for v in ir]   # 1 = preto, 0 = branco
    if sum(pesos) < 0.3:
        return None
    return sum(p * y for p, y in zip(pesos, Y_CANAIS)) / sum(pesos)


while not sensor.conectado:      # espera a primeira leitura chegar do sensor
    time.sleep(0.01)

def eh_vermelho(tcs):
    """Vermelho no TCS 1, 2 ou 3. A lib classifica; o RGB confirma (com pouca luz, como em
    cima da linha preta, a classificação sozinha às vezes erra)."""
    r, g, b, c = sensor.le_rgbc(tcs)
    return sensor.cor(tcs) == 'vermelho' and r > 1.8 * g and r > 1.8 * b and c > 20


try:
    erro_anterior = 0.0
    ultimo_lado = 1
    fim = time.time() + 60
    while time.time() < fim:
        if sum(eh_vermelho(k) for k in (1, 2, 3)) >= 2:   # fita vermelha da chegada
            print('Chegada!')
            anda(0, 0)
            time.sleep(6)                              # a regra pede mais de 5 s parado
            break
        pos = posicao_linha()
        if pos is None:
            # perdeu a linha: gira para o lado onde ela foi vista pela última vez
            anda(-25 * ultimo_lado, 25 * ultimo_lado)
        else:
            erro = pos                          # queremos a linha no centro (0 mm)
            correcao = KP * erro + KD * (erro - erro_anterior)
            erro_anterior = erro
            ultimo_lado = 1 if erro > 0 else -1
            anda(VEL - correcao, VEL + correcao)    # linha à esquerda -> roda direita mais rápida
        time.sleep(0.01)
finally:
    anda(0, 0)
