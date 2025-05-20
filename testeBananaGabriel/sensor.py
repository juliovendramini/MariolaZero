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
    return sensorCor.leReflexao()[3], sensorCor.leReflexao()[2], sensorCor.leReflexao()[1], sensorCor.leReflexao()[0]

#calcula o erro pro pid
def erro_pid():
    valErro = (leReflexaoEsqEX()*1.5 + leReflexaoEsq()) - (leReflexaoDirEX()*1.5 + leReflexaoDir())
    valErro = valErro/2
    # valErro = (leReflexaoEsqEX() + leReflexaoEsq()) - (leReflexaoDirEX() + leReflexaoDir())
    # valErro = (leReflexaoEsq()) - (leReflexaoDir())
    # valErro = valErro/2.5
    # if valErro > 100: valErro = 100
    # if valErro < -100: valErro = -100
    return valErro

def calculoErro(): #TA DANDO UM ERRO ESTRANHO

    valores_temp = [0,0,0,0]
    #são varias possbilidades
    #sensor 0 apenas na linha
    #sensor 3 apenas na linha
    #sensor 0 e 1 na linha
    #sensor 1 e 2 na linha
    #sensor 2 e 3 na linha
    #tres ou mais sensores na linha
    #na OBR o fundo é branco e a linha é preta então temos que invertar os valores
    valores_temp[0] = 100 - leReflexaoDirEX()
    valores_temp[1] = 100 - leReflexaoDir()
    valores_temp[2] = 100 - leReflexaoEsq()
    valores_temp[3] = 100 - leReflexaoEsqEX()
    posicao = 0
    posicaoSinal = 0
    ultimaPosicao = 0
    
    FORA=20
    QUANTIDADE_SENSORES = 4
    #tudo fora, retorna 0
    if(valores_temp[0] <= FORA and valores_temp[1] <= FORA and valores_temp[2] <= FORA and valores_temp[3] <= FORA):
        if(ultimaPosicao > 0):
                return 0
        else:
                return 0
        
    
    #se der valor baixo ignoro tbm
    if((valores_temp[0] + valores_temp[1] + valores_temp[2] + valores_temp[3]) < (QUANTIDADE_SENSORES*FORA)):
        if(ultimaPosicao > 0):
                return 0
        else:
                return 0
        
    
    #tudo dentro, retorna valor anterior
    if(valores_temp[0] > FORA and valores_temp[1] > FORA and valores_temp[2] > FORA and valores_temp[3] > FORA):
        return 0 
        #return ultimaPosicao;
    

    maiorValor = valores_temp[0];
    indiceMaiorValor = 0;
    i=1
    while( i < QUANTIDADE_SENSORES):
        if(valores_temp[i] > maiorValor):
                maiorValor = valores_temp[i];
                indiceMaiorValor = i;
        i+=1 
        
    
    
    if indiceMaiorValor == 0:
        if(valores_temp[1] <= FORA):
                posicao = 100 - valores_temp[0] / 4;
        else:
                posicao = 25 + ((valores_temp[0])) / 4 + (valores_temp[0] - valores_temp[1]) / 4;
        
    
    elif indiceMaiorValor == 1:
        if(valores_temp[0] > valores_temp[2]):
        #posicao = 25 + ((valores_temp[1] - valores_temp[0])) / 4;
                posicao = 25 + ((valores_temp[0])) / 4;
        else:
                posicao = ((valores_temp[1] - valores_temp[2])) / 4;
        
        
    
    elif indiceMaiorValor == 2:
        if(valores_temp[1] > valores_temp[3]):
                posicao = ((valores_temp[1] - valores_temp[2])) / 4;
        else:
                posicao = -25 - (valores_temp[3]) / 4;
        
        
    
    elif indiceMaiorValor == 3:
        if(valores_temp[2] <= FORA):
                posicao = -100 + (valores_temp[3]) / 4; 
        else:
                posicao = -25 - (valores_temp[3]) / 4 - ((valores_temp[3] - valores_temp[2])) / 4;


    posicaoSinal = posicao
    ultimaPosicao = posicaoSinal
    # posicaoSinal = posicao - 100;
    return posicaoSinal


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
    if (55 >= h >= 30) and (s >= 15) and (v > 15): #VERDE

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
