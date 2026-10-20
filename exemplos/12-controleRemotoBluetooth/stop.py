# Para tudo no brick: motores, servos e LEDs do Mariola (e as placas de controle de motor da lista abaixo).
# O stop.sh chama este script. Serve para quando o programa travou ou foi morto sem parar o robô.
# Obs.: a ventoinha (set_ventoinha) não é desligada aqui: mandar o comando dela num brick que não
# estava com a ventoinha ligada desativaria os servos até reiniciar o brick.
from portas import Portas
from motores import Motores

# IDs das placas de controle de motor usadas neste projeto (vazio = não usa placa de motor)
IDS_PLACAS_MOTOR = [5, 72]  # as mesmas do main.py

print("Parando os motores e encerrando...")
motores = Motores()  # ao conectar, a lib já manda os motores parados e todos os servos desativados
motores.para_motores()
for servo in range(1, 7):
    motores.desativa_servo(servo)
motores.atualiza_servos()
motores.set_led_rgb_all(0, 0, 0)

if IDS_PLACAS_MOTOR:
    from placaControleMotor import PlacaControleMotor
    porta = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
    placas = []  # guardadas até o fim: o __del__ de cada placa fecha a porta serial que todas usam
    for id_placa in IDS_PLACAS_MOTOR:
        try:
            placas.append(PlacaControleMotor(porta, id_equipamento=id_placa))
            placas[-1].para_motor()
        except Exception as e:
            print(f"Placa de motor {id_placa}: {e}")

print("Brick parado.")
