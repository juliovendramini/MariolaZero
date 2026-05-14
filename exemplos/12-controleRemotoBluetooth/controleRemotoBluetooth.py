import threading

from portas import Portas


class ControleRemotoBluetooth:
    """Leitura do controle remoto via Bluetooth usando o app Android 'BT Controller'
    no modo avancado (analogico).

    Protocolo - string ASCII de 6 caracteres, sem terminador:
        [0]     Direcao frente/tras : 'F' (frente) ou 'B' (re)
        [1..2]  Velocidade          : 2 digitos, 00-97
        [3]     Direcao esq/dir     : 'R' (direita) ou 'L' (esquerda)
        [4..5]  Desvio lateral      : 2 digitos, 00-60

    Exemplos: "F97R60"  "B43L12"  "F00R00" (parado)

    Os valores sao expostos ja normalizados:
        frente_tras       : -100 (re maxima) a +100 (frente maxima)
        esquerda_direita  : -100 (esq. maxima) a +100 (dir. maxima)
    """

    TAMANHO_PACOTE = 6
    BAUD_RATE = 9600

    MAX_FRENTE_TRAS = 97
    MAX_ESQUERDA_DIREITA = 60

    DEBUG = False

    def __init__(self, porta, leitura_continua=True):
        """
        Args:
            porta: Constante de porta de Portas (ex: Portas.SERIAL3) onde o HC-05
                   esta conectado. O HC-05 e transparente e aparece como porta serial comum.
            leitura_continua: Se True, inicia thread em background atualizando os valores
                              automaticamente. Se False, chame ler() manualmente.
        """
        portas = Portas()
        self.ser = portas.abre_porta_serial(porta, self.BAUD_RATE, timeout=1)
        if self.ser is None:
            raise Exception('Erro ao abrir a porta Bluetooth')

        self._frente_tras = 0
        self._esquerda_direita = 0

        self._lock = threading.Lock()
        self._rodando = False

        if leitura_continua:
            self._iniciar_leitura_continua()

    @property
    def frente_tras(self):
        """-100 = re maxima, 0 = parado, +100 = frente maxima."""
        with self._lock:
            return self._frente_tras

    @property
    def esquerda_direita(self):
        """-100 = esquerda maxima, 0 = centro, +100 = direita maxima."""
        with self._lock:
            return self._esquerda_direita

    def estado(self):
        """Retorna dicionario com os valores atuais de forma thread-safe."""
        with self._lock:
            return {
                'frente_tras': self._frente_tras,
                'esquerda_direita': self._esquerda_direita,
            }

    def ler(self):
        """Le e processa um pacote. Use quando leitura_continua=False."""
        pacote = self._ler_proximo_pacote()
        if pacote is not None:
            self._processar_pacote(pacote)
            return True
        return False

    def _processar_pacote(self, pacote):
        try:
            direcao_yt = pacote[0]
            valor_yt   = int(pacote[1:3])
            direcao_xl = pacote[3]
            valor_xl   = int(pacote[4:6])
        except (ValueError, IndexError):
            if self.DEBUG:
                print(f'[BT] Pacote invalido: {pacote!r}')
            return

        ft = round(valor_yt / self.MAX_FRENTE_TRAS * 100)
        if direcao_yt == 'B':
            ft = -ft

        ed = round(valor_xl / self.MAX_ESQUERDA_DIREITA * 100)
        if direcao_xl == 'L':
            ed = -ed

        with self._lock:
            self._frente_tras = ft
            self._esquerda_direita = ed

        if self.DEBUG:
            print(f'[BT] raw={pacote!r}  frente_tras={ft:+4d}  esquerda_direita={ed:+4d}')

    def _ler_proximo_pacote(self):
        """Sincroniza no primeiro byte valido ('F' ou 'B') e retorna o pacote ou None."""
        try:
            while True:
                byte = self.ser.read(1)
                if not byte:
                    return None
                c = chr(byte[0])
                if c in ('F', 'B'):
                    break

            resto = self.ser.read(self.TAMANHO_PACOTE - 1)
            if len(resto) != self.TAMANHO_PACOTE - 1:
                if self.DEBUG:
                    print(f'[BT] Pacote incompleto: {len(resto) + 1} bytes')
                return None

            return c + resto.decode('ascii', errors='replace')

        except Exception as e:
            if self.DEBUG:
                print(f'[BT] Erro na leitura: {e}')
            return None

    def _loop_leitura(self):
        while self._rodando:
            pacote = self._ler_proximo_pacote()
            if pacote is not None:
                self._processar_pacote(pacote)

    def _iniciar_leitura_continua(self):
        self._rodando = True
        self._thread = threading.Thread(
            target=self._loop_leitura,
            daemon=True,
            name='bt-controller-reader'
        )
        self._thread.start()

    def parar(self):
        """Para a thread de leitura e fecha a porta serial."""
        self._rodando = False
        if hasattr(self, '_thread'):
            self._thread.join(timeout=1.0)
        if self.ser is not None:
            self.ser.close()

    def __del__(self):
        self.parar()
