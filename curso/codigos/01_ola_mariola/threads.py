"""Tutorial 1b — o que é uma thread: uma função que roda "ao mesmo tempo" que o programa.

    python simulador.py --programa CAMINHO/01_ola_mariola/threads.py --sem-janela

Não usa nenhum hardware: roda igual no robô, no simulador ou no seu computador (python threads.py).
"""
import threading
import time

contador = 0          # variável global: a thread escreve, o programa principal lê


def conta():
    """Roda na thread: soma 1 a cada 0,1 s, para sempre."""
    global contador
    while True:
        contador += 1
        time.sleep(0.1)          # enquanto esta thread dorme, as outras trabalham


thread = threading.Thread(target=conta, daemon=True)   # daemon=True: morre junto com o programa
thread.start()                                         # a partir daqui, conta() está rodando

for i in range(5):
    print(f'programa principal, volta {i}: contador = {contador}')
    time.sleep(0.5)              # o principal não chama conta(), mas o contador continua subindo

print('fim do programa principal (a thread daemon termina junto)')
