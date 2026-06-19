from pybricks.iodevices import UARTDevice
import threading
import time


class SensorLinhaPro:
    """Biblioteca de comunicação com o sensor de linha Pro1616 para EV3.

    Layout dos 16 bytes recebidos do sensor:
      [0-3]:   Sensores infravermelhos de reflexão (0=branco, 255=preto)
      [4-7]:   Sensor de cor TCS1       (R, G, B, C)  — valores 0-127
      [8-11]:  Sensor de cor TCS meio   (R, G, B, C)  — valores 0-127
      [12-15]: Sensor de cor TCS2       (R, G, B, C)  — valores 0-127

    Comunicação binária: envia 1 byte de comando, recebe 16 bytes de dados.
    """

    # Modos do sensor (comandos enviados ao Arduino)
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

    _QTD_VALORES = 16

    # Mapeamento sensor (1,2,3) → índice base na lista de valores
    _OFFSET_COR = {1: 4, 2: 8, 3: 12}

    def __init__(self, porta, baudrate=115200, intervalo=0.03):
        """
        Args:
            porta: Porta do EV3 (Port.S1, Port.S2, etc.)
            baudrate: Velocidade serial (padrão 115200, igual ao sensor)
            intervalo: Intervalo entre leituras em segundos (~33 Hz padrão)
        """
        self.serial = UARTDevice(porta, baudrate, 100)
        self.lista = [0] * self._QTD_VALORES
        self._conectado = False
        self._executando = True
        self._pausado = False
        self._intervalo = intervalo
        self._ultimo_tempo = 0

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
                self.serial.write(bytes([self.MODO_CALIBRADO]))
                buf = b""
                inicio = time.time()
                while len(buf) < self._QTD_VALORES and time.time() - inicio < 0.15:
                    trecho = self._ler_disponivel()
                    if trecho:
                        buf += trecho
                    else:
                        time.sleep(0.005)

                if len(buf) >= self._QTD_VALORES:
                    for i in range(self._QTD_VALORES):
                        self.lista[i] = buf[i]
                    self._conectado = True
                    self._ultimo_tempo = time.time()

            except Exception:
                self._conectado = False

            time.sleep(self._intervalo)

    # ── Propriedades gerais ─────────────────────────────────────────────

    @property
    def conectado(self):
        """True se o sensor respondeu nos últimos 2 segundos."""
        return self._conectado and (time.time() - self._ultimo_tempo < 2)

    @property
    def valores(self):
        """Retorna cópia dos 16 valores brutos do sensor."""
        return list(self.lista)

    # ── Reflexão IR (índices 0-3) ───────────────────────────────────────

    def reflexao(self, sensor):
        """Valor de reflexão do sensor IR (0-3)"""
        if 0 <= sensor <= 3:
            return self.lista[sensor]
        return 0

    def le_reflexao(self):
        """Retorna lista com os 4 valores de reflexão IR."""
        return self.lista[0:4]

    # ── Cor RGBC (sensor: 1=TCS1, 2=TCS meio, 3=TCS2) ──────────────────

    def le_rgbc(self, sensor):
        """Retorna [R, G, B, C] do sensor de cor (1=TCS1, 2=TCS meio, 3=TCS2)."""
        base = self._OFFSET_COR.get(sensor)
        if base is not None:
            return self.lista[base:base + 4]
        return None

    def le_rgb(self, sensor):
        """Retorna [R, G, B] do sensor de cor (1=TCS1, 2=TCS meio, 3=TCS2)."""
        base = self._OFFSET_COR.get(sensor)
        if base is not None:
            return self.lista[base:base + 3]
        return None

    def le_hsv(self, sensor):
        """Retorna [H, S, V] do sensor de cor (1=TCS1, 2=TCS meio, 3=TCS2).
        H: 0-360, S: 0-100, V: 0-100."""
        rgb = self.le_rgb(sensor)
        if rgb is not None:
            return list(self.rgb_para_hsv(rgb[0], rgb[1], rgb[2]))
        return None

    def le_hsv120(self, sensor, valor_maximo=127):
        """Retorna [H, S, V] do sensor de cor (1=TCS1, 2=TCS meio, 3=TCS2).
        H: 0-120, S: 0-120, V: 0-120"""
        rgb = self.le_rgb(sensor)
        if rgb is not None:
            return list(self.rgb_para_hsv120(rgb[0], rgb[1], rgb[2], valor_maximo))
        return None

    def detecta_cor(self, sensor):
        """Detecta cor básica no sensor (1=TCS1, 2=TCS meio, 3=TCS2).
        Retorna constante COR_*."""
        rgbc = self.le_rgbc(sensor)
        if rgbc is None:
            return self.COR_NADA
        return self.detectar_cor(rgbc[0], rgbc[1], rgbc[2], rgbc[3])

    def nome_cor(self, sensor):
        """Retorna nome da cor detectada pelo sensor (1, 2 ou 3)."""
        return self.NOMES_CORES.get(self.detecta_cor(sensor), "desconhecida")

    # ── Calibração ──────────────────────────────────────────────────────

    def calibra_branco(self, timeout_ms=10000):
        """Solicita calibração do branco. Retorna True se confirmada."""
        return self._executar_calibracao(self.MODO_CALIBRA_BRANCO, timeout_ms)

    def calibra_preto(self, timeout_ms=5000):
        """Solicita calibração do preto. Retorna True se confirmada."""
        return self._executar_calibracao(self.MODO_CALIBRA_PRETO, timeout_ms)

    def _executar_calibracao(self, modo, timeout_ms):
        self._pausado = True
        time.sleep(0.15)
        try:
            self._ler_disponivel()
        except Exception:
            pass
        self.serial.write(bytes([modo]))
        resultado = False
        inicio = time.time()
        while (time.time() - inicio) * 1000 < timeout_ms:
            try:
                dados = self._ler_disponivel()
                if dados and 1 in dados:
                    resultado = True
                    break
            except Exception:
                pass
            time.sleep(0.2)
        self._pausado = False
        return resultado

    # ── Conversão RGB → HSV ─────────────────────────────────────────────

    @staticmethod
    def rgb_para_hsv(r, g, b):
        """Converte RGB (0-255) para HSV.
        Retorna (H: 0-360, S: 0-100, V: 0-100)."""
        #preciso colocar o valor para 0-255 e garantir q o maximo é 255 para evitar erros de leitura
        r = r*2
        g = g*2
        b = b*2
        if r > 255:
            r = 255
        if g > 255:
            g = 255
        if b > 255:
            b = 255
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

    @staticmethod
    def rgb_para_hsv120(r, g, b, valor_maximo=127):
        """Converte RGB para HSV na escala 0-120 (estilo Paint clássico do Windows).
        Retorna (H: 0-120, S: 0-120, V: 0-120).
        valor_maximo: valor de referência para normalização (padrão 127)."""
        if r > valor_maximo:
            r = valor_maximo
        if g > valor_maximo:
            g = valor_maximo
        if b > valor_maximo:
            b = valor_maximo
        r_n = min(r / valor_maximo, 1.0)
        g_n = min(g / valor_maximo, 1.0)
        b_n = min(b / valor_maximo, 1.0)

        cmax = max(r_n, g_n, b_n)
        cmin = min(r_n, g_n, b_n)
        delta = cmax - cmin

        if delta == 0:
            h = 0
        elif cmax == r_n:
            h = int(60 * ((g_n - b_n) / delta + 6)) % 360
        elif cmax == g_n:
            h = int(60 * ((b_n - r_n) / delta + 2))
        else:
            h = int(60 * ((r_n - g_n) / delta + 4))

        # Mapeia Hue de [0, 360] para [0, 120]
        h = h * 120 // 360

        s = int((delta / cmax) * 120) if cmax != 0 else 0
        v = int(cmax * 120)

        return (h, s, v)

    # ── Detecção de cor básica (portado de TCS34725::detectaCorBasica) ──

    @staticmethod
    def detectar_cor(r, g, b, c):
        """Detecta cor básica a partir de RGBC (0-255). Retorna constante COR_*."""
        #preciso colocar o valor para 0-255 e garantir q o maximo é 255 para evitar erros de leitura
        r = r*2
        g = g*2
        b = b*2
        if r > 255:
            r = 255
        if g > 255:
            g = 255
        if b > 255:
            b = 255
        if c <= 3 and r < 5 and g < 5 and b < 5:
            return SensorLinhaPro.COR_NADA
        if 3 < c < 25:
            return SensorLinhaPro.COR_PRETO
        if c > 230 and abs(r - g) < 20 and abs(r - b) < 20 and abs(g - b) < 20:
            return SensorLinhaPro.COR_BRANCO

        max_val = max(r, g, b)
        if max_val == 0:
            return SensorLinhaPro.COR_NADA

        rn = r / max_val
        gn = g / max_val
        bn = b / max_val

        if r == max_val:
            if gn > 0.6 and bn < 0.5:
                return SensorLinhaPro.COR_AMARELO
            return SensorLinhaPro.COR_VERMELHO
        if g == max_val:
            return SensorLinhaPro.COR_VERDE
        if b == max_val:
            return SensorLinhaPro.COR_AZUL

        if c > 150:
            return SensorLinhaPro.COR_BRANCO
        return SensorLinhaPro.COR_DESCONHECIDA

    # ── Controle ────────────────────────────────────────────────────────

    def fechar(self):
        """Para a thread de leitura."""
        self._executando = False