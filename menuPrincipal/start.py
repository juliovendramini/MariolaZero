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
    if teclado.le_botao(1) == Teclado.APERTADO:
        tela.mover_para_baixo()
        sleep(0.5)
    if teclado.le_botao(2) == Teclado.APERTADO:
        tela.mover_para_cima()
        sleep(0.5)
    if(cronometroAtualizarTela.tempo() > 1000):
        tela.atualizar_menu()
        cronometroAtualizarTela.reseta()
    if(teclado.le_botao(3) == Teclado.APERTADO):
        tela.executar_opcao_selecionada()
        sleep(0.5)
    
    if(teclado.le_botao(4) == Teclado.APERTADO):
        cronometroAtualizarTela.reseta()
        while(teclado.le_botao(4) == Teclado.APERTADO and cronometroAtualizarTela.tempo() < 2000):
            pass
        if(cronometroAtualizarTela.tempo() >= 2000):
            tela.modo_menu = tela.MENU_DESLIGAR
            tela.opcao_selecionada = 0
            tela.atualizar_menu()
            while(teclado.le_botao(4) == Teclado.APERTADO):
                pass
        else:
            tela.modo_menu = tela.MENU_PRINCIPAL
            tela.opcao_selecionada = 0
            tela.atualizar_menu()

    if(contadorAnaliseTelaTravada > 10):
        contadorAnaliseTelaTravada = 0
        tela.aguarda_se_tela_em_uso_por_outro_processo()
    else:
        contadorAnaliseTelaTravada += 1
    sleep(0.1)