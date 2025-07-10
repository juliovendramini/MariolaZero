# Classe para controlar os motores e servos da placa do Motores do novo brick
import struct
import time
import struct
from portas import Portas
class Motores:
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
    atualizaInstantaneo = False
    ser = None


    def __init__(self, atualizaInstantaneo = False):
        self.listaServos = [0xfd, 200, 200, 200, 200, 200, 200, 0, 0, 0]
        self.listaMotores = [0xfc, 0, 0, 0, 0, 0, 0, 0, 0, 0] 
        self.listaPID = [0xf9, 0, 0, 0, 0, 0, 0, 0, 0, 0] #
        portas = Portas()
        self.ser = portas.abrePortaSerial(Portas._SERIAL0, 250000)
        if self.ser == None:
            raise Exception("Erro ao abrir a porta serial")
        self.atualizaInstantaneo = atualizaInstantaneo
        self.atualizaMotores()
        self.atualizaServos()
        self.resetaAnguloMotor(1)
        self.resetaAnguloMotor(2)

    def __del__(self):
        self.paraMotores()
        self.ser.close()
        if self.DEBUG:
            print("Fechando a porta serial do motores")
        #self.ser.close() #não fecha a serial aqui pq o main.py fecha
        #self.ser = None
        #if self.DEBUG:
        #    print("Fechando a porta serial")

    def moveServo(self,servo,angulo):
        if(servo <= 0):
            return
        if(servo > 6):
            return
        if(angulo < 0):
            angulo = 0
        if(angulo > 180):
            angulo = 180
        self.listaServos[servo] = angulo
        if self.atualizaInstantaneo:
            self.atualizaServos()

    def atualizaServos(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes(self.listaServos))
        if self.DEBUG:
            print(f"Enviando: {self.listaServos}")
        retornoSerial = self.ser.read(1) 
        if(len(retornoSerial) == 1):
            if(retornoSerial[0] == 0xfd):
                return True
        raise Exception("Erro ao ler o estado dos servos")
    
    def atualizaMotores(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes(self.listaMotores))
        if self.DEBUG:
            #print(f"Enviando: {self.listaMotores}")
            #print("Enviando:" , [struct.unpack('b', bytes([x]))[0] for x in self.listaMotores])
            print("Enviando:" , self.listaMotores[0], end=" ")
            print(struct.unpack('b', bytes([self.listaMotores[1]]))[0], end=" ")
            print(struct.unpack('b', bytes([self.listaMotores[2]]))[0], end=" ")
            print(struct.unpack('b', bytes([self.listaMotores[3]]))[0], end=" ")
            print(struct.unpack('b', bytes([self.listaMotores[4]]))[0], end=" ")
            print(struct.unpack('>H', bytes(self.listaMotores[5:7]))[0], end=" ")
            print(struct.unpack('>H', bytes(self.listaMotores[7:9]))[0], end=" ")
            print(struct.unpack('b', bytes([self.listaMotores[9]]))[0])
        self.anguloMotor1 = 0 #assim q envio zero isso pq zerado ele nao anda por angulo
        self.anguloMotor2 = 0
        self.listaMotores[5] = 0
        self.listaMotores[6] = 0
        self.listaMotores[7] = 0
        self.listaMotores[8] = 0
        #leio o retorno da serial e salvo na lista

        retornoSerial = self.ser.read(10) 
        #if self.DEBUG:
            #print(f"retornoSerial: {retornoSerial}")
            #print("retornoSerial:", [struct.unpack('b', bytes([x]))[0] for x in retornoSerial])
        if(len(retornoSerial) == 10): #só leio se o retorno for exatamente 10 bytes
            if(retornoSerial[0] == 0xfc):
                self.anguloAbsolutoMotor1 = struct.unpack('>i', bytes(retornoSerial[1:5]))[0]
                self.anguloAbsolutoMotor2 = struct.unpack('>i', bytes(retornoSerial[5:9]))[0]
                self.estadoMotores = retornoSerial[9]
                if self.DEBUG:
                    print("retorno serial: ", retornoSerial[0], self.anguloAbsolutoMotor1, self.anguloAbsolutoMotor2, self.estadoMotores)
                return True
        raise Exception("Erro ao ler o estado dos motores")
    
    #funcao que envia informacao mas sem atualizar velocidades do controlador de motor
    def estado(self):
        temp = self.listaMotores[0]
        self.listaMotores[0] = 0xfb
        self.ser.write(bytes(self.listaMotores))
        # if self.DEBUG:
        #     #print(f"Enviando: {self.listaMotores}")
        #     #print("Enviando:", [struct.unpack('b', bytes([x]))[0] for x in self.listaMotores])
        #     print("Enviando:" , self.listaMotores[0], end=" ")
        #     print(struct.unpack('b', bytes([self.listaMotores[1]]))[0], end=" ")
        #     print(struct.unpack('b', bytes([self.listaMotores[2]]))[0], end=" ")
        #     print(struct.unpack('b', bytes([self.listaMotores[3]]))[0], end=" ")
        #     print(struct.unpack('b', bytes([self.listaMotores[4]]))[0], end=" ")
        #     print(struct.unpack('>H', bytes(self.listaMotores[5:7]))[0], end=" ")
        #     print(struct.unpack('>H', bytes(self.listaMotores[7:9]))[0], end=" ")
        #     print(struct.unpack('b', bytes([self.listaMotores[9]]))[0])
        self.listaMotores[0] = temp
        #leio o retorno da serial e salvo na lista
        retornoSerial = self.ser.read(10) 
        if(len(retornoSerial) == 10): #só leio se o retorno for exatamente 10 bytes
            if(retornoSerial[0] == 0xfb):
                self.anguloAbsolutoMotor1 = struct.unpack('>i', bytes(retornoSerial[1:5]))[0]
                self.anguloAbsolutoMotor2 = struct.unpack('>i', bytes(retornoSerial[5:9]))[0]
                self.estadoMotores = retornoSerial[9]
                # if self.DEBUG:
                #     print("Estado atualizado")
                #     print("retorno serial: ", retornoSerial[0], self.anguloAbsolutoMotor1, self.anguloAbsolutoMotor2, self.estadoMotores)
                return True
        raise Exception("Erro ao ler o estado dos motores")

    def direcaoMotor(self,motor, direcao):
        self.listaMotores[0] = 0xfc #comando para enviar motores como velocidade
        if(motor <= 0):
            return
        if(motor > 4):
            return
        if(direcao == self.NORMAL):
            self.motorInvertido[motor - 1] = False
        else:
            self.motorInvertido[motor - 1] = True
        if self.atualizaInstantaneo:
            self.atualizaMotores()

    def desativaServo(self,servo):
        if(servo <= 0):
            return
        if(servo > 6):
            return
        self.listaServos[servo] = 200 #maior que 180 desativa ele
        if self.atualizaInstantaneo:
            self.atualizaServos()
    
    def velocidadeMotor(self,motor,velocidade):
        self.listaMotores[0] = 0xfc #comando para enviar motores como velocidade
        if(motor <= 0):
            return
        if(motor > 4):
            return
        if(velocidade < -120):
            velocidade = -120
        if(velocidade > 120):
            velocidade = 120
        if(self.motorInvertido[motor - 1]):
            velocidade = -velocidade
        self.listaMotores[motor] = struct.pack('b', velocidade)[0]
        if self.atualizaInstantaneo:
            self.atualizaMotores()

    #essa função só move os motores 1 e 2, pois são os únicos que possuem encoder
    def moveMotor(self, motor, velocidade, angulo):
        self.listaMotores[0] = 0xfc #comando para enviar motores como velocidade
        angulo = abs(angulo) #sempre será positivo
        if(angulo > 65535): #erro, nao aceito valores maiores que 65535
            return
        if(motor <= 0):
            return
        if(motor > 2):
            return
        self.anguloMotor1 = angulo
        if(motor == 1):
            posicaoAnguloLista = 5
            self.anguloMotor1 = angulo
        if(motor == 2):
            posicaoAnguloLista = 7
            self.anguloMotor2 = angulo
        if(velocidade < -120):
            velocidade = -120
        if(velocidade > 120):
            velocidade = 120
        if(self.motorInvertido[motor - 1]):
            velocidade = -velocidade
        self.listaMotores[motor] = struct.pack('b', velocidade)[0]
        self.listaMotores[posicaoAnguloLista] = (angulo >> 8) & 0xFF #pego o byte mais significativo
        self.listaMotores[posicaoAnguloLista+1] = angulo & 0xFF #pego o byte menos significativo
        if self.atualizaInstantaneo:
            self.atualizaMotores()
            time.sleep(0.05)


    #Função que move os motores 1 e 2 ao mesmo tempo
    #velocidade1 e velocidade2 são os valores de velocidade dos motores, angulo1 e angulo2 são os angulos que os motores devem se mover
    def moveMotores(self,velocidade1,angulo1,velocidade2,angulo2):
        self.listaMotores[0] = 0xfc #comando para enviar motores como velocidade
        angulo1 = abs(angulo1) #sempre será positivo
        if(angulo1 > 65535):
            return
        angulo2 = abs(angulo2) #sempre será positivo
        if(angulo2 > 65535):
            return
        motor = 1
        if(velocidade1 < -120):
            velocidade1 = -120
        if(velocidade1 > 120):
            velocidade1 = 120
        if(self.motorInvertido[motor - 1]):
            velocidade1 = -velocidade1
        self.listaMotores[motor] = struct.pack('b', int(velocidade1))[0]
        motor = 2
        if(velocidade2 < -120):
            velocidade2 = -120
        if(velocidade2 > 120):
            velocidade2 = 120
        if(self.motorInvertido[motor - 1]):
            velocidade2 = -velocidade2
        self.listaMotores[motor] = struct.pack('b', int(velocidade2))[0]
        self.anguloMotor1 = angulo1
        self.listaMotores[5] = (angulo1 >> 8) & 0xFF #pego o byte mais significativo
        self.listaMotores[6] = angulo1 & 0xFF
        self.anguloMotor2 = angulo2
        self.listaMotores[7] = (angulo2 >> 8) & 0xFF #pego o byte mais significativo
        self.listaMotores[8] = angulo2 & 0xFF
        if self.atualizaInstantaneo:
            self.atualizaMotores()
            time.sleep(0.05)

    #Função que move para sempre os motores 1 e 2 ao mesmo tempo
    #velocidade1 e velocidade2 são os valores de velocidade dos motores
    def velocidadeMotores(self,velocidade1,velocidade2):
        self.listaMotores[0] = 0xfc #comando para enviar motores como velocidade
        motor = 1
        if(velocidade1 < -120):
            velocidade1 = -120
        if(velocidade1 > 120):
            velocidade1 = 120
        if(self.motorInvertido[motor - 1]):
            velocidade1 = -velocidade1
        self.listaMotores[motor] =struct.pack('b', int(velocidade1))[0]
        motor = 2
        if(velocidade2 < -120):
            velocidade2 = -120
        if(velocidade2 > 120):
            velocidade2 = 120
        if(self.motorInvertido[motor - 1]):
            velocidade2 = -velocidade2
        self.listaMotores[motor] = struct.pack('b', int(velocidade2))[0]
        if self.atualizaInstantaneo:
            self.atualizaMotores()

    #Função que move para sempre os motores 1 e 2 ao mesmo tempo
    #potencia1 e potencia2 são os valores de potencia do pwm dos motores
    def potenciaMotores(self,potencia1,potencia2):
        self.listaMotores[0] = 0xfa #comando para enviar motores como potencia
        motor = 1
        if(potencia1 < -100):
            potencia1 = -100
        if(potencia1 > 100):
            potencia1 = 100
        if(self.motorInvertido[motor - 1]):
            potencia1 = -potencia1
        self.listaMotores[motor] =struct.pack('b', int(potencia1))[0]
        motor = 2
        if(potencia2 < -100):
            potencia2 = -100
        if(potencia2 > 100):
            potencia2 = 100
        if(self.motorInvertido[motor - 1]):
            potencia2 = -potencia2
        self.listaMotores[motor] = struct.pack('b', int(potencia2))[0]
        if self.atualizaInstantaneo:
            self.atualizaMotores()


    #para todos os 4 motores
    def desligaMotores(self):
        self.listaMotores[0] = 0xfc
        self.listaMotores[1] = 0
        self.listaMotores[2] = 0
        self.listaMotores[3] = 0
        self.listaMotores[4] = 0
        self.listaMotores[5] = 0
        self.listaMotores[6] = 0
        self.listaMotores[7] = 0
        self.listaMotores[8] = 0
        self.listaMotores[9] = 0
        self.anguloMotor1 = 0
        self.anguloMotor2 = 0
        if self.atualizaInstantaneo:
            self.atualizaMotores()

    #para todos os 2 motores com encoder
    def paraMotores(self):
        self.velocidadeMotores(0,0)


    def modoFreio(self,modo):
        if(modo == self.BREAK):
            self.modoFreio = 0
        else:
            self.modoFreio = 1
        self.listaMotores[9] = self.modoFreio
        if self.atualizaInstantaneo:
            self.atualizaMotores()

    def resetaAnguloMotor(self, motor): # nao reseto o angulo diretalmente na placa, apenas crio uma diferença
        if(motor == 1):
            self.anguloDeltaMotor1 = self.anguloAbsolutoMotor1
        elif(motor == 2):
            self.anguloDeltaMotor2 = self.anguloAbsolutoMotor2
        else:
            return
        if self.atualizaInstantaneo:
            self.atualizaMotores()

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
    
    def estadoMotor(self,motor):
        if(motor == 1):
            return self.estadoMotores & 0b11
        elif(motor == 2):
            return (self.estadoMotores >> 2) & 0b11
        else:
            return 0

    def PIDMotor(self, kp, ki, kd):
        # Envia os valores de kp, ki e kd como inteiros de 16 bits para a placa usando listaPID
        # kp, ki, kd devem estar no intervalo 0~65535
        kp = kp * 100  # mando os valores multiplicados por 100 para evitar problemas de precisão
        ki = ki * 100
        kd = kd * 100
        kp = max(0, min(65535, int(kp)))
        ki = max(0, min(65535, int(ki)))
        kd = max(0, min(65535, int(kd)))
        self.listaPID[1] = (kp >> 8) & 0xFF
        self.listaPID[2] = kp & 0xFF
        self.listaPID[3] = (ki >> 8) & 0xFF
        self.listaPID[4] = ki & 0xFF
        self.listaPID[5] = (kd >> 8) & 0xFF
        self.listaPID[6] = kd & 0xFF
        self.ser.write(bytes(self.listaPID))
        if self.DEBUG:
            print(f"Enviando PID: kp={kp}, ki={ki}, kd={kd} -> {self.listaPID}")
        # Opcional: ler resposta da placa, se necessário
        #analiso se recebeu um byte de retorno
        retornoSerial = self.ser.read(1)
        if len(retornoSerial) == 1:
            if retornoSerial[0] == 0xf9:
                return True
        raise Exception("Erro ao configurar PID dos motores")