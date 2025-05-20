import movimentos as mov
import sensor
import crono as cr
import constantes as const

import conds as con

from defs import teclado
from defs import Teclado

def intercessao():
    if cr.PretoDirEX.tempo() > 800 and cr.PretoEsEX.tempo() < 100 and cr.Fez90.tempo() > 500:
        print("esq")

        mov.reto(12)

        if con.tudoBranco():
            print("esq valido")
            mov.girarGrausAtePreto(const.esq, 90)
            print("aaa")
            mov.reto(5, const.tras)
            cr.Fez90.reseta()
        

    elif cr.PretoDirEX.tempo() < 100 and cr.PretoEsEX.tempo() > 800 and cr.Fez90.tempo() > 500:
        print("dir")

        mov.reto(12)

        if con.tudoBranco():
            print("dir valido")
            mov.girarGrausAtePreto(const.dir, 90)
            print("aaa")
            mov.reto(5, const.tras)
            cr.Fez90.reseta()

def verde():
    if cr.VerdeEs.tempo() < 100 and cr.VerdeDir.tempo() > 600 and cr.FezVerde.tempo() > 500:
        print("verde esq")
        mov.reto(12)

        if cr.PretoEsEX.tempo() < cr.VerdeEs.tempo():
            if cr.VerdeEs.tempo() < 100:
                print("verde 180 valido")
                mov.girarGraus(const.dir, 180)
                mov.reto(5, const.tras)
                cr.FezVerde.reseta()
            else:
                print("verde esq valido")
                mov.girarGraus(const.esq, 90)
                mov.reto(5, const.tras)
                cr.FezVerde.reseta()

    elif cr.VerdeEs.tempo() > 600 and cr.VerdeDir.tempo() < 100 and cr.FezVerde.tempo() > 500:
        print("verde dir")
        mov.reto(12)

        if cr.PretoDirEX.tempo() < cr.VerdeDir.tempo():
            if cr.VerdeEs.tempo() < 100:
                print("verde 180 valido")
                mov.girarGraus(const.dir, 180)
                mov.reto(5, const.tras)
                cr.FezVerde.reseta()
            else:
                print("verde dir valido")
                mov.girarGraus(const.dir, 90)
                mov.reto(5, const.tras)
                cr.FezVerde.reseta()

    if cr.VerdeEs.tempo() < 100 and cr.VerdeDir.tempo() < 100 and cr.FezVerde.tempo() > 500:
        print("verde 180")
        mov.reto(12)

        if cr.PretoDirEX.tempo() < cr.VerdeDir.tempo():
            print("verde 180 valido")
            mov.girarGraus(const.dir, 180)
            mov.reto(5, const.tras)
            cr.FezVerde.reseta()

