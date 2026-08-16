import threading
import time

from portas import Portas
from pinosDigitais import PinosDigitais


class Lidar:
    """Biblioteca de comunicação com o sensor LIDAR (protocolo Neato XV-11) via serial em Linux.

    Cada pacote de 22 bytes recebido do sensor traz 4 leituras de distância
    referentes a ângulos consecutivos (0-359°), além da velocidade de rotação do motor.
    """

    HEAD_BYTE = 0xFA
    PACKET_SIZE = 22
    MIN_DISTANCE = 100    # mm
    MAX_DISTANCE = 3000   # mm

    def __init__(self, porta_serial, pino_liga=None):
        """
        Args:
            porta_serial: Constante da classe Portas (ex.: Portas.SERIAL1)
            pino_liga: Constante de pino da classe PinosDigitais (ex.: PinosDigitais.P7),
                usada para ligar/desligar o motor do lidar através de um relé.
                Opcional — se None, o lidar não é controlado por nenhum pino.
        """
        self._distancias = [0] * 360
        self._velocidade = 0
        self._velocidade_suavizada = 0

        portas = Portas()
        self.ser = portas.abre_porta_serial(porta_serial, 115200)
        if self.ser is None:
            raise Exception("Erro ao abrir a porta serial do sensor LIDAR")

        self.pino_liga = pino_liga
        self._pinos = None
        if self.pino_liga is not None:
            self._pinos = PinosDigitais()
            self._pinos.configura_pino(self.pino_liga, self._pinos.SAIDA)
            self.liga()

        self._wait_packet = True
        self._packet_index = 0
        self._packet = [0] * self.PACKET_SIZE

        self._thread_ativa = False
        self._thread = None
        self._ultimo_tempo = 0
        self._iniciar_thread()

    def __del__(self):
        self.fechar()

    # ── Controle de energia (pino opcional) ──────────────────────────────

    def liga(self):
        """Liga o motor do lidar através do pino digital configurado (se houver)."""
        if self._pinos is not None:
            self._pinos.escreve_pino(self.pino_liga, self._pinos.BAIXO)

    def desliga(self):
        """Desliga o motor do lidar através do pino digital configurado (se houver)."""
        if self._pinos is not None:
            self._pinos.escreve_pino(self.pino_liga, self._pinos.ALTO)

    # ── Thread de leitura ─────────────────────────────────────────────────

    def _atualiza_periodicamente(self):
        while self._thread_ativa:
            if self.ser.in_waiting > 0:
                self._processa_byte(self.ser.read(1)[0])
            else:
                time.sleep(0.001)

    def _iniciar_thread(self):
        if not self._thread_ativa:
            self._thread_ativa = True
            self._thread = threading.Thread(target=self._atualiza_periodicamente)
            self._thread.daemon = True
            self._thread.start()

    def _parar_thread(self):
        self._thread_ativa = False
        if self._thread is not None:
            self._thread.join()

    # ── Decodificação de pacotes ──────────────────────────────────────────

    def _processa_byte(self, recebido):
        if self._wait_packet:
            if recebido == self.HEAD_BYTE:
                self._packet_index = 0
                self._wait_packet = False
                self._packet[self._packet_index] = recebido
                self._packet_index += 1
        else:
            self._packet[self._packet_index] = recebido
            self._packet_index += 1
            if self._packet_index >= self.PACKET_SIZE:
                self._wait_packet = True
                self._decodifica_pacote(self._packet)

    @staticmethod
    def _checksum_valido(packet, tamanho):
        """Valida o checksum do pacote (portado do firmware original)."""
        chk32 = 0
        checksum_esperado = packet[tamanho] + (packet[tamanho + 1] << 8)
        for i in range(tamanho // 2):
            palavra = ((packet[i * 2 + 1] << 8) + packet[i * 2]) & 0xFFFF
            chk32 = ((chk32 << 1) + palavra) & 0xFFFFFFFF
        checksum_calculado = ((chk32 & 0x7FFF) + (chk32 >> 15)) & 0x7FFF
        return checksum_calculado == checksum_esperado

    def _decodifica_pacote(self, packet):
        angulo_base = (packet[1] - 0xA0) * 4
        if angulo_base < 0 or angulo_base >= 360:
            return
        if not self._checksum_valido(packet, self.PACKET_SIZE - 2):
            return

        velocidade = (packet[3] << 8) | packet[2]
        # suaviza a leitura de velocidade (às vezes há picos por ruído na serial)
        if abs(velocidade / 64 - self._velocidade_suavizada) > 100:
            self._velocidade_suavizada = self._velocidade_suavizada * 0.95 + (velocidade / 64) * 0.05
        else:
            self._velocidade_suavizada = velocidade / 64
        self._velocidade = self._velocidade_suavizada

        for offset_leitura, offset_pacote in enumerate((4, 8, 12, 16)):
            angulo = (angulo_base + offset_leitura) % 360
            distancia = ((packet[offset_pacote + 1] & 0x3F) << 8) | packet[offset_pacote]
            self._distancias[angulo] = distancia if self.MIN_DISTANCE <= distancia <= self.MAX_DISTANCE else 0

        self._ultimo_tempo = time.time()

    # ── Propriedades gerais ───────────────────────────────────────────────

    @property
    def conectado(self):
        """True se o sensor enviou dados válidos nos últimos 2 segundos."""
        return self._ultimo_tempo > 0 and (time.time() - self._ultimo_tempo < 2)

    @property
    def velocidade(self):
        """Velocidade de rotação do motor do lidar, em RPM."""
        return round(self._velocidade)

    # ── Leitura de pontos ─────────────────────────────────────────────────

    def pontos(self, angulo_inicio=0, angulo_fim=359):
        """Retorna os pontos coletados pelo lidar dentro de um intervalo de ângulos.

        Args:
            angulo_inicio: ângulo inicial do intervalo desejado (0-359). Padrão 0.
            angulo_fim: ângulo final do intervalo desejado (0-359). Padrão 359.
                Se angulo_inicio > angulo_fim, o intervalo é entendido como
                cruzando o 0° (ex.: 350 a 10 retorna os ângulos 350..359 e 0..10).

        Returns:
            Lista de tuplas (angulo, distancia_mm), apenas com leituras válidas.
        """
        angulo_inicio = max(0, min(359, angulo_inicio))
        angulo_fim = max(0, min(359, angulo_fim))

        if angulo_inicio <= angulo_fim:
            intervalo = range(angulo_inicio, angulo_fim + 1)
        else:
            intervalo = list(range(angulo_inicio, 360)) + list(range(0, angulo_fim + 1))

        return [(angulo, self._distancias[angulo]) for angulo in intervalo if self._distancias[angulo] > 0]

    # ── Controle ──────────────────────────────────────────────────────────

    def fechar(self):
        """Para a thread, desliga o motor (se houver pino) e fecha a porta serial."""
        self._parar_thread()
        self.desliga()
        if self.ser is not None:
            self.ser.close()
            self.ser = None
