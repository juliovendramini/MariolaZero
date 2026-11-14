import struct
import threading
import time

from libs.cronometro import Cronometro
from libs.portas import Portas


class Giroscopio:
    GYRO = 0
    GYRO2 = 1
    GYRO_CAL = 2
    modo = 0
    quantidade_bytes_modo = 8

    def __init__(self, porta_serial):
        # 8 valores
        self.lista = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        portas = Portas()
        self.ser = portas.abre_porta_serial(porta_serial, 115200)
        if self.ser is None:
            raise Exception('Erro ao abrir a porta serial do giroscopio')
        self.set_modo(self.GYRO)
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
            time.sleep(0.005)  # 25ms

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
        if modo < 0 or modo > 2:
            raise ValueError('Modo inválido. Deve ser 0, 1 ou 2.')
        self.modo = modo
        if modo in {self.GYRO, self.GYRO2}:
            self.quantidade_bytes_modo = 8
        elif modo == self.GYRO_CAL:
            self.quantidade_bytes_modo = 1

    def atualiza(self):
        # limpo o buffer de entrada
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        # Envia o comando para solicitar o bytes necessarios
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

    def le_angulo_x(self):
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        angulo_x = struct.unpack('>h', bytes(self.lista[0:2]))[0]
        return angulo_x

    def le_angulo_y(self):
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        angulo_y = struct.unpack('>h', bytes(self.lista[2:4]))[0]
        return angulo_y

    def le_angulo_z(self):
        # tenho q usar struct pra pegar dois bytes da lista e transformar em inteiro com sinal
        angulo_z = struct.unpack('>h', bytes(self.lista[4:6]))[0]
        return angulo_z

    def reseta_z(self):
        # apenas troco o modo de GYRO para GYRO2 ou o contrário
        if self.modo == self.GYRO:
            self.modo = self.GYRO2
        else:
            self.modo = self.GYRO
        time.sleep(0.025)

    def calibra(self):
        self._parar_thread()
        self.set_modo(self.GYRO_CAL)
        tempo = Cronometro()
        tempo.inicia()
        # Aguarda 5 segundos para a calibração
        self.ser.write(bytes([self.modo]))  # envio o modo novo de calibração
        while tempo.tempo() < 5000:
            dados = self.ser.read(1)  # o modo de calibracao do giroscopio só retorna 1 byte
            # Verifica se recebeu exatamente self.quantidade_bytes_modo bytes
            if len(dados) == 1:
                # Atualiza a lista com os valores recebidos
                break
        self.set_modo(self.GYRO)
        self._iniciar_thread()
        if tempo.tempo() >= 5000:
            print('Tempo de calibração excedido')
            return False
        # Aguarda 5 segundos para a calibração
        print('Calibração concluída')
        return True
