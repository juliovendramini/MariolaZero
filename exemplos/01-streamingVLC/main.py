#Exemplo para transmitir a imagem da camera usando Flask e OpenCV
# Requisitos: pip install opencv-python flask
# A saida da camera pode ser observada em http://ip:8080/video usando o VLC ou navegador
# infelizmente, dessa forma, o delay é alto, coisa de 4 segundos. Mas já ajudar analisar alguma coisa

import cv2
from flask import Flask, Response
import time
import threading

app = Flask(__name__)
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Define o buffer para 1 frame, assim nao atraso nenhuma transmissão
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
    # Captura o frame da câmera descartando qualquer frame anterior
    ret, frameAtual = camera.read()
    #esse código comentado abaixo é um exemplo de como descartar alguns frames
    # i=0
    # while ( i < 5):
    #     camera.grab()
    #     i += 1
    # ret, frameAtual = camera.retrieve()
    if not ret:
        break

    # Exibe o frame na janela
    cv2.imshow('Camera', frameAtual)

    # Pressione 'q' para sair
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break