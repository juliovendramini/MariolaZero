import time
import os

#retorna um tempo passado em milisegundos
class Cronometro:
    # se a criação do cronometro for sem nome de arquivo, ele não salva o tempo em arquivos
    # essa situação é utilizaza para cronometros temporarios
    def __init__(self, nomeArquivo = None):
        self.nomeArquivo = nomeArquivo
        self.tempo_inicial = None

    def inicia(self):
        self.tempo_inicial = time.time()
        if(self.nomeArquivo != None):
            self.salva()

    #so funciona se tiver salvo em arquivo
    def apaga(self):
        if(self.nomeArquivo != None):
            self.tempo_inicial = None
            temp = "rm " + str(self.nomeArquivo)
            os.system(str(temp))

    def reseta(self):
        self.tempo_inicial = time.time()
        self.salva()

    #retorna o tempo passado em milisegundos
    def tempo(self):
        if(self.tempo_inicial == None):
            return None
        return int(time.time()*1000 - self.tempo_inicial*1000)

    def salva(self):
        if(self.nomeArquivo != None):
            with open(self.nomeArquivo, 'w') as f:
                f.write(str(self.tempo_inicial))

    def carrega(self):
        if(self.nomeArquivo != None):
            try:
                with open(self.nomeArquivo, 'r') as f:
                    self.tempo_inicial = float(f.read())
            except: # se não conseguir carregar o arquivo, inicia o cronometro
                self.tempo_inicial = time.time()
                self.salva()