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
from vl53 import VL53L0X


motores = Motores(True)
motores.direcaoMotor(2, motores.NORMAL)
motores.direcaoMotor(1, motores.INVERTIDO)
# motores.modoFreio(motores.HOLD)

sensorCor = CorReflexao(Portas.SERIAL1)
#placaMuxLaser = PlacaMuxVl53l0x(Portas.SERIAL3)
giroscopio = Giroscopio(Portas.SERIAL2)
#placaMuxCor = PlacaMuxTCS34725(Portas.SERIAL4)

#giroscopio.calibra()

velocidadeMotor1 = 80
velocidadeMotor2 = 80
posicaoServo1 = 0
tela = Tela()
teclado = Teclado()
teclado.botaoParaEncerrarPrograma(Teclado.ESC)
tela.escreve("teste")

distanciaFrente = VL53L0X(Portas.I2C1)
distanciaFrente.read_range_single_millimeters()
#giroscopio: X e o eixo q usa na rampa, Z e o eixo q usa nos giros

def apagarTodosLeds():
    teclado.alteraLed(1,0)
    teclado.alteraLed(2,0)
    teclado.alteraLed(3,0)
    teclado.alteraLed(4,0)