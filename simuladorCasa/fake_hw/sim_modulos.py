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


def fora_do_relogio(ident=None):
    """A thread que chama isto (ou a de identificador 'ident') deixa de contar para o relógio
    sincronizado do simulador. Para threads que não são do robô e nunca dormem pelo time.sleep: o laço
    do asyncio que conversa com o Claude Code, as threads de vigia do tqdm que as bibliotecas de fala
    criam. Sem isto o relógio nunca vê "todas as threads esperando" e passa a andar pelo relógio real o
    tempo todo: o programa fica com menos voltas de laço por segundo e o robô anda pior."""
    import threading
    internos = getattr(cliente.relogio, 'internos', None)
    if internos is not None:
        internos.add(ident if ident is not None else threading.get_ident())


def modulos():
    sd = types.ModuleType('simdebug')
    sd.pose, sd.texto, sd.marca, sd.limpa = pose, texto, marca, limpa
    sd.fora_do_relogio = fora_do_relogio
    sd.NO_SIMULADOR = True
    return {'simdebug': sd}
