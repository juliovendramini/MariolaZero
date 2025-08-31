# Imports necessários para a comunicação serial
import serial
from motores import Movimento
from sensorCorReflexao import CorReflexao
from time import time, sleep
from cronometro import Cronometro

# Função que será executada antes do script fechar
def finalizar():
    print("\nParando os motores e encerrando...")
    # Parar os motores
    motores.velocidadeMotor(1, 0)
    motores.velocidadeMotor(2, 0)
    motores.velocidadeMotor(3, 0)
    motores.velocidadeMotor(4, 0)
    motores.desativaServo(1)
    motores.desativaServo(2)
    motores.desativaServo(3)
    motores.desativaServo(4)
    motores.desativaServo(5)
    motores.desativaServo(6)
    # Fechar conexões seriais
    if ser is not None:
        ser.close()
    if serCor is not None:
        serCor.close()
    print("Programa encerrado com segurança.")


portaSerial = '/dev/ttyUSB0'
portaSerialSensorCor = '/dev/ttyUSB1'
ser = None
serCor = None
# Conecta com a porta serial do brick
# Retorna True se a conexão foi estabelecida com sucesso
def conectar_serial(portaSerial,baud_rate=115200):
    ser=None
    try:
        # Inicializa a comunicação serial
        ser = serial.Serial(portaSerial, baud_rate, timeout=1)
        print(f"Comunicação estabelecida com sucesso na porta {portaSerial}.")
        return ser
    
    # Caso ocorra algum erro na comunicação serial
    except serial.SerialException as e:
        print(f"Erro ao tentar se comunicar com a porta {portaSerial}: {e}")
        return None
    
# Envia uma mensagem para o brick
def enviarMensagem(mensagem):
    ser.write(mensagem.encode())
    print(f"Mensagem enviada: {mensagem}")


ser = conectar_serial(portaSerial)
motores = Movimento(ser, True)
finalizar()