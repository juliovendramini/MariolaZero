# Exemplo de como salvar em arquivo imagens que são tiradas da camera e serão usadas para o processamento
# Isso é útil para melhorar no futuro o treinamento das redes, usando mais dados e analisando
# O que foi processado errado ou não. O script salva duas fotos, uma original e outra processada.
from ultralytics import YOLO
from datetime import datetime
import cv2
import torch
import copy
from flask import Flask, Response
import time
import numpy as np
import threading
torch.set_num_threads(4)  # ou quantos núcleos quiser usar

device = 'cpu'
print(f"Usando dispositivo: {device}")
# Carrega a rede treinada
model = YOLO("best.pt")

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


print("Exemplo processamento de IA encontrando posição dos objetos detectados na camera e salvar em arquivo")
#o código do flask deve ser iniciado em uma thread separada para poder rodar junto com o código principal
flask_thread = threading.Thread(target=iniciar_flask)
flask_thread.daemon = True
flask_thread.start()

objetos_detectados = []


#no exemplo abaixo, a cada frame da câmera, o código detecta os objetos e exibe a posição deles na tela, além de exibir a área e a classe do objeto detectado
#tudo é salvo numa lista de objetos detectados, que é limpa a cada frame
#essa lista pode ser utilizada depois em outros locais do código para tomar decisões ou enviar para outro lugar
while True:
    start_time = time.time()
    # Captura o frame da câmera 
    i=0
    while ( i < 5): # tento descartar frames antigos, para evitar atrasos na transmissão
        camera.grab()
        i += 1
    ret, frame = camera.retrieve()
    if not ret:
        break
    # É muito importante fazer a cópia do frame original antes de fazer qualquer processamento nele
    # A imagem que rodará na IA nao pode ser alterada
    frameOriginal = copy.deepcopy(frame)
    results = model(frame, imgsz=320, conf=0.7, device=device)

    objetos_detectados.clear()  # Limpa a lista a cada frame

    # essas duas linhas abaixo pegam as identificações dos objetos pela inferencia da rede
    boxes = results[0].boxes.xyxy.cpu().numpy()
    classes = results[0].boxes.cls.cpu().numpy()  # Índices das classes detectadas

    #para cada objeto detectado, pego os atributos interessantes e adiciono em uma lista, com essa lista eu posso trabalhar o que precisar depois
    for i, box in enumerate(boxes):
        x1, y1, x2, y2 = box[:4]
        
        #acho o meio do objeto
        centro_x = int((x1 + x2) / 2)
        centro_y = int((y1 + y2) / 2)
        
        #calculo o tamanho do objeto (usando o conceito da área ocupada por ele)
        largura = int(x2 - x1)
        altura = int(y2 - y1)
        area = largura * altura

        #pego a identificação da classe para identificar o objeto
        classe_idx = int(classes[i])
        classe_nome = model.names[classe_idx] if hasattr(model, "names") else str(classe_idx)

        #salvo os dados como uma lista, e insiro esse elemento (uma lista), dentro da lista global com todos os objetos detectados
        listaObjeto = [centro_x, centro_y, area, classe_nome]
        objetos_detectados.append(listaObjeto)


        #essas linhas abaixo são desenhos opcionais para ajudar na geração da imagem e analisarmos as detecções
        #elas podem ser comentadas caso desejem 
        cv2.circle(frame, (centro_x, centro_y), 5, (0, 0, 255), -1)
        cv2.putText(frame, f"Area: {area}", (centro_x, centro_y-10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        cv2.putText(frame, f"Classe: {classe_nome}", (centro_x, centro_y+20),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        
    #imprimo a lista com todos os objetos detectados
    print(objetos_detectados)
    # Desenha os resultados
    annotated_frame = results[0].plot()
    # Calcula e exibe FPS
    fps = 1 / (time.time() - start_time)
    cv2.putText(annotated_frame, f"FPS: {fps:.1f}", (10, 20),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

    #envio o frame com as modificações pra o flask
    frameAtual = annotated_frame.copy()
    #salvar os arquivos com o nome sendo a data atual (para nunca repetir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    img_filename = f"./imagens/{timestamp}.jpg"
    img_proc_filename = f"./imagensProcessadas/{timestamp}.jpg"
    # Salva a imagem
    cv2.imwrite(img_filename, frameOriginal)
    cv2.imwrite(img_proc_filename, frameAtual)

    
    # Mostra o frame com detecções
    cv2.imshow("YOLOv8 - Webcam 320x320", frameAtual)

    time.sleep(0.1)
    # Pressione 'q' para sair
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

