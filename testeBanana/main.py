# Imports necessários para a comunicação serial
from motores import Motores
from time import time, sleep
from cronometro import Cronometro
from sensorCorReflexao import CorReflexao
from giroscopio import Giroscopio
from placaMuxVl53l0x import PlacaMuxVl53l0x
from placaMuxTCS34725 import PlacaMuxTCS34725
from portas import Portas
from teclado import Teclado
from tela import Tela
from tcs import TCS34725
motores = Motores(True)
motores.direcaoMotor(2,Motores.INVERTIDO)
motores.modoFreio(Motores.HOLD)
sensorCor = CorReflexao(Portas.SERIAL1)
#placaMuxLaser = PlacaMuxVl53l0x(Portas.SERIAL3)
giroscopio = Giroscopio(Portas.SERIAL2)
#placaMuxCor = PlacaMuxTCS34725(Portas.SERIAL4)

#giroscopio.calibra()



velocidadeMotor1 = 100
velocidadeMotor2 = 100
posicaoServo1 = 0
tela = Tela()
teclado = Teclado()
teclado.botaoParaEncerrarPrograma(Teclado.ENTER)
tela.escreve("teste")

# sensorTCS1 = TCS34725(Portas.I2C1)
# motores.velocidadeMotor(1, velocidadeMotor1)
# motores.velocidadeMotor(2, velocidadeMotor2)
# sleep(1)
# velocidadeMotor1 = 0
# velocidadeMotor2 = 0
# # motores.velocidadeMotor(1, velocidadeMotor1)
# # motores.velocidadeMotor(2, velocidadeMotor2)
# motores.velocidadeMotores(velocidadeMotor1, velocidadeMotor2)
# sensorCor.calibraBranco();
# sleep(2)
# sensorCor.calibraPreto();
# sleep(2)

try:   
    while True:

        # print(placaMuxCor.leSensor(0))
        print(sensorCor.leReflexao())
        # print(giroscopio.leAnguloX())
        # print(sensorTCS1.leValores())
        if(teclado.botaoPressionado(Teclado.ESC)):
            break
        # if(teclado.botaoPressionado(Teclado.BAIXO)):
        #     tela.escreve("Baixo",2)
        # else:
        #     tela.apaga(2)
        # if(teclado.botaoPressionado(Teclado.CIMA)):
        #     tela.escreve("Cima",1)
        # else:
        #     tela.apaga(1)
        # velocidadeMotor1 = int(input("Digite a velocidade do motor 1 (0-255): "))
        # velocidadeMotor2 = int(input("Digite a velocidade do motor 2 (0-255): "))
        # posicaoServo1 = int(input("Digite a posição do servo 1 (0-180): "))
        # motores.velocidadeMotor(1, velocidadeMotor1)
        # motores.velocidadeMotor(2, velocidadeMotor2)
        # motores.moveServo(1, 0)
        # motores.moveServo(2, 0)
        # sleep(0.5)
        # motores.moveServo(1, 90)
        # motores.moveServo(2, 90)
        # sleep(0.5)
        # motores.moveServo(1, 180)
        # motores.moveServo(2, 180)
        # sleep(0.5)
        # motores.moveServo(1, 90)
        # motores.moveServo(2, 90)
        # sleep(0.5)



except KeyboardInterrupt as e:
    print("\nInterrupção detectada! Parando os motores e encerrando...")
    # Parar os motores
    motores.velocidadeMotor(1, 0)
    motores.velocidadeMotor(2, 0)
    #desativo todos os servos
    motores.desativaServo(1)
    motores.desativaServo(2)
    motores.desativaServo(3)
    motores.desativaServo(4)
    motores.desativaServo(5)
    motores.desativaServo(6)
    print("Programa encerrado com segurança.")
#    subprocess.run(["killall python3", None], check=True)

