#Atualmente ainda é necessário inserir os arquivos python das bibliotecas que serão utilizadas dentro do projeto
#Futuramente, quando tudo estiver estável, isso não será mais necessário
#Exemplo de uso do giroscopio
import random
from time import sleep
from portas import Portas
from sensorCorReflexao import CorReflexao

# servos = PlacaControleServo.buscar_servos(Portas.SERIAL1)
# print("Servos encontrados:")
# for servo in servos:
#     print(f"ID: {servo['id']}, Posição: {servo['posicao']}")

# exit()
sensorCor = CorReflexao(Portas.SERIAL4)
sensorCor.set_modo(2)  # Configura o modo desejado
try:   
    while(True):
        if sensorCor.atualiza():
            print(sensorCor.lista)
        else:
            print("Erro ao atualizar os dados do sensor de cor e reflexão.")
        sleep(0.3)

#Essa parte do código é responsável por lidar com a interrupção do programa quando no terminal apertamos Ctrl+C 
#ou interrompemos o programa pelo teclado do brick
except KeyboardInterrupt as e:
    print("\nInterrupção detectada! Encerrando...")
    print("Programa encerrado com segurança.")

