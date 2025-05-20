from defs import motores
from defs import giroscopio
from defs import sleep
import sensor
from constantes import esq, dir, frente, tras, velRapida, DELTA
import crono as cr


m = motores

#motor esquerdo vai ser o 1 e o direito o 2

erroAnterior = 0
def pid():
    global erroAnterior

    # print(sensor.leReflexaoTodos())
    
    kp = 0.32
    kd = 2.3

    erro = sensor.erro_pid()

    p = erro * kp 
    d = (erro - erroAnterior) * kd
    
    vb_pid = 60
    valor = p + d #variacao da potencia do motor
    # print(erro, valor)
    valor = int(valor)

    m.velocidadeMotor(esq, vb_pid + valor) # +
    m.velocidadeMotor(dir, vb_pid - valor) # -
    
    erroAnterior = erro


def reto(cm, direc = frente, vb = velRapida):
    distancia = cm * 17 #valor encontrado por meio de testes
 
    if direc == frente: 

        m.moveMotores(vb/2, distancia, (vb/2) - DELTA, distancia)

        sleep(0.1)
        m.estado()
        if not(m.estadoMotor(1) == m.PARADO and m.estadoMotor(2) == m.PARADO): 
            m.velocidadeMotores(vb, vb - DELTA)


    if direc == tras: 
        m.moveMotores(-vb/2, distancia, -(vb/2) - DELTA, distancia)

        sleep(0.1)
        m.estado()
        if not(m.estadoMotor(1) == m.PARADO and m.estadoMotor(2) == m.PARADO): 
            m.velocidadeMotores(-vb, -vb - DELTA)


    while True:
        cr.reset()
        m.estado()
        if m.estadoMotor(1) == m.PARADO and m.estadoMotor(2) == m.PARADO: break
        sleep(0.05)


    m.paraMotores()

def girarGraus(direc, graus, vb = velRapida):

    giroscopio.resetaZ()

    while graus > abs(giroscopio.leAnguloZ()):
        cr.reset()
        # print(angFinal, giroscopio.leAnguloZ())
        if direc == esq:
            if graus*0.5 < abs(giroscopio.leAnguloZ()):
                m.velocidadeMotores(-vb/2, vb/2 - DELTA)

            else: m.velocidadeMotores(-vb, vb - DELTA)

        elif direc == dir:
            if graus*0.5 < abs(giroscopio.leAnguloZ()):
                m.velocidadeMotores(vb/2, -vb/2 - DELTA)

            else: m.velocidadeMotores(vb, -vb - DELTA)

    m.paraMotores()
    
def girarGrausAtePreto(direc, graus, vb = velRapida):

    giroscopio.resetaZ()

    while graus > abs(giroscopio.leAnguloZ()):
        cr.reset()
        # print(angFinal, giroscopio.leAnguloZ())
        if cr.PretoDir.tempo() < 60 and cr.PretoEs.tempo() < 60: 
                break
        
        if direc == esq:
            if graus*0.5 < abs(giroscopio.leAnguloZ()):
                m.velocidadeMotores(-vb/2, vb/2 - DELTA)

            else: m.velocidadeMotores(-vb, vb - DELTA)

        elif direc == dir:
            if graus*0.5 < abs(giroscopio.leAnguloZ()):
                m.velocidadeMotores(vb/2, -vb/2 - DELTA)

            else: m.velocidadeMotores(vb, -vb - DELTA)

    m.paraMotores()
    

