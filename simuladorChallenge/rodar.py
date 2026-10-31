"""Executa o programa do aluno ligado ao simulador.

Normalmente quem chama este arquivo é o próprio simulador (botão Iniciar).
Uso manual (com o simulador já aberto):  python rodar.py caminho/do/main.py
"""

import os
import runpy
import sys
import traceback

RAIZ = os.path.dirname(os.path.abspath(__file__))


def main():
    if len(sys.argv) < 2:
        print('uso: python rodar.py caminho/do/main.py')
        sys.exit(2)
    programa = os.path.abspath(sys.argv[1])
    pasta = os.path.dirname(programa)

    sys.path.insert(0, RAIZ)
    import fake_hw
    sys.path.remove(RAIZ)
    fake_hw.instalar(pasta, os.path.join(RAIZ, 'libs_mariola'))

    os.chdir(pasta)
    sys.argv = [programa] + sys.argv[2:]
    try:
        runpy.run_path(programa, run_name='__main__')
    except KeyboardInterrupt:
        print('\n[simulador] programa interrompido (KeyboardInterrupt)')
    except SystemExit:
        raise
    except BaseException:
        traceback.print_exc()
        sys.stdout.flush()
        os._exit(1)
    sys.stdout.flush()
    os._exit(0)   # não espera threads das libs


if __name__ == '__main__':
    main()
