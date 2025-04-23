import struct
from cronometro import Cronometro
class Giroscopio:

    GYRO = 0
    GYRO2 = 1
    GYRO_CAL = 2
    modo = 0
    quantidadeBytesModo = 8;

    
    def __init__(self, portaSerial, atualizaInstantaneo = False):
        #8 valores
        self.lista = [0x00, 0x00, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00]
        self.ser = portaSerial
        self.atualizaInstantaneo = atualizaInstantaneo
        self.setModo(self.GYRO)

    def setModo(self, modo):
        if modo < 0 or modo > 2:
            raise ValueError("Modo inválido. Deve ser 0, 1 ou 2.")
        self.modo = modo
        if(modo == self.GYRO or
            modo == self.GYRO2):
            self.quantidadeBytesModo = 8
        elif(modo == self.GYRO_CAL):
            self.quantidadeBytesModo = 1
        if self.atualizaInstantaneo:
            self.atualiza()

    def atualiza(self):
        # Envia o comando para solicitar o bytes necessarios
        self.ser.write(bytes([self.modo]))
        
        # Aguarda receber os self.quantidadeBytesModo bytes via serial
        dados = self.ser.read(self.quantidadeBytesModo)
        
        # Verifica se recebeu exatamente self.quantidadeBytesModo bytes
        if len(dados) == self.quantidadeBytesModo:
            # Atualiza a lista com os valores recebidos
            self.lista = list(dados)
            return True
        else:
            return False

    def leAnguloX(self):
        # Atualiza os dados antes de ler
        if(self.atualizaInstantaneo):
            if not self.atualiza():
                return None
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        angulo_x = struct.unpack('>h', bytes(self.lista[0:2]))[0]
        return angulo_x    

    def leAnguloY(self):
        # Atualiza os dados antes de ler
        if(self.atualizaInstantaneo):
            if not self.atualiza():
                return None
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        angulo_y = struct.unpack('>h', bytes(self.lista[2:4]))[0]
        return angulo_y    

    def leAnguloZ(self):
        # Atualiza os dados antes de ler
        if(self.atualizaInstantaneo):
            if not self.atualiza():
                return None
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        angulo_z = struct.unpack('>h', bytes(self.lista[4:6]))[0]
        return angulo_z    

    def resetaZ(self):
        #apenas troco o modo de GYRO para GYRO2 ou o contrário
        if self.modo == self.GYRO:
            self.modo = self.GYRO2
        else:
            self.modo = self.GYRO
        self.atualiza()

    def calibra(self):
        temp = self.atualizaInstantaneo
        self.atualizaInstantaneo = False
        tempModo = self.modo
        self.setModo(self.GYRO_CAL)
        self.atualizaInstantaneo = temp
        tempo = Cronometro()
        tempo.inicia()
        # Aguarda 5 segundos para a calibração
        self.ser.write(bytes([self.modo])) #envio o modo novo de calibração
        while(tempo.tempo() < 5000):
            dados = self.ser.read(1) # o modo de calibracao do giroscopio só retorna 1 byte
            # Verifica se recebeu exatamente self.quantidadeBytesModo bytes
            if len(dados) == 1:
                # Atualiza a lista com os valores recebidos
                break
        if(tempo.tempo() >= 5000):
            print("Tempo de calibração excedido")
            return False
        # Aguarda 5 segundos para a calibração
        print("Calibração concluída")
        self.setModo(tempModo)
        return True
    
    