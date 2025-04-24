import struct
class PlacaMuxVl53l0x:

    DISTANCIA_4_PORTAS = 0
    modo = 0
    quantidadeBytesModo = 16;

    
    def __init__(self, portaSerial, atualizaInstantaneo = False):
        #8 valores
        self.lista = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        self.ser = portaSerial
        self.atualizaInstantaneo = atualizaInstantaneo
        self.modo = self.DISTANCIA_4_PORTAS


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

    def leDistancia(self,porta):
        # Atualiza os dados antes de ler
        if(porta < 0 or porta > 3):
            raise ValueError("Porta inválida. Deve ser 0, 1, 2 ou 3.")
        if(self.atualizaInstantaneo):
            if not self.atualiza():
                return None
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        indice = porta * 2
        distancia = struct.unpack('>h', bytes(self.lista[indice:indice+2]))[0]
        return distancia

    def botaoApertado(self, porta):
        if(porta < 0 or porta > 3):
            raise ValueError("Porta inválida. Deve ser 0, 1, 2 ou 3.")
        # Atualiza os dados antes de ler
        if(self.atualizaInstantaneo):
            if not self.atualiza():
                return None
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        indice = (porta * 2) + 8
        botao = struct.unpack('>h', bytes(self.lista[indice:indice+2]))[0]
        return (botao == 1) # True or False

