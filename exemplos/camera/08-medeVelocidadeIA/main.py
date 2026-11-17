# Mede quanto tempo a rede de vítimas (YOLOv8) leva no brick, foto por foto, SEM câmera.
# Compara o ONNX (OpenCV DNN, como no 03-posicionamentoDeteccaoONNX) com o NCNN
# (como no 03-posicionamentoDeteccaoNCNN) e mostra quantas bolas cada um achou.
#
# Como usar (no brick, pelo SSH):
#   1. Copie para esta pasta:
#        best.onnx                  -> yolo export model=best.pt format=onnx imgsz=320
#        best_ncnn_model/           -> yolo export model=best.pt format=ncnn imgsz=320
#        fotos/                     -> algumas fotos .jpg da câmera do robô (320x240)
#      Falta o .onnx ou o NCNN? Ele mede só o que encontrar. Sem fotos, usa imagens aleatórias
#      (o tempo vale, as detecções não).
#   2. python3 main.py            (3 passadas por todas as fotos)
#      python3 main.py 5          (5 passadas)
#
# A rede roda nos 4 núcleos e esquenta o brick: acompanhe a temperatura que ele imprime.
# Resultado de 17/11/2026 (rede da equipe, YOLOv8n 320, brick sem cooler, 198 fotos):
#   ONNX (OpenCV DNN) ...... 4,4 fps (~228 ms por foto)
#   NCNN 4 núcleos ......... 7,6 fps (~131 ms)
#   NCNN 3 núcleos ......... 6,7 fps (~150 ms)  <- deixa um núcleo livre para o resto do programa
#   NCNN 2 núcleos ......... 5,8 fps (~173 ms)
#   As detecções do ONNX e do NCNN foram as mesmas.
import glob
import os
import sys
import time

import cv2
import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
ONNX = os.path.join(AQUI, "best.onnx")
PASTA_NCNN = os.path.join(AQUI, "best_ncnn_model")
PASTA_FOTOS = os.path.join(AQUI, "fotos")
PASSADAS = int(sys.argv[1]) if len(sys.argv) > 1 else 3

TAM = 320          # tamanho de entrada da rede (o mesmo do export)
CONFIANCA = 0.5
NMS = 0.4
CLASSES = ["preta", "prata"]


def temperatura():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as f:
            return int(f.read()) / 1000
    except OSError:
        return float("nan")


def prepara(img):
    # igual ao exemplo ONNX: estica a foto para 320x320 e divide por 255
    return cv2.dnn.blobFromImage(img, 1 / 255.0, (TAM, TAM), swapRB=True, crop=False)


def deteccoes(saida):
    # saida: [1, 6, 2100] -> lista de (classe, confiança) depois do NMS
    saida = saida[0].T
    notas = saida[:, 4:]
    ids = np.argmax(notas, axis=1)
    conf = notas[np.arange(len(saida)), ids]
    ok = conf >= CONFIANCA
    if not np.any(ok):
        return []
    s, ids, conf = saida[ok], ids[ok], conf[ok]
    caixas = np.stack([s[:, 0] - s[:, 2] / 2, s[:, 1] - s[:, 3] / 2, s[:, 2], s[:, 3]], 1)
    escolhidas = cv2.dnn.NMSBoxes(caixas.tolist(), conf.tolist(), CONFIANCA, NMS)
    return [(int(ids[i]), float(conf[i])) for i in np.array(escolhidas).flatten()]


def motor_onnx():
    net = cv2.dnn.readNetFromONNX(ONNX)
    net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
    net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

    def roda(blob):
        net.setInput(blob)
        return net.forward()
    return roda


def motor_ncnn(nucleos):
    import ncnn
    net = ncnn.Net()
    net.opt.use_vulkan_compute = False
    net.opt.num_threads = nucleos
    net.load_param(os.path.join(PASTA_NCNN, "model.ncnn.param"))
    net.load_model(os.path.join(PASTA_NCNN, "model.ncnn.bin"))

    def roda(blob):
        with net.create_extractor() as ex:
            ex.input("in0", ncnn.Mat(blob[0]))
            _, saida = ex.extract("out0")
        return np.array(saida)[None]      # [1, 6, 2100], igual ao ONNX
    return roda


fotos = sorted(glob.glob(os.path.join(PASTA_FOTOS, "*.jpg")))
if fotos:
    imagens = [cv2.imread(f) for f in fotos]
else:
    print("Sem a pasta fotos/: usando 20 imagens aleatórias (só o tempo vale).")
    imagens = [np.random.randint(0, 255, (240, 320, 3), np.uint8) for _ in range(20)]

motores = []
if os.path.exists(ONNX):
    motores.append(("ONNX (OpenCV DNN)", motor_onnx))
else:
    print("Não achei o best.onnx")
if os.path.isdir(PASTA_NCNN):
    for n in (4, 3, 2):
        motores.append((f"NCNN {n} núcleos", lambda n=n: motor_ncnn(n)))
else:
    print("Não achei a pasta best_ncnn_model/")

print(f"{len(imagens)} imagens, {PASSADAS} passadas, temperatura {temperatura():.0f} °C\n")
for nome, cria in motores:
    roda = cria()
    for img in imagens[:5]:              # aquecimento (a 1ª rodada é sempre mais lenta)
        roda(prepara(img))
    tempos = []
    achou = [0, 0]
    t_ini = temperatura()
    for passada in range(PASSADAS):
        for img in imagens:
            inicio = time.perf_counter()
            dets = deteccoes(roda(prepara(img)))
            tempos.append(time.perf_counter() - inicio)
            if passada == 0:
                for classe, _ in dets:
                    achou[classe] += 1
    ms = np.array(tempos) * 1000
    print(f"{nome:20s} {1000 / ms.mean():4.1f} fps | média {ms.mean():5.0f} ms, pior 5% {np.percentile(ms, 95):4.0f} ms"
          f" | achou {achou[0]} pretas e {achou[1]} pratas | {t_ini:.0f} -> {temperatura():.0f} °C", flush=True)
