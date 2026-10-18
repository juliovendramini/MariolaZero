"""Tutorial 4b — o seguidor mais simples: dois canais do meio, "liga-desliga".

Funciona, mas balança muito e é lento. Compare com o seguidor_p.py.
    python simulador.py --robo robo_esteira.json --mapa mapas/curso_pista.json --programa CAMINHO/04_linha/seguidor_liga_desliga.py
"""
import time

from motores import Motores
from portas import Portas
from sensorCorReflexao import CorReflexao

PRETO = 50                     # abaixo disso o canal vê preto

motores = Motores(False)
motores.direcao_motor(2, Motores.INVERTIDO)
sensor = CorReflexao(Portas.SERIAL6)
while not sensor.conectado:
    time.sleep(0.01)


def anda(ve, vd):
    motores.velocidade_motores(ve, vd)
    motores.atualiza_motores()


try:
    fim = time.time() + 40
    while time.time() < fim:
        ir = sensor.le_reflexao()
        esq_preto = ir[1] < PRETO          # canal do meio à esquerda
        dir_preto = ir[2] < PRETO          # canal do meio à direita
        if esq_preto and not dir_preto:
            anda(5, 35)                    # linha puxando para a esquerda
        elif dir_preto and not esq_preto:
            anda(35, 5)                    # linha puxando para a direita
        else:
            anda(30, 30)                   # os dois (ou nenhum): reto
        time.sleep(0.01)
finally:
    anda(0, 0)
