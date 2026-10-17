"""Módulos que só existem no simulador (no robô real, use os arquivos de robo_real/):

* simdebug -> desenha a pose estimada / textos na tela do simulador
* visao    -> stub da câmera da frente (vítimas e triângulos já detectados)
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


class Deteccao:
    """Uma detecção da câmera. Vítima: tipo ('viva'/'morta'), angulo (graus, + = esquerda),
    distancia (mm), x, y, raio_px, confianca. Triângulo: cor ('verde'/'vermelho'), angulo,
    distancia (até a parede dele), x, x_min, x_max, largura_px."""

    def __init__(self, d):
        self.__dict__.update(d)

    def __repr__(self):
        return 'Deteccao(' + ', '.join(f'{k}={v}' for k, v in self.__dict__.items()) + ')'


class Visao:
    """Stub da câmera da frente (no robô real, robo_real/visao.py faz o mesmo com a YOLO e o OpenCV).

    vitimas()    -> lista de Deteccao das vítimas (IA a ~4 quadros/s)
    triangulos() -> lista de Deteccao dos triângulos (OpenCV a ~30 quadros/s)

    Cada chamada espera o próximo quadro e devolve o que a câmera viu quando ele foi capturado
    (o processamento leva um quadro: a resposta chega atrasada, como no robô)."""

    def __init__(self, camera=None, fps_vitimas=None, fps_triangulos=None):
        cam = cliente.config.get('camera')
        if not cam:
            raise RuntimeError('este robô não tem câmera (sem "camera" no robo.json)')
        self.periodo = {'vitimas': 1.0 / float(fps_vitimas or cam.get('fps_vitimas', 4)),
                        'triangulos': 1.0 / float(fps_triangulos or cam.get('fps_triangulos', 30))}
        self._livre = {'vitimas': 0.0, 'triangulos': 0.0}

    def _quadro(self, tipo):
        import time
        agora = time.time()
        inicio = max(agora, self._livre[tipo])
        if inicio > agora:
            time.sleep(inicio - agora)
        r = cliente.conexao.chamar('visao', tipo=tipo)['v']
        fim = inicio + self.periodo[tipo]
        self._livre[tipo] = fim
        resto = fim - time.time()
        if resto > 0:
            time.sleep(resto)
        return [Deteccao(d) for d in r]

    def vitimas(self):
        return self._quadro('vitimas')

    def triangulos(self):
        return self._quadro('triangulos')


def modulos():
    sd = types.ModuleType('simdebug')
    sd.pose, sd.texto, sd.marca, sd.limpa = pose, texto, marca, limpa
    sd.NO_SIMULADOR = True
    vi = types.ModuleType('visao')
    vi.Visao, vi.Deteccao = Visao, Deteccao
    vi.NO_SIMULADOR = True
    return {'simdebug': sd, 'visao': vi}
