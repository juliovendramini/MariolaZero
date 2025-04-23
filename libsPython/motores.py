# Classe para controlar os motores e servos da placa do movimento do novo brick
import struct
import time
class Movimento:
    motorInvertido = [False, False, False, False]
    DEBUG = False
    NORMAL = 0
    INVERTIDO = 1
    anguloMotor1 = 0
    anguloMotor2 = 0
    modoFreio = 0
    BREAK = 0
    HOLD = 1
    anguloAbsolutoMotor1 = 0
    anguloAbsolutoMotor2 = 0
    anguloDeltaMotor1 = 0 #o angulo delta é o angulo que o motor andou desde a ultima vez que foi resetado
    anguloDeltaMotor2 = 0 #o angulo delta é o angulo que o motor andou desde a ultima vez que foi resetado
    estadoMotores = 0
    PARADO = 0
    GIRANDO_NORMAL = 1
    GIRANDO_INVERTIDO = 2

    def __init__(self, portaSerial, atualizaInstantaneo = False):
        self.lista = [0xff, 200, 200, 200, 200, 200, 200, 100, 100, 100, 100, 0, 0, 0, 0, 0] #nos motores enviar 100 significa zero
        self.ser = portaSerial
        self.atualizaInstantaneo = atualizaInstantaneo
        self.atualiza()
        self.resetaAnguloMotor(1)
        self.resetaAnguloMotor(2)

    def moveServo(self,servo,angulo):
        if(servo <= 0):
            return
        if(servo > 6):
            return
        if(angulo < 0):
            angulo = 0
        if(angulo > 180):
            angulo = 180
        self.lista[servo] = angulo
        if self.atualizaInstantaneo:
            self.atualiza()

    def atualiza(self):
        self.ser.write(bytes(self.lista))
        if self.DEBUG:
            print(f"Enviando: {self.lista}")
        self.anguloMotor1 = 0 #assim q envio zero isso pq zerado ele nao anda por angulo
        self.anguloMotor2 = 0
        self.lista[11] = 0
        self.lista[12] = 0
        self.lista[13] = 0
        self.lista[14] = 0
        #leio o retorno da serial e salvo na lista

        retornoSerial = self.ser.read(10) 
        if(len(retornoSerial) == 10): #só leio se o retorno for exatamente 9 bytes
            if(retornoSerial[0] == 0xff):
                self.anguloAbsolutoMotor1 = struct.unpack('>i', bytes(retornoSerial[1:5]))[0]
                self.anguloAbsolutoMotor2 = struct.unpack('>i', bytes(retornoSerial[5:9]))[0]
                self.estadoMotores = retornoSerial[9]

    #funcao que envia informacao mas sem atualizar velocidades do controlador de motor
    def estado(self):
        self.lista[0] = 0xfe
        self.ser.write(bytes(self.lista))
        if self.DEBUG:
            print(f"Enviando: {self.lista}")
        self.lista[0] = 0xff
        #leio o retorno da serial e salvo na lista
        retornoSerial = self.ser.read(10) 
        if(len(retornoSerial) == 10): #só leio se o retorno for exatamente 10 bytes
            if(retornoSerial[0] == 0xfe):
                self.anguloAbsolutoMotor1 = struct.unpack('>i', bytes(retornoSerial[1:5]))[0]
                self.anguloAbsolutoMotor2 = struct.unpack('>i', bytes(retornoSerial[5:9]))[0]
                self.estadoMotores = retornoSerial[9]
                if self.DEBUG:
                    print("Estado atualizado")

    def direcaoMotor(self,motor, direcao):
        if(motor <= 0):
            return
        if(motor > 4):
            return
        if(direcao == self.NORMAL):
            self.motorInvertido[motor - 1] = False
        else:
            self.motorInvertido[motor - 1] = True
        if self.atualizaInstantaneo:
            self.atualiza()

    def desativaServo(self,servo):
        if(servo <= 0):
            return
        if(servo > 6):
            return
        self.lista[servo] = 200 #maior que 180 desativa ele
        if self.atualizaInstantaneo:
            self.atualiza()
    
    def velocidadeMotor(self,motor,velocidade):
        if(motor <= 0):
            return
        if(motor > 4):
            return
        if(velocidade < -100):
            velocidade = -100
        if(velocidade > 100):
            velocidade = 100
        if(self.motorInvertido[motor - 1]):
            velocidade = -velocidade
        self.lista[motor + 6] = velocidade + 100 #(envio valores somente positivos e na placa subtrai 100)
        if self.atualizaInstantaneo:
            self.atualiza()

    #essa função só move os motores 1 e 2, pois são os únicos que possuem encoder
    def moveMotor(self, motor, velocidade, angulo):
        angulo = abs(angulo) #sempre será positivo
        if(angulo > 65535): #erro, nao aceito valores maiores que 65535
            return
        if(motor <= 0):
            return
        if(motor > 2):
            return
        self.anguloMotor1 = angulo
        if(motor == 1):
            posicaoAnguloLista = 11
            self.anguloMotor1 = angulo
        if(motor == 2):
            posicaoAnguloLista = 13
            self.anguloMotor2 = angulo
        if(velocidade < -100):
            velocidade = -100
        if(velocidade > 100):
            velocidade = 100
        if(self.motorInvertido[motor - 1]):
            velocidade = -velocidade
        self.lista[motor + 6] = velocidade + 100 #(envio valores somente positivos e na placa subtrai 100)
        self.lista[posicaoAnguloLista] = (angulo >> 8) & 0xFF #pego o byte mais significativo
        self.lista[posicaoAnguloLista+1] = angulo & 0xFF #pego o byte menos significativo
        if self.atualizaInstantaneo:
            self.atualiza()
            time.sleep(0.05)

    #Função que move os motores 1 e 2 ao mesmo tempo
    #velocidade1 e velocidade2 são os valores de velocidade dos motores, angulo1 e angulo2 são os angulos que os motores devem se mover
    def moveMotores(self,velocidade1,angulo1,velocidade2,angulo2):
        angulo1 = abs(angulo1) #sempre será positivo
        if(angulo1 > 65535):
            return
        angulo2 = abs(angulo2) #sempre será positivo
        if(angulo2 > 65535):
            return
        motor = 1
        if(velocidade1 < -100):
            velocidade1 = -100
        if(velocidade1 > 100):
            velocidade1 = 100
        if(self.motorInvertido[motor - 1]):
            velocidade1 = -velocidade1
        self.lista[motor + 6] = velocidade1 + 100 #(envio valores somente positivos e na placa subtrai 100)
        motor = 2
        if(velocidade2 < -100):
            velocidade2 = -100
        if(velocidade2 > 100):
            velocidade2 = 100
        if(self.motorInvertido[motor - 1]):
            velocidade2 = -velocidade2
        self.lista[motor + 6] = velocidade2 + 100
        self.anguloMotor1 = angulo1
        self.lista[11] = (angulo1 >> 8) & 0xFF #pego o byte mais significativo
        self.lista[12] = angulo1 & 0xFF
        self.anguloMotor2 = angulo2
        self.lista[13] = (angulo2 >> 8) & 0xFF #pego o byte mais significativo
        self.lista[14] = angulo2 & 0xFF
        if self.atualizaInstantaneo:
            self.atualiza()
            time.sleep(0.05)

    #para todos os 4 motores
    def paraMotores(self):
        self.lista[6] = 100
        self.lista[7] = 100
        self.lista[8] = 100
        self.lista[9] = 100
        self.anguloMotor1 = 0
        self.anguloMotor2 = 0
        if self.atualizaInstantaneo:
            self.atualiza()


    def modoFreio(self,modo):
        if(modo == self.BREAK):
            self.modoFreio = 0
        else:
            self.modoFreio = 1
        self.lista[15] = self.modoFreio
        if self.atualizaInstantaneo:
            self.atualiza()

    def resetaAnguloMotor(self, motor): # nao reseto o angulo diretalmente na placa, apenas crio uma diferença
        if(motor == 1):
            self.anguloDeltaMotor1 = self.anguloAbsolutoMotor1
        elif(motor == 2):
            self.anguloDeltaMotor2 = self.anguloAbsolutoMotor2
        else:
            return
        if self.atualizaInstantaneo:
            self.atualiza()

    def anguloMotor(self, motor): #sempre vou retornar a subtração pelo Delta, e o anguloAbsoluto real sempre será transparente para o usuario
        if(motor == 1):
            if(self.motorInvertido[0] == True):
                return -self.anguloAbsolutoMotor1 + self.anguloDeltaMotor1
            return self.anguloAbsolutoMotor1 - self.anguloDeltaMotor1
        elif(motor == 2):
            if(self.motorInvertido[1] == True):
                return -self.anguloAbsolutoMotor2 + self.anguloDeltaMotor2
            return self.anguloAbsolutoMotor2 - self.anguloDeltaMotor2
        else:
            return 0
        if self.atualizaInstantaneo:
            self.atualiza()
    
    def estadoMotor(self,motor):
        if(motor == 1):
            return self.estadoMotores & 0b11
        elif(motor == 2):
            return (self.estadoMotores >> 2) & 0b11
        else:
            return 0
        if self.atualizaInstantaneo:
            self.atualiza()