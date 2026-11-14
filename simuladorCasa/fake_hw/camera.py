"""cv2.VideoCapture do simulador: a câmera da cabeça da garra.

O OpenCV de verdade continua sendo usado para todo o resto (cvtColor, inRange, findContours...); só
a captura é trocada. O dispositivo vem do robo.json (garra.camera.dispositivos, padrão 0 e
'/dev/video0'). Arquivos de vídeo/imagem que existem no PC abrem com o VideoCapture verdadeiro.

Tempo: a câmera solta um quadro a cada 1/fps (relógio do simulador). read() devolve o quadro mais
novo; se ele já foi lido, espera o próximo (como no robô, o laço fica preso no fps da câmera).
O tempo que o PC leva processando a imagem não conta (no Banana Pi conta).

Divisão do trabalho: o servidor manda só a pose da lente e as caixas que se mexem (objetos e dedos);
a imagem é desenhada aqui, no processo do programa (sim/camera_casa.py).
"""

import math
import os
import sys
import time

import numpy as np

from . import cliente
from sim import camera_casa as CC

CAP_PROP_POS_MSEC, CAP_PROP_FRAME_WIDTH, CAP_PROP_FRAME_HEIGHT, CAP_PROP_FPS = 0, 3, 4, 5
CAP_PROP_BUFFERSIZE = 38

_cena = None
_avisados = set()


def _avisa(msg):
    if msg not in _avisados:
        _avisados.add(msg)
        print('[simulador] ' + msg, file=sys.stderr, flush=True)


def config():
    g = cliente.config.get('garra') or (cliente.config.get('garras') or [None])[0]
    return (g or {}).get('camera')


def cena():
    global _cena
    if _cena is None:
        _cena = CC.Cena(cliente.conexao.chamar('casa')['casa'])
    return _cena


def instala():
    """Troca cv2.VideoCapture (se o OpenCV estiver instalado neste Python)."""
    try:
        import cv2
    except ImportError:
        return
    VideoCapture._Real = cv2.VideoCapture
    cv2.VideoCapture = VideoCapture


class VideoCapture:
    _Real = None

    def __init__(self, fonte=None, api=None, *args):
        self._real = None
        self._aberta = False
        if fonte is not None:
            self.open(fonte, api, *args)

    def open(self, fonte, api=None, *args):
        self.release()
        if isinstance(fonte, str) and os.path.isfile(fonte) and self._Real is not None:
            self._real = self._Real(fonte) if api is None else self._Real(fonte, api, *args)
            return self._real.isOpened()
        c = config()
        if c is None:
            _avisa(f'VideoCapture({fonte!r}): este robô não tem câmera ("garra.camera" no robo.json)')
            return False
        if fonte not in c.get('dispositivos', [0, '/dev/video0']):
            _avisa(f'VideoCapture({fonte!r}): não existe no simulador. A câmera é '
                   f'{" ou ".join(repr(d) for d in c.get("dispositivos", [0, "/dev/video0"]))}')
            return False
        self._w, self._h = int(c.get('largura_px', 320)), int(c.get('altura_px', 240))
        self._fps = float(c.get('fps', 15))
        self._fov = CC.campo_de_visao(c)
        self._t_quadro = -math.inf
        self._quadro = None
        self._aberta = True
        return True

    def isOpened(self):
        return self._real.isOpened() if self._real is not None else self._aberta

    def release(self):
        if self._real is not None:
            self._real.release()
            self._real = None
        self._aberta = False

    def grab(self):
        if self._real is not None:
            return self._real.grab()
        if not self._aberta:
            return False
        p = 1.0 / self._fps
        agora = time.monotonic()
        t = math.floor(agora / p + 1e-6) * p            # último quadro que a câmera soltou
        if t <= self._t_quadro + 1e-9:                  # esse já foi lido: espera o próximo
            t = self._t_quadro + p
            time.sleep(max(0.0, t - agora))
        self._t_quadro = t
        r = cliente.conexao.chamar('camera')
        self._quadro = cena().desenha(r['cam'], r['din'], self._w, self._h, *self._fov,
                                      rng=np.random.default_rng(r['s']))
        return True

    def retrieve(self, image=None, flag=0):
        if self._real is not None:
            return self._real.retrieve()
        if self._quadro is None:
            return False, None
        return True, self._quadro.copy()

    def read(self, image=None):
        if self._real is not None:
            return self._real.read()
        if not self.grab():
            return False, None
        return self.retrieve()

    def set(self, prop, valor):
        if self._real is not None:
            return self._real.set(prop, valor)
        if not self._aberta:
            return False
        if prop == CAP_PROP_FRAME_WIDTH and valor >= 16:
            self._w = int(valor)
        elif prop == CAP_PROP_FRAME_HEIGHT and valor >= 16:
            self._h = int(valor)
        elif prop == CAP_PROP_FPS and valor > 0:
            self._fps = min(float(valor), float(config().get('fps', 15)))
        elif prop != CAP_PROP_BUFFERSIZE:
            return False
        return True

    def get(self, prop):
        if self._real is not None:
            return self._real.get(prop)
        if not self._aberta:
            return 0.0
        if prop == CAP_PROP_FRAME_WIDTH:
            return float(self._w)
        if prop == CAP_PROP_FRAME_HEIGHT:
            return float(self._h)
        if prop == CAP_PROP_FPS:
            return float(self._fps)
        if prop == CAP_PROP_POS_MSEC:
            return max(0.0, self._t_quadro) * 1000.0
        return 0.0

    def getBackendName(self):
        return 'SIMULADOR'

    def setExceptionMode(self, ligado):
        pass

    def __del__(self):
        try:
            self.release()
        except Exception:
            pass
