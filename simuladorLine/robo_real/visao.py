"""visao.py — versão do ROBÔ REAL da câmera da frente (no simulador este módulo é um stub).

Mesma interface do simulador, para o mesmo programa rodar nos dois:

    from visao import Visao
    v = Visao()
    for d in v.vitimas():      # d.tipo ('viva'/'morta'), d.angulo (graus, + = esquerda),
        ...                    # d.distancia (mm), d.x, d.y, d.raio_px, d.confianca
    for t in v.triangulos():   # t.cor ('verde'/'vermelho'), t.angulo, t.distancia, t.x, t.x_min,
        ...                    # t.x_max, t.largura_px

Aqui é só o esqueleto: troque _detecta_vitimas() pela sua YOLO (exemplos em
bananaPiM4Zero/exemplos/camera/03-posicionamentoDeteccao*) e _detecta_triangulos() pelo seu
OpenCV (exemplos 04/07). As contas de ângulo e distância usam a câmera como no simulador:
altura ALTURA_MM, ângulo de visão FOV_GRAUS, imagem LARGURA x ALTURA.
"""

import math
import threading
import time

import cv2

NO_SIMULADOR = False

CAMERA = '/dev/video_usb1'      # ou o índice (0, 1...)
LARGURA, ALTURA = 320, 240
FOV_GRAUS = 62.0                # ângulo de visão horizontal (A MEDIR)
ALTURA_MM = 50.0                # altura da câmera (A MEDIR)
RAIO_BOLA = 22.5


class Deteccao:
    def __init__(self, **d):
        self.__dict__.update(d)

    def __repr__(self):
        return 'Deteccao(' + ', '.join(f'{k}={v}' for k, v in self.__dict__.items()) + ')'


class Visao:
    def __init__(self, camera=CAMERA):
        self.cap = cv2.VideoCapture(camera)
        self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, LARGURA)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, ALTURA)
        self.f = (LARGURA / 2) / math.tan(math.radians(FOV_GRAUS) / 2)
        self.quadro = None
        self._trava = threading.Lock()
        threading.Thread(target=self._captura, daemon=True).start()

    def _captura(self):
        while True:
            ok, img = self.cap.read()
            if ok:
                with self._trava:
                    self.quadro = img
            else:
                time.sleep(0.01)

    def _ultimo(self):
        while True:
            with self._trava:
                if self.quadro is not None:
                    return self.quadro.copy()
            time.sleep(0.005)

    # ---------------------------------------------------------------- conversões
    def angulo(self, x):
        return math.degrees(math.atan((LARGURA / 2 - x) / self.f))

    def distancia_bola(self, raio_px):
        return self.f * RAIO_BOLA / max(raio_px, 1e-3)

    # ---------------------------------------------------------------- interface
    def vitimas(self):
        img = self._ultimo()
        out = []
        for tipo, x, y, raio, conf in self._detecta_vitimas(img):
            out.append(Deteccao(tipo=tipo, angulo=round(self.angulo(x), 1),
                                distancia=round(self.distancia_bola(raio)), x=x, y=y,
                                raio_px=raio, confianca=conf))
        out.sort(key=lambda d: d.distancia)
        return out

    def triangulos(self):
        img = self._ultimo()
        out = []
        for cor, x_min, x_max, y_base in self._detecta_triangulos(img):
            x = (x_min + x_max) / 2
            # distância pela linha de baixo da parede no chão (câmera a ALTURA_MM do piso)
            dep = math.atan((y_base - ALTURA / 2) / self.f)
            dist = ALTURA_MM / math.tan(dep) if dep > 0.01 else 9999
            out.append(Deteccao(cor=cor, angulo=round(self.angulo(x), 1), distancia=round(dist),
                                x=round(x), x_min=x_min, x_max=x_max, largura_px=x_max - x_min))
        return out

    # ---------------------------------------------------------------- troque pelo seu código
    def _detecta_vitimas(self, img):
        """Lista de (tipo, x, y, raio_px, confianca). Coloque aqui a sua YOLO."""
        raise NotImplementedError('coloque aqui a detecção de vítimas (YOLO) do seu robô')

    def _detecta_triangulos(self, img):
        """Lista de (cor, x_min, x_max, y_base) das paredes verde/vermelha. Coloque aqui o OpenCV."""
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        faixas = {'verde': [((40, 80, 40), (85, 255, 255))],
                  'vermelho': [((0, 120, 60), (8, 255, 255)), ((170, 120, 60), (180, 255, 255))]}
        out = []
        for cor, fs in faixas.items():
            mascara = None
            for lo, hi in fs:
                m = cv2.inRange(hsv, lo, hi)
                mascara = m if mascara is None else cv2.bitwise_or(mascara, m)
            cont, _ = cv2.findContours(mascara, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cont:
                continue
            c = max(cont, key=cv2.contourArea)
            if cv2.contourArea(c) < 150:
                continue
            x, y, w, h = cv2.boundingRect(c)
            out.append((cor, x, x + w, y + h))
        return out
