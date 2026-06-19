import struct
import threading
import time

from pybricks.iodevices import UARTDevice


class Giroscopio:
    """Biblioteca do giroscópio compatível com PyBricks 2.0.0 (LEGO EV3).

    A leitura é feita automaticamente em background por uma thread interna.
    Use os métodos le_angulo_*() a qualquer momento para obter os valores atuais.

    Exemplo de uso:
        from pybricks.parameters import Port
        from giroscopio_ev3 import Giroscopio

        gyro = Giroscopio(Port.S1)

        while True:
            angulo_z = gyro.le_angulo_z()
    """

    GYRO = 0
    GYRO2 = 1
    GYRO_CAL = 2

    def __init__(self, porta, baudrate=115200, intervalo=0.005):
        """
        Args:
            porta:     Porta do EV3 (Port.S1, Port.S2, Port.S3 ou Port.S4)
            baudrate:  Velocidade serial (padrão 115200)
            intervalo: Intervalo entre leituras em segundos (padrão 5ms)
        """
        self.lista = [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00]
        self.modo = self.GYRO
        self.quantidade_bytes_modo = 8

        self.serial = UARTDevice(porta, baudrate, 100)

        self._executando = True
        self._pausado = False
        self._conectado = False
        self._ultimo_tempo = 0
        self._intervalo = intervalo

        self._thread = threading.Thread(target=self._loop_leitura)
        self._thread.daemon = True
        self._thread.start()

    # ── Leitura serial interna ──────────────────────────────────────────

    def _ler_disponivel(self):
        """Lê todos os bytes disponíveis no buffer serial."""
        n = self.serial.waiting()
        if n > 0:
            return self.serial.read(n)
        return b""

    def _loop_leitura(self):
        while self._executando:
            if self._pausado:
                time.sleep(0.05)
                continue
            try:
                self._ler_disponivel()
                self.serial.write(bytes([self.modo]))

                buf = b""
                inicio = time.time()
                while len(buf) < self.quantidade_bytes_modo and time.time() - inicio < 0.15:
                    trecho = self._ler_disponivel()
                    if trecho:
                        buf += trecho
                    else:
                        time.sleep(0.005)

                if len(buf) >= self.quantidade_bytes_modo:
                    for i in range(self.quantidade_bytes_modo):
                        self.lista[i] = buf[i]
                    self._conectado = True
                    self._ultimo_tempo = time.time()

            except Exception:
                self._conectado = False

            time.sleep(self._intervalo)

    # ── Controle de modo ────────────────────────────────────────────────

    def set_modo(self, modo):
        """Define o modo de operação: GYRO (0), GYRO2 (1) ou GYRO_CAL (2)."""
        if modo < 0 or modo > 2:
            raise ValueError('Modo inválido. Deve ser 0, 1 ou 2.')
        self.modo = modo
        if modo == self.GYRO or modo == self.GYRO2:
            self.quantidade_bytes_modo = 8
        elif modo == self.GYRO_CAL:
            self.quantidade_bytes_modo = 1

    # ── Propriedades gerais ─────────────────────────────────────────────

    @property
    def conectado(self):
        """True se o sensor respondeu nos últimos 2 segundos."""
        return self._conectado and (time.time() - self._ultimo_tempo < 2)

    # ── Leitura de ângulos ──────────────────────────────────────────────

    def le_angulo_x(self):
        """Retorna o ângulo no eixo X (em graus)."""
        return struct.unpack('>h', bytes(self.lista[0:2]))[0]

    def le_angulo_y(self):
        """Retorna o ângulo no eixo Y (em graus)."""
        return struct.unpack('>h', bytes(self.lista[2:4]))[0]

    def le_angulo_z(self):
        """Retorna o ângulo no eixo Z (em graus)."""
        return struct.unpack('>h', bytes(self.lista[4:6]))[0]

    # ── Operações ───────────────────────────────────────────────────────

    def reseta_z(self):
        """Reseta o ângulo Z alternando entre os modos GYRO e GYRO2."""
        if self.modo == self.GYRO:
            self.modo = self.GYRO2
        else:
            self.modo = self.GYRO
        time.sleep(0.025)

    def calibra(self, timeout_ms=5000):
        """
        Executa a calibração do giroscópio (mantenha o sensor parado).
        Aguarda até timeout_ms pelo sinal de conclusão.

        :return: True se concluída com sucesso, False se o tempo foi excedido.
        """
        self._pausado = True
        time.sleep(0.15)
        try:
            self._ler_disponivel()
        except Exception:
            pass

        self.set_modo(self.GYRO_CAL)
        self.serial.write(bytes([self.modo]))

        resultado = False
        inicio = time.time()
        while (time.time() - inicio) * 1000 < timeout_ms:
            try:
                dados = self._ler_disponivel()
                if len(dados) == 1:
                    resultado = True
                    break
            except Exception:
                pass
            time.sleep(0.1)

        self.set_modo(self.GYRO)
        self._pausado = False

        if resultado:
            print('Calibração concluída')
        else:
            print('Tempo de calibração excedido')
        return resultado
