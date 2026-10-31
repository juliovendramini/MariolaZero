"""Módulos que só existem no simulador (no robô real, use os arquivos de robo_real/):

* simdebug -> desenha a pose estimada / textos na tela do simulador
"""

import types

from . import cliente


def pose(x_mm, y_mm, theta_graus):
    """Pose que o seu algoritmo acha que o robô está, no referencial do início
    (x para frente na direção inicial, y para a esquerda, theta anti-horário)."""
    cliente.conexao.chamar('debug', pose=[float(x_mm), float(y_mm), float(theta_graus)])


def texto(s):
    cliente.conexao.chamar('debug', texto=str(s))


def marca(x_mm, y_mm, cor='amarelo'):
    cliente.conexao.chamar('debug', marca=[float(x_mm), float(y_mm), cor])


def limpa():
    cliente.conexao.chamar('debug', limpa=True)


def modulos():
    sd = types.ModuleType('simdebug')
    sd.pose, sd.texto, sd.marca, sd.limpa = pose, texto, marca, limpa
    sd.NO_SIMULADOR = True
    return {'simdebug': sd}
