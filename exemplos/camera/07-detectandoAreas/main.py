#exemplo de como detectar áreas de uma cor específica (neste caso, azul) usando OpenCV
import cv2
import numpy as np
import time




# intervalo da cor de exemplo, neste caso, é o hsv do azul
# Intervalo de azul em HSV (pode ajustar conforme necessário)
# Como cores podem variar, é importante calibrar esses valores e colocar um intervalo que funcione bem para o seu ambiente
valorBaixoAzul = np.array([100, 100, 100])
valorAltoAzul = np.array([130, 255, 255])

# Iniciar captura da webcam
camera = cv2.VideoCapture(0)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)

frameAtual = None
objetos_detectados = []

def encontraObjetos(frame):
    global objetos_detectados
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    objetos_detectados = []  # Limpa a lista de objetos detectados a cada frame
    # Criar máscara para azul
    mask = cv2.inRange(hsv, valorBaixoAzul, valorAltoAzul)

    kernel = np.ones((10,10), np.uint8)
    maskAzul = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

    # Encontrar contornos
    contours, _ = cv2.findContours(maskAzul, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Desenhar contornos que são retângulos
    i = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        print (f"Area do contorno {i}: {area}")
        if area > 700:  # Ajuste esse valor conforme necessário para filtrar tamanho dos objetos
            x, y, w, h = cv2.boundingRect(cnt)
            #desenha um retângulo que envolve o objeto detectado
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            centro_x = x + w // 2
            centro_y = y + h // 2
            #adiciono os dados do objeto detectado na lista de objetos detectados
            #assim posso trabalhar com esses dados depois para tomar alguma decisão
            objetos_detectados.append([centro_x, centro_y, w*h, "Objeto Azul"])
            i += 1


    # Mostrar resultado
    cv2.imshow("Objetos Azuis", frame)


while True:
    ret, frame = camera.read()
    if not ret:
        break
    encontraObjetos(frame)
    print(objetos_detectados)
    
    #time.sleep(2)
    # Sair com tecla 'q'
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

camera.release()
cv2.destroyAllWindows()
