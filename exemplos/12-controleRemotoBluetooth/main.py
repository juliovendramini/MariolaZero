from time import sleep
from portas import Portas
from controleRemotoBluetooth import ControleRemotoBluetooth

ctrl = ControleRemotoBluetooth(Portas.SERIAL3)
ctrl.DEBUG = False

print("Aguardando dados do controle... (Ctrl+C para sair)\n")

try:
    while True:
        e = ctrl.estado()
        #print(f"frente_tras={e['frente_tras']:+4d}  esquerda_direita={e['esquerda_direita']:+4d}")
        velocidade_base = e['frente_tras']
        ajuste_direcao = e['esquerda_direita']
        print(f"Velocidade base: {velocidade_base:+4d}  Ajuste direção: {ajuste_direcao:+4d}")
        potencia_motor1 = velocidade_base + ajuste_direcao
        potencia_motor2 = velocidade_base - ajuste_direcao
        print(potencia_motor1, potencia_motor2)
        sleep(0.1)
except KeyboardInterrupt:
    print("\nEncerrando...")
    ctrl.parar()

# print("\nBuscando Servos:")
# servos = PlacaControleServo.buscar_servos(Portas.SERIAL1)
# print("Servos encontrados:")
# for servo in servos:
#     print(f"ID: {servo['id']}, Posição: {servo['posicao']}")
# exit()



#id 67 e 71
portas = Portas()
portaSerialbarramento = portas.abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
motor1 = PlacaControleMotor(portaSerialbarramento, id_equipamento=5)
motor2 = PlacaControleMotor(portaSerialbarramento, id_equipamento=72)
posicao = 0
potencia = 0
zona_morta = 5

motores = Motores(True);
motores.direcao_motor(2, Motores.INVERTIDO)
# calibracao = motor1.calibrar()
# print(calibracao)
# calibracao = motor2.calibrar()
# print(calibracao)
#motor1.set_freio(PlacaControleMotor.FREIO_TRAVADO)


resultado = motor1.reset()
print(resultado)
resultado = motor2.reset()
print(resultado)

motor1.direcao_motor(Motores.INVERTIDO)

# print("-------------------------------------")
# resultado = motor1.obter_calibracao();
# print(resultado)
# resultado = motor2.obter_calibracao();
# print(resultado)


# print("alterando calibração do motor 1")
# motor1.calibracao_manual(32,-32)

resultado = motores.obtem_calibracao_motores()
print(resultado)
# motores.calibra_motores();
# exit()
sleep(0.5)
motores.set_modo_freio(Motores.HOLD)
motor1.set_freio(PlacaControleMotor.FREIO_TRAVADO)
motor2.set_freio(PlacaControleMotor.FREIO_TRAVADO)
motor1.set_kp_freio(3)
motor1.set_kd_freio(10)
motor2.set_kp_freio(3)
motor2.set_kd_freio(10)
motor1.set_delta_freio(20)
motor2.set_delta_freio(20)
motor1.pid_motor(2,2,2)
motor1.calibrar();
try:   
    
    #motor1.reseta_angulo_motor()
    #resultado = motor1.move_motor(50, 2000)
    
    import time
    import threading

    while True:
        resultado1 = motor1.velocidade_motor(15)
        print(resultado1)
        sleep(0.5)

    contador = 0
    tempo_inicio = time.time()
    while True:
        resultado1 = motor1.move_motor(0, 0)
        resultado2 = motor2.move_motor(0, 0)
        print(resultado1, resultado2)    
    while(True):
        contador+=1
        t = threading.Thread(target=motores.potencia_motores, args=(50, 50))
        t.start()
        resultado = motor1.potencia_motor(50)
        t.join()
        resultado = motor2.potencia_motor(50)
        # print("----------")
        tempo_atual = time.time()
        if tempo_atual - tempo_inicio >= 1.0:
            print(f"Loops por segundo: {contador}")
            contador = 0
            tempo_inicio = tempo_atual
        # sleep(0.3)
    while(True):
        # resultado = motor1.move_motor(512, 0, 5)
        # print(resultado)
        # continue
        #leio do terminal a posição desejada do servo, a potência e a zona morta
        # posicao = int(input("Digite a posição desejada do servo (0-1023): "))
        # potencia = int(input("Digite a potência desejada (0-255): "))
        # zona_morta = int(input("Digite a zona morta desejada (0-255): "))
        potencia = 100
        zona_morta = 8
        posicao1 = 100
        posicao2 = 900
        resultado = servo1.move_servo(posicao1, potencia, zona_morta)
        servo2.move_servo(posicao2, potencia, zona_morta)
        # while(abs(resultado - posicao) > zona_morta):
        #     print(resultado)
        #     resultado = servo1.move_servo(posicao, potencia, zona_morta)
        sleep(2)
        posicao1 = 900
        posicao2 = 100
        resultado = servo1.move_servo(posicao1, potencia, zona_morta)
        servo2.move_servo(posicao2, potencia, zona_morta)
        # while(abs(resultado - posicao) > zona_morta):
        #     print(resultado)
        #     resultado = servo1.move_servo(posicao, potencia, zona_morta)
        sleep(2)
        sleep(0.3)

#Essa parte do código é responsável por lidar com a interrupção do programa quando no terminal apertamos Ctrl+C 
#ou interrompemos o programa pelo teclado do brick
except KeyboardInterrupt as e:
    motores.para_motores()
    motor1.para_motor()
    motor2.para_motor()
    print("\nInterrupção detectada! Parando os motores e encerrando...")
    print("Programa encerrado com segurança.")

