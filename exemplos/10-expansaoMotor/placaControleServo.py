import time

import serial


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
        65002  polaridade do motor x potenciômetro: [3..4] = ação (0 normal, 1 invertida,
               2 refazer a autodetecção, outro = consulta). A placa responde com 65002 no
               lugar da posição, [3] = polaridade (0, 1 ou 0xFF = não calibrada) e
               [4] = resultado da última autodetecção (0 não rodou, 1 sucesso, 2 falhou).
               A autodetecção (2) não responde.
        65003  configuração do controle: [3] = parâmetro (0x80 | parâmetro = só consulta,
               0x7F = restaura padrões), [4] = valor. A placa responde com 65003 no lugar da
               posição, [3] = parâmetro, [4] = valor em uso.
        0xFFxx troca de ID (ver define_id)

    Modos de controle (firmware de 21/10/2026, ver configura_controle):
        MODO_LIGA_DESLIGA  potência cheia até a zona morta (o original; vibra em volta do alvo)
        MODO_PROPORCIONAL  potência = KP*erro - KD*velocidade + termo I, com freio e histerese
                           (padrão). O termo I (KI) vem desligado; ligue com valores pequenos
                           (ex.: ki=0.25) se uma carga constante deixar o servo parado antes do alvo.

    Polaridade (firmware de 21/10/2026): na primeira vez que liga, a placa descobre sozinha para
    que lado acionar a ponte H e grava na EEPROM. Se errar, corrija com define_polaridade() ou
    inverte_polaridade().

    Porta fixa (debug, ex.: direto no Windows): passe porta_fixa='COM7' (ou '/dev/ttyUSB0') e a
    porta é aberta direto pelo pyserial, sem a classe Portas (que nem precisa existir):
        servo = PlacaControleServo(None, 5, porta_fixa='COM7')
        PlacaControleServo.buscar_servos(None, porta_fixa='COM7')
    """
    ID_BROADCAST = 254
    ultima_posicao = None
    TAMANHO_PACOTE = 6
    DEBUG = False          # True imprime cada pacote enviado/recebido (deixa o laço lento)

    COMANDO_CALIBRACAO = 65000
    COMANDO_CONSULTA = 65001
    COMANDO_POLARIDADE = 65002
    TEMPO_DETECTA_TRAVA_MIN = 1000  # ms - limite mínimo aceito pela placa
    TEMPO_DETECTA_TRAVA_MAX = 5000  # ms - limite máximo aceito pela placa

    # Ações do comando de polaridade
    POLARIDADE_ACAO_NORMAL = 0
    POLARIDADE_ACAO_INVERTIDA = 1
    POLARIDADE_ACAO_AUTODETECTA = 2
    POLARIDADE_ACAO_CONSULTA = 3
    # Valores de polaridade na resposta
    POLARIDADE_NORMAL = 0
    POLARIDADE_INVERTIDA = 1
    POLARIDADE_NAO_CALIBRADA = 0xFF
    # Resultado da última autodetecção na resposta
    AUTODETECCAO_NAO_RODOU = 0
    AUTODETECCAO_SUCESSO = 1
    AUTODETECCAO_FALHOU = 2
    TEMPO_AUTODETECCAO = 2.0  # s - a placa leva no máximo ~1,5 s

    COMANDO_CONTROLE = 65003
    MODO_LIGA_DESLIGA = 0
    MODO_PROPORCIONAL = 1
    # Parâmetros do comando de controle
    PARAM_MODO = 0
    PARAM_KP = 1
    PARAM_KD = 2
    PARAM_PWM_MINIMO = 3
    PARAM_HISTERESE = 4
    PARAM_PERIODO_MS = 5
    PARAM_KI = 6
    PARAM_FAIXA_INTEGRAL = 7
    PARAM_LIMITE_INTEGRAL = 8
    _CONTROLE_RESTAURA_PADRAO = 0x7F
    _CONTROLE_SO_CONSULTA = 0x80
    ESCALA_GANHO = 16  # a placa guarda KP, KD e KI em 1/16
    _NOMES_PARAMETROS = {
        'modo': PARAM_MODO,
        'kp': PARAM_KP,
        'kd': PARAM_KD,
        'pwm_minimo': PARAM_PWM_MINIMO,
        'histerese': PARAM_HISTERESE,
        'periodo_ms': PARAM_PERIODO_MS,
        'ki': PARAM_KI,
        'faixa_integral': PARAM_FAIXA_INTEGRAL,
        'limite_integral': PARAM_LIMITE_INTEGRAL,
    }
    _GANHOS = ('kp', 'kd', 'ki')
    # Timeout de leitura com porta fixa. Maior que o da Portas (10 ms) porque conversores USB-serial
    # no Windows costumam ter ~16 ms de latência; só pesa quando a placa não responde.
    TIMEOUT_PORTA_FIXA = 0.05  # s

    def __init__(self, porta_serial, id_equipamento, baud_rate=250000, porta_fixa=None,
                 timeout_porta_fixa=TIMEOUT_PORTA_FIXA):
        """
        Args:
            porta_serial: Porta lógica da Portas (ex.: Portas.SERIAL1). Ignorada se porta_fixa for dada.
            id_equipamento: ID da placa (0-253)
            baud_rate: Baud rate da comunicação, default 250000
            porta_fixa: Nome da porta no sistema (ex.: 'COM7', '/dev/ttyUSB0'), para debug
            timeout_porta_fixa: Timeout de leitura (s) usado com porta_fixa
        """
        self.id_equipamento = id_equipamento & 0xFF
        self.ser = self._abre_serial(porta_serial, baud_rate, porta_fixa, timeout_porta_fixa)
        if self.ser is None:
            raise Exception('Erro ao abrir a porta serial da PlacaControleServo')

    def __del__(self):
        if getattr(self, 'ser', None) is not None:
            self.ser.close()
            if self.DEBUG:
                print('Fechando a porta serial do PlacaControleServo')

    @staticmethod
    def _abre_serial(porta_serial, baud_rate, porta_fixa=None, timeout_porta_fixa=TIMEOUT_PORTA_FIXA):
        """Abre a porta fixa direto pelo pyserial ou, sem ela, a porta lógica pela Portas."""
        if porta_fixa is not None:
            try:
                ser = serial.Serial(porta_fixa, baud_rate, timeout=timeout_porta_fixa)
                print(f'Comunicação estabelecida com sucesso na porta fixa {porta_fixa}.')
                return ser
            except serial.SerialException as e:
                print(f'Erro ao tentar se comunicar com a porta fixa {porta_fixa}: {e}')
                return None

        from portas import Portas   # só a Banana Pi precisa; com porta fixa nem é importada
        return Portas().abre_porta_serial(porta_serial, baud_rate)

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

    def _comando_polaridade(self, acao, tentativas=3):
        """Envia o comando de polaridade e devolve {'polaridade', 'autodeteccao'} ou None."""
        pacote = self._montar_pacote_comando(self.COMANDO_POLARIDADE, acao)
        for _ in range(tentativas):
            resultado = self._transacao(pacote, tentativas=1)
            if resultado is not None and resultado['posicao'] == self.COMANDO_POLARIDADE:
                return {'polaridade': resultado['potencia'], 'autodeteccao': resultado['zona_morta']}
            time.sleep(0.002)
        return None

    def consulta_polaridade(self, tentativas=3):
        """Lê a polaridade do motor em uso na placa.

        Returns:
            dict com 'polaridade' (POLARIDADE_NORMAL, POLARIDADE_INVERTIDA ou
            POLARIDADE_NAO_CALIBRADA) e 'autodeteccao' (resultado da última autodetecção desde
            o boot: AUTODETECCAO_NAO_RODOU, AUTODETECCAO_SUCESSO ou AUTODETECCAO_FALHOU),
            ou None se a placa não respondeu
        """
        return self._comando_polaridade(self.POLARIDADE_ACAO_CONSULTA, tentativas)

    def define_polaridade(self, invertida, tentativas=3):
        """Força a polaridade do motor e grava na EEPROM da placa.

        Args:
            invertida: False = normal (PINO1 faz o potenciômetro aumentar),
                       True = invertida (PINO2 faz o potenciômetro aumentar)

        Returns:
            True se a placa confirmou a polaridade pedida, False caso contrário
        """
        esperada = self.POLARIDADE_INVERTIDA if invertida else self.POLARIDADE_NORMAL
        acao = self.POLARIDADE_ACAO_INVERTIDA if invertida else self.POLARIDADE_ACAO_NORMAL
        resultado = self._comando_polaridade(acao, tentativas)
        return resultado is not None and resultado['polaridade'] == esperada

    def inverte_polaridade(self, tentativas=3):
        """Inverte a polaridade atual da placa (útil quando a autodetecção errou).

        Consulta a polaridade e grava a oposta, assim uma resposta perdida e reenviada não
        desfaz a inversão. Se a placa não estiver calibrada, ela usa a normal, então vira invertida.

        Returns:
            A nova polaridade (POLARIDADE_NORMAL ou POLARIDADE_INVERTIDA), ou None se falhou
        """
        atual = self.consulta_polaridade(tentativas)
        if atual is None:
            return None
        invertida = atual['polaridade'] != self.POLARIDADE_INVERTIDA
        if not self.define_polaridade(invertida, tentativas):
            return None
        return self.POLARIDADE_INVERTIDA if invertida else self.POLARIDADE_NORMAL

    def autodetecta_polaridade(self, tentativas=3):
        """Manda a placa refazer a autodetecção da polaridade (o servo dá dois pulsos curtos).

        A placa não responde durante o teste; espera TEMPO_AUTODETECCAO e consulta o resultado.
        Se a autodetecção falhar, a placa mantém a polaridade que já tinha.

        Returns:
            A polaridade detectada (POLARIDADE_NORMAL ou POLARIDADE_INVERTIDA), ou None se a
            autodetecção falhou ou a placa não respondeu
        """
        pacote = self._montar_pacote_comando(self.COMANDO_POLARIDADE, self.POLARIDADE_ACAO_AUTODETECTA)
        self._envia_sem_resposta(pacote, 'AUTODETECTA POLARIDADE TX')
        time.sleep(self.TEMPO_AUTODETECCAO)
        resultado = self.consulta_polaridade(tentativas)
        if resultado is None or resultado['autodeteccao'] != self.AUTODETECCAO_SUCESSO:
            return None
        return resultado['polaridade']

    def autodetecta_polaridade_todos(self):
        """Manda todas as placas do barramento refazerem a autodetecção (broadcast, sem confirmação).

        Espera TEMPO_AUTODETECCAO antes de retornar; depois use consulta_polaridade() em cada placa.
        """
        pacote = self._montar_pacote_comando(self.COMANDO_POLARIDADE, self.POLARIDADE_ACAO_AUTODETECTA,
                                             id_equipamento=self.ID_BROADCAST)
        self._envia_sem_resposta(pacote, 'BROADCAST AUTODETECTA POLARIDADE TX')
        time.sleep(self.TEMPO_AUTODETECCAO)

    # ------------------------------------------------------------------ modo de controle
    def _pacote_controle(self, parametro, valor=0, id_equipamento=None):
        pacote = [
            self.id_equipamento if id_equipamento is None else id_equipamento,
            (self.COMANDO_CONTROLE >> 8) & 0xFF,
            self.COMANDO_CONTROLE & 0xFF,
            parametro & 0xFF,
            max(0, min(255, int(valor))),
        ]
        pacote.append(self._calcular_crc(pacote))
        return bytes(pacote)

    def _comando_controle(self, parametro, valor=0, tentativas=3):
        """Envia o comando de controle e devolve o valor em uso (0-255) ou None."""
        pacote = self._pacote_controle(parametro, valor)
        esperado = parametro & ~self._CONTROLE_SO_CONSULTA
        for _ in range(tentativas):
            resultado = self._transacao(pacote, tentativas=1)
            if (resultado is not None and resultado['posicao'] == self.COMANDO_CONTROLE
                    and resultado['potencia'] == esperado):
                return resultado['zona_morta']
            time.sleep(0.002)
        return None

    def _valores_brutos_controle(self, **parametros):
        """Converte os argumentos de configura_controle em {parâmetro: byte}, ignorando os None."""
        valores = {}
        for nome, valor in parametros.items():
            if valor is None:
                continue
            if nome in self._GANHOS:
                valor = round(valor * self.ESCALA_GANHO)
            valores[self._NOMES_PARAMETROS[nome]] = max(0, min(255, int(valor)))
        return valores

    def configura_controle(self, modo=None, kp=None, kd=None, pwm_minimo=None, histerese=None,
                           periodo_ms=None, ki=None, faixa_integral=None, limite_integral=None,
                           tentativas=3):
        """Configura o controle de posição da placa (grava na EEPROM). Só muda o que for passado.

        Args:
            modo: MODO_LIGA_DESLIGA ou MODO_PROPORCIONAL
            kp: ganho proporcional (PWM por contagem de erro), 0 a 15.9 em passos de 1/16
            kd: ganho de freio (PWM por contagem/período de velocidade), 0 a 15.9 em passos de 1/16
            pwm_minimo: PWM mínimo para vencer o atrito (0-255)
            histerese: contagens além da zona morta para religar depois de parar (0-255)
            periodo_ms: período de medida da velocidade e da integral (1-100 ms)
            ki: ganho integral (PWM somado por contagem de erro a cada período), 0 a 15.9 em
                passos de 1/16; 0 desliga o termo I
            faixa_integral: só acumula o termo I com |erro| até este valor (contagens, 0-255).
                Mudanças de alvo maiores que ela zeram o termo I.
            limite_integral: PWM máximo do termo I (0-255)

        Exemplo:
            servo.configura_controle(modo=PlacaControleServo.MODO_PROPORCIONAL, kp=3, kd=8, ki=0.25)

        Returns:
            True se a placa confirmou todos os valores pedidos, False caso contrário
        """
        valores = self._valores_brutos_controle(
            modo=modo, kp=kp, kd=kd, pwm_minimo=pwm_minimo, histerese=histerese,
            periodo_ms=periodo_ms, ki=ki, faixa_integral=faixa_integral,
            limite_integral=limite_integral)
        ok = True
        for parametro, valor in valores.items():
            if parametro == self.PARAM_PERIODO_MS:
                valor = max(1, min(100, valor))   # a placa limita da mesma forma
            ok = self._comando_controle(parametro, valor, tentativas) == valor and ok
        return ok

    def configura_controle_todos(self, modo=None, kp=None, kd=None, pwm_minimo=None, histerese=None,
                                 periodo_ms=None, ki=None, faixa_integral=None, limite_integral=None):
        """Igual a configura_controle, para todas as placas (broadcast, sem confirmação)."""
        valores = self._valores_brutos_controle(
            modo=modo, kp=kp, kd=kd, pwm_minimo=pwm_minimo, histerese=histerese,
            periodo_ms=periodo_ms, ki=ki, faixa_integral=faixa_integral,
            limite_integral=limite_integral)
        for parametro, valor in valores.items():
            pacote = self._pacote_controle(parametro, valor, id_equipamento=self.ID_BROADCAST)
            self._envia_sem_resposta(pacote, 'BROADCAST CONTROLE TX')
            time.sleep(0.01)   # tempo da placa gravar a EEPROM

    def define_modo_controle(self, modo, tentativas=3):
        """Escolhe o modo de controle (MODO_LIGA_DESLIGA ou MODO_PROPORCIONAL).

        Returns:
            True se a placa confirmou o modo pedido, False caso contrário
        """
        return self.configura_controle(modo=modo, tentativas=tentativas)

    def le_configuracao_controle(self, tentativas=3):
        """Lê a configuração do controle em uso na placa.

        Returns:
            dict com 'modo', 'kp', 'kd', 'ki' (floats), 'pwm_minimo', 'histerese', 'periodo_ms',
            'faixa_integral' e 'limite_integral', ou None se a placa não respondeu
        """
        config = {}
        for nome, parametro in self._NOMES_PARAMETROS.items():
            valor = self._comando_controle(parametro | self._CONTROLE_SO_CONSULTA, 0, tentativas)
            if valor is None:
                return None
            config[nome] = valor / self.ESCALA_GANHO if nome in self._GANHOS else valor
        return config

    def restaura_controle_padrao(self, tentativas=3):
        """Volta a configuração do controle aos padrões do firmware (grava na EEPROM).

        Returns:
            True se a placa confirmou, False caso contrário
        """
        return self._comando_controle(self._CONTROLE_RESTAURA_PADRAO, 0, tentativas) is not None

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
    def buscar_servos(porta_serial, baud_rate=250000, porta_fixa=None,
                      timeout_porta_fixa=TIMEOUT_PORTA_FIXA):
        """Escaneia todos os IDs (0-253) e retorna os que responderam.

        Cada servo encontrado fica com o motor desligado (potência 0).

        Args:
            porta_serial: Porta serial (ex: Portas.SERIAL1). Ignorada se porta_fixa for dada.
            baud_rate: Baud rate da comunicação, default 250000
            porta_fixa: Nome da porta no sistema (ex.: 'COM7', '/dev/ttyUSB0'), para debug
            timeout_porta_fixa: Timeout de leitura (s) usado com porta_fixa

        Returns:
            Lista de dicts com 'id' e 'posicao' dos servos encontrados
        """
        ser = PlacaControleServo._abre_serial(porta_serial, baud_rate, porta_fixa, timeout_porta_fixa)
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
