import movimentos as mov
import sensor
import crono as cr
import constantes as const
from constantes import esq, dir, frente, tras

import conds as con

from defs import teclado
from defs import Teclado
from defs import tela

def intercessao():
    if cr.PretoDirEX.tempo() > 800 and cr.PretoEsEX.tempo() < 100 and cr.Fez90.tempo() > 500:
        print("curva de 90 graus para esquerda")

        mov.reto(3)

        if con.tudoBranco():
            print("esq valido")
            mov.girarGrausAtePreto(esq, 90)
            mov.reto(2, tras)
            cr.Fez90.reseta()
        

    elif cr.PretoDirEX.tempo() < 100 and cr.PretoEsEX.tempo() > 800 and cr.Fez90.tempo() > 500:
        print("dir")

        mov.reto(3)

        if con.tudoBranco():
            print("dir valido")
            mov.girarGrausAtePreto(dir, 90)
            # mov.reto(5, const.tras)
            cr.Fez90.reseta()

def verde():
    #MARCACAO NA ESQUERDA
    if cr.VerdeEs.tempo() < 100 and cr.VerdeDir.tempo() > 600 and cr.FezVerde.tempo() > 500:
        print("verde na esquerda")
        mov.reto(6)

        if cr.PretoEsEX.tempo() < cr.VerdeEs.tempo():
            print(cr.PretoEsEX.tempo(), cr.VerdeEs.tempo())
            if cr.VerdeDir.tempo() < 100:
                print("verde 180 valido")
                mov.girarGraus(const.dir, 180)
                mov.reto(2, const.tras)
                cr.FezVerde.reseta()
            else:
                print("verde esq valido")
                mov.girarGraus(const.esq, 90)
                mov.reto(2, const.tras)
                cr.FezVerde.reseta()
        else: print("nao aceitei o verde esquerdo: ", cr.PretoEsEX.tempo(), cr.VerdeEs.tempo())

    #MARCACAO NA DIREITA
    elif cr.VerdeEs.tempo() > 600 and cr.VerdeDir.tempo() < 100 and cr.FezVerde.tempo() > 500:
        print("verde na direita")
        mov.reto(6)

        if cr.PretoDirEX.tempo() < cr.VerdeDir.tempo():
            if cr.VerdeEs.tempo() < 100:
                print("verde 180 valido")
                mov.girarGraus(const.dir, 180)
                mov.reto(2, const.tras)
                cr.FezVerde.reseta()
            else:
                print("verde dir valido")
                mov.girarGraus(const.dir, 90)
                mov.reto(2, const.tras)
                cr.FezVerde.reseta()
        else: print("nao aceitei o verde direito: ", cr.PretoDirEX.tempo(), cr.VerdeDir.tempo())

    #MARCACAO NOS DOIS LADOS
    elif cr.VerdeEs.tempo() < 100 and cr.VerdeDir.tempo() < 100 and cr.FezVerde.tempo() > 500:
        print("verde 180")
        mov.reto(6)

        if cr.PretoDirEX.tempo() < cr.VerdeDir.tempo():
            print("verde 180 valido")
            mov.girarGraus(const.dir, 180)
            mov.reto(2, const.tras)
            cr.FezVerde.reseta()

