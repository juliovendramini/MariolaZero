#pra logar: ssh banana@192.168.1.113
#pra entrar no ambiente especifico do pyhton: source meu_venv/bin/activate
#source meu_venv/bin/activate
#sudo shutdown now

#ordem dos botoes 
#ESC ENTER UP DOWN

from defs import tela
from defs import teclado
from defs import Teclado
from defs import motores
from defs import sleep
import movimentos as mov
import constantes as const
from defs import giroscopio
import funcs
import crono as cr
import sensor as se

def calibracaoSensorCor():
    print("calibrando branco")
    se.sensorCor.calibraBranco()
    print("aperte enter")
    while True:
        if (teclado.botaoPressionado(Teclado.ENTER)):
            break
    print("calibrando preto")
    se.sensorCor.calibraPreto()

# calibracaoSensorCor()
# giroscopio.calibra()

# mov.reto(6, const.frente, 100)
# motores.moveMotores(50, 300, 50, 300)
# mov.girarGraus(const.esq, 90)
# sleep(2000)
# motores.potenciaMotores()

def seguidorDeLinha():
    funcs.verde()
    #funcs.intercessao()
    mov.pid()

try:   
    cr.iniciarThreadCronometros()
    run = 1
    while run == 1:

        seguidorDeLinha()

        # print(cr.PretoEsEX.tempo(), cr.PretoDirEX.tempo())
        # print(cr.Fez90.tempo())
        # print(se.sensorCor.leReflexao())
        # mov.reto(15, const.tras)
        #motores.velocidadeMotores(50,50)

        # sleep(2)
        # mov.reto(30)
        # sleep(2)

        # mov.girarGraus(const.dir, 90)
        # sleep(3)

        # mov.girarGraus(const.esq, 90)
        # mov.reto(30, const.frente)
        
        # print(mov.calculoErro())
        
        # print(cr.VerdeEs.tempo(), cr.VerdeMeio.tempo(), cr.VerdeDir.tempo())

        # print(cr.PretoEsEX.tempo(), cr.PretoEs.tempo(), cr.PretoDir.tempo(), cr.PretoDirEX.tempo())
  
        # print(se.leReflexaoTodos())

        # print(se.leHSVesq(), se.checarCorHSV(se.leHSVesq()) == const.verde)
        # sleep(0.5)

        # print(giroscopio.leAnguloZ())
        # break

        if (teclado.botaoPressionado(Teclado.ENTER)):
            break


except KeyboardInterrupt as e:
    print("\nInterrupção detectada! Parando os motores e encerrando...")
    # Parar os motores
    motores.velocidadeMotor(1, 0)
    motores.velocidadeMotor(2, 0)
    #desativo todos os servos
    motores.desativaServo(1)
    motores.desativaServo(2)
    motores.desativaServo(3)
    motores.desativaServo(4)
    motores.desativaServo(5)
    motores.desativaServo(6)
    print("Programa encerrado com segurança.")
#    subprocess.run(["killall python3", None], check=True)

