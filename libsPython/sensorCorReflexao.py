from cronometro import Cronometro
class CorReflexao:
    MODO_RGB_HSV_4X = 0
    MODO_RGB_HSV_16X = 1
    MODO_RGB_HSV_AUTO = 2
    MODO_CALIBRA_BRANCO = 3
    MODO_CALIBRA_PRETO = 4
    MODO_RAW_AUTO = 5


    
    def __init__(self, portaSerial, atualizaInstantaneo = False):
        #32 valores
        self.lista = [0xff, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b]
        self.ser = portaSerial
        self.atualizaInstantaneo = atualizaInstantaneo
        self.modo = 2
        self.quantidadeBytesModo = 32

    def setModo(self, modo):
        self.modo = modo
        if(modo == 0 or 
           modo == 1 or
           modo == 2 or
           modo == 5):
            self.quantidadeBytesModo = 32
        else:
            self.quantidadeBytesModo = 1
        if self.atualizaInstantaneo:
            self.atualiza()

    def atualiza(self):
        # Envia o comando para solicitar os 32 bytes
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

    def leReflexao(self):
        # Atualiza os dados antes de ler
        if(self.atualizaInstantaneo):
            if self.atualiza():
                # Retorna os 4 primeiros valores de reflexão
                return self.lista[0:4]
            else:
                return None
        return self.lista[0:4]
    
    def calibraBranco(self):
        temp = self.atualizaInstantaneo
        self.atualizaInstantaneo = False
        self.setModo(self.MODO_CALIBRA_BRANCO)
        self.atualizaInstantaneo = temp
        tempo = Cronometro()
        tempo.inicia()
        # Aguarda 5 segundos para a calibração
        self.ser.write(bytes([self.modo])) #envio o modo novo de calibração do branco
        while(tempo.tempo() < 5000):
            dados = self.ser.read(self.quantidadeBytesModo)
            # Verifica se recebeu exatamente self.quantidadeBytesModo bytes
            if len(dados) == self.quantidadeBytesModo:
                # Atualiza a lista com os valores recebidos
                self.lista = list(dados)
                break
        if(tempo.tempo() >= 5000):
            print("Tempo de calibração excedido")
            return False
        # Aguarda 5 segundos para a calibração
        print("Calibração concluída")
        return True
    
    def calibraPreto(self):
        temp = self.atualizaInstantaneo
        self.atualizaInstantaneo = False
        self.setModo(self.MODO_CALIBRA_PRETO)
        self.atualizaInstantaneo = temp
        tempo = Cronometro()
        tempo.inicia()
        # Aguarda 5 segundos para a calibração
        self.ser.write(bytes([self.modo])) #envio o modo novo de calibração do branco
        while(tempo.tempo() < 3000):
            dados = self.ser.read(self.quantidadeBytesModo)
            # Verifica se recebeu exatamente self.quantidadeBytesModo bytes
            if len(dados) == self.quantidadeBytesModo:
                # Atualiza a lista com os valores recebidos
                self.lista = list(dados)
                break
        if(tempo.tempo() >= 3000):
            print("Tempo de calibração excedido")
            return False
        # Aguarda 5 segundos para a calibração
        print("Calibração concluída")
        return True
