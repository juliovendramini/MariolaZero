from time import sleep
from cronometro import Cronometro
from telaMenu import MenuPrincipal
from teclado import Teclado

tela = MenuPrincipal()
teclado = Teclado()
cronometroAtualizarTela = Cronometro()
cronometroAtualizarTela.inicia()
contadorAnaliseTelaTravada = 0
while True:
    if teclado.leBotao(1) == Teclado.APERTADO:
        tela.moverParaBaixo();
        sleep(0.5)
    if teclado.leBotao(2) == Teclado.APERTADO:
        tela.moverParaCima();
        sleep(0.5)
    if(cronometroAtualizarTela.tempo() > 1000):
        tela.atualizarMenu()
        cronometroAtualizarTela.reseta()
    if(teclado.leBotao(3) == Teclado.APERTADO):
        tela.executarOpcaoSelecionada()
        sleep(0.5)
    
    if(teclado.leBotao(4) == Teclado.APERTADO):
        cronometroAtualizarTela.reseta()
        while(teclado.leBotao(4) == Teclado.APERTADO and cronometroAtualizarTela.tempo() < 2000):
            pass
        if(cronometroAtualizarTela.tempo() >= 2000):
            tela.modoMenu = tela.MENU_DESLIGAR
            tela.opcaoSelecionada = 0
            tela.atualizarMenu()
            while(teclado.leBotao(4) == Teclado.APERTADO):
                pass
        else:
            tela.modoMenu = tela.MENU_PRINCIPAL
            tela.opcaoSelecionada = 0
            tela.atualizarMenu()

    if(contadorAnaliseTelaTravada > 10):
        contadorAnaliseTelaTravada = 0
        tela.aguardaSeTelaEmUsoPorOutroProcesso()
    else:
        contadorAnaliseTelaTravada += 1
    sleep(0.1)