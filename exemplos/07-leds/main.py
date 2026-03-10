#Atualmente ainda é necessário inserir os arquivos python das bibliotecas que serão utilizadas dentro do projeto
#Futuramente, quando tudo estiver estável, isso não será mais necessário
#Exemplo de uso do giroscopio
import random
from time import sleep
from portas import Portas
from motores import Motores

motores = Motores(True)
motores.direcao_motor(1, Motores.INVERTIDO)
motores.direcao_motor(3, Motores.INVERTIDO)
motores.set_modo_freio(Motores.HOLD)
r=g=b=0;
index = 0;

def piscaLed(led, cor, delay):
    for i in range(5):
        motores.set_led_rgb_one(led, *cor)
        sleep(delay)
        motores.set_led_rgb_one(led, 0,0,0)
        sleep(delay)

piscaLed(0, (0,127,0), 0.5)

try:   
    while(True):
        # velocidade = int(input("Digite a velocidade dos motores (1-100): "))
        #print("enviando comando para motor 1")
        #motores.estado()
        # print(motores.angulo_motor(2))
        #motores.velocidade_motores_4x4(50,50);

        # r=b=g=g+10
        # if g>255:
        #     g=0
        #     r=0
        #     b=0
        r = random.randint(0,255)
        g = random.randint(0,255)
        b = random.randint(0,255)
        #motores.set_led_rgb_all(r,g,b);
        motores.set_led_rgb_one(index, r, g, b)
        index = (index + 1) % 8 # só ta com 8    
        sleep(0.3)

#Essa parte do código é responsável por lidar com a interrupção do programa quando no terminal apertamos Ctrl+C 
#ou interrompemos o programa pelo teclado do brick
except KeyboardInterrupt as e:
    motores.para_motores()
    print("\nInterrupção detectada! Parando os motores e encerrando...")
    print("Programa encerrado com segurança.")

