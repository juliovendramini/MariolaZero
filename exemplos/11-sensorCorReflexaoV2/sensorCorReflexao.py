import threading
import time

from portas import Portas


class CorReflexao:
    """Biblioteca de comunicação com o sensor de linha Pro1616 (ATtiny1616) via serial em Linux.

    Layout dos 16 bytes recebidos do sensor:
      [0-3]:   Sensores infravermelhos de reflexão (0=branco, 255=preto)
      [4-7]:   Sensor de cor TCS1       (R, G, B, C)  — valores 0-255
      [8-11]:  Sensor de cor TCS meio   (R, G, B, C)  — valores 0-255
      [12-15]: Sensor de cor TCS2       (R, G, B, C)  — valores 0-255
    """

    QUANTIDADE_BYTES = 16

    # Comandos enviados ao ATtiny1616
    MODO_CALIBRADO = 0x61
    MODO_CALIBRA_BRANCO = 0x62
    MODO_CALIBRA_PRETO = 0x63

    # Cores básicas (portado de TCS34725::CorBasica)
    COR_NADA = -1
    COR_PRETO = 0
    COR_BRANCO = 1
    COR_VERMELHO = 2
    COR_VERDE = 3
    COR_AZUL = 4
    COR_AMARELO = 5
    COR_DESCONHECIDA = 6

    NOMES_CORES = {
        -1: "nada",
        0: "preto",
        1: "branco",
        2: "vermelho",
        3: "verde",
        4: "azul",
        5: "amarelo",
        6: "desconhecida",
    }

    def __init__(self, porta_serial):
        """
        Args:
            porta_serial: Constante da classe Portas (ex.: Portas.SERIAL1)
        """
        self.lista = [0] * self.QUANTIDADE_BYTES
        portas = Portas()
        self.ser = portas.abre_porta_serial(porta_serial, 115200)
        if self.ser is None:
            raise Exception("Erro ao abrir a porta serial do sensor de cor e reflexão")
        self._thread_ativa = False
        self._thread = None
        self._ultimo_tempo = 0
        self._iniciar_thread()

    def __del__(self):
        self._parar_thread()
        if self.ser is not None:
            self.ser.close()

    # ── Thread de leitura ───────────────────────────────────────────────

    def _atualiza_periodicamente(self):
        while self._thread_ativa:
            self.atualiza()
            time.sleep(0.01)

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

    # ── Comunicação serial ──────────────────────────────────────────────

    def atualiza(self):
        """Solicita e recebe os 16 bytes do sensor."""
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes([self.MODO_CALIBRADO]))
        dados = self.ser.read(self.QUANTIDADE_BYTES)
        if len(dados) == self.QUANTIDADE_BYTES:
            self.lista = list(dados)
            self._ultimo_tempo = time.time()
            return True
        return False

    # ── Propriedades gerais ─────────────────────────────────────────────

    @property
    def conectado(self):
        """True se o sensor respondeu nos últimos 2 segundos."""
        return self._ultimo_tempo > 0 and (time.time() - self._ultimo_tempo < 2)

    @property
    def valores(self):
        """Retorna cópia dos 16 valores brutos do sensor."""
        return list(self.lista)

    # ── Reflexão IR (índices 0-3) ───────────────────────────────────────

    def le_reflexao(self):
        """Retorna lista com os 4 valores de reflexão IR (0=branco, 255=preto)."""
        return self.lista[0:4]

    def reflexao(self, sensor):
        """Valor de reflexão individual (sensor 0-3)."""
        if 0 <= sensor <= 3:
            return self.lista[sensor]
        return 0

    # ── Cor RGBC ────────────────────────────────────────────────────────

    def le_rgbc(self, sensor):
        """Retorna [R, G, B, C] do sensor de cor (1=TCS1, 2=TCS meio, 3=TCS2)."""
        if sensor == 1:
            return self.lista[4:8]
        elif sensor == 2:
            return self.lista[8:12]
        elif sensor == 3:
            return self.lista[12:16]
        return None

    def le_rgb(self, sensor):
        """Retorna [R, G, B] do sensor de cor (1=TCS1, 2=TCS meio, 3=TCS2)."""
        rgbc = self.le_rgbc(sensor)
        if rgbc is not None:
            return rgbc[0:3]
        return None

    # ── Conversão HSV (calculada no Python) ─────────────────────────────

    def le_hsv(self, sensor):
        """Retorna [H, S, V] do sensor de cor (1=TCS1, 2=TCS meio, 3=TCS2).
        H: 0-360, S: 0-100, V: 0-100."""
        rgb = self.le_rgb(sensor)
        if rgb is not None:
            return list(self.rgb_para_hsv(rgb[0], rgb[1], rgb[2]))
        return None

    @staticmethod
    def rgb_para_hsv(r, g, b):
        """Converte RGB (0-255) para HSV. Retorna (H: 0-360, S: 0-100, V: 0-100)."""
        r_n = r / 255.0
        g_n = g / 255.0
        b_n = b / 255.0

        cmax = max(r_n, g_n, b_n)
        cmin = min(r_n, g_n, b_n)
        delta = cmax - cmin

        if delta == 0:
            h = 0.0
        elif cmax == r_n:
            h = 60.0 * (((g_n - b_n) / delta) % 6)
        elif cmax == g_n:
            h = 60.0 * (((b_n - r_n) / delta) + 2)
        else:
            h = 60.0 * (((r_n - g_n) / delta) + 4)
        if h < 0:
            h += 360.0

        s = 0.0 if cmax == 0 else (delta / cmax) * 100.0
        v = cmax * 100.0

        return (round(h), round(s), round(v))

    # ── Detecção de cor (portado de TCS34725::detectaCorBasica) ─────────

    def detecta_cor(self, sensor):
        """Detecta cor básica no sensor (1=TCS1, 2=TCS meio, 3=TCS2).
        Retorna constante COR_*."""
        rgbc = self.le_rgbc(sensor)
        if rgbc is None:
            return self.COR_NADA
        return self.detectar_cor(rgbc[0], rgbc[1], rgbc[2], rgbc[3])

    def nome_cor(self, sensor):
        """Retorna o nome da cor detectada pelo sensor (1, 2 ou 3)."""
        return self.NOMES_CORES.get(self.detecta_cor(sensor), "desconhecida")

    @staticmethod
    def detectar_cor(r, g, b, c):
        """Detecta cor básica a partir de RGBC (0-255). Retorna constante COR_*."""
        if c <= 3 and r < 5 and g < 5 and b < 5:
            return CorReflexao.COR_NADA
        if 3 < c < 25:
            return CorReflexao.COR_PRETO
        if c > 230 and abs(r - g) < 20 and abs(r - b) < 20 and abs(g - b) < 20:
            return CorReflexao.COR_BRANCO

        max_val = max(r, g, b)
        if max_val == 0:
            return CorReflexao.COR_NADA

        rn = r / max_val
        gn = g / max_val
        bn = b / max_val

        if r == max_val:
            if gn > 0.6 and bn < 0.5:
                return CorReflexao.COR_AMARELO
            return CorReflexao.COR_VERMELHO
        if g == max_val:
            return CorReflexao.COR_VERDE
        if b == max_val:
            return CorReflexao.COR_AZUL

        if c > 150:
            return CorReflexao.COR_BRANCO
        return CorReflexao.COR_DESCONHECIDA

    # ── Calibração ──────────────────────────────────────────────────────

    def calibra_branco(self, timeout_ms=10000):
        """Solicita calibração do branco. Retorna True se confirmada."""
        return self._executar_calibracao(self.MODO_CALIBRA_BRANCO, timeout_ms)

    def calibra_preto(self, timeout_ms=5000):
        """Solicita calibração do preto. Retorna True se confirmada."""
        return self._executar_calibracao(self.MODO_CALIBRA_PRETO, timeout_ms)

    def _executar_calibracao(self, modo, timeout_ms):
        self._parar_thread()
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes([modo]))
        inicio = time.time()
        resultado = False
        while (time.time() - inicio) * 1000 < timeout_ms:
            dados = self.ser.read(1)
            if dados and dados[0] == 1:
                resultado = True
                break
            time.sleep(0.1)
        if resultado:
            print("Calibração concluída")
        else:
            print("Tempo de calibração excedido")
        self._iniciar_thread()
        return resultado

    # ── Controle ────────────────────────────────────────────────────────

    def fechar(self):
        """Para a thread e fecha a porta serial."""
        self._parar_thread()
        if self.ser is not None:
            self.ser.close()
            self.ser = None
