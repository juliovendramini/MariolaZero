# Melhoria dos exemplos anteriores, agora detectando objetos e marcando a posição deles na tela, além de exibir posição e área
# As classes também são identificadas e exibidas
# Versão: OpenCV mínimo + NCNN (sem ultralytics, sem torch)
#
# ── Conversão do modelo (executar UMA VEZ, offline) ──────────────────────────
#   Opção A – via ultralytics (recomendado, gera best_ncnn_model/):
#     pip install ultralytics
#     yolo export model=best.pt format=ncnn imgsz=320
#     → gera best_ncnn_model/model.ncnn.param e model.ncnn.bin
#
#   Opção B – via onnx2ncnn (binário do repositório NCNN):
#     onnx2ncnn best.onnx best.param best.bin
#
#   Ajuste PARAM_PATH / BIN_PATH abaixo conforme o caminho gerado.
# ─────────────────────────────────────────────────────────────────────────────
import cv2
import ncnn
import numpy as np
from flask import Flask, Response
import time
import threading

# ── Configurações ─────────────────────────────────────────────────────────────
PARAM_PATH   = "modelo_ncnn/model.ncnn.param"  # ajuste se necessário
BIN_PATH     = "modelo_ncnn/model.ncnn.bin"
INPUT_NAME   = "in0"    # nome da camada de entrada no .param
OUTPUT_NAME  = "out0"   # nome da camada de saída  no .param
INPUT_SIZE   = 320
CONF_THRESH  = 0.7
NMS_THRESH   = 0.45
NUM_THREADS  = 4

# Nomes das classes – deve corresponder à ordem usada no treinamento
CLASS_NAMES = ["Black Ball", "Silver Ball"]
# ─────────────────────────────────────────────────────────────────────────────

print("Iniciando o código, carregando a rede neural e a câmera...")
inicio = time.time()

# Carrega o modelo NCNN
net = ncnn.Net()
net.opt.use_vulkan_compute = False   # sem GPU Vulkan → CPU puro
net.opt.num_threads = NUM_THREADS
net.load_param(PARAM_PATH)
net.load_model(BIN_PATH)

fim = time.time()
print(f"Tempo de carregamento da rede: {fim - inicio:.2f} segundos")

app = Flask(__name__)
camera = cv2.VideoCapture(1)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Define o buffer para 1 frame, assim nao atraso nenhuma transmissão
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

frameAtual = None

# Define a função de geração de frames MJPEG
# Pega o frame atual (global) da camera, converte para JPEG e envia como resposta para ser exibido
def atualizaTransmissao():
    global frameAtual
    while True:
        # Codifica o frame como JPEG
        ret, buffer = cv2.imencode('.jpg', frameAtual)
        frame_bytes = buffer.tobytes()
        # Yield no formato MJPEG
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(1)  # transmissão a cada 1 segundo

# Rota para o streaming de vídeo
@app.route('/video')
def video_feed():
    return Response(atualizaTransmissao(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

def iniciar_flask():
    app.run(host='0.0.0.0', port=8080, threaded=True)


# ── Pré-processamento: letterbox para quadrado INPUT_SIZE x INPUT_SIZE ────────
def preprocess(frame):
    h, w = frame.shape[:2]
    scale = min(INPUT_SIZE / w, INPUT_SIZE / h)
    new_w = int(w * scale)
    new_h = int(h * scale)
    resized = cv2.resize(frame, (new_w, new_h))
    padded = np.full((INPUT_SIZE, INPUT_SIZE, 3), 114, dtype=np.uint8)
    pad_x = (INPUT_SIZE - new_w) // 2
    pad_y = (INPUT_SIZE - new_h) // 2
    padded[pad_y:pad_y + new_h, pad_x:pad_x + new_w] = resized
    return padded, scale, pad_x, pad_y


# ── Pós-processamento: saída YOLOv8 → detecções em coordenadas originais ──────
# Formato da saída NCNN (export ultralytics): [1, 4+num_classes, num_anchors]
# As 4 primeiras linhas = cx, cy, w, h em pixels do espaço INPUT_SIZE
def postprocess(output, scale, pad_x, pad_y, orig_w, orig_h):
    output = np.squeeze(output)          # → [4+num_classes, num_anchors]
    num_anchors = output.shape[1]

    raw_boxes, raw_scores, class_ids = [], [], []

    for i in range(num_anchors):
        cx, cy, bw, bh = output[0:4, i]
        class_scores = output[4:, i]
        class_id = int(np.argmax(class_scores))
        conf = float(class_scores[class_id])

        if conf < CONF_THRESH:
            continue

        # Converte de coordenadas do espaço letterbox para a imagem original
        x1 = (cx - bw / 2 - pad_x) / scale
        y1 = (cy - bh / 2 - pad_y) / scale
        x2 = (cx + bw / 2 - pad_x) / scale
        y2 = (cy + bh / 2 - pad_y) / scale

        x1 = max(0.0, min(float(x1), orig_w))
        y1 = max(0.0, min(float(y1), orig_h))
        x2 = max(0.0, min(float(x2), orig_w))
        y2 = max(0.0, min(float(y2), orig_h))

        raw_boxes.append([x1, y1, x2 - x1, y2 - y1])  # formato [x,y,w,h] para NMS
        raw_scores.append(conf)
        class_ids.append(class_id)

    if not raw_boxes:
        return []

    indices = cv2.dnn.NMSBoxes(raw_boxes, raw_scores, CONF_THRESH, NMS_THRESH)

    detections = []
    for idx in indices:
        i = int(idx) if not isinstance(idx, (list, np.ndarray)) else int(idx[0])
        x, y, w, h = raw_boxes[i]
        detections.append({
            'x1': int(x),        'y1': int(y),
            'x2': int(x + w),    'y2': int(y + h),
            'conf': raw_scores[i],
            'class_id': class_ids[i],
        })
    return detections
# ─────────────────────────────────────────────────────────────────────────────


print("Exemplo processamento de IA encontrando posição dos objetos detectados na camera")
# o código do flask deve ser iniciado em uma thread separada para poder rodar junto com o código principal
flask_thread = threading.Thread(target=iniciar_flask)
flask_thread.daemon = True
flask_thread.start()

objetos_detectados = []

# no exemplo abaixo, a cada frame da câmera, o código detecta os objetos e exibe a posição deles na tela, além de exibir a área e a classe do objeto detectado
# tudo é salvo numa lista de objetos detectados, que é limpa a cada frame
# essa lista pode ser utilizada depois em outros locais do código para tomar decisões ou enviar para outro lugar
while True:
    start_time = time.time()

    # Captura o frame da câmera
    i = 0
    while i < 5:  # descarta frames antigos para evitar atrasos na transmissão
        camera.grab()
        i += 1
    ret, frame = camera.retrieve()
    if not ret:
        break

    orig_h, orig_w = frame.shape[:2]

    # ── Pré-processamento ────────────────────────────────────────────────────
    input_img, scale, pad_x, pad_y = preprocess(frame)

    # ── Inferência NCNN ──────────────────────────────────────────────────────
    mat_in = ncnn.Mat.from_pixels(input_img, ncnn.Mat.PixelType.PIXEL_BGR,
                                  INPUT_SIZE, INPUT_SIZE)
    mat_in.substract_mean_normalize(
        [0.0, 0.0, 0.0],          # mean  (0 → sem subtração)
        [1 / 255.0, 1 / 255.0, 1 / 255.0]  # norm  (divide por 255)
    )
    ex = net.create_extractor()
    ex.input(INPUT_NAME, mat_in)
    _, mat_out = ex.extract(OUTPUT_NAME)
    output = np.array(mat_out)

    # ── Pós-processamento ────────────────────────────────────────────────────
    detections = postprocess(output, scale, pad_x, pad_y, orig_w, orig_h)

    objetos_detectados.clear()  # Limpa a lista a cada frame
    annotated_frame = frame.copy()

    # para cada objeto detectado, pego os atributos interessantes e adiciono em uma lista
    for det in detections:
        x1, y1, x2, y2 = det['x1'], det['y1'], det['x2'], det['y2']
        classe_idx = det['class_id']
        classe_nome = CLASS_NAMES[classe_idx] if classe_idx < len(CLASS_NAMES) else str(classe_idx)

        # acho o meio do objeto
        centro_x = int((x1 + x2) / 2)
        centro_y = int((y1 + y2) / 2)

        # calculo o tamanho do objeto (usando o conceito da área ocupada por ele)
        largura = x2 - x1
        altura  = y2 - y1
        area    = largura * altura

        # salvo os dados como uma lista, e insiro esse elemento dentro da lista global
        listaObjeto = [centro_x, centro_y, area, classe_nome]
        objetos_detectados.append(listaObjeto)

        # essas linhas abaixo são desenhos opcionais para ajudar na geração da imagem e analisarmos as detecções
        # elas podem ser comentadas caso desejem
        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
        cv2.circle(annotated_frame, (centro_x, centro_y), 5, (0, 0, 255), -1)
        cv2.putText(annotated_frame, f"Area: {area}", (centro_x, centro_y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        cv2.putText(annotated_frame, f"Classe: {classe_nome}", (centro_x, centro_y + 20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        cv2.putText(annotated_frame, f"{classe_nome} {det['conf']:.2f}", (x1, max(y1 - 5, 0)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

    # imprimo a lista com todos os objetos detectados
    print(objetos_detectados)

    # Calcula e exibe FPS
    fps = 1 / (time.time() - start_time)
    cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    # envio o frame com as modificações para o flask
    frameAtual = annotated_frame.copy()

    # Mostra o frame com detecções
    #cv2.imshow("YOLOv8 NCNN - Webcam 320x320", frameAtual)

    time.sleep(0.1)
    # Pressione 'q' para sair
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
#cv2.destroyAllWindows()