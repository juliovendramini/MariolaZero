from smbus2 import SMBus

class IoI2C:
    LIBERADO = 1
    APERTADO = 0
    def __init__(self, i2c_bus=1, i2c_address=0x20):
        """
        Inicializa o PCF8574.
        :param i2c_bus: Número do barramento I2C (ex.: 0 para /dev/i2c-0).
        :param i2c_address: Endereço I2C do PCF8574 (padrão: 0x20).
        """
        self.bus = SMBus(i2c_bus)
        self.address = i2c_address

        # Estado inicial dos pinos (1 = entrada, 0 = saída)
        self.state = 0xFF  # Todos os pinos configurados como entrada inicialmente
        self._atualizar_estado()
        self.configurar_pinos()

    def _atualizar_estado(self):
        """
        Atualiza o estado dos pinos no PCF8574.
        """
        self.bus.write_byte(self.address, self.state)

    def configurar_pinos(self):
        """
        Configura os 4 primeiros pinos como entrada (botões) e os 4 últimos como saída (LEDs).
        """
        # Pinos 0-3 como entrada (1), pinos 4-7 como saída (0)
        self.state = 0x0F
        self._atualizar_estado()

    def ler_botao(self, botao):
        """
        Lê o estado de um botão (índices 1 a 4).
        :param botao: Número do botão (1 a 4).
        :return: Estado do botão (0 = pressionado, 1 = liberado).
        """
        if botao < 1 or botao > 4:
            raise ValueError("Os botões devem estar entre 1 e 4.")
        pino = botao - 1  # Converter índice 1-4 para 0-3
        leitura = self.bus.read_byte(self.address)
        return (leitura >> pino) & 0x01

    def escrever_led(self, led, valor):
        """
        Controla o estado de um LED (índices 1 a 4).
        :param led: Número do LED (1 a 4).
        :param valor: Valor a ser escrito (0 = desligado, 1 = ligado).
        """
        if led < 1 or led > 4:
            raise ValueError("Os LEDs devem estar entre 1 e 4.")
        pino = led + 3  # Converter índice 1-4 para 4-7
        if valor:
            self.state |= (1 << pino)  # Define o pino como alto (1)
        else:
            self.state &= ~(1 << pino)  # Define o pino como baixo (0)
        self._atualizar_estado()

    def ler_todos_botoes(self):
        """
        Lê o estado de todos os botões (índices 1 a 4).
        :return: Lista com o estado de todos os botões (0 = pressionado, 1 = liberado).
        """
        leitura = self.bus.read_byte(self.address)
        return [(leitura >> i) & 0x01 for i in range(4)]

    def escrever_todos_leds(self, valores):
        """
        Controla o estado de todos os LEDs (índices 1 a 4).
        :param valores: Lista com os valores para os LEDs (0 = desligado, 1 = ligado).
        """
        if len(valores) != 4:
            raise ValueError("A lista de valores deve conter exatamente 4 elementos.")
        for i, valor in enumerate(valores, start=4):
            if valor:
                self.state |= (1 << i)
            else:
                self.state &= ~(1 << i)
        self._atualizar_estado()