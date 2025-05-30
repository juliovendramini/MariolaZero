import sensor as sen
import crono as cr
import constantes as consts

def tudoBranco():
    if cr.PretoDirEX.tempo() > 100 and cr.PretoDir.tempo() > 100 and cr.PretoEs.tempo() > 100 and cr.PretoEsEX.tempo() > 100:
        return True
    else: return False

def meioBranco():
    if cr.PretoDir.tempo() > 100 and cr.PretoEs.tempo() > 100:
        return True
    else: return False

def tudoVermelho():
    if cr.VermEs.tempo() < 100 and cr.VermMeio.tempo() < 100 and cr.VermDir.tempo() < 100: return True
    else: return False

def tudoPrata():
    if cr.PrataEs.tempo() < 100 and cr.PrataMeio.tempo() < 100 and cr.PrataDir.tempo() < 100: return True; print("tudo prata")
    else: return False