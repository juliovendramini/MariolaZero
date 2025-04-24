import struct

class PlacaMuxTCS34725:

    RGB_4X = 0
    RGB_16X = 1
    RGB_4X_LED_OFF = 2
    RGB_16X_LED_OFF = 3
    modo = 0
    quantidadeBytesModo = 32;

    
    def __init__(self, portaSerial, atualizaInstantaneo = False):
        self.lista = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        self.ser = portaSerial
        self.atualizaInstantaneo = atualizaInstantaneo
        self.setModo(self.RGB_4X)

    def setModo(self, modo):
        if modo < 0 or modo >= 4:
            raise ValueError("Modo inválido. Deve ser 0, 1, 2 ou 3")
        self.modo = modo
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

    def leSensor(self, porta):
        # Atualiza os dados antes de ler
        if porta < 0 or porta > 3:
            raise ValueError("Porta inválida. Deve ser 0, 1, 2 ou 3.")
        if(self.atualizaInstantaneo):
            if not self.atualiza():
                return None
        # tenho que usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        indice = porta * 4
        r = struct.unpack('>h', bytes(self.lista[indice:indice+2]))[0]
        g = struct.unpack('>h', bytes(self.lista[indice+2:indice+4]))[0]
        b = struct.unpack('>h', bytes(self.lista[indice+4:indice+6]))[0]
        c = struct.unpack('>h', bytes(self.lista[indice+6:indice+8]))[0]
        return (r, g, b, c)
