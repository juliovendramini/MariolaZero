from defs import sensorCor

import constantes as const


#RETORNA OS VALORES DE REFLEXAO
def leReflexaoEsqEX(): 
    return sensorCor.leReflexao()[3]

def leReflexaoEsq(): 
    return sensorCor.leReflexao()[2]

def leReflexaoDir(): 
    return sensorCor.leReflexao()[1]

def leReflexaoDirEX(): 
    return sensorCor.leReflexao()[0]

def leReflexaoTodos():
    return sensorCor.leReflexao()

#calcula o erro pro pid
def erro_pid():
    return (leReflexaoEsqEX() + leReflexaoEsq()) - (leReflexaoDirEX() + leReflexaoDir())


#RETORNA OS VALORES RGBC
def leRGBCesq():
    return sensorCor.leRGBC(1)

def leRGBCmeio():
    return sensorCor.leRGBC(2)

def leRGBCdir():
    return sensorCor.leRGBC(3)


#RETORNA OS VALORES HSV 
def leHSVesq():
    return sensorCor.leHSV(3)

def leHSVmeio():
    return sensorCor.leHSV(2)

def leHSVdir():
    return sensorCor.leHSV(1)


#FAZ A CHEACAGEM DE COR POR VALORES HSV
def checarCorHSV(valores):
    h = valores[0]
    s = valores[1]
    v = valores[2]

    #checa se os valores estao dentro de um intervalo especifico encontrado por meio de testes
    if (65 >= h >= 45) and (s >= 30) and (v > 10): #VERDE

        return const.verde
    
    elif ((7 >= h >= 0) or (125 >= h >= 123)) and (s >= 55) and (v > 10): #VERMELHO

        return const.vermelho
    
    else:
        return "erro"
    

#FAZ A CHEACAGEM DE COR POR VALORES RGB
def checarCorRGBC(valores):
    r = valores[0]
    g = valores[1]
    b = valores[2]
    c = valores[3]


    #checa se os valores estao dentro de um intervalo especifico encontrado por meio de testes
    
    ## ainda falta fazer os testes
    ## eu imagino que eu so vou precisar de usar essa funcao pra prata
