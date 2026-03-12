from time import sleep
from cronometro import Cronometro
from telaMenu import MenuPrincipal
from teclado import Teclado

tela = MenuPrincipal()

try:
    teclado = Teclado()
    teclado_encontrado = True
except Exception:
    teclado_encontrado = False

if(not teclado_encontrado): #vou tentar conectar na outra i2c
    try:
        teclado = Teclado(i2c_bus=0)
        teclado_encontrado = True
    except Exception:
        teclado_encontrado = False

if teclado_encontrado:
    cronometroAtualizarTela = Cronometro()
    cronometroAtualizarTela.inicia()
    contadorAnaliseTelaTravada = 0
    while True:
        if teclado.le_botao(teclado.BOTAO_BAIXO) == Teclado.APERTADO:
            tela.mover_para_baixo()
            sleep(0.5)
        if teclado.le_botao(teclado.BOTAO_CIMA) == Teclado.APERTADO:
            tela.mover_para_cima()
            sleep(0.5)
        if(cronometroAtualizarTela.tempo() > 1000):
            tela.atualizar_menu()
            cronometroAtualizarTela.reseta()
        if(teclado.le_botao(teclado.BOTAO_ENTER) == Teclado.APERTADO):
            tela.executar_opcao_selecionada()
            sleep(0.5)
        
        if(teclado.le_botao(teclado.BOTAO_VOLTAR) == Teclado.APERTADO):
            cronometroAtualizarTela.reseta()
            while(teclado.le_botao(teclado.BOTAO_VOLTAR) == Teclado.APERTADO and cronometroAtualizarTela.tempo() < 2000):
                pass
            if(cronometroAtualizarTela.tempo() >= 2000):
                tela.modo_menu = tela.MENU_DESLIGAR
                tela.opcao_selecionada = 0
                tela.atualizar_menu()
                while(teclado.le_botao(teclado.BOTAO_VOLTAR) == Teclado.APERTADO):
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
else:
    while True:
        tela.atualizar_menu()
        sleep(2)
        try:
            teclado = Teclado()
            teclado_encontrado = True
        except Exception:
            teclado_encontrado = False
        if teclado_encontrado:
            exit()