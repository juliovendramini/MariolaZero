#Atualmente ainda é necessário inserir os arquivos python das bibliotecas que serão utilizadas dentro do projeto
#Futuramente, quando tudo estiver estável, isso não será mais necessário
#Exemplo de uso do giroscopio
from time import sleep
from portas import Portas
from vl53 import VL53L0X
from tcs34725 import TCS34725

sensor1 = VL53L0X(Portas.I2C1)
sensor1_cor = TCS34725(Portas.I2C1)
try:   
    while(True):
        # velocidade = int(input("Digite a velocidade dos motores (1-100): "))
        print(sensor1.read_range_single_millimeters())
        print(sensor1_cor.le_valores())
        #sleep(0.5)
        # motores.velocidade_motores(velocidade, velocidade)
        #o código de calibração não precisa ser executado todas as vezes... Uma vez o giroscópio no lugar e calibrado, não é necessário repetir
        # if(giroscopio.calibra()):
        #     print("Giroscópio calibrado com sucesso!")
        # else:
        #     print("Falha na calibração do giroscópio.")


#Essa parte do código é responsável por lidar com a interrupção do programa quando no terminal apertamos Ctrl+C 
#ou interrompemos o programa pelo teclado do brick
except KeyboardInterrupt as e:
    print("\nInterrupção detectada! Parando os motores e encerrando...")
    print("Programa encerrado com segurança.")

