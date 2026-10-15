"""Módulos que só existem no simulador (no robô real, use os arquivos de robo_real/):

* deteccaoVitimas  -> DeteccaoVitimas.detecta()
* dispensadorKits  -> DispensadorKits.deposita(quantidade, lado)
* simdebug         -> desenha a pose estimada / textos na tela do simulador
"""

import time
import types

from . import cliente


# ---------------------------------------------------------------- deteccaoVitimas
class DeteccaoVitimas:
    """Câmeras de vítimas. No simulador a detecção "funciona": devolve o que a câmera enxerga.

    detecta(camera=None) -> dict ou None
        {'camera': 'esquerda'|'direita', 'tipo': 'letra'|'cognitivo',
         'status': 'ferida'|'estavel'|'ilesa', 'kits': 2|1|0,
         'letra': 'H'|'S'|'U' (só para letras), 'distancia_mm': int}
    """
    ESQUERDA = 'esquerda'
    DIREITA = 'direita'
    FERIDA = 'ferida'
    ESTAVEL = 'estavel'
    ILESA = 'ilesa'

    def __init__(self, *args, **kwargs):
        self.tempo = float(cliente.config.get('deteccao', {}).get('tempo_processamento_s', 0.03))

    def detecta_todas(self, camera=None):
        if self.tempo > 0:
            time.sleep(self.tempo)
        return cliente.conexao.chamar('vitimas', camera=camera)['v']

    def detecta(self, camera=None):
        v = self.detecta_todas(camera)
        return v[0] if v else None

    def fechar(self):
        pass


# ---------------------------------------------------------------- dispensadorKits
class DispensadorKits:
    """Depósito de kits de resgate. deposita() devolve quantos kits saíram."""
    ESQUERDA = 'esquerda'
    DIREITA = 'direita'

    def __init__(self, *args, **kwargs):
        self.tempo = float(cliente.config['kits'].get('tempo_por_kit_s', 0.7))

    def deposita(self, quantidade=1, lado='esquerda'):
        if lado not in ('esquerda', 'direita'):
            raise ValueError("lado deve ser 'esquerda' ou 'direita'")
        n = 0
        for _ in range(int(quantidade)):
            time.sleep(self.tempo)
            r = cliente.conexao.chamar('kit', qtd=1, lado=lado)
            n += r['n']
        return n

    def restantes(self):
        return cliente.conexao.chamar('kits_restantes')['n']


# ---------------------------------------------------------------- simdebug
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
    dv = types.ModuleType('deteccaoVitimas')
    dv.DeteccaoVitimas = DeteccaoVitimas
    dk = types.ModuleType('dispensadorKits')
    dk.DispensadorKits = DispensadorKits
    sd = types.ModuleType('simdebug')
    sd.pose, sd.texto, sd.marca, sd.limpa = pose, texto, marca, limpa
    sd.NO_SIMULADOR = True
    return {'deteccaoVitimas': dv, 'dispensadorKits': dk, 'simdebug': sd}
