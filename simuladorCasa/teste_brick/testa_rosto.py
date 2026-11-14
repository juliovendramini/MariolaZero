"""Mostra as carinhas do robô (rosto.py) na tela do brick (SSD1309 de 2,42", I2C 0, 0x3C).

    cd ~/robo_casa
    /meu_venv/bin/python testa_rosto.py                    (desfile: todas, 2,5 s cada, e a boca falando)
    /meu_venv/bin/python testa_rosto.py --carinha zoeiro --tempo 10
    /meu_venv/bin/python testa_rosto.py --mede             (quantos quadros por segundo a tela aguenta)
    ROSTO_GIRA=2 /meu_venv/bin/python testa_rosto.py       (tela montada de cabeça para baixo)

O menu do brick usa a mesma tela: pause o menu antes (kill -STOP no start.py) e continue depois
(kill -CONT), senão os dois desenham por cima um do outro.
"""

import argparse
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import rosto  # noqa: E402


def mostra(tela, nome, segundos, falando=False, quadros_s=10):
    """Anima uma carinha por um tempo, como o Rosto faz (com a boca que mexe, se falando)."""
    r = rosto.Rosto(tela)
    r.QUADROS_S = quadros_s
    if nome not in rosto.CARINHAS:
        raise SystemExit(f'não existe a carinha {nome!r}. Existem: {", ".join(rosto.CARINHAS)}')
    r.estado(nome)
    r.fala(falando)
    fim = time.time() + segundos
    while time.time() < fim:
        r.passo()
        time.sleep(0.01)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--carinha', help='só esta carinha')
    ap.add_argument('--tempo', type=float, default=2.5, help='segundos de cada carinha')
    ap.add_argument('--mede', action='store_true', help='mede quantos quadros por segundo a tela aguenta')
    ap.add_argument('--brilho', type=int, help='contraste da tela, 0 a 255')
    a = ap.parse_args()

    t = time.perf_counter()
    tela = rosto.abre_tela()
    if tela is None:
        raise SystemExit('não abri a tela')
    print(f'tela aberta em {time.perf_counter() - t:.2f} s ({type(tela).__name__}, gira {rosto.ROSTO_GIRA})', flush=True)
    if a.brilho is not None:
        tela.contrast(max(0, min(255, a.brilho)))

    if a.mede:
        nomes = list(rosto.CARINHAS)
        imgs = [rosto.quadro(nomes[i % len(nomes)], i * 0.1) for i in range(40)]
        t = time.perf_counter()
        for img in imgs:
            tela.display(img)
        gasto = (time.perf_counter() - t) / len(imgs)
        t = time.perf_counter()
        for i in range(40):
            rosto.quadro(nomes[i % len(nomes)], i * 0.1)
        desenho = (time.perf_counter() - t) / 40
        print(f'mandar um quadro para a tela: {gasto * 1000:.0f} ms ({1 / gasto:.0f} quadros/s); '
              f'desenhar um quadro: {desenho * 1000:.1f} ms', flush=True)
    elif a.carinha:
        mostra(tela, a.carinha, a.tempo)
    else:
        for i, nome in enumerate(rosto.CARINHAS, 1):
            print(f'{i:2}. {nome}', flush=True)
            mostra(tela, nome, a.tempo)
        print('falando (a boca mexe por cima da carinha)', flush=True)
        mostra(tela, 'feliz', 4.0, falando=True)
    tela.clear()


if __name__ == '__main__':
    main()
