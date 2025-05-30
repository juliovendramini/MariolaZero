from cronometro import Cronometro
import sensor
import constantes as const
import threading
from time import sleep
from defs import teclado as tcl


relogio = Cronometro("tempo") ## MEDE O TEMPO DE EXECUCAO DO ROBO
espera = Cronometro()

## CRONOMETRO QUE MEDE O TEMPO DES DE A ULTIMA VEZ QUE VIU ALGO NO SENSOR ESPECIFICADO
VerdeDir = Cronometro() 
VerdeMeio = Cronometro()
VerdeEs = Cronometro()

VermDir = Cronometro() 
VermMeio = Cronometro()
VermEs = Cronometro()

PrataDir = Cronometro() 
PrataMeio = Cronometro()
PrataEs = Cronometro()

PretoDirEX = Cronometro()
PretoDir = Cronometro()
PretoEs = Cronometro()
PretoEsEX = Cronometro()

FezVerde = Cronometro()

Fez90 = Cronometro()

RampaSubiu = Cronometro()
RampaDesceu = Cronometro()

fezGap = Cronometro()


#INICIA OS CRONOMETROS
relogio.carrega()
espera.inicia()

FezVerde.inicia()
Fez90.inicia()

VerdeDir.inicia()
VerdeMeio.inicia()
VerdeEs.inicia()

VermDir.inicia()
VermMeio.inicia()
VermEs.inicia()

PrataDir.inicia()
PrataMeio.inicia()
PrataEs.inicia()

PretoDirEX.inicia()
PretoDir.inicia()
PretoEs.inicia()
PretoEsEX.inicia()

RampaSubiu.inicia()
RampaDesceu.inicia()

fezGap.inicia()


def reset():
    ##reset dos cronometros, pra mostrar quanto tempo faz des de o ultimo momento em que eles viram algo
    # print(sensor.leHSVdir())
    if sensor.checarCorHSV(sensor.leHSVdir()) == const.verde: VerdeDir.reseta(); tcl.alteraLed(2, 1); 
    else: tcl.alteraLed(2, 0)
    if sensor.checarCorHSV(sensor.leHSVmeio()) == const.verde: VerdeMeio.reseta(); tcl.alteraLed(2, 1)
    else: tcl.alteraLed(2, 0)
    if sensor.checarCorHSV(sensor.leHSVesq()) == const.verde: VerdeEs.reseta(); tcl.alteraLed(2, 1)
    else: tcl.alteraLed(2, 0)


    if sensor.checarCorHSV(sensor.leHSVdir()) == const.vermelho: VermDir.reseta()
    if sensor.checarCorHSV(sensor.leHSVmeio()) == const.vermelho: VermMeio.reseta()
    if sensor.checarCorHSV(sensor.leHSVesq()) == const.vermelho: VermEs.reseta()

    if sensor.checarCorRGBC(sensor.leRGBCdir()) == const.prata: PrataDir.reseta()
    if sensor.checarCorRGBC(sensor.leRGBCmeio()) == const.prata: PrataMeio.reseta()
    if sensor.checarCorRGBC(sensor.leRGBCesq()) == const.prata: PrataEs.reseta()

    if sensor.leReflexaoDirEX() < const.PRETO: PretoDirEX.reseta()
    if sensor.leReflexaoDir() < const.PRETO: PretoDir.reseta()
    if sensor.leReflexaoEsq() < const.PRETO: PretoEs.reseta()
    if sensor.leReflexaoEsqEX() < const.PRETO: PretoEsEX.reseta()


def thread_reset():
    while True: 
        reset()
        sleep(0.02)

def dorme(ms):
    print("dorme")
    espera.reseta()
    while espera.tempo() <= ms:
        pass
    print("saiu dorme")

threadCronometros = None
def iniciarThreadCronometros():
        global threadCronometros
        """Inicia a thread para chamar `atualiza` periodicamente."""
        threadCronometros = threading.Thread(target=thread_reset)
        threadCronometros.daemon = True  # Permite que o programa principal encerre mesmo com a thread ativa
        threadCronometros.start()