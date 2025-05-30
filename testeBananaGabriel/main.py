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
import defs
import funcs
import crono as cr
import sensor as se
import dist

import area

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
# while True: 
# motores.moveMotores(100, 900, 100, 900)
# motores.velocidadeMotores(100, 100)
#     # motores.potenciaMotores(50, 50)
#     sleep(2)
    # motores.velocidadeMotores(0, 0)
    # motores.potenciaMotores(0, 0)
# sleep(200)
# mov.girarGraus(const.esq, 90)
# sleep(2000)
# motores.potenciaMotores()

def seguidorDeLinha():
    funcs.verde()
    funcs.intercessao()
    funcs.gap()
    funcs.rampa()
    funcs.obstaculo()
    funcs.pararNoVermelho()

    mov.pid()
    
defs.apagarTodosLeds()

motores.modoFreio_(0)

try:   
    cr.iniciarThreadCronometros()
    run = 1
    coiso = 0
    sleep(1)
    while run == 1:

        # area.areaDeResgate()
        seguidorDeLinha()

        # motores.velocidadeMotores(60, -60)

        # mov.alinhar()
        # motores.potenciaMotores(60, 60)
        # motores.velocidadeMotores(100, 100)
        # if (teclado.botaoPressionado(Teclado.CIMA)): 
        #     coiso +=1 
        #     print("apertou cima")
        #     sleep(0.4) 
        # elif (teclado.botaoPressionado(Teclado.BAIXO)): 
        #     coiso -=1 
        #     print("apertou baixo")
        #     sleep(0.4) 
        # else: print("apertou nada")

        # if coiso > 3: coiso = 3
        # if coiso < 0: coiso = 0
            
        # match coiso:
        #     case 0: tela.escreve("aaaaa", 1)
        #     case 1: tela.escreve("bbbbb", 1)
        #     case 2: tela.escreve("ccccc", 1)
        #     case 3: tela.escreve("ddddd", 1)

        # print(cr.PretoEsEX.tempo(), cr.PretoDirEX.tempo())
        # print(cr.Fez90.tempo())
        # print(se.sensorCor.leReflexao())
        # mov.reto(15, const.tras)
        #motores.velocidadeMotores(50,50)

        # sleep(2)
        # mov.reto(10, const.frente)
        # mov.reto(10, const.tras)
        # sleep(2)

        # mov.girarGraus(const.dir, 90)
        # sleep(3)

        # mov.girarGraus(const.esq, 90)
        # mov.reto(30, const.frente)
        
        # print(mov.calculoErro())
        
        # print(cr.VerdeEs.tempo(), cr.VerdeMeio.tempo(), cr.VerdeDir.tempo())
        # print(cr.VermEs.tempo(), cr.VermMeio.tempo(), cr.VermDir.tempo())

        # print(cr.PretoEsEX.tempo(), cr.PretoEs.tempo(), cr.PretoDir.tempo(), cr.PretoDirEX.tempo())
  

        # print(se.leReflexaoTodos())

        # print(se.leHSVesq(), se.checarCorHSV(se.leHSVesq()) == const.verde)
        # print(se.leHSVesq(), se.leHSVmeio(), se.leHSVdir())
        # sleep(0.5)

        # print(giroscopio.leAnguloX())
        # break

        # print(cr.PrataDir.tempo(), cr.PrataMeio.tempo(), cr.PrataEs.tempo())

        # print(dist.leDistanciaFrente())

        if (teclado.botaoPressionado(Teclado.ENTER)):
            break


except KeyboardInterrupt as e:
    print("\nInterrupção detectada! Parando os motores e encerrando...")
    defs.apagarTodosLeds()
    # Parar os motores
    motores.desligaMotores()
    #desativo todos os servos
    motores.desativaServo(1)
    motores.desativaServo(2)
    motores.desativaServo(3)
    motores.desativaServo(4)
    motores.desativaServo(5)
    motores.desativaServo(6)
    print("Programa encerrado com segurança.")
#    subprocess.run(["killall python3", None], check=True)

