#exemplo de como usar thread, e neste exemplo, como usar uma thread para capturar frames da webcam:
#-O que é uma Thread?
    #Uma thread permite que você execute threadExecutadas simultâneas dentro do mesmo programa. 
    #Por exemplo, você pode ler um sensor enquanto pega o ulimo frame da webcam, tudo ao mesmo tempo.
import cv2
import threading
import time




# === Classe da câmera com thread e lock ===
# Usar camera em thread é recomendável para evitar atrasos de frames nas imagens. Isso pode acontecer caso o processamento seja mais lento do que o processamento
# Com isso acontece do processamento pegar um frame antigo, criando um comportamento estranho e atrasos nas imagens.
class ExemploThread:
    def __init__(self, indiceCamera=0):
        self.indiceCamera = indiceCamera
        self.video = cv2.VideoCapture(indiceCamera) #inicio a camera para pegar os frames
        self.frameAtual = None
        self.rodando = True
        self.threadExecutada = self.iniciarExemploThread()

    def atualizar(self):
        while self.rodando:
            ok, frame = self.video.read() # o OK retorna se o frame foi lido corretamente
            if ok:
                with threading.Lock():
                    self.frameAtual = frame
            else:
                self.frameAtual = None #digo que nao consegui obter retornando o valor como None
                print("Erro ao ler o frame da câmera.")
                #tento reconectar a camera
                self.video.release()
                self.video = cv2.VideoCapture(self.indiceCamera)  # Tenta reiniciar a câmera
            
            time.sleep(0.01)  # Evita uso excessivo da CPU

    def obterFrame(self):
        with threading.Lock(): #o lock garante que o frame atual não seja modificado enquanto estou pegando ele
            if self.frameAtual is not None:
                copia_frame = self.frameAtual.copy()
            else:
                copia_frame = None
        return copia_frame

    def parar(self):
        self.rodando = False
        self.video.release()
    
    def iniciarExemploThread(self):
        threadExecutada = threading.Thread(target=self.atualizar)
        threadExecutada.start()
        return threadExecutada


#crio a thread que será responsável pela camera, o código da função (atualizar) dela vai ficar rodando o tempo todo capturando as fotos, em paralelo com o resto do código
#passo como parametro o ID da camera que vou utilizar
camera = ExemploThread(0)


#exemplo de como pegar essa foto que foi tirada pela classe e está como um objeto(variavel)
while True:
    #pego a ultima foto que foi tirada
    imagem = camera.obterFrame()
    #exibo a foto... (poderia fazer processamento nessa foto como nos exemplos anteriores)
    if imagem is not None:
        cv2.imshow("Imagem da Webcam", imagem)

    tecla = cv2.waitKey(1)
    if tecla == 27:  # Tecla ESC
        break

#desativo a camera (caso nao seja mais necessario, é bom fazer isso no código, para economizar processamento e bateria)
camera.parar()
cv2.destroyAllWindows()
