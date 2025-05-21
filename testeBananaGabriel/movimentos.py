from defs import motores
from defs import giroscopio
from defs import sleep
import sensor as se
from constantes import esq, dir, frente, tras, velRapida, DELTA
import crono as cr


m = motores

#motor esquerdo vai ser o 1 e o direito o 2

erroAnterior = 0
def pid():
    global erroAnterior

    # print(sensor.leReflexaoTodos())
    
    kp = 0.5
    kd = 1.5
    erro = se.erro_pid()
 

    p = erro * kp 
    d = (erro - erroAnterior) * kd
    
    vb_pid = 50
    valor = p + d #variacao da potencia do motor
    # print(erro)
    valor = int(valor)
    # print(valor)

    # valorEsq = vb_pid + valor
    # valorDir = vb_pid - valor

    # if valorEsq > 100:
    #     valorEsq -= 100
    # else: valorEsq = 0

    # if valorDir > 100:
    #     valorDir -= 100
    # else: valorDir = 0

    #m.potenciaMotores(vb_pid + valor, vb_pid - valor)
    m.potenciaMotores(vb_pid + valor, vb_pid - valor)
    # m.velocidadeMotores(vb_pid + valor, vb_pid - valor)
    

    # m.velocidadeMotor(esq, vb_pid + valor - valorDir) # +
    # m.velocidadeMotor(dir, vb_pid - valor - valorEsq) # -

    # m.velocidadeMotor(esq, vb_pid + valor) # +
    # m.velocidadeMotor(dir, vb_pid - valor) # -
    
    erroAnterior = erro


def reto(cm, direc = frente, vb = 80):
    #sleep(0.2)
    print("anda reto")
    distancia = cm * 46 #valor encontrado por meio de testes
 
    if direc == frente: 
        m.moveMotores(vb, distancia, vb, distancia)
        # sleep(0.1)
        # cr.dorme(400)
        # if not(m.estadoMotor(1) == m.PARADO and m.estadoMotor(2) == m.PARADO): 
        #     m.velocidadeMotores(vb, vb - DELTA)


    if direc == tras: 
        m.moveMotores(-vb, distancia, -(vb) - DELTA, distancia)
        # sleep(0.1)
        # cr.dorme(400)
        # if not(m.estadoMotor(1) == m.PARADO and m.estadoMotor(2) == m.PARADO): 
        #     m.velocidadeMotores(-vb, -vb - DELTA)

    counter = 0
    cr.espera.reseta()
    while True:
        # cr.reset()
        # print(se.leReflexaoTodos())
        m.estado()
        if m.estadoMotor(1) == m.PARADO and m.estadoMotor(2) == m.PARADO: break
        counter += 1
        if cr.espera.tempo() > 1000: 
            print("tempo demais no loop do reto")
            raise Exception("tempo demais no loop do reto")
            break

    print("numero de loops do reto: ", counter)
        
    m.paraMotores()
    sleep(1)

# def reto(cm, direc = frente, vb = 30):
#     print("anda reto")
#     distancia = cm * 46
#     if direc == frente: 

#         m.moveMotores(vb, distancia, vb, distancia)

#     if direc == tras: 

#         m.moveMotores(-vb, distancia, -vb, distancia)
#     print("anda reto fim")

def girarGraus(direc, graus, vb = velRapida):

    print("girando")

    giroscopio.resetaZ()

    while graus > abs(giroscopio.leAnguloZ()):
        # cr.reset()
        # print(angFinal, giroscopio.leAnguloZ())
        if direc == esq:
            if graus*0.5 < abs(giroscopio.leAnguloZ()):
                m.velocidadeMotores(-2*vb/5, 2*vb/5 - DELTA)

            else: m.velocidadeMotores(-vb, vb - DELTA)

        elif direc == dir:
            if graus*0.5 < abs(giroscopio.leAnguloZ()):
                m.velocidadeMotores(2*vb/5, -2*vb/5 - DELTA)

            else: m.velocidadeMotores(vb, -vb - DELTA)

    m.paraMotores()
    
def girarGrausAtePreto(direc, graus, vb = velRapida):
    # m.paraMotores()
    # cr.dorme(50)
    # sleep(0.2)

    giroscopio.resetaZ()

    while graus > abs(giroscopio.leAnguloZ()):
        # cr.reset()
        # print(angFinal, giroscopio.leAnguloZ())
        if cr.PretoDir.tempo() < 60 and cr.PretoEs.tempo() < 60: 
                m.paraMotores()
                break
        
        if direc == esq:
            if graus*0.6 < abs(giroscopio.leAnguloZ()):
                m.velocidadeMotores(-2*vb/5, 2*vb/5 - DELTA)

            else: m.velocidadeMotores(-vb, vb - DELTA)

        elif direc == dir:
            if graus*0.6 < abs(giroscopio.leAnguloZ()):
                m.velocidadeMotores(2*vb/5, -2*vb/5 - DELTA)

            else: m.velocidadeMotores(vb, -vb - DELTA)

    m.paraMotores()
    

