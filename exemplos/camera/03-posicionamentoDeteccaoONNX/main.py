# Deteccao de objetos usando OpenCV DNN com modelo ONNX (YOLOv8)
# Nao depende de ultralytics nem torch -- inicializacao muito mais rapida
# Para gerar o ONNX: yolo export model=yolov8n.pt format=onnx imgsz=320
import cv2
import numpy as np
from flask import Flask, Response
import time
import threading

# --- Configuracoes ---
MODELO_ONNX   = "best.onnx"  # coloque o arquivo .onnx na mesma pasta
CONFIANCA_MIN = 0.5
NMS_LIMIAR    = 0.4
LARG_ENTRADA  = 320
ALT_ENTRADA   = 320

CLASSES = ["Black Ball","Silver Ball"]

# Carrega a rede ONNX via OpenCV DNN (sem torch, sem ultralytics)

net = cv2.dnn.readNetFromONNX(MODELO_ONNX)
net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)

app = Flask(__name__)
camera = cv2.VideoCapture(1)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # buffer minimo para evitar frames atrasados
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

frameAtual   = None
frameCaptura = None
lock_frame   = threading.Lock()

# Thread dedicada para captura: evita que camera.read() bloqueie o loop de inferencia
def capturar_frames():
    global frameCaptura
    while True:
        ret, frame = camera.read()
        if ret and frame is not None:
            frameCaptura = frame  # atribuicao atomica no CPython (GIL)

threading.Thread(target=capturar_frames, daemon=True).start()


def detectar_yolov8(frame):
    """Executa inferencia YOLOv8 ONNX via OpenCV e retorna lista de deteccoes."""
    altura_orig, largura_orig = frame.shape[:2]

    blob = cv2.dnn.blobFromImage(
        frame, scalefactor=1 / 255.0,
        size=(LARG_ENTRADA, ALT_ENTRADA),
        swapRB=True, crop=False
    )
    net.setInput(blob)
    saida = net.forward()  # shape: [1, num_saidas, N]
    saida = saida[0].T     # [N, num_saidas]

    scale_x = largura_orig / LARG_ENTRADA
    scale_y = altura_orig  / ALT_ENTRADA

    # --- Vetorizacao NumPy: substitui o loop Python por operacoes de array ---
    scores_classes = saida[:, 4:]                                        # [N, C]
    ids_classes    = np.argmax(scores_classes, axis=1)                   # [N]
    confianças     = scores_classes[np.arange(len(saida)), ids_classes]  # [N]

    mask = confianças >= CONFIANCA_MIN
    if not np.any(mask):
        return []

    saida_f = saida[mask]
    ids_f   = ids_classes[mask]
    conf_f  = confianças[mask]

    cx   = saida_f[:, 0];  cy   = saida_f[:, 1]
    w    = saida_f[:, 2];  h    = saida_f[:, 3]
    x1   = ((cx - w / 2) * scale_x).astype(np.int32)
    y1   = ((cy - h / 2) * scale_y).astype(np.int32)
    larg = (w * scale_x).astype(np.int32)
    alt  = (h * scale_y).astype(np.int32)

    caixas      = np.stack([x1, y1, larg, alt], axis=1).tolist()
    confianças_l = conf_f.tolist()

    # Non-Maximum Suppression
    indices = cv2.dnn.NMSBoxes(caixas, confianças_l, CONFIANCA_MIN, NMS_LIMIAR)

    deteccoes = []
    if len(indices) > 0:
        for i in indices.flatten():
            x, y, lw, lh = caixas[i]
            nome = CLASSES[ids_f[i]] if ids_f[i] < len(CLASSES) else str(ids_f[i])
            deteccoes.append({
                "caixa": (x, y, x + lw, y + lh),
                "confianca": confianças_l[i],
                "nome_classe": nome,
            })
    return deteccoes


# Define a funcao de geracao de frames MJPEG
def atualizaTransmissao():
    while True:
        with lock_frame:
            local = frameAtual
        if local is None:
            time.sleep(0.01)
            continue
        ret, buffer = cv2.imencode('.jpg', local)
        if not ret:
            continue
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
        time.sleep(0.1)  # transmissao a cada 0.1 segundo


# Rota para o streaming de video
@app.route('/video')
def video_feed():
    return Response(atualizaTransmissao(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def iniciar_flask():
    app.run(host='0.0.0.0', port=8080, threaded=True)


print("Exemplo processamento de IA encontrando posicao dos objetos detectados na camera")
# O Flask roda em thread separada para nao bloquear o loop principal
flask_thread = threading.Thread(target=iniciar_flask)
flask_thread.daemon = True
flask_thread.start()

objetos_detectados = []
frame_count = 0

# A cada frame da camera: detecta objetos, salva posicao/area/classe e anota a imagem
while True:
    start_time = time.time()

    if frameCaptura is None:
        time.sleep(0.01)
        continue
    frame = frameCaptura  # sem copia: detectar_yolov8 nao modifica o frame

    deteccoes = detectar_yolov8(frame)
    objetos_detectados.clear()  # Limpa a lista a cada frame
    frame_anotado = frame.copy()

    for det in deteccoes:
        x1, y1, x2, y2 = det["caixa"]
        classe_nome = det["nome_classe"]

        # Calcula centro e area
        centro_x = (x1 + x2) // 2
        centro_y = (y1 + y2) // 2
        largura   = x2 - x1
        altura    = y2 - y1
        area      = largura * altura

        # Salva na lista global para uso posterior
        objetos_detectados.append([centro_x, centro_y, area, classe_nome])

        # Anotacoes visuais (podem ser comentadas se nao forem necessarias)
        cv2.rectangle(frame_anotado, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(frame_anotado, (centro_x, centro_y), 5, (0, 0, 255), -1)
        cv2.putText(frame_anotado, f"Area: {area}", (centro_x, centro_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        cv2.putText(frame_anotado, f"Classe: {classe_nome}", (centro_x, centro_y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)

    # Calcula e exibe FPS
    fps = 1.0 / (time.time() - start_time)
    cv2.putText(frame_anotado, f"FPS: {fps:.1f}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # Envia o frame anotado para o Flask (com lock para evitar race condition)
    with lock_frame:
        frameAtual = frame_anotado

    print(f"FPS: {fps:.1f} - Objetos detectados: {objetos_detectados}")

    #cv2.imshow("YOLOv8 ONNX - Webcam 320x240", frameAtual)
    # Pressione 'q' para sair
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break