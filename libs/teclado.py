import os
import signal
import threading
from time import sleep

from smbus2 import SMBus


class Teclado:
    LIBERADO = 1
    APERTADO = 0
    ENTER = 3
    ESC = 4
    CIMA = 2
    BAIXO = 1

    def __init__(self, i2c_bus=1, i2c_address=0x38):
        """
        Inicializa o PCF8574A.
        :param i2c_bus: Número do barramento I2C (ex.: 0 para /dev/i2c-0).
        :param i2c_address: Endereço I2C do PCF8574A (padrão: 0x38).
        """
        self.bus = SMBus(i2c_bus)
        self.address = i2c_address

        # Estado inicial dos pinos (1 = entrada, 0 = saída)
        self.state = 0xFF  # Todos os pinos configurados como entrada inicialmente
        self._atualizar_estado()
        self._configurar_pinos()

    def _atualizar_estado(self):
        """
        Atualiza o estado dos pinos no PCF8574.
        """
        self.bus.write_byte(self.address, self.state)

    def _configurar_pinos(self):
        """
        Configura os 4 primeiros pinos como entrada (botões) e os 4 últimos como saída (LEDs).
        """
        # Pinos 0-3 como entrada (1), pinos 4-7 como saída (0)
        self.state = 0x0F
        self._atualizar_estado()

    def le_botao(self, botao):
        """
        Lê o estado de um botão (índices 1 a 4).
        :param botao: Número do botão (1 a 4).
        :return: Estado do botão (0 = pressionado, 1 = liberado).
        """
        if botao < 1 or botao > 4:
            raise ValueError('Os botões devem estar entre 1 e 4.')
        pino = botao - 1  # Converter índice 1-4 para 0-3
        leitura = self.bus.read_byte(self.address)
        return (leitura >> pino) & 0x01

    def botao_pressionado(self, botao):
        """
        Verifica se um botão está pressionado (índices 1 a 4).
        :param botao: Número do botão (1 a 4).
        :return: True se o botão estiver pressionado, False caso contrário.
        """
        return self.le_botao(botao) == self.APERTADO

    def altera_led(self, led, valor):
        """
        Controla o estado de um LED (índices 1 a 4).
        :param led: Número do LED (1 a 4).
        :param valor: Valor a ser escrito (0 = desligado, 1 = ligado).
        """
        if led < 1 or led > 4:
            raise ValueError('Os LEDs devem estar entre 1 e 4.')
        pino = led + 3  # Converter índice 1-4 para 4-7
        if valor:
            self.state |= 1 << pino  # Define o pino como alto (1)
        else:
            self.state &= ~(1 << pino)  # Define o pino como baixo (0)
        self._atualizar_estado()

    def botao_para_encerrar_programa(self, botao=3):
        """
        Monitora o botão para encerrar o programa.
        :param botao: Número do botão (1 a 4).
        """
        if botao < 1 or botao > 4:
            raise ValueError('Os botões devem estar entre 1 e 4.')
        """Função para monitorar o teclado em uma thread separada."""
        self.botao_encerrar_codigo = botao
        thread_teclado = threading.Thread(target=self._thread_encerrar_programa, daemon=True)
        thread_teclado.start()

    def _thread_encerrar_programa(self):
        """Função para monitorar o teclado em uma thread separada."""
        while True:
            entrada = self.le_botao(self.botao_encerrar_codigo)
            if entrada == self.APERTADO:
                print('Botão apertado, encerrando o programa...')
                # raise KeyboardInterrupt  # Lança a exceção KeyboardInterrupt
                os.kill(os.getpid(), signal.SIGINT)
            # lanca execssao para poder fechar o programa

            sleep(0.1)  # Aguarda 100ms
