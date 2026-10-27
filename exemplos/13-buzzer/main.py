#Atualmente ainda é necessário inserir os arquivos python das bibliotecas que serão utilizadas dentro do projeto
#Futuramente, quando tudo estiver estável, isso não será mais necessário
#Exemplo do buzzer do Mariola (pino DEBUG/PWM): sons prontos, melodias, tom avulso e motores andando
#enquanto a melodia toca.
#Atenção: servos, ventoinha e buzzer usam o mesmo timer da placa. O primeiro que for usado fica com
#ele até o brick reiniciar: depois de tocar o buzzer, os servos e a ventoinha não funcionam.
from time import sleep
from portas import Portas
from motores import Motores

motores = Motores(True)
motores.direcao_motor(1, Motores.INVERTIDO)
motores.direcao_motor(3, Motores.INVERTIDO)
motores.set_modo_freio(Motores.HOLD)

# O buzzer padrão do Mariola apita com o pino em LOW. Se o seu apita em HIGH, descomente a linha abaixo
# (fica salvo no brick, só precisa rodar uma vez):
# motores.set_nivel_buzzer(Motores.BUZZER_LIGA_HIGH)
print("Nível do buzzer:", "HIGH" if motores.nivel_buzzer() == Motores.BUZZER_LIGA_HIGH else "LOW")

sons = [
    (Motores.SOM_BIPE, "bipe"),
    (Motores.SOM_BIPE_DUPLO, "bipe duplo"),
    (Motores.SOM_SUCESSO, "sucesso"),
    (Motores.SOM_ERRO, "erro"),
    (Motores.SOM_ALERTA, "alerta"),
    (Motores.SOM_LIGANDO, "ligando"),
    (Motores.SOM_DESLIGANDO, "desligando"),
    (Motores.SOM_LARGADA, "largada"),
    (Motores.SOM_RE, "ré"),
    (Motores.SOM_SIRENE_DOIS_TONS, "sirene de dois tons"),
    (Motores.SOM_SIRENE, "sirene"),
    (Motores.SOM_MOEDA, "moeda"),
    (Motores.SOM_POWER_UP, "power-up"),
    (Motores.SOM_LASER, "laser"),
    (Motores.SOM_BATERIA_FRACA, "bateria fraca"),
    (Motores.SOM_ROBO, "robô falando"),
]

melodias = [
    (Motores.MELODIA_ESCALA, "escala"),
    (Motores.MELODIA_PARABENS, "parabéns pra você"),
    (Motores.MELODIA_BRILHA_ESTRELINHA, "brilha, brilha estrelinha"),
    (Motores.MELODIA_ODE_ALEGRIA, "ode à alegria"),
    (Motores.MELODIA_JINGLE_BELLS, "jingle bells"),
    (Motores.MELODIA_FUR_ELISE, "für elise"),
    (Motores.MELODIA_GRAN_VALS, "gran vals (toque de celular)"),
]

try:
    # 1. os sons de sinalização, um de cada vez (esperar=True só volta quando o som termina)
    for som, nome in sons:
        print("Tocando:", nome)
        motores.toca_som(som, esperar=True)
        sleep(0.5)

    # 2. repetições e velocidade: o "ré" 4 vezes e a escala duas vezes mais rápida
    print("Ré 4 vezes")
    motores.toca_som(Motores.SOM_RE, vezes=4, esperar=True)
    print("Escala com velocidade 200%")
    motores.toca_som(Motores.MELODIA_ESCALA, velocidade=200, esperar=True)

    # 3. tom avulso: frequência em Hz e duração em ms
    for frequencia in (500, 1000, 2000, 3000):
        print(f"Tom de {frequencia} Hz")
        motores.toca_tom(frequencia, 300, esperar=True)
        sleep(0.2)

    # 4. o buzzer não trava o programa: o robô gira no lugar enquanto a melodia toca
    print("Girando enquanto toca o parabéns (o robô vai se mexer!)")
    motores.toca_som(Motores.MELODIA_PARABENS)  # sem esperar: volta na hora
    motores.velocidade_motores(30, -30)
    while motores.buzzer_tocando():
        motores.estado()
        print("ângulos:", motores.angulo_motor(1), motores.angulo_motor(2))
        sleep(0.2)
    motores.para_motores()

    # 5. vezes=0 repete até mandar parar
    print("Sirene por 3 segundos")
    motores.toca_som(Motores.SOM_SIRENE, vezes=0)
    sleep(3)
    motores.para_buzzer()

    # 6. as melodias
    for melodia, nome in melodias:
        print("Tocando:", nome)
        motores.toca_som(melodia, esperar=True)
        sleep(1)

#Essa parte do código é responsável por lidar com a interrupção do programa quando no terminal apertamos Ctrl+C
#ou interrompemos o programa pelo teclado do brick
except KeyboardInterrupt as e:
    motores.para_motores()
    motores.para_buzzer()
    print("\nInterrupção detectada! Parando os motores e o buzzer e encerrando...")
    print("Programa encerrado com segurança.")
