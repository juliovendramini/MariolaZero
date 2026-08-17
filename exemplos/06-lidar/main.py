from time import sleep

from portas import Portas
from pinosDigitais import PinosDigitais
from sensorLidar import Lidar
lidar = Lidar(Portas.SERIAL6, pino_liga=PinosDigitais.P7)  # Inicializa o LIDAR na porta SERIAL1 e usa o pino P1 para ligar/desligar

try:
    print("Iniciando leitura dos dados do LIDAR...")
    print("Pressione Ctrl+C para parar")

    while True:
        print(lidar.pontos(340, 20))  # exemplo: filtra apenas o intervalo de 0 a 90 graus
        print("Velocidade do LIDAR:", lidar.velocidade, "RPM")
        sleep(0.5)

except KeyboardInterrupt:
    print("\nParando a leitura...")
finally:
    lidar.fechar()
    print("Lidar desligado e porta serial fechada.")

