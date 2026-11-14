# Classe para controlar os motores e servos da placa do Motores do novo brick
import struct
import time

from portas import Portas


class Motores:
    motor_invertido = [False, False, False, False]
    DEBUG = False
    NORMAL = 0
    INVERTIDO = 1
    angulo_motor1 = 0
    angulo_motor2 = 0
    modo_freio = 0
    BREAK = 0
    HOLD = 1
    angulo_absoluto_motor1 = 0
    angulo_absoluto_motor2 = 0
    angulo_delta_motor1 = 0  # o angulo delta é o angulo que o motor andou desde a ultima vez que foi resetado
    angulo_delta_motor2 = 0  # o angulo delta é o angulo que o motor andou desde a ultima vez que foi resetado
    estado_motores = 0
    PARADO = 0
    GIRANDO_NORMAL = 1
    GIRANDO_INVERTIDO = 2
    atualiza_instantaneo = False
    ser = None
    ENVIA_SERVOS = 0xFD #253
    ENVIA_MOTORES = 0xFC #252
    ATUALIZA_MOTORES = 0xFB #251
    ENVIA_MOTORES_POTENCIA = 0xFA #250
    ENVIA_PID = 0xF9 #249
    ENVIA_MOTORES_4X4 = 0xF8
    ENVIA_MOTORES_4X4_POTENCIA = 0xF7
    LED_RGB_ALL = 0xF6
    LED_RGB_ONE = 0xF5
    OBTEM_CALIBRACAO_MOTORES = 0xF4 #244
    CALIBRA_MOTORES = 0xF3 #243
    ATIVA_VENTOINHA = 0xF2 #242
    LED_RGB_ALL_PORTA4 = 0xF1 #241
    LED_RGB_ONE_PORTA4 = 0xF0 #240
    TOCA_BUZZER = 0xEF #239
    TOCA_SOM = 0xEE #238
    CONSULTA_BUZZER = 0xED #237
    CONFIGURA_BUZZER = 0xEC #236
    BUZZER_LIGA_LOW = 0   # padrão: o buzzer apita com o pino em LOW (repouso em HIGH)
    BUZZER_LIGA_HIGH = 1
    NUM_LEDS_PORTA4 = 10  # numLeds do LEDStrip da porta 4 no firmware

    # O Timer2 do Mariola atende só uma função: servos, ventoinha ou buzzer. A primeira que for usada
    # fica com ele até o brick reiniciar e os comandos das outras são ignorados pelo firmware.
    TIMER2_LIVRE = 0
    TIMER2_SERVOS = 1
    TIMER2_VENTOINHA = 2
    TIMER2_BUZZER = 3
    _NOMES_TIMER2 = {0: 'livre', 1: 'servos', 2: 'ventoinha', 3: 'buzzer'}
    _DONO_TIMER2 = {1: 'os servos', 2: 'a ventoinha', 3: 'o buzzer'}  # para as mensagens de erro

    # status das respostas do buzzer
    _BUZZER_RECUSADO = 0
    _BUZZER_OK = 1
    _BUZZER_SOM_INVALIDO = 2

    # sons do buzzer (número do som no firmware)
    SOM_BIPE = 1
    SOM_BIPE_DUPLO = 2
    SOM_SUCESSO = 3
    SOM_ERRO = 4
    SOM_ALERTA = 5
    SOM_LIGANDO = 6
    SOM_DESLIGANDO = 7
    SOM_LARGADA = 8
    SOM_RE = 9
    SOM_SIRENE_DOIS_TONS = 10
    SOM_SIRENE = 11
    SOM_MOEDA = 12
    SOM_POWER_UP = 13
    SOM_LASER = 14
    SOM_BATERIA_FRACA = 15
    SOM_ROBO = 16
    MELODIA_ESCALA = 17
    MELODIA_PARABENS = 18
    MELODIA_BRILHA_ESTRELINHA = 19
    MELODIA_ODE_ALEGRIA = 20
    MELODIA_JINGLE_BELLS = 21
    MELODIA_FUR_ELISE = 22
    MELODIA_GRAN_VALS = 23  # o toque clássico de celular
    QUANTIDADE_SONS = 23

    # Comunicação com o brick. O Mariola tem um hub USB com os conversores seriais (o do brick e os das
    # placas de motor). Se o hub reinicia (queda dos 5 V ou ruído dos motores; no dmesg: "usb 1-1: reset
    # high-speed USB device"), a resposta não chega e a porta some e volta. Até 12/11/2026 a lib desistia em
    # 10 ms ("Erro ao ler o estado dos motores") e o programa morria com os motores girando até o timeout
    # de 5 s do firmware. Agora ela espera a resposta um pouco mais, reabre a porta e manda de novo, por até
    # TEMPO_RECUPERACAO segundos; só depois disso dá o erro. falhas_comunicacao conta as falhas (diagnóstico).
    TEMPO_RESPOSTA = 0.05      # s esperando a resposta completa (a porta lê com timeout de 10 ms)
    TEMPO_RECUPERACAO = 3.0    # s tentando de novo (abaixo dos 5 s em que o firmware solta os motores)
    falhas_comunicacao = 0

    def __init__(self, atualiza_instantaneo=False):
        #qualquer lista que for enviada deve ter o mesmo tamanho sempre. Para evitar problemas de sincronismo
        self.lista_servos = [self.ENVIA_SERVOS, 200, 200, 200, 200, 200, 200, 0, 0, 0]
        self.lista_motores = [self.ENVIA_MOTORES, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.lista_pid = [self.ENVIA_PID, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.lista_led = [self.LED_RGB_ALL, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.ventoinha_ativa = False
        self.buzzer_ativo = False
        self.servos_ativos = False  # algum servo já recebeu ângulo: o Timer2 ficou com os servos
        portas = Portas()
        self.ser = portas.abre_porta_serial(Portas._SERIAL0, 250000)
        if self.ser is None:
            raise Exception('Erro ao abrir a porta serial')
        self.atualiza_instantaneo = atualiza_instantaneo
        self.atualiza_motores()
        self.atualiza_servos()
        self.reseta_angulo_motor(1)
        self.reseta_angulo_motor(2)

    def __del__(self):
        # Chamado quando o programa termina: manda os motores pararem em vez de esperar o timeout de 5 s do firmware.
        # Cada passo fica num try: se a placa não responder (ou a porta nem tiver aberto), os outros ainda são tentados.
        if self.ser is None:
            return
        self.TEMPO_RECUPERACAO = 0.5  # saindo do programa: não fica 3 s esperando um brick que sumiu
        try:
            self.para_motores()
            if not self.atualiza_instantaneo:
                # com Motores() ou Motores(False) o para_motores() só preenche a lista: sem isto nada era enviado
                self.atualiza_motores()
        except Exception:
            pass
        try:
            if self.ventoinha_ativa:
                self.desliga_ventoinha()  # o timeout do firmware não desliga a ventoinha
        except Exception:
            pass
        try:
            if self.buzzer_ativo:
                self.para_buzzer()
        except Exception:
            pass
        try:
            self.ser.close()
        except Exception:
            pass
        if self.DEBUG:
            print('Fechando a porta serial do motores')

    def _troca(self, pacote, tamanho):
        """Manda o pacote e lê a resposta, esperando até TEMPO_RESPOSTA pelos bytes que faltarem."""
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(pacote)
        if self.DEBUG:
            print(f'Enviando: {list(pacote)}')
        resposta = bytes(self.ser.read(tamanho))
        fim = time.monotonic() + self.TEMPO_RESPOSTA
        while len(resposta) < tamanho and time.monotonic() < fim:
            resposta += self.ser.read(tamanho - len(resposta))
        if self.DEBUG:
            print('retorno_serial (int):', list(resposta))
        return resposta

    def _conversa(self, pacote, tamanho, aceita, mensagem, repetir=True, ja_chegou=None):
        """Manda o pacote e devolve a resposta (tamanho bytes, o primeiro em 'aceita').

        Se falhar, reabre a porta (Portas.reabre_porta_serial) e manda de novo, por até TEMPO_RECUPERACAO
        segundos; depois disso dá Exception(mensagem). repetir=False: uma tentativa só. ja_chegou: chamada
        antes de mandar de novo; se devolver uma resposta, o comando já tinha chegado ao brick e não vai
        outra vez (comando com ângulo)."""
        pacote = bytes(pacote)
        inicio = time.monotonic()
        falhou = False
        while True:
            try:
                if falhou and ja_chegou is not None:
                    resposta = ja_chegou()
                    if resposta is not None:
                        print(f'[Motores] comunicação de volta em {time.monotonic() - inicio:.2f} s')
                        return resposta
                resposta = self._troca(pacote, tamanho)
                if len(resposta) == tamanho and resposta[0] in aceita:
                    if falhou:
                        print(f'[Motores] comunicação de volta em {time.monotonic() - inicio:.2f} s')
                    return resposta
                problema = f'resposta {list(resposta)}' if resposta else 'sem resposta'
                porta_caiu = False
            except Exception as erro:  # SerialException, OSError, termios.error: a porta caiu
                problema = str(erro) or type(erro).__name__
                porta_caiu = True
            self.falhas_comunicacao += 1
            restante = self.TEMPO_RECUPERACAO - (time.monotonic() - inicio)
            if not repetir or restante <= 0:
                raise Exception(f'{mensagem} ({problema})')
            if not falhou:
                print(f'[Motores] {mensagem}: {problema}. Tentando de novo por até {restante:.1f} s')
            if porta_caiu or falhou:  # na primeira falha sem erro da porta, só manda de novo
                Portas().reabre_porta_serial(self.ser, restante)
            falhou = True

    def move_servo(self, servo, angulo):
        if servo <= 0:
            return
        if servo > 6:
            return
        if self.ventoinha_ativa or self.buzzer_ativo:
            dono = self._DONO_TIMER2[self.TIMER2_VENTOINHA if self.ventoinha_ativa else self.TIMER2_BUZZER]
            raise Exception(f'Servos desativados: o Timer2 do Mariola já está com {dono} '
                            '(reinicie o brick para voltar a usar os servos)')
        angulo = max(angulo, 0)
        angulo = min(angulo, 180)
        self.lista_servos[servo] = angulo
        if self.atualiza_instantaneo:
            self.atualiza_servos()

    def atualiza_servos(self):
        self._conversa(self.lista_servos, 1, (self.ENVIA_SERVOS,), 'Erro ao ler o estado dos servos')
        if any(angulo <= 180 for angulo in self.lista_servos[1:7]):
            self.servos_ativos = True  # o firmware reservou o Timer2 para os servos
        return True

    def atualiza_motores(self):
        pacote = bytes(self.lista_motores)
        estado_antes = self.estado_motores
        self.angulo_motor1 = 0  # assim q envio zero isso pq zerado ele nao anda por angulo
        self.angulo_motor2 = 0
        self.lista_motores[5] = 0
        self.lista_motores[6] = 0
        self.lista_motores[7] = 0
        self.lista_motores[8] = 0
        ja_chegou = None
        if any(pacote[5:9]):  # comando com ângulo: não pode chegar duas vezes
            ja_chegou = lambda: self._comando_ja_chegou(pacote, estado_antes)
        resposta = self._conversa(pacote, 10, (self.ENVIA_MOTORES, self.ATUALIZA_MOTORES),
                                  'Erro ao ler o estado dos motores', ja_chegou=ja_chegou)
        self._le_estado(resposta)
        return True

    def _le_estado(self, resposta):
        self.angulo_absoluto_motor1 = struct.unpack('>i', bytes(resposta[1:5]))[0]
        self.angulo_absoluto_motor2 = struct.unpack('>i', bytes(resposta[5:9]))[0]
        self.estado_motores = resposta[9]

    def _comando_ja_chegou(self, pacote, estado_antes):
        """Depois de uma falha num comando com ângulo. O brick conta o ângulo a partir de onde o motor está,
        então mandar de novo um comando que já tinha chegado dobraria o giro. Pergunta o estado (o ATUALIZA
        não muda nada): se um motor com ângulo estava parado e agora gira, o comando chegou e não vai de
        novo. Motor que já girava antes não dá para saber: o comando vai de novo (no pior caso o giro
        dobra, mas o motor para; sem o comando ele não pararia)."""
        consulta = bytes([self.ATUALIZA_MOTORES]) + pacote[1:]
        resposta = self._conversa(consulta, 10, (self.ATUALIZA_MOTORES,), 'Erro ao ler o estado dos motores',
                                  repetir=False)
        for bits, posicao in ((0, 5), (2, 7)):     # motor 1: bits 0-1 e ângulo em 5-6; motor 2: 2-3 e 7-8
            if any(pacote[posicao:posicao + 2]) and not (estado_antes >> bits) & 0b11 and (resposta[9] >> bits) & 0b11:
                return resposta
        return None

    # funcao que envia informacao mas sem atualizar velocidades do controlador de motor
    def estado(self):
        pacote = bytes([self.ATUALIZA_MOTORES]) + bytes(self.lista_motores[1:])
        resposta = self._conversa(pacote, 10, (self.ATUALIZA_MOTORES,), 'Erro ao ler o estado dos motores')
        self._le_estado(resposta)
        if self.DEBUG:
            print('Estado atualizado')
        return True

    def direcao_motor(self, motor, direcao):
        self.lista_motores[0] = self.ENVIA_MOTORES  # comando para enviar motores como velocidade
        if motor <= 0:
            return
        if motor > 4:
            return
        if direcao == self.NORMAL:
            self.motor_invertido[motor - 1] = False
        else:
            self.motor_invertido[motor - 1] = True
        if self.atualiza_instantaneo:
            self.atualiza_motores()

    def desativa_servo(self, servo):
        if servo <= 0:
            return
        if servo > 6:
            return
        self.lista_servos[servo] = 200  # maior que 180 desativa ele
        if self.atualiza_instantaneo:
            self.atualiza_servos()

    def velocidade_motor(self, motor, velocidade):
        self.lista_motores[0] = self.ENVIA_MOTORES  # comando para enviar motores como velocidade
        if motor <= 0:
            return
        if motor > 4:
            return
        velocidade = max(velocidade, -120)
        velocidade = min(velocidade, 120)
        if self.motor_invertido[motor - 1]:
            velocidade = -velocidade
        self.lista_motores[motor] = struct.pack('b', velocidade)[0]
        if self.atualiza_instantaneo:
            self.atualiza_motores()

    # essa função só move os motores 1 e 2, pois são os únicos que possuem encoder
    def move_motor(self, motor, velocidade, angulo):
        self.lista_motores[0] = self.ENVIA_MOTORES  # comando para enviar motores como velocidade
        angulo = abs(angulo)  # sempre será positivo
        if angulo > 65535:  # erro, nao aceito valores maiores que 65535
            return
        if motor <= 0:
            return
        if motor > 2:
            return
        self.angulo_motor1 = angulo
        if motor == 1:
            posicao_angulo_lista = 5
            self.angulo_motor1 = angulo
        if motor == 2:
            posicao_angulo_lista = 7
            self.angulo_motor2 = angulo
        velocidade = max(velocidade, -120)
        velocidade = min(velocidade, 120)
        if self.motor_invertido[motor - 1]:
            velocidade = -velocidade
        self.lista_motores[motor] = struct.pack('b', velocidade)[0]
        self.lista_motores[posicao_angulo_lista] = (angulo >> 8) & 0xFF  # pego o byte mais significativo
        self.lista_motores[posicao_angulo_lista + 1] = angulo & 0xFF  # pego o byte menos significativo
        if self.atualiza_instantaneo:
            self.atualiza_motores()
            time.sleep(0.05)

    # Função que move os motores 1 e 2 ao mesmo tempo
    # velocidade1 e velocidade2 são os valores de velocidade dos motores, angulo1 e angulo2 são os angulos que os motores devem se mover
    def move_motores(self, velocidade1, angulo1, velocidade2, angulo2):
        self.lista_motores[0] = self.ENVIA_MOTORES  # comando para enviar motores como velocidade
        angulo1 = abs(angulo1)  # sempre será positivo
        if angulo1 > 65535:
            return
        angulo2 = abs(angulo2)  # sempre será positivo
        if angulo2 > 65535:
            return
        motor = 1
        velocidade1 = max(velocidade1, -120)
        velocidade1 = min(velocidade1, 120)
        if self.motor_invertido[motor - 1]:
            velocidade1 = -velocidade1
        self.lista_motores[motor] = struct.pack('b', int(velocidade1))[0]
        motor = 2
        velocidade2 = max(velocidade2, -120)
        velocidade2 = min(velocidade2, 120)
        if self.motor_invertido[motor - 1]:
            velocidade2 = -velocidade2
        self.lista_motores[motor] = struct.pack('b', int(velocidade2))[0]
        self.angulo_motor1 = angulo1
        self.lista_motores[5] = (angulo1 >> 8) & 0xFF  # pego o byte mais significativo
        self.lista_motores[6] = angulo1 & 0xFF
        self.angulo_motor2 = angulo2
        self.lista_motores[7] = (angulo2 >> 8) & 0xFF  # pego o byte mais significativo
        self.lista_motores[8] = angulo2 & 0xFF
        if self.atualiza_instantaneo:
            self.atualiza_motores()
            time.sleep(0.05)

    # Função que move os motores ao mesmo tempo
    # velocidade1 e velocidade2 são os valores de velocidade dos motores, angulo1 e angulo2 são os angulos que os motores devem se mover, os motores sem encoder acompanham os motores com encoder
    def move_motores_4x4(self, velocidade1, angulo1, velocidade2, angulo2):
        self.lista_motores[0] = self.ENVIA_MOTORES_4X4  # comando para enviar motores como velocidade
        angulo1 = abs(angulo1)  # sempre será positivo
        if angulo1 > 65535:
            return
        angulo2 = abs(angulo2)  # sempre será positivo
        if angulo2 > 65535:
            return
        motor = 1
        velocidade1 = max(velocidade1, -120)
        velocidade1 = min(velocidade1, 120)
        if self.motor_invertido[motor - 1]:
            velocidade1 = -velocidade1
        self.lista_motores[motor] = struct.pack('b', int(velocidade1))[0]
        motor = 2
        velocidade2 = max(velocidade2, -120)
        velocidade2 = min(velocidade2, 120)
        if self.motor_invertido[motor - 1]:
            velocidade2 = -velocidade2
        self.lista_motores[motor] = struct.pack('b', int(velocidade2))[0]
        self.angulo_motor1 = angulo1
        self.lista_motores[5] = (angulo1 >> 8) & 0xFF  # pego o byte mais significativo
        self.lista_motores[6] = angulo1 & 0xFF
        self.angulo_motor2 = angulo2
        self.lista_motores[7] = (angulo2 >> 8) & 0xFF  # pego o byte mais significativo
        self.lista_motores[8] = angulo2 & 0xFF
        if self.atualiza_instantaneo:
            self.atualiza_motores()
            time.sleep(0.05)



    # Função que move para sempre os motores 1 e 2 ao mesmo tempo
    # velocidade1 e velocidade2 são os valores de velocidade dos motores
    def velocidade_motores(self, velocidade1, velocidade2):
        self.lista_motores[0] = self.ENVIA_MOTORES  # comando para enviar motores como velocidade
        motor = 1
        velocidade1 = max(velocidade1, -120)
        velocidade1 = min(velocidade1, 120)
        if self.motor_invertido[motor - 1]:
            velocidade1 = -velocidade1
        self.lista_motores[motor] = struct.pack('b', int(velocidade1))[0]
        motor = 2
        velocidade2 = max(velocidade2, -120)
        velocidade2 = min(velocidade2, 120)
        if self.motor_invertido[motor - 1]:
            velocidade2 = -velocidade2
        self.lista_motores[motor] = struct.pack('b', int(velocidade2))[0]
        if self.atualiza_instantaneo:
            self.atualiza_motores()

    # Função que move para sempre os motores 1 e 2 ao mesmo tempo
    # potencia1 e potencia2 são os valores de potencia do pwm dos motores
    def potencia_motores(self, potencia1, potencia2):
        self.lista_motores[0] = self.ENVIA_MOTORES_POTENCIA  # comando para enviar motores como potencia
        motor = 1
        potencia1 = max(potencia1, -100)
        potencia1 = min(potencia1, 100)
        if self.motor_invertido[motor - 1]:
            potencia1 = -potencia1
        self.lista_motores[motor] = struct.pack('b', int(potencia1))[0]
        motor = 2
        potencia2 = max(potencia2, -100)
        potencia2 = min(potencia2, 100)
        if self.motor_invertido[motor - 1]:
            potencia2 = -potencia2
        self.lista_motores[motor] = struct.pack('b', int(potencia2))[0]
        if self.atualiza_instantaneo:
            self.atualiza_motores()


    # Função que move para sempre os motores 1 e 2 ao mesmo tempo e coloca o mesmo valor nos motores 3 e 4 internamente
    # potencia1 e potencia2 são os valores de potencia do pwm dos motores
    def potencia_motores_4x4(self, potencia1, potencia2):
        self.lista_motores[0] = self.ENVIA_MOTORES_4X4_POTENCIA  # comando para enviar motores como potencia
        motor = 1
        potencia1 = max(potencia1, -100)
        potencia1 = min(potencia1, 100)
        if self.motor_invertido[motor - 1]:
            potencia1 = -potencia1
        self.lista_motores[motor] = struct.pack('b', int(potencia1))[0]
        motor = 2
        potencia2 = max(potencia2, -100)
        potencia2 = min(potencia2, 100)
        if self.motor_invertido[motor - 1]:
            potencia2 = -potencia2
        self.lista_motores[motor] = struct.pack('b', int(potencia2))[0]
        if self.atualiza_instantaneo:
            self.atualiza_motores()

    # Função que move para sempre os motores 1 e 2 ao mesmo tempo e coloca o mesmo valor nos motores 3 e 4 internamente
    # velocidade1 e velocidade2 são os valores de velocidade dos motores
    def velocidade_motores_4x4(self, velocidade1, velocidade2):
        self.lista_motores[0] = self.ENVIA_MOTORES_4X4  # comando para enviar motores como velocidade
        motor = 1
        velocidade1 = max(velocidade1, -100)
        velocidade1 = min(velocidade1, 100)
        if self.motor_invertido[motor - 1]:
            velocidade1 = -velocidade1
        self.lista_motores[motor] = struct.pack('b', int(velocidade1))[0]
        motor = 2
        velocidade2 = max(velocidade2, -100)
        velocidade2 = min(velocidade2, 100)
        if self.motor_invertido[motor - 1]:
            velocidade2 = -velocidade2
        self.lista_motores[motor] = struct.pack('b', int(velocidade2))[0]
        if self.atualiza_instantaneo:
            self.atualiza_motores()


    def potencia_motor(self, motor, potencia):
        self.lista_motores[0] = self.ENVIA_MOTORES_POTENCIA  # comando para enviar motores como potencia
        potencia = max(potencia, -100)
        potencia = min(potencia, 100)
        if self.motor_invertido[motor - 1]:
            potencia = -potencia
        self.lista_motores[motor] = struct.pack('b', int(potencia))[0]
        if self.atualiza_instantaneo:
            self.atualiza_motores()


    # para todos os 4 motores (o modo de freio continua o que foi escolhido no set_modo_freio)
    def para_motores(self):
        # Mantém o tipo do último comando. No 4x4 o firmware copia nos motores 3 e 4 tudo o que faz nos
        # motores 1 e 2, inclusive as correções do freio HOLD: antes o para_motores() mandava sempre o
        # comando 4x4, e num robô de duas rodas o motor 3 ou 4 (uma garra, por exemplo) se mexia com o HOLD.
        if self.lista_motores[0] in (self.ENVIA_MOTORES_4X4, self.ENVIA_MOTORES_4X4_POTENCIA):
            self.lista_motores[0] = self.ENVIA_MOTORES_4X4
        else:
            self.lista_motores[0] = self.ENVIA_MOTORES
        for posicao in range(1, 9):  # velocidade dos 4 motores e ângulo dos motores 1 e 2
            self.lista_motores[posicao] = 0
        self.angulo_motor1 = 0
        self.angulo_motor2 = 0
        if self.atualiza_instantaneo:
            self.atualiza_motores()

    def set_modo_freio(self, modo):
        if modo == self.BREAK:
            self.modo_freio = 0
        else:
            self.modo_freio = 1
        self.lista_motores[9] = self.modo_freio
        # if self.atualiza_instantaneo:
        #     self.atualiza_motores()

    def pid_motor(self, kp, ki, kd):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        # Envia os valores de kp, ki e kd como inteiros de 16 bits para a placa usando lista_pid
        # kp, ki, kd devem estar no intervalo 0~65535
        kp = kp * 100  # mando os valores multiplicados por 100 para evitar problemas de precisão
        ki = ki * 100
        kd = kd * 100
        kp = max(0, min(65535, int(kp)))
        ki = max(0, min(65535, int(ki)))
        kd = max(0, min(65535, int(kd)))
        self.lista_pid[1] = (kp >> 8) & 0xFF
        self.lista_pid[2] = kp & 0xFF
        self.lista_pid[3] = (ki >> 8) & 0xFF
        self.lista_pid[4] = ki & 0xFF
        self.lista_pid[5] = (kd >> 8) & 0xFF
        self.lista_pid[6] = kd & 0xFF
        self.ser.write(bytes(self.lista_pid))
        if self.DEBUG:
            print(f"Enviando PID: kp={kp}, ki={ki}, kd={kd} -> {self.lista_pid}")
        time.sleep(0.1)  # aguardo para confirmar as piscadas na placa de alteração
        retorno_serial = self.ser.read(1)
        if self.DEBUG:
            retorno_serial_lista = list(retorno_serial)
            print("retorno_serial (int):", [int(b) for b in retorno_serial_lista])
            # print(f'retorno_serial: {retorno_serial}')
        time.sleep(1) #aguardo para confirmar as piscadas na placa de alteração
        if len(retorno_serial) == 1:
            if retorno_serial[0] == self.ENVIA_PID:
                return True
        raise Exception('Erro ao enviar dados do PID')

    def reseta_angulo_motor(self, motor):  # nao reseto o angulo diretalmente na placa, apenas crio uma diferença
        if motor == 1:
            self.angulo_delta_motor1 = self.angulo_absoluto_motor1
        elif motor == 2:
            self.angulo_delta_motor2 = self.angulo_absoluto_motor2
        else:
            return
        if self.atualiza_instantaneo:
            self.atualiza_motores()

    def angulo_motor(self, motor):  # sempre vou retornar a subtração pelo Delta, e o angulo_absoluto real sempre será transparente para o usuario
        if motor == 1:
            if self.motor_invertido[0]:
                return -self.angulo_absoluto_motor1 + self.angulo_delta_motor1
            return self.angulo_absoluto_motor1 - self.angulo_delta_motor1
        elif motor == 2:
            if self.motor_invertido[1]:
                return -self.angulo_absoluto_motor2 + self.angulo_delta_motor2
            return self.angulo_absoluto_motor2 - self.angulo_delta_motor2
        else:
            return 0

    def estado_motor(self, motor):
        if motor == 1:
            return self.estado_motores & 0b11
        elif motor == 2:
            return (self.estado_motores >> 2) & 0b11
        else:
            return 0

    def set_led_rgb_all(self, r, g, b):
        self.lista_led[0] = self.LED_RGB_ALL
        self.lista_led[1] = r & 0xFF
        self.lista_led[2] = g & 0xFF
        self.lista_led[3] = b & 0xFF
        self.lista_led[4] = 0  # reservado para futuro uso
        self.lista_led[5] = 0  # reservado para futuro uso
        self.lista_led[6] = 0  # reservado para futuro uso
        self.lista_led[7] = 0  # reservado para futuro uso
        self.lista_led[8] = 0  # reservado para futuro uso
        self.lista_led[9] = 0  # reservado para futuro uso
        self._conversa(self.lista_led, 1, (self.LED_RGB_ALL,), 'Erro ao enviar dados do LED RGB ALL')
        return True
    
    def set_led_rgb_one(self, index, r, g, b):
        self.lista_led[0] = self.LED_RGB_ONE
        self.lista_led[1] = r & 0xFF
        self.lista_led[2] = g & 0xFF
        self.lista_led[3] = b & 0xFF
        if(index > 9):  # o firmware tem 10 LEDs (0 a 9)
            index = 9
        elif(index < 0):
            index = 0
        self.lista_led[4] = index
        self.lista_led[5] = 0  # reservado para futuro uso
        self.lista_led[6] = 0  # reservado para futuro uso
        self.lista_led[7] = 0  # reservado para futuro uso
        self.lista_led[8] = 0  # reservado para futuro uso
        self.lista_led[9] = 0  # reservado para futuro uso
        self._conversa(self.lista_led, 1, (self.LED_RGB_ONE,), 'Erro ao enviar dados do LED RGB ONE')
        return True

    # A porta 4 de servo/led (pino 17) pode ser servo ou uma segunda fita de LEDs WS2812B (10 LEDs).
    # O firmware decide pelo último comando: um comando de LED da porta 4 desliga o servo 4 e liga a
    # fita; mandar o servo 4 para um ângulo (0 a 180) apaga a fita e volta a porta para servo.
    def set_led_rgb_all_porta4(self, r, g, b):
        return self._envia_led_porta4(self.LED_RGB_ALL_PORTA4, r, g, b, 0)

    def set_led_rgb_one_porta4(self, index, r, g, b):
        index = max(0, min(index, self.NUM_LEDS_PORTA4 - 1))
        return self._envia_led_porta4(self.LED_RGB_ONE_PORTA4, r, g, b, index)

    def _envia_led_porta4(self, comando, r, g, b, index):
        # a porta virou fita de LEDs: o servo 4 fica desativado na lista, senão o próximo
        # atualiza_servos() mandaria o ângulo antigo e a porta voltaria a ser servo
        self.lista_servos[4] = 200
        self.lista_led[0] = comando
        self.lista_led[1] = r & 0xFF
        self.lista_led[2] = g & 0xFF
        self.lista_led[3] = b & 0xFF
        self.lista_led[4] = index  # só o LED_RGB_ONE_PORTA4 usa
        for i in range(5, 10):
            self.lista_led[i] = 0  # reservado para futuro uso
        self._conversa(self.lista_led, 1, (comando,), 'Erro ao enviar dados do LED RGB da porta 4')
        return True

    def obtem_calibracao_motores(self):
        # o comando vai num pacote à parte: antes ele ficava no lista_motores[0], e o próximo
        # atualiza_motores() sem um velocidade_...() antes mandava o pedido de calibração de novo
        pacote = bytes([self.OBTEM_CALIBRACAO_MOTORES]) + bytes(self.lista_motores[1:])
        resposta = self._conversa(pacote, 10, (self.OBTEM_CALIBRACAO_MOTORES,), 'Erro ao ler a calibração dos motores')
        calibracao_motor1 = struct.unpack('>i', bytes(resposta[1:5]))[0]
        calibracao_motor2 = struct.unpack('>i', bytes(resposta[5:9]))[0]
        self._byte_estado_calibracao = resposta[9]
        return calibracao_motor1, calibracao_motor2

    # resultado da última calibração feita desde que o brick ligou (bits 2-3 de cada motor)
    RESULTADO_CALIBRACAO = ('ok', 'o encoder não contou', 'contou para o mesmo lado nos dois sentidos',
                            'um sentido bem mais lento que o outro')

    def estado_calibracao_motores(self):
        """Estado da calibração dos motores 1 e 2 (firmware de 10/11/2026 em diante).

        Devolve uma lista com um dicionário por motor:
          'calibrado': True se há calibração válida em uso (sem ela o motor não usa o encoder);
          'encoder_invertido': True se, na calibração, o encoder contou ao contrário do motor
              (motor ou encoder ligado invertido). O brick já corrige sozinho: é só um aviso;
          'resultado': 'ok' ou o que deu errado na última calibração feita desde que o brick ligou
              ('o encoder não contou' = motor ou encoder desligado, ou um canal do encoder solto;
              nesse caso a calibração nova não é gravada).
        Com firmware antigo, que não informa o estado, devolve None."""
        calibracao = self.obtem_calibracao_motores()
        estado = self._byte_estado_calibracao
        motores = []
        for i in range(2):
            bits = (estado >> (4 * i)) & 0x0F
            if calibracao[i] != 0 and not bits & 0x01:
                return None  # firmware antigo: esse byte era o estado dos motores
            motores.append({'calibrado': bool(bits & 0x01), 'encoder_invertido': bool(bits & 0x02),
                            'resultado': self.RESULTADO_CALIBRACAO[(bits >> 2) & 0x03]})
        return motores
    
    def calibra_motores(self):
        """Manda o brick calibrar os motores 1 e 2 (rodas no ar: eles giram sozinhos por ~30 s e o brick
        não responde nesse tempo). A calibração também descobre se o encoder conta ao contrário do motor
        e corrige. Depois dos 30 s, estado_calibracao_motores() diz como foi."""
        # uma tentativa só: se o pedido chegou, o brick fica ~30 s calibrando sem responder
        pacote = bytes([self.CALIBRA_MOTORES]) + bytes(self.lista_motores[1:])
        self._conversa(pacote, 1, (self.CALIBRA_MOTORES,), 'Erro ao calibrar os motores', repetir=False)
        print('Calibração dos motores iniciada, aguarde...')
        return True

    # Ventoinha no pino 11 (o TX do serialDebug), PWM do Timer2 a ~976 Hz.
    # Servos, ventoinha e buzzer dividem o Timer2: o primeiro que for usado fica com ele até o brick
    # reiniciar. Se a ventoinha for a primeira, o firmware desliga TODOS os servos e o serialDebug.
    # O timeout de 5 s do firmware NÃO desliga a ventoinha: ela fica girando até receber potência 0.
    def set_ventoinha(self, potencia):  # potencia de 0 a 100 (%)
        if self.servos_ativos or self.buzzer_ativo:
            dono = self._DONO_TIMER2[self.TIMER2_SERVOS if self.servos_ativos else self.TIMER2_BUZZER]
            raise Exception(f'Ventoinha indisponível: o Timer2 do Mariola já está com {dono} '
                            '(reinicie o brick para usar a ventoinha)')
        potencia = max(0, min(potencia, 100))
        pwm = round(potencia * 255 / 100)
        self.ventoinha_ativa = True
        for servo in range(1, 7):
            self.lista_servos[servo] = 200  # o firmware já desligou os servos
        lista = [self.ATIVA_VENTOINHA, pwm, 0, 0, 0, 0, 0, 0, 0, 0]
        self._conversa(lista, 1, (self.ATIVA_VENTOINHA,), 'Erro ao enviar dados da ventoinha')
        return True

    def desliga_ventoinha(self):
        return self.set_ventoinha(0)

    # Buzzer no pino 11 (PB3), gerado pelo Timer2. Tudo é feito pelo firmware sem travar a placa:
    # depois de mandar o som o programa continua na hora, e os motores seguem funcionando enquanto ele toca.
    # Servos, ventoinha e buzzer dividem o Timer2: o primeiro que for usado fica com ele até o brick
    # reiniciar. Se o buzzer for o primeiro, o firmware desliga TODOS os servos e o serialDebug.

    # Toca um dos sons prontos (SOM_... ou MELODIA_...).
    # vezes: quantas vezes toca (0 = repete até chamar para_buzzer())
    # velocidade: % do andamento original (100 = normal, 200 = duas vezes mais rápido, 50 = metade), de 10 a 255
    # esperar: True espera o som terminar antes de voltar
    def toca_som(self, som, vezes=1, velocidade=100, esperar=False):
        if som < 1 or som > self.QUANTIDADE_SONS:
            raise ValueError(f'Som {som} não existe (use de 1 a {self.QUANTIDADE_SONS})')
        if vezes == 0 and esperar:
            raise ValueError('Com vezes=0 o som repete para sempre: não dá para esperar ele terminar')
        repeticoes = 255 if vezes == 0 else max(0, min(int(vezes) - 1, 254))
        velocidade = max(10, min(int(velocidade), 255))
        self._envia_buzzer([self.TOCA_SOM, som, repeticoes, velocidade, 0, 0, 0, 0, 0, 0])
        if esperar:
            self.espera_buzzer()
        return True

    # Toca um tom de 'frequencia' Hz (31 a 20000) por 'duracao_ms' milissegundos (até 65535).
    def toca_tom(self, frequencia, duracao_ms, esperar=False):
        frequencia = max(0, min(int(frequencia), 20000))
        duracao_ms = max(0, min(int(duracao_ms), 65535))
        self._envia_buzzer([self.TOCA_BUZZER,
                            (frequencia >> 8) & 0xFF, frequencia & 0xFF,
                            (duracao_ms >> 8) & 0xFF, duracao_ms & 0xFF,
                            0, 0, 0, 0, 0])
        if esperar:
            self.espera_buzzer()
        return True

    # Para o som. Pode chamar sempre: o firmware não reserva o Timer2 para o buzzer só por causa do
    # comando de parar (se o Timer2 for dos servos ou da ventoinha, não muda nada).
    def para_buzzer(self):
        self._envia_buzzer([self.TOCA_SOM, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        return True

    # True enquanto o buzzer estiver tocando
    def buzzer_tocando(self):
        tocando, _ = self._envia_buzzer([self.CONSULTA_BUZZER, 0, 0, 0, 0, 0, 0, 0, 0, 0])
        return tocando == 1

    # Nível que liga o buzzer: BUZZER_LIGA_LOW (padrão) ou BUZZER_LIGA_HIGH. Fica salvo na EEPROM do
    # Mariola, então só precisa configurar uma vez por brick. Não reserva o Timer2.
    def set_nivel_buzzer(self, nivel):
        if nivel not in (self.BUZZER_LIGA_LOW, self.BUZZER_LIGA_HIGH):
            raise ValueError('Use Motores.BUZZER_LIGA_LOW ou Motores.BUZZER_LIGA_HIGH')
        salvo, _ = self._envia_buzzer([self.CONFIGURA_BUZZER, nivel, 0, 0, 0, 0, 0, 0, 0, 0])
        if salvo != nivel:
            raise Exception('Erro ao salvar o nível do buzzer')
        return True

    def nivel_buzzer(self):
        nivel, _ = self._envia_buzzer([self.CONFIGURA_BUZZER, 0xFF, 0, 0, 0, 0, 0, 0, 0, 0])  # 0xFF = só consulta
        return nivel

    # Espera o som atual terminar. timeout em segundos (None = sem limite); retorna False se estourou
    def espera_buzzer(self, timeout=None):
        inicio = time.monotonic()
        while self.buzzer_tocando():
            if timeout is not None and time.monotonic() - inicio > timeout:
                return False
            time.sleep(0.05)
        return True

    # Envia um comando do buzzer. O firmware responde [comando, status, modo do Timer2].
    def _envia_buzzer(self, lista):
        comando = lista[0]
        retorno_serial = self._conversa(lista, 3, (comando,), 'Erro ao enviar dados do buzzer')
        status = retorno_serial[1]
        modo = retorno_serial[2]
        if comando in (self.CONSULTA_BUZZER, self.CONFIGURA_BUZZER):
            return status, modo
        if status == self._BUZZER_SOM_INVALIDO:
            raise ValueError('Som inválido para o firmware do Mariola')
        if status == self._BUZZER_RECUSADO:
            dono = self._DONO_TIMER2.get(modo, f'o modo {modo}')
            raise Exception(f'Buzzer indisponível: o Timer2 do Mariola já está com {dono} '
                            '(reinicie o brick para usar o buzzer)')
        if modo == self.TIMER2_BUZZER and not self.buzzer_ativo:
            self.buzzer_ativo = True
            for servo in range(1, 7):
                self.lista_servos[servo] = 200  # o firmware já desligou os servos
        return status, modo