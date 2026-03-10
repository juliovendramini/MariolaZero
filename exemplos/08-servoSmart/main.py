#Atualmente ainda é necessário inserir os arquivos python das bibliotecas que serão utilizadas dentro do projeto
#Futuramente, quando tudo estiver estável, isso não será mais necessário
#Exemplo de uso do giroscopio
import random
from time import sleep
from portas import Portas
from motores import Motores
from placaControleServo import PlacaControleServo

servo1 = PlacaControleServo(Portas.SERIAL1, id_equipamento=1)
posicao = 0
potencia = 128
try:   
    while(True):
        # resultado = servo1.move_servo(512, 0, 5)
        # print(resultado)
        # continue
        #leio do terminal a posição desejada do servo, a potência e a zona morta
        # posicao = int(input("Digite a posição desejada do servo (0-1023): "))
        # potencia = int(input("Digite a potência desejada (0-255): "))
        # zona_morta = int(input("Digite a zona morta desejada (0-255): "))
        potencia = 100
        zona_morta = 8
        posicao = 100
        resultado = servo1.move_servo(posicao, potencia, zona_morta)
        # while(abs(resultado - posicao) > zona_morta):
        #     print(resultado)
        #     resultado = servo1.move_servo(posicao, potencia, zona_morta)
        sleep(2)
        posicao = 900
        resultado = servo1.move_servo(posicao, potencia, zona_morta)
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

