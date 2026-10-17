import json
import math
import threading
import time

from portas import Portas


class CorReflexao:
    """Biblioteca do sensor de linha/cor Pro1616 (ATtiny1616) via serial em Linux.

    Layout dos 16 bytes recebidos do sensor (comando 0x61):
      [0-3]:   Reflexão IR dos 4 sensores. Escala do firmware: 0 = preto, ~100 = branco
               calibrado, acima de 100 = mais refletivo que o branco (ex.: piso prateado).
      [4-7]:   Sensor de cor TCS1     (R, G, B, C)
      [8-11]:  Sensor de cor TCS meio (R, G, B, C)
      [12-15]: Sensor de cor TCS2     (R, G, B, C)
      O TCS é calibrado no branco e o firmware envia METADE do valor: branco ~127, o que
      deixa folga até 255 para superfícies refletivas (prata).

    Detecção de cor
    ---------------
    Cada cor é uma referência (média e desvio) de cinco características:
      cromaticidade r/(r+g+b), g/(r+g+b), b/(r+g+b)  -> a cor em si, independe do brilho
      brilho C / 127                                  -> branco = 1, prata > 1, preto ~ 0
      IR / 100                                        -> branco = 1, prata > 1, preto ~ 0
    A leitura vai para a referência mais próxima (distância medida em desvios). Se nenhuma
    estiver perto o bastante, o resultado é COR_DESCONHECIDA.

    As referências padrão são só um ponto de partida. No tempo de calibração, coloque o
    robô sobre cada cor e chame aprende_cor('azul') etc.; salve com salva_cores() e
    carregue com carrega_cores() (ou passe arquivo_cores no construtor).

        sensor = CorReflexao(Portas.SERIAL6, arquivo_cores='cores.json')
        sensor.usa_cores(['branco', 'preto', 'prata', 'azul', 'vermelho'])   # Maze
        sensor.aprende_cor('azul')            # robô parado com os 3 TCS sobre o azul
        sensor.salva_cores('cores.json')
        sensor.cor(2)                         # 'azul'  (TCS do meio)
        sensor.cor_piso()                     # votação dos 3 TCS
        sensor.detecta_cor(2)                 # mesma coisa, como constante COR_*
    """

    QUANTIDADE_BYTES = 16

    # Comandos enviados ao ATtiny1616
    MODO_CALIBRADO = 0x61
    MODO_CALIBRA_BRANCO = 0x62
    MODO_CALIBRA_PRETO = 0x63

    # Cores (constantes mantidas da versão anterior; PRATA é nova)
    COR_NADA = -1
    COR_PRETO = 0
    COR_BRANCO = 1
    COR_VERMELHO = 2
    COR_VERDE = 3
    COR_AZUL = 4
    COR_AMARELO = 5
    COR_DESCONHECIDA = 6
    COR_PRATA = 7

    NOMES_CORES = {
        -1: "nada",
        0: "preto",
        1: "branco",
        2: "vermelho",
        3: "verde",
        4: "azul",
        5: "amarelo",
        6: "desconhecida",
        7: "prata",
    }
    CODIGO_COR = {v: k for k, v in NOMES_CORES.items()}

    # Referências padrão na escala do firmware: (R, G, B, C) do TCS e IR. Estimativas!
    REFERENCIAS_PADRAO = {
        "branco":   ((127, 128, 126, 127), 100),
        "preto":    ((3, 3, 4, 5), 2),
        "prata":    ((190, 195, 200, 205), 190),
        "azul":     ((20, 45, 115, 66), 70),
        "vermelho": ((115, 25, 22, 58), 85),
        "verde":    ((30, 85, 45, 62), 75),
        "amarelo":  ((125, 115, 35, 110), 95),
    }
    # desvio mínimo de cada característica (cr, cg, cb, brilho, ir)
    DESVIO_MINIMO = (0.03, 0.03, 0.03, 0.08, 0.08)
    # abaixo deste brilho (escala 0-255) a cromaticidade é só ruído e não pesa
    BRILHO_MINIMO_COR = 15
    # IR que fica do lado de cada TCS: TCS1 -> IR 0, meio -> IR 1 e 2, TCS2 -> IR 3
    IR_DO_TCS = {1: (0,), 2: (1, 2), 3: (3,)}

    def __init__(self, porta_serial, arquivo_cores=None, limiar=6.0, usar_ir=True):
        """
        Args:
            porta_serial: Constante da classe Portas (ex.: Portas.SERIAL6)
            arquivo_cores: JSON com referências aprendidas (opcional)
            limiar: distância máxima (em desvios) para aceitar uma cor
            usar_ir: considera a reflexão IR na classificação de cor
        """
        self.lista = [0] * self.QUANTIDADE_BYTES
        self.limiar = limiar
        self.usar_ir = usar_ir
        self.referencias = {}
        for nome, (rgbc, ir) in self.REFERENCIAS_PADRAO.items():
            self.referencias[nome] = (self.caracteristicas(rgbc, ir), self.DESVIO_MINIMO)
        if arquivo_cores:
            self.carrega_cores(arquivo_cores)
        portas = Portas()
        self.ser = portas.abre_porta_serial(porta_serial, 115200)
        if self.ser is None:
            raise Exception("Erro ao abrir a porta serial do sensor de cor e reflexão")
        self._thread_ativa = False
        self._thread = None
        self._ultimo_tempo = 0
        self._iniciar_thread()

    def __del__(self):
        if getattr(self, '_thread', None) is not None:
            self._parar_thread()
        if getattr(self, 'ser', None) is not None:
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
        """Lista com os 4 valores de reflexão IR (0 = preto, ~100 = branco, >100 = prata)."""
        return self.lista[0:4]

    def reflexao(self, sensor):
        """Valor de reflexão individual (sensor 0-3)."""
        if 0 <= sensor <= 3:
            return self.lista[sensor]
        return 0

    # ── Cor RGBC ────────────────────────────────────────────────────────

    def le_rgbc(self, sensor):
        """Retorna [R, G, B, C] do sensor de cor (1=TCS1, 2=TCS meio, 3=TCS2). Branco ~127."""
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
        H: 0-360, S: 0-100, V: 0-100 (V com branco calibrado ~50; prata pode chegar a 100)."""
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

    def le_hsv120(self, sensor, valor_maximo=255):
        """Retorna [H, S, V] do sensor de cor (1=TCS1, 2=TCS meio, 3=TCS2).
        H: 0-120, S: 0-120, V: 0-120 (escala estilo Paint clássico do Windows)."""
        rgb = self.le_rgb(sensor)
        if rgb is not None:
            return list(self.rgb_para_hsv120(rgb[0], rgb[1], rgb[2], valor_maximo))
        return None

    @staticmethod
    def rgb_para_hsv120(r, g, b, valor_maximo=255):
        """Converte RGB para HSV na escala 0-120 (estilo Paint clássico do Windows).
        H: 0-120, S: 0-120, V: 0-120.
        valor_maximo: valor de referência para normalização (padrão 255)."""
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

    # ── Detecção de cor por referências ─────────────────────────────────

    @staticmethod
    def caracteristicas(rgbc, ir):
        """(cr, cg, cb, brilho, ir): cromaticidade e valores relativos ao branco calibrado."""
        r, g, b, c = (float(x) for x in rgbc)
        s = r + g + b
        if s <= 0:
            cr = cg = cb = 1.0 / 3
        else:
            cr, cg, cb = r / s, g / s, b / s
        return (cr, cg, cb, c / 127.0, float(ir) / 100.0)

    def _distancia(self, f, referencia):
        media, desvio = referencia
        pesa_cor = min(f[3], media[3]) * 127.0 >= self.BRILHO_MINIMO_COR
        soma = 0.0
        for i in range(5):
            if i < 3 and not pesa_cor:
                continue
            if i == 4 and not self.usar_ir:
                continue
            soma += ((f[i] - media[i]) / desvio[i]) ** 2
        return math.sqrt(soma)

    def _leitura(self, sensor):
        rgbc = self.le_rgbc(sensor)
        irs = self.le_reflexao()
        idx = self.IR_DO_TCS[sensor]
        ir = sum(irs[i] for i in idx) / len(idx)
        return self.caracteristicas(rgbc, ir)

    def distancias(self, sensor=2):
        """Lista [(distância, nome)] ordenada; útil para depurar e ajustar o limiar."""
        f = self._leitura(sensor)
        return sorted((self._distancia(f, ref), nome) for nome, ref in self.referencias.items())

    def cor(self, sensor=2):
        """Nome da cor no sensor (1=TCS1, 2=TCS meio, 3=TCS2) ou 'desconhecida'."""
        d = self.distancias(sensor)
        if not d:
            return "desconhecida"
        dist, nome = d[0]
        return nome if dist <= self.limiar else "desconhecida"

    def cores(self):
        """Nome da cor nos três TCS: [TCS1, meio, TCS2]."""
        return [self.cor(s) for s in (1, 2, 3)]

    def cor_piso(self):
        """Votação dos três TCS; sem maioria, vale o do meio."""
        v = self.cores()
        for nome in set(v):
            if v.count(nome) >= 2:
                return nome
        return v[1]

    def detecta_cor(self, sensor):
        """Cor no sensor (1=TCS1, 2=TCS meio, 3=TCS2) como constante COR_*."""
        if not self.conectado and not any(self.lista):
            return self.COR_NADA
        return self.CODIGO_COR.get(self.cor(sensor), self.COR_DESCONHECIDA)

    def nome_cor(self, sensor):
        """Retorna o nome da cor detectada pelo sensor (1, 2 ou 3)."""
        return self.cor(sensor)

    def detectar_cor(self, r, g, b, c, ir=None):
        """Classifica um RGBC avulso (escala do firmware, branco ~127). Retorna constante COR_*.
        Sem IR, usa só cromaticidade e brilho."""
        f = self.caracteristicas((r, g, b, c), 100 if ir is None else ir)
        usar_ir, self.usar_ir = self.usar_ir, self.usar_ir and ir is not None
        try:
            d = sorted((self._distancia(f, ref), nome) for nome, ref in self.referencias.items())
        finally:
            self.usar_ir = usar_ir
        if not d or d[0][0] > self.limiar:
            return self.COR_DESCONHECIDA
        return self.CODIGO_COR.get(d[0][1], self.COR_DESCONHECIDA)

    # ── Referências de cor (calibração no campo) ────────────────────────

    def usa_cores(self, nomes):
        """Mantém só as cores listadas (ex.: na Maze não há verde nem amarelo)."""
        self.referencias = {n: r for n, r in self.referencias.items() if n in nomes}
        for n in nomes:
            if n not in self.referencias and n in self.REFERENCIAS_PADRAO:
                rgbc, ir = self.REFERENCIAS_PADRAO[n]
                self.referencias[n] = (self.caracteristicas(rgbc, ir), self.DESVIO_MINIMO)

    def aprende_cor(self, nome, amostras=25, intervalo=0.03, sensores=(1, 2, 3)):
        """Robô parado com os sensores sobre a cor `nome`: lê várias vezes e grava a
        referência (média e 2 desvios de folga). Retorna (media, desvio)."""
        fs = []
        for _ in range(amostras):
            for s in sensores:
                fs.append(self._leitura(s))
            time.sleep(intervalo)
        n = len(fs)
        media = tuple(sum(f[i] for f in fs) / n for i in range(5))
        desvio = tuple(
            max(2.0 * math.sqrt(sum((f[i] - media[i]) ** 2 for f in fs) / max(1, n - 1)),
                self.DESVIO_MINIMO[i])
            for i in range(5))
        self.referencias[nome] = (media, desvio)
        return self.referencias[nome]

    def esquece_cor(self, nome):
        self.referencias.pop(nome, None)

    def salva_cores(self, arquivo="cores.json"):
        with open(arquivo, "w") as f:
            json.dump({n: {"media": list(m), "desvio": list(d)} for n, (m, d) in self.referencias.items()},
                      f, indent=1)

    def carrega_cores(self, arquivo="cores.json"):
        """Carrega referências salvas. Retorna False se o arquivo não existir."""
        try:
            with open(arquivo) as f:
                dados = json.load(f)
        except (OSError, ValueError):
            return False
        for nome, r in dados.items():
            desvio = tuple(max(d, m) for d, m in zip(r["desvio"], self.DESVIO_MINIMO))
            self.referencias[nome] = (tuple(r["media"]), desvio)
        return True

    # ── Calibração do firmware ──────────────────────────────────────────

    def calibra_branco(self, timeout_ms=10000):
        """Solicita calibração do branco (o firmware leva ~7 s). Retorna True se confirmada."""
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
