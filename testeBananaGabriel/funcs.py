import movimentos as mov
import sensor
import dist
import crono as cr
import constantes as const
from constantes import esq, dir, frente, tras
from time import sleep

import conds as con
    
from defs import teclado as tcl
from defs import Teclado
from defs import tela

from defs import giroscopio as giro

andada = 5
volta = 3

def intercessao():
    if cr.PretoDirEX.tempo() > 380 and cr.PretoEsEX.tempo() < 100 and cr.Fez90.tempo() > 500:
        print("curva de 90 graus para esquerda")

        mov.reto(andada)

        if con.meioBranco():
            print("esq valido")
            mov.girarGrausAtePreto(esq, 90)
            mov.reto(volta, tras)
            cr.Fez90.reseta()
        

    elif cr.PretoDirEX.tempo() < 100 and cr.PretoEsEX.tempo() > 380 and cr.Fez90.tempo() > 500:
        print("dir")

        mov.reto(andada)

        if con.meioBranco():
            print("dir valido")
            mov.girarGrausAtePreto(dir, 90)
            mov.reto(volta, const.tras)
            cr.Fez90.reseta()

def verde():
    #MARCACAO NA ESQUERDA
    if cr.VerdeEs.tempo() < 100 and cr.VerdeDir.tempo() > 600 and cr.FezVerde.tempo() > 500:
        print("verde na esquerda")
        mov.reto(andada)

        if cr.PretoEsEX.tempo() < cr.VerdeEs.tempo():
            print(cr.PretoEsEX.tempo(), cr.VerdeEs.tempo())
            if cr.VerdeDir.tempo() < 100:
                print("verde 180 valido")
                mov.girarGraus(dir, 180)
                mov.reto(volta, tras, 35)
                cr.FezVerde.reseta()
            else:
                print("verde esq valido")
                mov.girarGraus(esq, 55)
                mov.girarGrausAtePreto(esq, 35)
                mov.reto(volta, tras, 35)
                cr.FezVerde.reseta()
        else: print("nao aceitei o verde esquerdo: ", cr.PretoEsEX.tempo(), cr.VerdeEs.tempo())

    #MARCACAO NA DIREITA
    elif cr.VerdeEs.tempo() > 600 and cr.VerdeDir.tempo() < 100 and cr.FezVerde.tempo() > 500:
        print("verde na direita")
        mov.reto(andada)

        if cr.PretoDirEX.tempo() < cr.VerdeDir.tempo():
            if cr.VerdeEs.tempo() < 100:
                print("verde 180 valido")
                mov.girarGraus(dir, 180)
                mov.reto(volta, tras, 35)
                cr.FezVerde.reseta()
            else:
                print("verde dir valido")
                mov.girarGraus(dir, 55)
                mov.girarGrausAtePreto(dir, 35)
                mov.reto(volta, tras, 35)
                cr.FezVerde.reseta()
        else: print("nao aceitei o verde direito: ", cr.PretoDirEX.tempo(), cr.VerdeDir.tempo())

    #MARCACAO NOS DOIS LADOS
    elif cr.VerdeEs.tempo() < 100 and cr.VerdeDir.tempo() < 100 and cr.FezVerde.tempo() > 500:
        print("verde 180")
        mov.reto(andada)

        if cr.PretoDirEX.tempo() < cr.VerdeDir.tempo():
            print("verde 180 valido")
            mov.girarGraus(dir, 180)
            mov.reto(volta, tras, 35)
            cr.FezVerde.reseta()

    elif cr.VerdeEs.tempo() < 700 and cr.VerdeMeio.tempo() < 100 and cr.VerdeDir.tempo() < 700:
        print("verde no meio")
        mov.reto(7, tras)

def gap(): ## TEM QUE FAZER A VARREDURA DPS
    if con.tudoBranco():
        print("confere gap")
        mov.retoAtePreto(16)

        if con.tudoBranco():

            print("gap falso, se perdeu")
            mov.reto(18, tras)
        else: print("gap verdadeiro")

def pararNoVermelho():
    if con.tudoVermelho():
        mov.reto(2.2, tras, 25)
        mov.motores.paraMotores()
        print("viu vermelho")
        validarVermelho = True
        
        esperaVermelho = cr.Cronometro()
        esperaVermelho.reseta()
        while esperaVermelho.tempo() < 5000:
            if not(con.tudoVermelho()):
                validarVermelho = False
                print("falso vermelho")
                break

        if validarVermelho == True:
            mov.motores.paraMotores()
            while True:
                print("finalizou a pista")
                pass

def rampa():

    #rampa subida
    if giro.leAnguloX() < -19:
        
        cr.RampaSubiu.reseta()

        erroAnterior = 0
        print("subida da rampa")
        while True:

            ##PID DA RAMPA
            kp = 0.2
            kd = 9
            erro = sensor.erro_pid()
        

            p = erro * kp 
            d = (erro - erroAnterior) * kd
            
            valor = p + d #variacao da potencia do motor
            valor = int(valor)

            vb_pid = 60
            mov.motores.velocidadeMotores(vb_pid + valor, vb_pid - valor - const.DELTA)
           

            erroAnterior = erro

            if giro.leAnguloX() < -19:
                cr.RampaSubiu.reseta()
                
            if cr.RampaSubiu.tempo() > 100:
                print("saiu da subida da rampa")
                # mov.reto(4, tras)
                tcl.alteraLed(1, 0)
                break

            tcl.alteraLed(1, 1)

    #rampa descida
    if giro.leAnguloX() > 19:
        cr.RampaDesceu.reseta()

        mov.reto(2, tras)

        erroAnterior = 0
        print("descida da rampa")
        while True:

            ##PID DA RAMPA
            kp = 0.25
            kd = 10
            erro = sensor.erro_pid()
        
            p = erro * kp 
            d = (erro - erroAnterior) * kd
            
            valor = p + d #variacao da potencia do motor
            valor = int(valor)

            vb_pid = 20
            mov.motores.velocidadeMotores(vb_pid + valor, vb_pid - valor - const.DELTA)


            erroAnterior = erro

            if giro.leAnguloX() > 19:
                cr.RampaDesceu.reseta()
                
            if cr.RampaDesceu.tempo() > 350:
                print("saiu da descida da rampa")
                tcl.alteraLed(1, 0)
                break

            tcl.alteraLed(1, 1)

def obstaculo():
    pass