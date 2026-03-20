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

    def __init__(self, porta_serial):
        # 32 valores
        self.lista = [0xFF, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29, 0x2A, 0x2B]  # fmt: skip
        portas = Portas()
        self.ser = portas.abre_porta_serial(porta_serial, 115200)
        if self.ser is None:
            raise Exception('Erro ao abrir a porta serial do sensor de cor e reflexão')
        self.modo = 2
        self.quantidade_bytes_modo = 32
        self._thread_ativa = False
        self._thread = None
        self._iniciar_thread()

    def __del__(self):
        """Destrutor da classe. Para a thread e fecha a porta serial."""
        self._parar_thread()
        if self.ser is not None:
            self.ser.close()

    def _atualiza_periodicamente(self):
        """Função que chama `atualiza` a cada 25ms."""
        while self._thread_ativa:
            self.atualiza()
            time.sleep(0.01)  # 25ms

    def _iniciar_thread(self):
        """Inicia a thread para chamar `atualiza` periodicamente."""
        if not self._thread_ativa:
            self._thread_ativa = True
            self._thread = threading.Thread(target=self._atualiza_periodicamente)
            self._thread.daemon = True  # Permite que o programa principal encerre mesmo com a thread ativa
            self._thread.start()

    def _parar_thread(self):
        """Para a thread que chama `atualiza`."""
        self._thread_ativa = False
        if self._thread is not None:
            self._thread.join()

    def set_modo(self, modo):
        self.modo = modo
        if modo in {0, 1, 2, 3, 4, 5}:
            self.quantidade_bytes_modo = 32
        else:
            self.quantidade_bytes_modo = 1

    def atualiza(self):
        # Envia o comando para solicitar os 32 bytes
        # limpo o buffer de entrada
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes([self.modo]))

        # Aguarda receber os self.quantidade_bytes_modo bytes via serial
        dados = self.ser.read(self.quantidade_bytes_modo)

        # Verifica se recebeu exatamente self.quantidade_bytes_modo bytes
        if len(dados) == self.quantidade_bytes_modo:
            # Atualiza a lista com os valores recebidos
            self.lista = list(dados)
            return True
        else:
            return False

    def le_reflexao(self):
        # Atualiza os dados antes de ler
        return self.lista[0:4]

    def posicao(self):
        # Atualiza os dados antes de ler
        return self.lista[29]

    def le_rgbc(self, sensor):
        # Atualiza os dados antes de ler
        if sensor == 1:
            return self.lista[4:8]
        elif sensor == 2:
            return self.lista[8:12]
        elif sensor == 3:
            return self.lista[12:16]
        else:
            return None

    def le_hsv(self, sensor):
        # Atualiza os dados antes de ler
        if sensor == 1:
            return self.lista[20:23]
        elif sensor == 2:
            return self.lista[23:26]
        elif sensor == 3:
            return self.lista[26:29]
        else:
            return None

    def calibra_branco(self):
        self._parar_thread()
        modo_antigo = self.modo
        self.set_modo(self.MODO_CALIBRA_BRANCO)
        tempo = Cronometro()
        tempo.inicia()
        # Aguarda 5 segundos para a calibração
        self.ser.write(bytes([self.modo]))  # envio o modo novo de calibração do branco
        while tempo.tempo() < 5000:
            dados = self.ser.read(self.quantidade_bytes_modo)
            # Verifica se recebeu exatamente self.quantidade_bytes_modo bytes
            if len(dados) == self.quantidade_bytes_modo:
                # Atualiza a lista com os valores recebidos
                self.lista = list(dados)
                break
        self.set_modo(modo_antigo)
        self.ser.write(bytes([self.modo]))  # envio o modo novo de calibração do branco
        self._iniciar_thread()
        if tempo.tempo() >= 5000:
            print('Tempo de calibração excedido')
            return False
        print('Calibração concluída')
        return True

    def calibra_preto(self):
        self._parar_thread()
        modo_antigo = self.modo
        self.set_modo(self.MODO_CALIBRA_PRETO)
        tempo = Cronometro()
        tempo.inicia()
        # Aguarda 5 segundos para a calibração
        self.ser.write(bytes([self.modo]))  # envio o modo novo de calibração do branco
        while tempo.tempo() < 3000:
            dados = self.ser.read(self.quantidade_bytes_modo)
            # Verifica se recebeu exatamente self.quantidade_bytes_modo bytes
            if len(dados) == self.quantidade_bytes_modo:
                # Atualiza a lista com os valores recebidos
                self.lista = list(dados)
                break
        self.set_modo(modo_antigo)
        self.ser.write(bytes([self.modo]))  # envio o modo novo de calibração do branco
        self._iniciar_thread()
        if tempo.tempo() >= 3000:
            print('Tempo de calibração excedido')
            return False
        # Aguarda 3 segundos para a calibração
        print('Calibração concluída')
        return True
