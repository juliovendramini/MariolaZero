#Atualmente ainda é necessário inserir os arquivos python das bibliotecas que serão utilizadas dentro do projeto
#Futuramente, quando tudo estiver estável, isso não será mais necessário
#Exemplo de uso do giroscopio
from time import sleep
from portas import Portas
from giroscopio import Giroscopio

giroscopio = Giroscopio(Portas.SERIAL4)

#Declaração das bibliotecas que serão usadas
giroscopio.set_modo(giroscopio.GYRO)

try:   
    #o código de calibração não precisa ser executado todas as vezes... Uma vez o giroscópio no lugar e calibrado, não é necessário repetir
    # if(giroscopio.calibra()):
    #     print("Giroscópio calibrado com sucesso!")
    # else:
    #     print("Falha na calibração do giroscópio.")
    while(True):
        print(giroscopio.le_angulo_z())
        print(giroscopio.le_angulo_y())
        print(giroscopio.le_angulo_x())
        sleep(1)

#Essa parte do código é responsável por lidar com a interrupção do programa quando no terminal apertamos Ctrl+C 
#ou interrompemos o programa pelo teclado do brick
except KeyboardInterrupt as e:
    print("\nInterrupção detectada! Parando os motores e encerrando...")
    print("Programa encerrado com segurança.")

