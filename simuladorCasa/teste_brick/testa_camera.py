"""Mede a câmera e a rede neural de detecção (YOLO) no próprio Mariola.

Roda no brick, com o venv que já está nele (o /meu_venv, que tem OpenCV, onnxruntime, ncnn e
Ultralytics):

    cd ~/robo_casa
    /meu_venv/bin/python testa_camera.py                                    (câmera da porta 3, ncnn)
    /meu_venv/bin/python testa_camera.py --modelo modelos/yolo11n.onnx modelos/yolo11n_ncnn_model
    /meu_venv/bin/python testa_camera.py --quadros 60 --tamanho 256

Mostra quanto tempo leva para pegar um quadro da câmera e para a rede achar os objetos nele, e grava
a última foto com as caixas desenhadas em saida/camera_<modelo>.jpg (para olhar no PC).

A rede é a YOLO11n pronta (treinada no COCO, 80 classes: pessoa, cadeira, garrafa, ursinho, bola...).
Ela não conhece "roupa" nem "brinquedo" do jeito que o robô precisa: aqui o que interessa é a
velocidade. A rede do robô (roupa / brinquedo / deixa) vai ser treinada depois com fotos da casa.
"""

import argparse
import os
import time

import cv2

AQUI = os.path.dirname(os.path.abspath(__file__))


def abre_camera(disp, largura, altura):
    cam = cv2.VideoCapture(disp, cv2.CAP_V4L2)
    if not cam.isOpened():
        raise SystemExit(f'não abri a câmera {disp}')
    cam.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
    cam.set(cv2.CAP_PROP_FRAME_WIDTH, largura)
    cam.set(cv2.CAP_PROP_FRAME_HEIGHT, altura)
    cam.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    return cam


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--camera', default='/dev/video_usb3', help='dispositivo da câmera (padrão: a da porta 3)')
    ap.add_argument('--modelo', nargs='+', default=[os.path.join(AQUI, 'modelos', 'yolo11n_ncnn_model')],
                    help='um ou mais modelos (.onnx, .pt ou a pasta _ncnn_model)')
    ap.add_argument('--tamanho', type=int, default=320, help='lado da imagem que entra na rede (px)')
    ap.add_argument('--quadros', type=int, default=30)
    ap.add_argument('--resolucao', default='640x480', help='resolução pedida à câmera')
    ap.add_argument('--confianca', type=float, default=0.35)
    ap.add_argument('--gira', type=int, default=0, choices=(0, 90, 180, 270),
                    help='gira a imagem (graus, sentido horário): câmera montada de lado ou de cabeça para baixo')
    a = ap.parse_args()
    giro = {90: cv2.ROTATE_90_CLOCKWISE, 180: cv2.ROTATE_180, 270: cv2.ROTATE_90_COUNTERCLOCKWISE}.get(a.gira)

    def foto():
        ok, im = cam.read()
        return (cv2.rotate(im, giro) if ok and giro is not None else im) if ok else None

    os.environ.setdefault('YOLO_CONFIG_DIR', os.path.join(AQUI, '.ultralytics'))
    from ultralytics import YOLO

    lg, al = (int(v) for v in a.resolucao.lower().split('x'))
    cam = abre_camera(a.camera, lg, al)
    for _ in range(5):                              # os primeiros quadros saem escuros (exposição)
        cam.read()
    t0 = time.perf_counter()
    for _ in range(10):
        img = foto()
    t_cap = (time.perf_counter() - t0) / 10
    if img is None:
        raise SystemExit('a câmera abriu mas não mandou imagem')
    print(f'câmera {a.camera}: {img.shape[1]}x{img.shape[0]}, {t_cap * 1000:.0f} ms por quadro '
          f'({1 / t_cap:.1f} quadros/s só de captura)')
    os.makedirs(os.path.join(AQUI, 'saida'), exist_ok=True)

    for caminho in a.modelo:
        nome = os.path.basename(caminho.rstrip('/'))
        t = time.perf_counter()
        rede = YOLO(caminho, task='detect')
        rede.predict(img, imgsz=a.tamanho, verbose=False)           # a primeira é mais lenta (prepara tudo)
        print(f'\n{nome}: carregou em {time.perf_counter() - t:.1f} s')
        tempos, vistos = [], {}
        res = None
        for _ in range(a.quadros):
            img = foto()
            if img is None:
                continue
            t = time.perf_counter()
            res = rede.predict(img, imgsz=a.tamanho, conf=a.confianca, verbose=False)[0]
            tempos.append(time.perf_counter() - t)
            for c in res.boxes.cls.tolist():
                n = res.names[int(c)]
                vistos[n] = vistos.get(n, 0) + 1
        tempos.sort()
        med = tempos[len(tempos) // 2]
        print(f'  rede em {a.tamanho} px: mediana {med * 1000:.0f} ms, melhor {tempos[0] * 1000:.0f}, '
              f'pior {tempos[-1] * 1000:.0f}  ->  {1 / (med + t_cap):.1f} quadros/s com a captura')
        print('  viu (quadros em que apareceu): ' + (', '.join(f'{n} {k}' for n, k in
                                                        sorted(vistos.items(), key=lambda x: -x[1])) or 'nada'))
        if res is not None:
            foto = os.path.join(AQUI, 'saida', f'camera_{os.path.splitext(nome)[0]}.jpg')
            cv2.imwrite(foto, res.plot())
            print(f'  última foto com as caixas: {foto}')
    cam.release()


if __name__ == '__main__':
    main()
