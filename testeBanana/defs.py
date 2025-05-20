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
motores.direcaoMotor(2, motores.INVERTIDO)
motores.direcaoMotor(1, motores.NORMAL)


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
teclado.botaoParaEncerrarPrograma(Teclado.ENTER)
tela.escreve("teste")