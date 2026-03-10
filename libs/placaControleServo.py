import struct
import time

from portas import Portas


class PlacaControleServo:
    """Controle de servo via protocolo serial half-duplex one-wire.

    Protocolo (6 bytes):
        [0] ID do equipamento
        [1] Posição desejada HIGH byte
        [2] Posição desejada LOW byte
        [3] Potência PWM (0-255)
        [4] Zona morta (0-255)
        [5] CRC = XOR dos bytes 0..4
    """
    ultima_posicao = None
    TAMANHO_PACOTE = 6
    DEBUG = False

    def __init__(self, porta_serial, id_equipamento, baud_rate=115200):
        self.id_equipamento = id_equipamento & 0xFF
        portas = Portas()
        self.ser = portas.abre_porta_serial(porta_serial, baud_rate)
        if self.ser is None:
            raise Exception('Erro ao abrir a porta serial da PlacaControleServo')

    def __del__(self):
        if self.ser is not None:
            self.ser.close()
            if self.DEBUG:
                print('Fechando a porta serial do PlacaControleServo')

    @staticmethod
    def _calcular_crc(buf):
        crc = 0
        for b in buf:
            crc ^= b
        return crc & 0xFF

    def _montar_pacote(self, posicao, potencia, zona_morta):
        posicao = max(0, min(1023, posicao))
        potencia = max(0, min(255, potencia))
        zona_morta = max(0, min(255, zona_morta))
        pacote = [
            self.id_equipamento,
            (posicao >> 8) & 0xFF,
            posicao & 0xFF,
            potencia & 0xFF,
            zona_morta & 0xFF,
        ]
        pacote.append(self._calcular_crc(pacote))
        return bytes(pacote)

    def _parsear_resposta(self, dados):
        if len(dados) != self.TAMANHO_PACOTE:
            return None
        crc_calculado = self._calcular_crc(dados[:5])
        if crc_calculado != dados[5]:
            if self.DEBUG:
                print(f'CRC inválido: esperado {crc_calculado:#04x}, recebido {dados[5]:#04x}')
            return None
        id_equip = dados[0]
        posicao_atual = (dados[1] << 8) | dados[2]
        potencia = dados[3]
        zona_morta = dados[4]
        return {
            'id': id_equip,
            'posicao': posicao_atual,
            'potencia': potencia,
            'zona_morta': zona_morta,
        }

    def envia_comando(self, posicao, potencia, zona_morta=5, tentativas=3):
        """Envia comando para o equipamento e retorna a resposta.

        Args:
            posicao: Posição desejada do potenciômetro (0-1023)
            potencia: Potência PWM (0-255)
            zona_morta: Zona morta do controle (0-255), default 5
            tentativas: Número de tentativas em caso de falha

        Returns:
            dict com 'id', 'posicao', 'potencia', 'zona_morta' ou None se falhou
        """
        pacote = self._montar_pacote(posicao, potencia, zona_morta)

        for i in range(tentativas):
            self.ser.reset_input_buffer()
            self.ser.write(pacote)
            self.ser.flush()

            # Descarta o eco do próprio envio (one-wire: HOST ouve o que envia)
            eco = self.ser.read(self.TAMANHO_PACOTE)

            # Lê a resposta do equipamento
            resposta = self.ser.read(self.TAMANHO_PACOTE)

            if self.DEBUG:
                print(f'TX:  {[f"0x{b:02x}" for b in pacote]}')
                print(f'ECO: {[f"0x{b:02x}" for b in eco]}')
                print(f'RX:  {[f"0x{b:02x}" for b in resposta]}')

            resultado = self._parsear_resposta(resposta)
            if resultado is not None:
                return resultado

            if self.DEBUG:
                print(f'Tentativa {i + 1}/{tentativas} falhou')
            time.sleep(0.005)

        return None

    def move_servo(self, posicao, potencia=255, zona_morta=5):
        """Move o servo para a posição desejada.

        Args:
            posicao: Posição desejada (0-1023)
            potencia: Potência PWM (0-255), default 255
            zona_morta: Zona morta do controle (0-255), default 5

        Returns:
            Posição atual reportada pelo equipamento, ou None se falhou
        """
        resultado = self.envia_comando(posicao, potencia, zona_morta)
        if resultado is not None:
            return resultado['posicao']
        return None

    def le_posicao(self):
        """Lê a posição atual do servo sem alterar o comando.

        Envia posição 512 com potência 0 (motor parado) para apenas consultar.

        Returns:
            Posição atual reportada pelo equipamento, ou None se falhou
        """
        resultado = self.envia_comando(512, 0)
        if resultado is not None:
            return resultado['posicao']
        return None

    def para_servo(self):
        """Para o motor do servo (potência 0).

        Returns:
            Posição atual reportada pelo equipamento, ou None se falhou
        """
        resultado = self.envia_comando(512, 0)
        if resultado is not None:
            return resultado['posicao']
        return None
