import threading
import time
from cronometro import Cronometro
from portas import Portas
class CorReflexao:
    MODO_RGB_HSV_4X = 0
    MODO_RGB_HSV_16X = 1
    MODO_RGB_HSV_AUTO = 2
    MODO_CALIBRA_BRANCO = 3
    MODO_CALIBRA_PRETO = 4
    MODO_RAW_AUTO = 5


    
    def __init__(self, portaSerial):
        #32 valores
        self.lista = [0xff, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1a, 0x1b, 0x1c, 0x1d, 0x1e, 0x1f, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2a, 0x2b]
        portas = Portas()
        self.ser = portas.abrePortaSerial(portaSerial, 115200)
        if self.ser == None:
            raise Exception("Erro ao abrir a porta serial do sensor de cor e reflexão")
        self.modo = 2
        self.quantidadeBytesModo = 32
        self._thread_ativa = False
        self._thread = None
        self._iniciarThread()

    def __del__(self):
        """Destrutor da classe. Para a thread e fecha a porta serial."""
        self._pararThread()
        if self.ser is not None:
            self.ser.close()

    def _atualizaPeriodicamente(self):
        """Função que chama `atualiza` a cada 25ms."""
        while self._thread_ativa:
            self.atualiza()
            time.sleep(0.01)  # 25ms

    def _iniciarThread(self):
        """Inicia a thread para chamar `atualiza` periodicamente."""
        if not self._thread_ativa:
            self._thread_ativa = True
            self._thread = threading.Thread(target=self._atualizaPeriodicamente)
            self._thread.daemon = True  # Permite que o programa principal encerre mesmo com a thread ativa
            self._thread.start()

    def _pararThread(self):
        """Para a thread que chama `atualiza`."""
        self._thread_ativa = False
        if self._thread is not None:
            self._thread.join()

    def setModo(self, modo):
        self.modo = modo
        if(modo == 0 or 
           modo == 1 or
           modo == 2 or
           modo == 5):
            self.quantidadeBytesModo = 32
        else:
            self.quantidadeBytesModo = 1

    def atualiza(self):
        # Envia o comando para solicitar os 32 bytes
        #limpo o buffer de entrada
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
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
        return self.lista[0:4]
    
    def posicao(self):
        # Atualiza os dados antes de ler
        return self.lista[29]

    def leRGBC(self,sensor):
        # Atualiza os dados antes de ler
        if sensor == 1:
            return self.lista[4:8]
        elif sensor == 2:
            return self.lista[8:12]
        elif sensor == 3:
            return self.lista[12:16]
        else:
            return None

    def leHSV(self,sensor):
        # Atualiza os dados antes de ler
        if sensor == 1:
            return self.lista[20:23]
        elif sensor == 2:
            return self.lista[23:26]
        elif sensor == 3:
            return self.lista[26:29]
        else:
            return None


    def calibraBranco(self):
        self._pararThread()
        modoAntigo = self.modo
        self.setModo(self.MODO_CALIBRA_BRANCO)
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
        self.setModo(modoAntigo)
        self.ser.write(bytes([self.modo])) #envio o modo novo de calibração do branco
        self._iniciarThread()
        if(tempo.tempo() >= 5000):
            print("Tempo de calibração excedido")
            return False
        print("Calibração concluída")
        return True
    
    def calibraPreto(self):
        self._pararThread()
        modoAntigo = self.modo
        self.setModo(self.MODO_CALIBRA_PRETO)
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
        self.setModo(modoAntigo)
        self.ser.write(bytes([self.modo])) #envio o modo novo de calibração do branco
        self._iniciarThread()
        if(tempo.tempo() >= 3000):
            print("Tempo de calibração excedido")
            return False
        # Aguarda 3 segundos para a calibração
        print("Calibração concluída")
        return True
