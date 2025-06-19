#exemplo de como detectar objetos retangulares de uma cor específica (neste caso, azul) usando OpenCV
import cv2
import numpy as np
import time



# Função para verificar se um contorno é retangular
def is_rectangle(contour, epsilon_ratio=0.02):
    peri = cv2.arcLength(contour, True)
    approx = cv2.approxPolyDP(contour, epsilon_ratio * peri, True)
    return len(approx) == 4 and cv2.isContourConvex(approx)

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

    # Encontrar contornos
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # Desenhar contornos que são retângulos
    i=0
    for cnt in contours:
        if is_rectangle(cnt):
            x, y, w, h = cv2.boundingRect(cnt)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
            #pego os dados retornados pelo boundingRect para mapear onde na imagem o objeto foi encontrado
            # e calculo o centro do retângulo
            centro_x = x + w // 2
            centro_y = y + h // 2
            #adiciono os dados do objeto detectado na lista de objetos detectados
            #assim posso trabalhar com esses dados depois para tomar alguma decisão
            objetos_detectados.append([centro_x, centro_y, w*h, i])
            i+=1

    # Mostrar resultado
    cv2.imshow("Retangulos Azuis", frame)
    #cv2.imshow("Mascara Azul", mask)


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
