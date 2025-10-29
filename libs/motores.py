# Classe para controlar os motores e servos da placa do Motores do novo brick
import struct
import time

from portas import Portas


class Motores:
    motor_invertido = [False, False, False, False]
    DEBUG = True
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

    def __init__(self, atualiza_instantaneo=False):
        #qualquer lista que for enviada deve ter o mesmo tamanho sempre. Para evitar problemas de sincronismo
        self.lista_servos = [self.ENVIA_SERVOS, 200, 200, 200, 200, 200, 200, 0, 0, 0]
        self.lista_motores = [self.ENVIA_MOTORES, 0, 0, 0, 0, 0, 0, 0, 0, 0]
        self.lista_pid = [self.ENVIA_PID, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
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
        self.para_motores()
        self.ser.close()
        if self.DEBUG:
            print('Fechando a porta serial do motores')

    def move_servo(self, servo, angulo):
        if servo <= 0:
            return
        if servo > 6:
            return
        angulo = max(angulo, 0)
        angulo = min(angulo, 180)
        self.lista_servos[servo] = angulo
        if self.atualiza_instantaneo:
            self.atualiza_servos()

    def atualiza_servos(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes(self.lista_servos))
        if self.DEBUG:
            print(f'Enviando: {self.lista_servos}')
        retorno_serial = self.ser.read(1)
        if self.DEBUG:
            retorno_serial_lista = list(retorno_serial)
            print("retorno_serial (int):", [int(b) for b in retorno_serial_lista])
            # print(f'retorno_serial: {retorno_serial}')
        if len(retorno_serial) == 1:
            if retorno_serial[0] == self.ENVIA_SERVOS:
                return True
        raise Exception('Erro ao ler o estado dos servos')

    def atualiza_motores(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes(self.lista_motores))
        if self.DEBUG:
            print(f'Enviando: {self.lista_motores}')
        self.angulo_motor1 = 0  # assim q envio zero isso pq zerado ele nao anda por angulo
        self.angulo_motor2 = 0
        self.lista_motores[5] = 0
        self.lista_motores[6] = 0
        self.lista_motores[7] = 0
        self.lista_motores[8] = 0
        # leio o retorno da serial e salvo na lista

        retorno_serial = self.ser.read(10)
        if self.DEBUG:
            retorno_serial_lista = list(retorno_serial)
            print("retorno_serial (int):", [int(b) for b in retorno_serial_lista])
            # print(f'retorno_serial: {retorno_serial}')
        if len(retorno_serial) == 10:  # só leio se o retorno for exatamente 10 bytes
            if retorno_serial[0] == self.ENVIA_MOTORES:
                self.angulo_absoluto_motor1 = struct.unpack('>i', bytes(retorno_serial[1:5]))[0]
                self.angulo_absoluto_motor2 = struct.unpack('>i', bytes(retorno_serial[5:9]))[0]
                self.estado_motores = retorno_serial[9]
                return True
        raise Exception('Erro ao ler o estado dos motores')

    # funcao que envia informacao mas sem atualizar velocidades do controlador de motor
    def estado(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        temp = self.lista_motores[0]
        self.lista_motores[0] = self.ATUALIZA_MOTORES
        self.ser.write(bytes(self.lista_motores))
        if self.DEBUG:
            print(f'Enviando: {self.lista_motores}')
        self.lista_motores[0] = temp
        # leio o retorno da serial e salvo na lista
        retorno_serial = self.ser.read(10)
        if self.DEBUG:
            retorno_serial_lista = list(retorno_serial)
            print("retorno_serial (int):", [int(b) for b in retorno_serial_lista])
            # print(f'retorno_serial: {retorno_serial}')
        if len(retorno_serial) == 10:  # só leio se o retorno for exatamente 10 bytes
            if retorno_serial[0] == self.ATUALIZA_MOTORES:
                self.angulo_absoluto_motor1 = struct.unpack('>i', bytes(retorno_serial[1:5]))[0]
                self.angulo_absoluto_motor2 = struct.unpack('>i', bytes(retorno_serial[5:9]))[0]
                self.estado_motores = retorno_serial[9]
                if self.DEBUG:
                    print('Estado atualizado')
                return True
        raise Exception('Erro ao ler o estado dos motores')

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
        self.lista_motores[0] = self.ENVIA_MOTORES_4X4_VELOCIDADE  # comando para enviar motores como velocidade
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


    # para todos os 4 motores
    def para_motores(self):
        self.lista_motores[3] = 0
        self.lista_motores[4] = 0
        self.move_motores(0, 1, 0, 1)
        return
        self.lista_motores[0] = 0xFC
        self.lista_motores[1] = 0
        self.lista_motores[2] = 0
        self.lista_motores[3] = 0
        self.lista_motores[4] = 0
        self.lista_motores[5] = 0
        self.lista_motores[6] = 0
        self.lista_motores[7] = 0
        self.lista_motores[8] = 0
        self.lista_motores[9] = 0
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
        if self.atualiza_instantaneo:
            self.atualiza_motores()

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
