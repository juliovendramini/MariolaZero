"""Compila e executa o programa do brick Paçoca (.ino) ligado ao simulador.

Normalmente quem chama este arquivo é o próprio simulador (botão Iniciar), quando o programa
é um .ino. Uso manual (com o simulador já aberto):  python rodar_pacoca.py caminho/do/programa.ino
Só compilar (para ver os erros):                     python pacoca/compila.py caminho/do/programa.ino
"""

import os
import sys

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

from pacoca import compila, ponte  # noqa: E402

REINICIA = 42      # o brick fez reset (jmp 0): o programa começa de novo


def main():
    if len(sys.argv) < 2:
        print('uso: python rodar_pacoca.py caminho/do/programa.ino')
        sys.exit(2)
    ino = os.path.abspath(sys.argv[1])
    pasta = os.path.dirname(ino)
    try:
        exe = compila.compila(ino, log=lambda s: print(s, flush=True))
    except compila.ErroCompilacao as e:
        print('[simulador] erro de compilação:\n' + str(e), flush=True)
        sys.exit(1)
    while True:
        p = ponte.Ponte(exe, pasta)
        rc = p.roda()
        if rc == REINICIA and not p.parar:
            print('[simulador] o programa reiniciou', flush=True)
            continue
        break
    sys.stdout.flush()
    os._exit(rc if isinstance(rc, int) and rc >= 0 else 0)


if __name__ == '__main__':
    main()
