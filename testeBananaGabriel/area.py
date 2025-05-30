import crono as cr
import sensor as se
import movimentos as mov
import constantes as const
import conds as con
import dist
from defs import sleep
from defs import giroscopio

from defs import tela
from defs import teclado as tcl

def areaDeResgate():
    if con.tudoPrata():
        print("confere area")
        mov.m.paraMotores()
        validarPrata = True
        
        esperaPrata = cr.Cronometro()
        esperaPrata.reseta()
        while esperaPrata.tempo() < 2000:
            if not(con.tudoPrata()):
                validarPrata = False
                print("falso prata")
                break

        if validarPrata == True:
            tcl.alteraLed(4, 1)
            mov.m.paraMotores()
            print("entrou na area de resgate")

        ## agora tem que ter a logica de como faz pra sair de la
        ## que provavelmente deve usar o parachoque e outros sensores de cor e distancia
                