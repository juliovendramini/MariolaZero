#Atualmente ainda é necessário inserir os arquivos python das bibliotecas que serão utilizadas dentro do projeto
#Futuramente, quando tudo estiver estável, isso não será mais necessário
#Exemplo de uso do giroscopio
from time import sleep
from portas import Portas
from motores import Motores

motores = Motores(True)
motores.direcao_motor(1, Motores.INVERTIDO)
motores.direcao_motor(3, Motores.INVERTIDO)
try:   
    while(True):
        # velocidade = int(input("Digite a velocidade dos motores (1-100): "))
        motores.estado()
        # print(motores.angulo_motor(2))
        motores.potencia_motores_4x4(50,50);
        sleep(2)
        motores.para_motores();
        sleep(1)
        motores.potencia_motor(1,50);
        sleep(1)
        motores.potencia_motor(2,50);
        sleep(1)
        motores.potencia_motor(3,50);
        sleep(1)
        motores.potencia_motor(4,50);
        sleep(1)
        motores.para_motores();
        sleep(1)
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

