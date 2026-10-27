"""Calibração das cores do piso no campo (no tempo de calibração da rodada).

Branco: os três TCS sobre o branco. Preto, verde e vermelho: só o TCS do MEIO sobre a cor
(a linha e o marcador verde são estreitos). Aperte o botão de início em cada cor.
As referências vão para cores_line.json, que o robo.py carrega.

No simulador: rode este arquivo com --programa exemplo_aluno/calibra_cores.py e arraste o
robô (com o programa parado entre as cores) ou use o Q/E para posicionar.
"""

import time

from pinosDigitais import PinosDigitais
from portas import Portas
from sensorCorReflexao import CorReflexao

CORES = [('branco', (1, 2, 3)), ('preto', (2,)), ('verde', (2,)), ('vermelho', (2,))]


def espera_botao(b):
    while not b.botao_pressionado(PinosDigitais.P3):
        time.sleep(0.02)
    while b.botao_pressionado(PinosDigitais.P3):
        time.sleep(0.02)


def main():
    cor = CorReflexao(Portas.SERIAL6, arquivo_cores='cores_line.json')
    cor.usa_cores([n for n, _ in CORES])
    b = PinosDigitais()
    for nome, sensores in CORES:
        onde = 'os três sensores de cor' if len(sensores) == 3 else 'o sensor de cor do MEIO'
        print(f'Coloque {onde} sobre o {nome.upper()} e aperte o botão')
        espera_botao(b)
        media, _ = cor.aprende_cor(nome, sensores=sensores)
        print(f'  {nome}: média {[round(x, 3) for x in media]}')
    cor.salva_cores('cores_line.json')
    print('Gravado em cores_line.json. Conferindo (aperte o botão para ler, Ctrl+C sai):')
    while True:
        espera_botao(b)
        print(cor.cores(), cor.le_reflexao())


if __name__ == '__main__':
    main()
