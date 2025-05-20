from cronometro import Cronometro
import sensor
import constantes as const


relogio = Cronometro("tempo") ## MEDE O TEMPO DE EXECUCAO DO ROBO
espera = Cronometro()

## CRONOMETRO QUE MEDE O TEMPO DES DE A ULTIMA VEZ QUE VIU ALGO NO SENSOR ESPECIFICADO
VerdeDir = Cronometro() 
VerdeMeio = Cronometro()
VerdeEs = Cronometro()

PretoDirEX = Cronometro()
PretoDir = Cronometro()
PretoEs = Cronometro()
PretoEsEX = Cronometro()

FezVerde = Cronometro()

Fez90 = Cronometro()

RampaSubiu = Cronometro()
RampaDesceu = Cronometro()


#INICIA OS CRONOMETROS
relogio.carrega()
espera.inicia()

FezVerde.inicia()
Fez90.inicia()

VerdeDir.inicia()
VerdeMeio.inicia()
VerdeEs.inicia()
PretoDirEX.inicia()
PretoDir.inicia()
PretoEs.inicia()
PretoEsEX.inicia()

RampaSubiu.inicia()
RampaDesceu.inicia()


def reset():
    ##reset dos cronometros, pra mostrar quanto tempo faz des de o ultimo momento em que eles viram algo
    # print(sensor.leHSVdir())
    if sensor.checarCorHSV(sensor.leHSVdir()) == const.verde: 
        print("resetou CorDir")
        VerdeDir.reseta()

    if sensor.checarCorHSV(sensor.leHSVmeio()) == const.verde:
        print("resetou CorMeio")
        VerdeMeio.reseta()

    if sensor.checarCorHSV(sensor.leHSVesq()) == const.verde:
        print("resetou CorEsq")
        VerdeEs.reseta()


    if sensor.leReflexaoDirEX() < const.PRETO:
        # print("resetou dirEX")
        PretoDirEX.reseta()
    if sensor.leReflexaoDir() < const.PRETO:
        # print("resetou dir")
        PretoDir.reseta()
    if sensor.leReflexaoEsq() < const.PRETO:
        # print("resetou esq")
        PretoEs.reseta()
    if sensor.leReflexaoEsqEX() < const.PRETO:
        # print("resetou esqEX")
        PretoEsEX.reseta()