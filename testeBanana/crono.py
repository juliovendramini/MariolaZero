from cronometro import Cronometro
import sensor
import constantes as const


relogio = Cronometro("tempo") ## MEDE O TEMPO DE EXECUCAO DO ROBO

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
        # print("resetou dir")
        VerdeDir.reseta()

    if sensor.checarCorHSV(sensor.leHSVmeio()) == const.verde:
        # print("resetou meio")
        VerdeMeio.reseta()

    if sensor.checarCorHSV(sensor.leHSVesq()) == const.verde:
        # print("resetou esq")
        VerdeEs.reseta()


    if sensor.leReflexaoDirEX() < const.PRETO:
        PretoDirEX.reseta()
    if sensor.leReflexaoDir() < const.PRETO:
        PretoDir.reseta()
    if sensor.leReflexaoEsq() < const.PRETO:
        PretoEs.reseta()
    if sensor.leReflexaoEsqEX() < const.PRETO:
        PretoEsEX.reseta()