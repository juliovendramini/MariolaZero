#Atualmente ainda é necessário inserir os arquivos python das bibliotecas que serão utilizadas dentro do projeto
#Futuramente, quando tudo estiver estável, isso não será mais necessário

#Declaração das bibliotecas que serão usadas
from time import sleep
from motores import Motores
motores = Motores(True) #O parametro True significa que a atualização dos motores será instantânea, ou seja, o programador não precisa se preocupar em mudar
                        #no controlador, as velocidades e parametros após chamar os métodos da classe. Isso pode ser alterado para uma performance mais controlada
                        #mas geralmente a atualização automática é preferida
                        
#Todo o código incial deve ser escrito e chamado dentro do try abaixo. Isso é necessário para quando algum problema
#acontecer, o catch abaixo enviar para os motores o comando de parar o funcionamento de tudo
try:   
    motores.move_servo(1, 90) #move o servo 1 para a posição 90 graus                      
    # motores.pid_motor(1,1,1) #configuração de parametros do PID do motor. Não é necessário chamar essa função a cada iteração nem a cada execução.
                            #essa informação fica guardada na EEPROM
    velocidadeMotor1 = int(input("Digite a velocidade do motor 1 (0-100): "))
    velocidadeMotor2 = int(input("Digite a velocidade do motor 2 (0-100): "))
    posicaoServo1 = int(input("Digite a posição do servo 1 (0-180): "))
    # motores.velocidade_motores(velocidadeMotor1, velocidadeMotor2)
    while True:
        #sleep(2)
        print(motores.atualiza_motores())
        print(motores.angulo_motor(1), motores.angulo_motor(2))
        motores.potencia_motores(velocidadeMotor1, velocidadeMotor2)
        motores.move_servo(1, posicaoServo1)
        # sleep(0.1)
        sleep(0.5)  
        
        
        
        
        # motores.velocidadeMotor(1, velocidadeMotor1)
        # motores.velocidadeMotor(2, velocidadeMotor2)
        # motores.moveServo(2, 0)
        # sleep(0.5)
        # motores.moveServo(1, 90)
        # motores.moveServo(2, 90)
        # sleep(0.5)
        # motores.moveServo(1, 180)
        # motores.moveServo(2, 180)
        # sleep(0.5)
        # motores.moveServo(1, 90)
        # motores.moveServo(2, 90)
        # sleep(0.5)


#Essa parte do código é responsável por lidar com a interrupção do programa quando no terminal apertamos Ctrl+C 
#ou interrompemos o programa pelo teclado do brick
except KeyboardInterrupt as e:
    print("\nInterrupção detectada! Parando os motores e encerrando...")
    # Parar os motores
    motores.velocidade_motor(1, 0)
    motores.velocidade_motor(2, 0)
    #desativo todos os servos
    motores.desativa_servo(1)
    motores.desativa_servo(2)
    motores.desativa_servo(3)
    motores.desativa_servo(4)
    motores.desativa_servo(5)
    motores.desativa_servo(6)
    print("Programa encerrado com segurança.")

