#Atualmente ainda é necessário inserir os arquivos python das bibliotecas que serão utilizadas dentro do projeto
#Futuramente, quando tudo estiver estável, isso não será mais necessário
#Exemplo de uso do giroscopio
import random
from time import sleep
from portas import Portas
from motores import Motores
from placaControleMotor import PlacaControleMotor
import portas

# servos = PlacaControleServo.buscar_servos(Portas.SERIAL1)
# print("Servos encontrados:")
# for servo in servos:
#     print(f"ID: {servo['id']}, Posição: {servo['posicao']}")

# motores = PlacaControleMotor.buscar_motores(Portas.SERIAL1)
# print("Motores encontrados:")
# for motor in motores:
#     print(f"ID: {motor['id']}, Posição: {motor['posicao']}")
# exit()

#id 67 e 71
portas = Portas()
portaSerialbarramento = portas.abre_porta_serial(Portas.SERIAL1, 115200, timeout=0.005)
motor1 = PlacaControleMotor(portaSerialbarramento, id_equipamento=67)
motor2 = PlacaControleMotor(portaSerialbarramento, id_equipamento=71)
posicao = 0
potencia = 0
zona_morta = 5

motores = Motores(True);

# calibracao = motor2.calibrar()
# print(calibracao)
#motor1.set_freio(PlacaControleMotor.FREIO_TRAVADO)
resultado = motor1.reset()
print(resultado)
resultado = motor2.reset()
print(resultado)

print("-------------------------------------")
resultado = motor1.obter_calibracao();
print(resultado)
resultado = motor2.obter_calibracao();
print(resultado)
try:   
    
    #motor1.reseta_angulo_motor()
    #resultado = motor1.move_motor(50, 2000)
    
    import time
    contador = 0
    tempo_inicio = time.time()
    
    while(True):
        motores.velocidade_motores(50, 50)
        resultado = motor1.velocidade_motor(50)
        resultado = motor2.velocidade_motor(50)
        tempo_atual = time.time()
        contador += 1
        
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
        zona_morta =8
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
    print("\nInterrupção detectada! Parando os motores e encerrando...")
    print("Programa encerrado com segurança.")

