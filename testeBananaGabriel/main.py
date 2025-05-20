#pra logar: ssh banana@192.168.1.113
#pra entrar no ambiente especifico do pyhton: source meu_venv/bin/activate
#source meu_venv/bin/activate
#sudo shutdown now

#ordem dos botoes 
#ESC ENTER UP DOWN

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
# giroscopio.leAnguloZ()
#giroscopio.calibra()
#giroscopio.resetaZ()
# mov.reto(30, const.frente, 40)
# mov.girarGraus(const.esq, 90)
# motores.moveMotores(40, 2000, 40, 2000)
# motores.moveMotor(2, 70, 10000)
# motores.potenciaMotores()

try:   
    run = 1
    while run == 1:

        cr.espera.reseta()
        cr.reset()
        # print(cr.PretoEsEX.tempo(), cr.PretoDirEX.tempo())
        # print(cr.Fez90.tempo())
        #print(se.sensorCor.leReflexao())
        # print(se.leReflexaoTodos())
        #mov.reto(15, const.frente)
        #motores.velocidadeMotores(50,50)
        
        # sleep(2)
        # mov.reto(10, const.tras, 40)
        # sleep(2)

        # mov.girarGraus(const.dir, 90)
        # sleep(2)

        # mov.girarGraus(const.esq, 90)
        # mov.reto(30, const.frente)
        
        # funcs.intercessao()
        funcs.verde()
        mov.pid()


        # print(mov.calculoErro())
        
        # print(cr.VerdeEs.tempo(), cr.VerdeMeio.tempo(), cr.VerdeDir.tempo())
        # print(se.leReflexaoTodos())
        # print(se.leHSVesq(), se.leHSVmeio(), se.leHSVdir())
        # sleep(1)

        # print(giroscopio.leAnguloZ())
        # break
        # leep(0.025)
        if (teclado.botaoPressionado(Teclado.ENTER)):
            break
        # while cr.espera.tempo() < 25:
        #     continue
        # print(se.sensorCor.taxaAtualizacao())


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

