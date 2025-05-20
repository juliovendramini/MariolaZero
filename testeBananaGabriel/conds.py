import sensor as sen
import crono as cr
import constantes as consts

def tudoBranco():
    if cr.PretoDirEX.tempo() > 100 and cr.PretoDir.tempo() > 100 and cr.PretoEs.tempo() > 100 and cr.PretoEsEX.tempo() > 100:
        return True
    else: return False