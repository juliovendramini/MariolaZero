import time

from portas import Portas


class PlacaControleServo:
    """Controle de servo via protocolo serial half-duplex one-wire.

    Versão unificada (17/10/2026): junta a lib de bananaPiM4Zero/libs (broadcast e troca de ID)
    com a do Dropbox (calibração do tempo de trava). Precisa do firmware unificado da placa
    (placaControleServo.ino da mesma data) para usar todos os recursos.

    Protocolo (6 bytes):
        [0] ID do equipamento (254 = broadcast sem resposta)
        [1] Posição desejada HIGH byte  (0xFF = troca de ID)
        [2] Posição desejada LOW byte
        [3] Potência PWM (0-255)          (0xAA na troca de ID)
        [4] Zona morta (0-255)             (0x55 na troca de ID)
        [5] CRC = XOR dos bytes 0..4

    Comandos especiais (valores de "posição" fora da faixa 0-1023):
        65000  calibração do tempo de trava: [3..4] = tempo em ms (1000-5000); a placa
               responde com 65000 no lugar da posição
        65001  consulta: a placa só responde com a posição atual, sem mudar o comando
        0xFFxx troca de ID (ver define_id)
    """
    ID_BROADCAST = 254
    ultima_posicao = None
    TAMANHO_PACOTE = 6
    DEBUG = False          # True imprime cada pacote enviado/recebido (deixa o laço lento)

    COMANDO_CALIBRACAO = 65000
    COMANDO_CONSULTA = 65001
    TEMPO_DETECTA_TRAVA_MIN = 1000  # ms - limite mínimo aceito pela placa
    TEMPO_DETECTA_TRAVA_MAX = 5000  # ms - limite máximo aceito pela placa

    def __init__(self, porta_serial, id_equipamento, baud_rate=250000):
        self.id_equipamento = id_equipamento & 0xFF
        portas = Portas()
        self.ser = portas.abre_porta_serial(porta_serial, baud_rate)
        if self.ser is None:
            raise Exception('Erro ao abrir a porta serial da PlacaControleServo')

    def __del__(self):
        if getattr(self, 'ser', None) is not None:
            self.ser.close()
            if self.DEBUG:
                print('Fechando a porta serial do PlacaControleServo')

    # ------------------------------------------------------------------ pacotes
    @staticmethod
    def _calcular_crc(buf):
        crc = 0
        for b in buf:
            crc ^= b
        return crc & 0xFF

    def _montar_pacote(self, posicao, potencia, zona_morta, id_equipamento=None):
        posicao = max(0, min(1023, int(posicao)))
        potencia = max(0, min(255, int(potencia)))
        zona_morta = max(0, min(255, int(zona_morta)))
        pacote = [
            self.id_equipamento if id_equipamento is None else id_equipamento,
            (posicao >> 8) & 0xFF,
            posicao & 0xFF,
            potencia & 0xFF,
            zona_morta & 0xFF,
        ]
        pacote.append(self._calcular_crc(pacote))
        return bytes(pacote)

    def _montar_pacote_comando(self, comando, valor, id_equipamento=None):
        """Monta um pacote de comando especial (ex.: calibração).

        Diferente de _montar_pacote, o campo de "posição" não é limitado a
        0-1023, pois carrega o código do comando (ex.: COMANDO_CALIBRACAO).
        O campo valor (16 bits) ocupa os bytes normalmente usados por
        potência e zona morta.
        """
        comando = max(0, min(0xFFFF, int(comando)))
        valor = max(0, min(0xFFFF, int(valor)))
        pacote = [
            self.id_equipamento if id_equipamento is None else id_equipamento,
            (comando >> 8) & 0xFF,
            comando & 0xFF,
            (valor >> 8) & 0xFF,
            valor & 0xFF,
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
        return {
            'id': dados[0],
            'posicao': (dados[1] << 8) | dados[2],
            'potencia': dados[3],
            'zona_morta': dados[4],
        }

    def _envia_sem_resposta(self, pacote, rotulo='TX'):
        self.ser.reset_input_buffer()
        self.ser.write(pacote)
        self.ser.flush()
        self.ser.read(self.TAMANHO_PACOTE)  # descarta eco (one-wire: o HOST ouve o que envia)
        if self.DEBUG:
            print(f'{rotulo}: {[f"0x{b:02x}" for b in pacote]}')

    def _transacao(self, pacote, tentativas=3):
        """Envia o pacote e devolve a resposta já conferida (dict) ou None."""
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
            if resultado is not None and resultado['id'] == self.id_equipamento:
                return resultado

            if self.DEBUG:
                print(f'Tentativa {i + 1}/{tentativas} falhou')
            time.sleep(0.002)
        return None

    # ------------------------------------------------------------------ comandos
    def envia_broadcast(self, posicao, potencia, zona_morta=5):
        """Envia comando para todos os dispositivos; nenhuma resposta é esperada."""
        pacote = self._montar_pacote(posicao, potencia, zona_morta, id_equipamento=self.ID_BROADCAST)
        self._envia_sem_resposta(pacote, 'BROADCAST TX')

    def define_id(self, novo_id):
        """Grava novo_id na EEPROM do dispositivo e o adota como ID ativo.

        Envia o comando especial (buf[1]=0xFF, buf[3]=0xAA, buf[4]=0x55)
        endereçado ao ID atual. O firmware não responde a este comando.
        Atenção: uma placa com o firmware antigo do Dropbox não conhece este comando e
        manda o servo para a posição 1023.

        Args:
            novo_id: Novo ID desejado (0-253)

        Returns:
            True se o pacote foi enviado, False se novo_id inválido.
        """
        if not (0 <= novo_id < self.ID_BROADCAST):
            if self.DEBUG:
                print(f'define_id: ID {novo_id} inválido (deve ser 0-253)')
            return False

        pacote = [self.id_equipamento, 0xFF, novo_id & 0xFF, 0xAA, 0x55]
        pacote.append(self._calcular_crc(pacote))
        self._envia_sem_resposta(bytes(pacote), 'SET ID TX')
        self.id_equipamento = novo_id
        return True

    def calibrar_tempo_detecta_trava(self, tempo_ms, tentativas=3):
        """Calibra o tempo (ms) sem movimento para o motor ser considerado travado.

        A placa grava o valor na EEPROM, limitando-o entre TEMPO_DETECTA_TRAVA_MIN e
        TEMPO_DETECTA_TRAVA_MAX, e confirma ecoando COMANDO_CALIBRACAO na resposta.

        Returns:
            True se a placa confirmou o comando, False caso contrário
        """
        pacote = self._montar_pacote_comando(self.COMANDO_CALIBRACAO, tempo_ms)
        for _ in range(tentativas):
            resultado = self._transacao(pacote, tentativas=1)
            if resultado is not None and resultado['posicao'] == self.COMANDO_CALIBRACAO:
                return True
            time.sleep(0.002)
        return False

    def calibrar_tempo_detecta_trava_todos(self, tempo_ms):
        """Calibra o tempo de trava de todas as placas do barramento (broadcast, sem confirmação)."""
        pacote = self._montar_pacote_comando(self.COMANDO_CALIBRACAO, tempo_ms,
                                             id_equipamento=self.ID_BROADCAST)
        self._envia_sem_resposta(pacote, 'BROADCAST CALIBRA TX')

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
        return self._transacao(self._montar_pacote(posicao, potencia, zona_morta), tentativas)

    def move_servo(self, posicao, potencia=255, zona_morta=5):
        """Move o servo para a posição desejada.

        Returns:
            Posição atual reportada pelo equipamento, ou None se falhou
        """
        resultado = self.envia_comando(posicao, potencia, zona_morta)
        if resultado is not None:
            self.ultima_posicao = resultado['posicao']
            return resultado['posicao']
        return None

    def consulta_posicao(self, tentativas=3):
        """Lê a posição atual SEM mudar o comando (o servo continua indo para onde estava indo).

        Precisa do firmware unificado: o firmware antigo entende 65001 como posição e manda o
        servo para 1023. Com firmware antigo, use le_posicao().

        Returns:
            Posição atual reportada pelo equipamento, ou None se falhou
        """
        resultado = self._transacao(self._montar_pacote_comando(self.COMANDO_CONSULTA, 0), tentativas)
        if resultado is not None:
            self.ultima_posicao = resultado['posicao']
            return resultado['posicao']
        return None

    def le_posicao(self):
        """Lê a posição atual enviando posição 512 com potência 0.

        Atenção: isso DESLIGA o motor do servo (potência 0) até o próximo move_servo.
        Para só consultar sem parar o servo, use consulta_posicao() (firmware unificado).

        Returns:
            Posição atual reportada pelo equipamento, ou None se falhou
        """
        resultado = self.envia_comando(512, 0)
        if resultado is not None:
            self.ultima_posicao = resultado['posicao']
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

    @staticmethod
    def buscar_servos(porta_serial, baud_rate=250000):
        """Escaneia todos os IDs (0-253) e retorna os que responderam.

        Cada servo encontrado fica com o motor desligado (potência 0).

        Args:
            porta_serial: Porta serial (ex: Portas.SERIAL1)
            baud_rate: Baud rate da comunicação, default 250000

        Returns:
            Lista de dicts com 'id' e 'posicao' dos servos encontrados
        """
        portas = Portas()
        ser = portas.abre_porta_serial(porta_serial, baud_rate)
        if ser is None:
            raise Exception('Erro ao abrir a porta serial para busca de servos')

        encontrados = []
        posicao = 512
        potencia = 0
        zona_morta = 5

        try:
            for id_equip in range(PlacaControleServo.ID_BROADCAST):   # 254 (broadcast) não responde
                pacote = [
                    id_equip & 0xFF,
                    (posicao >> 8) & 0xFF,
                    posicao & 0xFF,
                    potencia & 0xFF,
                    zona_morta & 0xFF,
                ]
                pacote.append(PlacaControleServo._calcular_crc(pacote))
                dados = bytes(pacote)

                ser.reset_input_buffer()
                ser.write(dados)
                ser.flush()

                # Descarta eco (half-duplex one-wire)
                ser.read(PlacaControleServo.TAMANHO_PACOTE)
                # Lê resposta
                resposta = ser.read(PlacaControleServo.TAMANHO_PACOTE)

                if len(resposta) == PlacaControleServo.TAMANHO_PACOTE:
                    crc_calculado = PlacaControleServo._calcular_crc(resposta[:5])
                    if crc_calculado == resposta[5]:
                        pos_atual = (resposta[1] << 8) | resposta[2]
                        encontrados.append({'id': resposta[0], 'posicao': pos_atual})
                        print(f'Servo encontrado! ID: {resposta[0]}, Posição: {pos_atual}')

                if PlacaControleServo.DEBUG:
                    if id_equip % 32 == 0:
                        print(f'Escaneando IDs {id_equip}-{min(id_equip + 31, 253)}...')
        finally:
            ser.close()

        print(f'\nBusca concluída. {len(encontrados)} servo(s) encontrado(s).')
        return encontrados
