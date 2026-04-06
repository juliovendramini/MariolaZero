import struct
import time

from portas import Portas


class PlacaControleMotor:
    """Controle de motor DC com encoder via protocolo serial half-duplex one-wire.

    Protocolo de comando (6 bytes):
        [0] ID do equipamento
        [1] Modo/Tipo de mensagem
        [2] Velocidade (int8_t, -100 a 100) ou dado HIGH
        [3] Giro comando HIGH byte (ou dado)
        [4] Giro comando LOW byte (ou dado)
        [5] CRC = XOR dos bytes 0..4

    Protocolo de resposta (8 bytes):
        [0] ID
        [1] Modo atual
        [2] Estado do motor (0=parado, 1=horário, 2=anti-horário)
        [3..6] Contagem absoluta de pulsos (int32_t, big-endian)
        [7] CRC = XOR dos bytes 0..6
    """
    TAMANHO_PACOTE_CMD = 6
    TAMANHO_PACOTE_RESP = 8
    DEBUG = True

    MODO_PID = 0
    MODO_PWM = 1
    MODO_SET_FREIO = 2
    MODO_RESET = 3
    MODO_CALIBRACAO = 4
    MODO_SET_KP = 5
    MODO_SET_KI = 6
    MODO_SET_KD = 7
    MODO_ATUALIZA = 9

    FREIO_BREAK = 0
    FREIO_TRAVADO = 1

    NORMAL = 0
    INVERTIDO = 1

    PARADO = 0
    GIRANDO_NORMAL = 1
    GIRANDO_INVERTIDO = 2

    def __init__(self, porta_serial, id_equipamento, baud_rate=115200):
        self.id_equipamento = id_equipamento & 0xFF
        self.motor_invertido = False
        self.angulo_delta = 0
        portas = Portas()
        self.ser = portas.abre_porta_serial(porta_serial, baud_rate)
        if self.ser is None:
            raise Exception('Erro ao abrir a porta serial da PlacaControleMotor')
        self.reset()

    def __del__(self):
        if self.ser is not None:
            self.ser.close()
            if self.DEBUG:
                print('Fechando a porta serial do PlacaControleMotor')

    @staticmethod
    def _calcular_crc(buf):
        crc = 0
        for b in buf:
            crc ^= b
        return crc & 0xFF

    def _montar_pacote(self, modo, valor, giro=0):
        """Monta pacote de comando.

        Args:
            modo: Modo de operação
            valor: Velocidade (-100 a 100) como int8 ou dado
            giro: Giro em pulsos (0 = contínuo)
        """
        modo = max(0, min(255, modo))
        valor_byte = valor & 0xFF  # int8 → uint8 para transmissão
        giro = max(0, min(65535, giro))
        pacote = [
            self.id_equipamento,
            modo & 0xFF,
            valor_byte,
            (giro >> 8) & 0xFF,
            giro & 0xFF,
        ]
        pacote.append(self._calcular_crc(pacote))
        return bytes(pacote)

    def _processar_resposta(self, dados):
        if len(dados) != self.TAMANHO_PACOTE_RESP:
            return None
        crc_calculado = self._calcular_crc(dados[:7])
        if crc_calculado != dados[7]:
            if self.DEBUG:
                print(f'CRC inválido: esperado {crc_calculado:#04x}, recebido {dados[7]:#04x}')
            return None
        id_equip = dados[0]
        modo = dados[1]
        estado = dados[2]
        pulsos = struct.unpack('>i', bytes(dados[3:7]))[0]
        return {
            'id': id_equip,
            'modo': modo,
            'estado': estado,
            'pulsos': pulsos,
        }

    def envia_comando(self, modo, valor, giro=0, tentativas=3):
        """Envia comando para o equipamento e retorna a resposta.

        Args:
            modo: Modo de operação
            valor: Velocidade (-100 a 100) ou dado
            giro: Giro em pulsos (0 = contínuo)
            tentativas: Número de tentativas em caso de falha

        Returns:
            dict com 'id', 'modo', 'estado', 'pulsos' ou None se falhou
        """
        pacote = self._montar_pacote(modo, valor, giro)

        for i in range(tentativas):
            self.ser.reset_input_buffer()
            self.ser.write(pacote)
            self.ser.flush()

            # Descarta o eco do próprio envio (one-wire: HOST ouve o que envia)
            eco = self.ser.read(self.TAMANHO_PACOTE_CMD)

            # Lê a resposta do equipamento
            resposta = self.ser.read(self.TAMANHO_PACOTE_RESP)

            if self.DEBUG:
                print(f'TX:  {[f"0x{b:02x}" for b in pacote]}')
                print(f'ECO: {[f"0x{b:02x}" for b in eco]}')
                print(f'RX:  {[f"0x{b:02x}" for b in resposta]}')

            resultado = self._processar_resposta(resposta)
            if resultado is not None:
                return resultado

            if self.DEBUG:
                print(f'Tentativa {i + 1}/{tentativas} falhou')
            time.sleep(0.005)

        return None

    def mover_pid(self, velocidade, giro=0):
        """Move o motor em modo PID (controle de velocidade).

        Args:
            velocidade: Velocidade desejada (-100 a 100). Positivo = horário, negativo = anti-horário.
            giro: Quantidade de pulsos para girar (0 = contínuo)

        Returns:
            dict com 'id', 'modo', 'estado', 'pulsos' ou None se falhou
        """
        velocidade = max(-100, min(100, velocidade))
        return self.envia_comando(self.MODO_PID, velocidade, giro)

    def mover_pwm(self, velocidade):
        """Move o motor em modo PWM direto (potência, sem PID).

        Args:
            velocidade: Velocidade/potência desejada (-100 a 100). Positivo = horário, negativo = anti-horário.

        Returns:
            dict com 'id', 'modo', 'estado', 'pulsos' ou None se falhou
        """
        velocidade = max(-100, min(100, velocidade))
        return self.envia_comando(self.MODO_PWM, velocidade)

    def parar_motor(self):
        """Para o motor (PID com velocidade 0).

        Returns:
            dict com 'id', 'modo', 'estado', 'pulsos' ou None se falhou
        """
        return self.envia_comando(self.MODO_PID, 0)

    def atualizar(self):
        """Lê o estado atual (pulsos/estado) sem alterar o comando.

        Returns:
            dict com 'id', 'modo', 'estado', 'pulsos' ou None se falhou
        """
        return self.envia_comando(self.MODO_ATUALIZA, 0)

    def le_pulsos(self):
        """Lê a contagem de pulsos atual sem alterar o comando.

        Returns:
            Contagem de pulsos (int32) ou None se falhou
        """
        resultado = self.atualizar()
        if resultado is not None:
            return resultado['pulsos']
        return None

    def set_freio(self, modo_freio):
        """Configura o modo de frenagem.

        Args:
            modo_freio: FREIO_BREAK (0) = soltar, FREIO_TRAVADO (1) = manter posição

        Returns:
            dict com resposta ou None se falhou
        """
        return self.envia_comando(self.MODO_SET_FREIO, modo_freio)

    def reset(self):
        """Reseta o equipamento ao estado inicial (como se tivesse acabado de ligar).

        Para o motor, zera contadores, reseta PID e frenagem, recarrega
        calibração e PID da EEPROM.

        Returns:
            dict com resposta ou None se falhou
        """
        resultado = self.envia_comando(self.MODO_RESET, 0)
        if resultado is not None:
            self.motor_invertido = False
            self.angulo_delta = 0
        return resultado

    def calibrar(self, tentativas=1):
        """Inicia a calibração de velocidade máxima do motor.

        O firmware roda o motor em ambos os sentidos e mede a velocidade.
        Este comando é bloqueante no firmware (~12s).

        Args:
            tentativas: Número de tentativas em caso de falha

        Returns:
            dict com 'giro_max_horario' e 'giro_max_antihorario' ou None se falhou
        """
        pacote = self._montar_pacote(self.MODO_CALIBRACAO, 0)

        for i in range(tentativas):
            self.ser.reset_input_buffer()
            self.ser.write(pacote)
            self.ser.flush()

            # Descarta o eco do próprio envio
            self.ser.read(self.TAMANHO_PACOTE_CMD)

            # Calibração demora ~12s, aumenta timeout temporariamente
            timeout_original = self.ser.timeout
            self.ser.timeout = 30
            resposta = self.ser.read(self.TAMANHO_PACOTE_RESP)
            self.ser.timeout = timeout_original

            if self.DEBUG:
                print(f'TX:  {[f"0x{b:02x}" for b in pacote]}')
                print(f'RX:  {[f"0x{b:02x}" for b in resposta]}')

            if len(resposta) == self.TAMANHO_PACOTE_RESP:
                crc_calculado = self._calcular_crc(resposta[:7])
                if crc_calculado == resposta[7]:
                    giro_horario = struct.unpack('>h', bytes(resposta[3:5]))[0]
                    giro_antihorario = struct.unpack('>h', bytes(resposta[5:7]))[0]
                    return {
                        'giro_max_horario': giro_horario,
                        'giro_max_antihorario': giro_antihorario,
                    }

            if self.DEBUG:
                print(f'Tentativa {i + 1}/{tentativas} de calibração falhou')
            time.sleep(0.1)

        return None

    def set_kp(self, valor):
        """Define a constante proporcional (Kp) do PID.

        Args:
            valor: Valor de Kp (float, será multiplicado por 100 e enviado como int)

        Returns:
            dict com resposta ou None se falhou
        """
        return self._enviar_constante_pid(self.MODO_SET_KP, valor)

    def set_ki(self, valor):
        """Define a constante integral (Ki) do PID.

        Args:
            valor: Valor de Ki (float, será multiplicado por 100 e enviado como int)

        Returns:
            dict com resposta ou None se falhou
        """
        return self._enviar_constante_pid(self.MODO_SET_KI, valor)

    def set_kd(self, valor):
        """Define a constante derivativa (Kd) do PID.

        Args:
            valor: Valor de Kd (float, será multiplicado por 100 e enviado como int)

        Returns:
            dict com resposta ou None se falhou
        """
        return self._enviar_constante_pid(self.MODO_SET_KD, valor)

    def _enviar_constante_pid(self, modo, valor, tentativas=3):
        """Envia uma constante PID para o equipamento.

        No protocolo, o valor × 100 é dividido em:
            byte[2] = HIGH byte
            byte[3] = LOW byte
            byte[4] = não usado (0)

        Args:
            modo: MODO_SET_KP, MODO_SET_KI ou MODO_SET_KD
            valor: Valor float da constante
            tentativas: Número de tentativas

        Returns:
            dict com resposta ou None se falhou
        """
        valor_raw = int(round(valor * 100))
        valor_raw = max(0, min(65535, valor_raw))
        pacote = [
            self.id_equipamento,
            modo & 0xFF,
            (valor_raw >> 8) & 0xFF,
            valor_raw & 0xFF,
            0,
        ]
        pacote.append(self._calcular_crc(pacote))
        dados = bytes(pacote)

        for i in range(tentativas):
            self.ser.reset_input_buffer()
            self.ser.write(dados)
            self.ser.flush()

            eco = self.ser.read(self.TAMANHO_PACOTE_CMD)
            resposta = self.ser.read(self.TAMANHO_PACOTE_RESP)

            if self.DEBUG:
                print(f'TX:  {[f"0x{b:02x}" for b in dados]}')
                print(f'ECO: {[f"0x{b:02x}" for b in eco]}')
                print(f'RX:  {[f"0x{b:02x}" for b in resposta]}')

            resultado = self._processar_resposta(resposta)
            if resultado is not None:
                return resultado

            if self.DEBUG:
                print(f'Tentativa {i + 1}/{tentativas} falhou')
            time.sleep(0.005)

        return None

    def direcao_motor(self, direcao):
        """Define a direção do motor (normal ou invertido).

        Args:
            direcao: NORMAL (0) ou INVERTIDO (1)
        """
        if direcao == self.NORMAL:
            self.motor_invertido = False
        else:
            self.motor_invertido = True

    def velocidade_motor(self, velocidade):
        """Move o motor continuamente com controle PID de velocidade.

        Aplica inversão se direcao_motor foi configurada como INVERTIDO.

        Args:
            velocidade: Velocidade desejada (-100 a 100)

        Returns:
            dict com resposta ou None se falhou
        """
        velocidade = max(-100, min(100, velocidade))
        if self.motor_invertido:
            velocidade = -velocidade
        return self.mover_pid(velocidade)

    def move_motor(self, velocidade, angulo):
        """Move o motor por uma certa quantidade de pulsos (ângulo).

        Aplica inversão se direcao_motor foi configurada como INVERTIDO.

        Args:
            velocidade: Velocidade desejada (-100 a 100)
            angulo: Quantidade de pulsos para girar (0~65535)

        Returns:
            dict com resposta ou None se falhou
        """
        angulo = abs(angulo)
        if angulo > 65535:
            return None
        velocidade = max(-100, min(100, velocidade))
        if self.motor_invertido:
            velocidade = -velocidade
        return self.mover_pid(velocidade, angulo)

    def potencia_motor(self, potencia):
        """Move o motor em modo PWM direto (potência, sem PID).

        Aplica inversão se direcao_motor foi configurada como INVERTIDO.

        Args:
            potencia: Potência desejada (-100 a 100)

        Returns:
            dict com resposta ou None se falhou
        """
        potencia = max(-100, min(100, potencia))
        if self.motor_invertido:
            potencia = -potencia
        return self.mover_pwm(potencia)

    def para_motor(self):
        """Para o motor (PID com velocidade 0).

        Returns:
            dict com resposta ou None se falhou
        """
        return self.mover_pid(0)

    def set_modo_freio(self, modo):
        """Configura o modo de frenagem.

        Args:
            modo: FREIO_BREAK (0) = soltar, FREIO_TRAVADO (1) = manter posição

        Returns:
            dict com resposta ou None se falhou
        """
        return self.set_freio(modo)

    def pid_motor(self, kp, ki, kd):
        """Define as três constantes do PID de uma vez.

        Args:
            kp: Constante proporcional (float)
            ki: Constante integral (float)
            kd: Constante derivativa (float)

        Returns:
            True se todas foram enviadas com sucesso, False caso contrário
        """
        r1 = self.set_kp(kp)
        r2 = self.set_ki(ki)
        r3 = self.set_kd(kd)
        return r1 is not None and r2 is not None and r3 is not None

    def reseta_angulo_motor(self):
        """Reseta a referência de ângulo do motor.

        Não reseta o ângulo diretamente na placa, apenas cria uma diferença (delta)
        para que o ângulo retornado por angulo_motor() comece do zero.
        """
        resultado = self.atualizar()
        if resultado is not None:
            self.angulo_delta = resultado['pulsos']

    def angulo_motor(self):
        """Retorna o ângulo relativo do motor (pulsos desde o último reset).

        Considera a inversão de direção e o delta do reseta_angulo_motor().

        Returns:
            Ângulo relativo em pulsos (int) ou 0 se falhou
        """
        resultado = self.atualizar()
        if resultado is not None:
            pulsos = resultado['pulsos']
            if self.motor_invertido:
                return -pulsos + self.angulo_delta
            return pulsos - self.angulo_delta
        return 0

    def estado_motor(self):
        """Retorna o estado atual do motor.

        Returns:
            PARADO (0), GIRANDO_NORMAL (1) ou GIRANDO_INVERTIDO (2)
        """
        resultado = self.atualizar()
        if resultado is not None:
            return resultado['estado']
        return self.PARADO

    @staticmethod
    def buscar_motores(porta_serial, baud_rate=115200):
        """Escaneia todos os 256 IDs possíveis (0-255) e retorna os que responderam.

        Args:
            porta_serial: Porta serial (ex: Portas.SERIAL1)
            baud_rate: Baud rate da comunicação, default 115200

        Returns:
            Lista de dicts com 'id', 'estado' e 'pulsos' dos motores encontrados
        """
        portas = Portas()
        ser = portas.abre_porta_serial(porta_serial, baud_rate)
        if ser is None:
            raise Exception('Erro ao abrir a porta serial para busca de motores')

        encontrados = []
        modo = PlacaControleMotor.MODO_ATUALIZA
        valor = 0
        giro = 0

        try:
            for id_equip in range(256):
                pacote = [
                    id_equip & 0xFF,
                    modo & 0xFF,
                    valor & 0xFF,
                    (giro >> 8) & 0xFF,
                    giro & 0xFF,
                ]
                pacote.append(PlacaControleMotor._calcular_crc(pacote))
                dados = bytes(pacote)

                ser.reset_input_buffer()
                ser.write(dados)
                ser.flush()

                # Descarta eco (half-duplex one-wire)
                ser.read(PlacaControleMotor.TAMANHO_PACOTE_CMD)
                # Lê resposta
                resposta = ser.read(PlacaControleMotor.TAMANHO_PACOTE_RESP)

                if len(resposta) == PlacaControleMotor.TAMANHO_PACOTE_RESP:
                    crc_calculado = PlacaControleMotor._calcular_crc(resposta[:7])
                    if crc_calculado == resposta[7]:
                        pulsos = struct.unpack('>i', bytes(resposta[3:7]))[0]
                        estado = resposta[2]
                        encontrados.append({'id': resposta[0], 'estado': estado, 'pulsos': pulsos})
                        print(f'Motor encontrado! ID: {resposta[0]}, Estado: {estado}, Pulsos: {pulsos}')

                if PlacaControleMotor.DEBUG:
                    if id_equip % 32 == 0:
                        print(f'Escaneando IDs {id_equip}-{min(id_equip + 31, 255)}...')
        finally:
            ser.close()

        print(f'\nBusca concluída. {len(encontrados)} motor(es) encontrado(s).')
        return encontrados
