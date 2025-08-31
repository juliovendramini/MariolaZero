#Exemplo para transmitir a imagem da camera usando Flask e OpenCV
# Requisitos: pip install opencv-python flask
# A saida da camera pode ser observada em http://ip:8080/video usando o VLC ou navegador
# infelizmente, dessa forma, o delay é alto, coisa de 4 segundos. Mas já ajudar analisar alguma coisa
from ultralytics import YOLO
import cv2
import torch
from flask import Flask, Response
import time
import threading
torch.set_num_threads(4)  # ou quantos núcleos quiser usar

device = 'cpu'
print(f"Usando dispositivo: {device}")
# Carrega a rede treinada
model = YOLO("yolov8n.pt")

app = Flask(__name__)
camera = cv2.VideoCapture(0)
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
        time.sleep(1) #trasmissão a cada 1 segundo

# Rota para o streaming de vídeo
@app.route('/video')
def video_feed():
    return Response(atualizaTransmissao(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')


def iniciar_flask():
    app.run(host='0.0.0.0', port=8080, threaded=True)


#o código do flask deve ser iniciado em uma thread separada para poder rodar junto com o código principal
flask_thread = threading.Thread(target=iniciar_flask)
flask_thread.daemon = True
flask_thread.start()

#exemplo de captura de frames da camera descartando alguns frames
while True:
    start_time = time.time()
    # Captura o frame da câmera 
    ret, frame = camera.read()
    if not ret:
        break

    results = model(frame, imgsz=320, conf=0.7, device=device)

    # Desenha os resultados
    annotated_frame = results[0].plot()
    # Calcula e exibe FPS
    fps = 1 / (time.time() - start_time)
    cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    #envio o frame com as modificações pra o flask
    frameAtual = annotated_frame.copy() 
    
    # Mostra o frame com detecções
    cv2.imshow("YOLOv8 - Webcam 320x320", frameAtual)


    # Pressione 'q' para sair
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break