from smbus2 import SMBus
'''Classe para controlar os sensores i2c TCS34725 nas portas I2C do MariolaZero.
Precisamos passar como parametro qual porta ele I2C está usando'''
class TCS34725:
    MUX_ADDR = 0x70  # Endereço do TCA9548A
    TCS_ADDR = 0x29  # Endereço do sensor TCS34725
    COMMAND_BIT = 0x80
    ENABLE = 0x00
    ATIME = 0x01
    CONTROL = 0x0F
    ID = 0x12
    CDATAL = 0x14
    bus = None
    I2C_BUS = 1  # Verifique qual /dev/i2c-X você está usando
    def __init__(self, portaMux = None):
        self.bus = SMBus(self.I2C_BUS)
        self.portaMux = portaMux
        if self.portaMux > 7 or self.portaMux < 0:
            raise ValueError("Canal inválido (deve ser 0 a 7)")
        self._selectChannel()
            # Ativa o sensor (PON + AEN)
        self.bus.write_byte_data(self.TCS_ADDR, self.COMMAND_BIT | self.ENABLE, 0x03)

        # Tempo de integração (2.4ms × (256 - ATIME)) → ATIME = 0xC0 → ~60ms
        self.bus.write_byte_data(self.TCS_ADDR, self.COMMAND_BIT | self.ATIME, 0xC0)

        # Ganho (1x, 4x, 16x, 60x) → 0x01 = 4x
        self.bus.write_byte_data(self.TCS_ADDR, self.COMMAND_BIT | self.CONTROL, 0x01)
    
    # Função para selecionar canal no TCA9548A
    def _selectChannel(self):
        self.bus.write_byte(self.MUX_ADDR, 1 << self.portaMux)
            

    # Função para ler ID do TCS34725 (deve retornar 0x44 ou 0x10)
    def _readTcsId(self):
        TCS34725_ID = 0x12
        return self.bus.read_byte_data(self.TCS_ADDR, TCS34725_ID)


    # Funções auxiliares
    def _readWord(self, reg):
        low = self.bus.read_byte_data(self.TCS_ADDR, self.COMMAND_BIT | reg)
        high = self.bus.read_byte_data(self.TCS_ADDR, self.COMMAND_BIT | (reg + 1))
        return (high << 8) | low

    def leValores(self):
        # Lê os valores
        self._selectChannel()
        self._selectChannel()
        clear = self._readWord(self.CDATAL)
        red = self._readWord(self.CDATAL + 2)
        green = self._readWord(self.CDATAL + 4)
        blue = self._readWord(self.CDATAL + 6)
        return (red, green, blue, clear)
