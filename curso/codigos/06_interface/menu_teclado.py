"""Tutorial 6b — escolher o que o robô vai fazer pelo teclado do brick, com a tela OLED e os LEDs.

Placa da tela + teclado (conector TELA, barramento I2C 0):
  botões, da esquerda para a direita: Voltar, Baixo, Cima, Enter
  LEDs,   da esquerda para a direita: branco, vermelho, laranja, verde
No simulador a tela e o teclado aparecem no canto do mapa: clique nos botões ou use F1..F4.
    python simulador.py --programa CAMINHO/06_interface/menu_teclado.py
"""
import time

from tela import Tela
from teclado import Teclado

OPCOES = ['Seguir linha', 'Calibrar cores', 'Testar garra', 'Sair']
LED_BRANCO, LED_VERMELHO, LED_LARANJA, LED_VERDE = 1, 2, 3, 4
LED_ACENDE_COM = 0      # na placa atual o LED acende com o bit em 0 (confira no seu brick)


def abre_teclado():
    """O teclado fica no barramento 0 (placa nova, junto com a tela) ou no 1 (placa antiga)."""
    for barramento in (0, 1):
        try:
            return Teclado(i2c_bus=barramento)
        except OSError:
            pass
    raise RuntimeError('teclado não encontrado')


def led(numero, aceso):
    teclado.altera_led(numero, LED_ACENDE_COM if aceso else 1 - LED_ACENDE_COM)


def apaga_leds():
    for n in (1, 2, 3, 4):
        led(n, False)


def apertou(botao):
    """True só uma vez por aperto (espera soltar)."""
    if teclado.le_botao(botao) == Teclado.APERTADO:
        while teclado.le_botao(botao) == Teclado.APERTADO:
            time.sleep(0.02)
        return True
    return False


def mostra_menu(escolha):
    tela.escreve('Escolha o programa:', 0)
    for i in range(3):                      # 3 linhas de opções, a escolhida no meio quando dá
        k = max(0, min(len(OPCOES) - 3, escolha - 1)) + i
        tela.escreve(('> ' if k == escolha else '  ') + OPCOES[k], i + 1)


tela = Tela()
teclado = abre_teclado()
apaga_leds()
led(LED_BRANCO, True)                       # branco: esperando escolha
escolha = 0
mostra_menu(escolha)
fim = time.time() + 30
while time.time() < fim:
    if apertou(Teclado.BOTAO_BAIXO):
        escolha = (escolha + 1) % len(OPCOES)
        mostra_menu(escolha)
    elif apertou(Teclado.BOTAO_CIMA):
        escolha = (escolha - 1) % len(OPCOES)
        mostra_menu(escolha)
    elif apertou(Teclado.BOTAO_ENTER):
        apaga_leds()
        led(LED_VERDE, True)                # verde: escolhido
        tela.limpa()
        tela.escreve('Escolhido:', 0)
        tela.escreve(OPCOES[escolha], 1)
        print('escolhido:', OPCOES[escolha])
        time.sleep(2)
        break
    elif apertou(Teclado.BOTAO_VOLTAR):
        apaga_leds()
        led(LED_VERMELHO, True)             # vermelho: cancelado
        tela.limpa()
        tela.escreve('Cancelado', 0)
        print('cancelado')
        time.sleep(2)
        break
    time.sleep(0.05)
apaga_leds()
