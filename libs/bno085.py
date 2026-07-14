import math
import time

from smbus2 import SMBus, i2c_msg

"""Classe para controlar o sensor IMU BNO085 (acelerômetro, giroscópio,
magnetômetro e fusão de sensores/quaternion) nas portas I2C do MariolaZero.
Precisamos passar como parâmetro qual porta I2C (ver portas.py) ele está usando.

Implementa uma versão simplificada do protocolo SHTP/SH-2 (Sensor Hub
Transport Protocol) usado pelo BNO08x: reset do sensor, leitura do Product ID,
habilitação dos relatórios desejados e decodificação dos pacotes de dados.

Exemplo de uso (main.py):
    imu = BNO085(Portas.I2C2)
    while True:
        dados = imu.le_valores()
        print(dados['euler'])       # (yaw, pitch, roll) em graus
        print(dados['aceleracao'])  # (x, y, z) em m/s²
"""


class BNO085:
    MUX_ADDR = 0x70  # Endereço do TCA9548A
    BNO08X_ADDR = 0x4A  # Endereço padrão do sensor (0x4B se ADR estiver em nível alto)
    I2C_BUS = 1  # Verifique qual /dev/i2c-X você está usando

    # ------------------------------------------------------------------
    # Canais do protocolo SHTP
    # ------------------------------------------------------------------
    CHANNEL_COMMAND = 0
    CHANNEL_EXECUTABLE = 1
    CHANNEL_CONTROL = 2
    CHANNEL_INPUT_REPORTS = 3
    CHANNEL_WAKE_INPUT_REPORTS = 4
    CHANNEL_GYRO_ROTATION_VECTOR = 5

    # Relatórios de controle (enviados/recebidos no CHANNEL_CONTROL)
    _PRODUCT_ID_REQUEST = 0xF9
    _PRODUCT_ID_RESPONSE = 0xF8
    _SET_FEATURE_COMMAND = 0xFD
    _GET_FEATURE_RESPONSE = 0xFC
    _BASE_TIMESTAMP = 0xFB
    _COMMAND_RESPONSE = 0xF1

    # IDs dos relatórios de sensores (trafegam no CHANNEL_INPUT_REPORTS)
    REPORT_ACELEROMETRO = 0x01
    REPORT_GIROSCOPIO = 0x02
    REPORT_MAGNETOMETRO = 0x03
    REPORT_ACELERACAO_LINEAR = 0x04
    REPORT_VETOR_ROTACAO = 0x05
    REPORT_GRAVIDADE = 0x06
    REPORT_VETOR_ROTACAO_JOGO = 0x08

    # Fator de escala (Q-point) de cada relatório -> valor real = bruto / 2**Q
    _Q_POINT = {
        REPORT_ACELEROMETRO: 8,
        REPORT_GIROSCOPIO: 9,
        REPORT_MAGNETOMETRO: 4,
        REPORT_ACELERACAO_LINEAR: 8,
        REPORT_VETOR_ROTACAO: 14,
        REPORT_GRAVIDADE: 8,
        REPORT_VETOR_ROTACAO_JOGO: 14,
    }

    # Timeouts padrão (ms)
    TIMEOUT_RESET_MS = 1000
    TIMEOUT_LEITURA_MS = 200

    # Intervalo padrão entre amostras de cada relatório habilitado (µs).
    # 20000 µs = 50 Hz — valor mais seguro dado o custo de troca de canal
    # do mux a cada pacote lido. Se quiser mais frequência, aumente o valor
    # de TIMEOUT_LEITURA_MS/timeout_ms de le_valores() na mesma proporção.
    INTERVALO_PADRAO_US = 20000

    def __init__(self, porta_mux=None, endereco=None):
        if porta_mux is None or porta_mux > 7 or porta_mux < 0:
            raise ValueError('Canal inválido (deve ser 0 a 7)')

        self.porta_mux = porta_mux
        self.endereco = endereco or self.BNO08X_ADDR
        self.bus = SMBus(self.I2C_BUS)

        # Número de sequência (0-255) de cada canal SHTP
        self._seq = [0, 0, 0, 0, 0, 0]

        # Últimos valores lidos de cada sensor
        self.aceleracao = (0.0, 0.0, 0.0)
        self.giroscopio = (0.0, 0.0, 0.0)
        self.magnetometro = (0.0, 0.0, 0.0)
        self.aceleracao_linear = (0.0, 0.0, 0.0)
        self.gravidade = (0.0, 0.0, 0.0)
        self.quaternion = (0.0, 0.0, 0.0, 1.0)  # i, j, k, real

        self.select_channel()
        self._reset_sensor()
        self._verifica_id()
        self._habilita_relatorios_padrao()

    # ------------------------------------------------------------------
    # Seleção de canal do mux
    # ------------------------------------------------------------------

    def select_channel(self):
        self.bus.write_byte(self.MUX_ADDR, 1 << self.porta_mux)
        time.sleep(0.005)

    def close_channel(self):
        self.bus.write_byte(self.MUX_ADDR, 0x00)
        time.sleep(0.005)

    # ------------------------------------------------------------------
    # Recuperação de bus stuck no segmento downstream
    # ------------------------------------------------------------------

    def recover(self):
        """
        Fecha o canal do mux e reabre — libera o segmento downstream
        sem precisar de pino de reset. Após recuperação reinicializa o sensor.
        """
        print(f'[BNO085] Recuperando sensor no canal {self.porta_mux}...')
        try:
            self.close_channel()
            time.sleep(0.1)
            self.select_channel()
            time.sleep(0.5)
            self._reset_sensor()
            self._verifica_id()
            self._habilita_relatorios_padrao()
            print(f'[BNO085] Canal {self.porta_mux} recuperado com sucesso.')
        except OSError as e:
            raise OSError(f'[BNO085] Falha na recuperação do canal {self.porta_mux}: {e}')

    # ------------------------------------------------------------------
    # Envio e recebimento de pacotes SHTP
    # ------------------------------------------------------------------

    def _envia_pacote(self, canal, dados):
        """
        Monta o cabeçalho SHTP (tamanho + canal + sequência) e envia.
        Não seleciona o canal do mux — quem chama é responsável por isso,
        já que este método costuma ser usado várias vezes em sequência.
        """
        tamanho_total = len(dados) + 4
        cabecalho = [
            tamanho_total & 0xFF,
            (tamanho_total >> 8) & 0xFF,
            canal,
            self._seq[canal],
        ]
        self._seq[canal] = (self._seq[canal] + 1) & 0xFF

        pacote = cabecalho + list(dados)
        msg = i2c_msg.write(self.endereco, pacote)
        self.bus.i2c_rdwr(msg)

    def _le_pacote(self, timeout_ms=None):
        """
        Lê um pacote SHTP completo (cabeçalho + payload), respeitando um
        timeout — se nada estiver disponível o sensor devolve tamanho 0.
        Retorna (canal, payload) ou (None, None) se der timeout.

        Não seleciona o canal do mux (custaria 5 ms por pacote) — quem
        chama (método de nível superior) já deve ter selecionado antes.
        """
        timeout_ms = timeout_ms or self.TIMEOUT_LEITURA_MS
        deadline = time.monotonic() + timeout_ms / 1000

        while True:
            try:
                leitura_cabecalho = i2c_msg.read(self.endereco, 4)
                self.bus.i2c_rdwr(leitura_cabecalho)
                cabecalho = list(leitura_cabecalho)
                tamanho = (cabecalho[0] | (cabecalho[1] << 8)) & 0x7FFF
                canal = cabecalho[2]
            except OSError:
                tamanho = 0
                canal = None

            if tamanho == 0 or tamanho == 0x7FFF:
                if time.monotonic() > deadline:
                    return None, None
                time.sleep(0.001)
                continue

            leitura_pacote = i2c_msg.read(self.endereco, tamanho)
            self.bus.i2c_rdwr(leitura_pacote)
            payload = list(leitura_pacote)[4:]
            return canal, payload

    # ------------------------------------------------------------------
    # Inicialização
    # ------------------------------------------------------------------

    def _reset_sensor(self):
        """Envia o comando de reset pelo canal executável e descarta o boot."""
        self.select_channel()
        self._envia_pacote(self.CHANNEL_EXECUTABLE, [0x01])
        time.sleep(0.5)

        # Descarta os pacotes de inicialização (anúncio, resposta de reset etc.)
        deadline = time.monotonic() + self.TIMEOUT_RESET_MS / 1000
        while time.monotonic() < deadline:
            canal, payload = self._le_pacote(timeout_ms=50)
            if canal is None:
                break

    def _verifica_id(self):
        """Solicita e confere o Product ID do sensor (relatório 0xF8)."""
        self.select_channel()
        self._envia_pacote(self.CHANNEL_CONTROL, [self._PRODUCT_ID_REQUEST, 0x00])

        deadline = time.monotonic() + self.TIMEOUT_RESET_MS / 1000
        while time.monotonic() < deadline:
            canal, payload = self._le_pacote(timeout_ms=100)
            if payload and payload[0] == self._PRODUCT_ID_RESPONSE:
                return payload
        raise OSError(f'[BNO085] Sensor não respondeu no canal {self.porta_mux}')

    def _habilita_relatorios_padrao(self):
        """Habilita vetor de rotação, acelerômetro, giroscópio e magnetômetro a 100 Hz."""
        for id_relatorio in (
            self.REPORT_VETOR_ROTACAO,
            self.REPORT_ACELEROMETRO,
            self.REPORT_GIROSCOPIO,
            self.REPORT_MAGNETOMETRO,
        ):
            self.habilita_relatorio(id_relatorio, intervalo_us=self.INTERVALO_PADRAO_US)

    def habilita_relatorio(self, id_relatorio, intervalo_us=None):
        """
        Habilita um relatório de sensor (ex.: REPORT_ACELEROMETRO) informando
        o intervalo entre leituras em microssegundos. Evite valores muito
        baixos (alta frequência) — a troca de canal do mux antes de cada
        pacote lido custa alguns milissegundos, então gerar dados mais rápido
        do que conseguimos ler só faz o buffer do sensor acumular atraso.
        """
        intervalo_us = intervalo_us or self.INTERVALO_PADRAO_US
        self.select_channel()
        dados = [
            self._SET_FEATURE_COMMAND,
            id_relatorio,
            0x00,  # flags
            0x00,  # sensitivity (LSB)
            0x00,  # sensitivity (MSB)
            intervalo_us & 0xFF,
            (intervalo_us >> 8) & 0xFF,
            (intervalo_us >> 16) & 0xFF,
            (intervalo_us >> 24) & 0xFF,
            0x00, 0x00, 0x00, 0x00,  # batch interval
            0x00, 0x00, 0x00, 0x00,  # sensitivity adicional
        ]
        self._envia_pacote(self.CHANNEL_CONTROL, dados)

    # ------------------------------------------------------------------
    # Decodificação dos relatórios de sensores
    # ------------------------------------------------------------------

    @staticmethod
    def _para_inteiro_com_sinal(low, high):
        valor = (high << 8) | low
        if valor >= 0x8000:
            valor -= 0x10000
        return valor

    def _decodifica_vetor(self, id_relatorio, payload):
        q = self._Q_POINT[id_relatorio]
        x = self._para_inteiro_com_sinal(payload[4], payload[5]) / (1 << q)
        y = self._para_inteiro_com_sinal(payload[6], payload[7]) / (1 << q)
        z = self._para_inteiro_com_sinal(payload[8], payload[9]) / (1 << q)
        return (x, y, z)

    def _decodifica_quaternion(self, payload):
        q = self._Q_POINT[self.REPORT_VETOR_ROTACAO]
        i = self._para_inteiro_com_sinal(payload[4], payload[5]) / (1 << q)
        j = self._para_inteiro_com_sinal(payload[6], payload[7]) / (1 << q)
        k = self._para_inteiro_com_sinal(payload[8], payload[9]) / (1 << q)
        real = self._para_inteiro_com_sinal(payload[10], payload[11]) / (1 << q)
        return (i, j, k, real)

    def _processa_relatorio_sensor(self, payload):
        """Decodifica um pacote do CHANNEL_INPUT_REPORTS e atualiza o estado interno."""
        indice = 0
        while indice < len(payload):
            id_relatorio = payload[indice]

            if id_relatorio == self._BASE_TIMESTAMP:
                indice += 5  # id (1) + timestamp (4) — apenas pula
                continue

            if id_relatorio == self.REPORT_VETOR_ROTACAO:
                self.quaternion = self._decodifica_quaternion(payload[indice:indice + 14])
                indice += 14
            elif id_relatorio == self.REPORT_ACELEROMETRO:
                self.aceleracao = self._decodifica_vetor(id_relatorio, payload[indice:indice + 10])
                indice += 10
            elif id_relatorio == self.REPORT_GIROSCOPIO:
                self.giroscopio = self._decodifica_vetor(id_relatorio, payload[indice:indice + 10])
                indice += 10
            elif id_relatorio == self.REPORT_MAGNETOMETRO:
                self.magnetometro = self._decodifica_vetor(id_relatorio, payload[indice:indice + 10])
                indice += 10
            elif id_relatorio == self.REPORT_ACELERACAO_LINEAR:
                self.aceleracao_linear = self._decodifica_vetor(id_relatorio, payload[indice:indice + 10])
                indice += 10
            elif id_relatorio == self.REPORT_GRAVIDADE:
                self.gravidade = self._decodifica_vetor(id_relatorio, payload[indice:indice + 10])
                indice += 10
            else:
                # Relatório desconhecido — aborta o processamento deste pacote
                break

    def le_valores(self, timeout_ms=50, max_pacotes=20):
        """
        Processa os pacotes pendentes do sensor e retorna um dicionário com
        os valores mais recentes: aceleração, giroscópio, magnetômetro,
        aceleração linear, gravidade, quaternion e ângulos de Euler.

        `timeout_ms` limita o tempo TOTAL gasto nesta chamada (não apenas a
        espera por um pacote individual) e `max_pacotes` limita quantos
        pacotes são processados por chamada. Isso evita que a função fique
        presa caso o sensor esteja gerando dados mais rápido do que
        conseguimos drenar (ex.: vários relatórios habilitados em alta
        frequência) — nesse caso simplesmente retornamos os valores mais
        recentes já decodificados e o restante fica pendente para a
        próxima chamada.
        """
        self.select_channel()
        deadline = time.monotonic() + timeout_ms / 1000

        for _ in range(max_pacotes):
            if time.monotonic() > deadline:
                break
            canal, payload = self._le_pacote(timeout_ms=5)
            if canal is None:
                break
            if canal in (self.CHANNEL_INPUT_REPORTS, self.CHANNEL_WAKE_INPUT_REPORTS):
                self._processa_relatorio_sensor(payload)

        return {
            'aceleracao': self.aceleracao,
            'giroscopio': self.giroscopio,
            'magnetometro': self.magnetometro,
            'aceleracao_linear': self.aceleracao_linear,
            'gravidade': self.gravidade,
            'quaternion': self.quaternion,
            'euler': self.euler(),
        }

    def euler(self):
        """Converte o quaternion atual em ângulos de Euler em graus: (yaw, pitch, roll)."""
        i, j, k, real = self.quaternion

        sinr_cosp = 2 * (real * i + j * k)
        cosr_cosp = 1 - 2 * (i * i + j * j)
        roll = math.atan2(sinr_cosp, cosr_cosp)

        sinp = max(-1.0, min(1.0, 2 * (real * j - k * i)))
        pitch = math.asin(sinp)

        siny_cosp = 2 * (real * k + i * j)
        cosy_cosp = 1 - 2 * (j * j + k * k)
        yaw = math.atan2(siny_cosp, cosy_cosp)

        return (math.degrees(yaw), math.degrees(pitch), math.degrees(roll))
