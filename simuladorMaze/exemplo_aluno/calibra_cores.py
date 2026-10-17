"""Calibração das cores do piso no campo (permitido no tempo de calibração da regra 5.3.2).

Coloque o robô com os três sensores de cor sobre cada cor e aperte o botão de início.
As referências vão para cores_piso.json, que o robô carrega (CorReflexao(arquivo_cores=...)).
"""

import time

from botoes import Botoes
from portas import Portas
from sensorCorReflexao import CorReflexao

CORES = ['branco', 'preto', 'prata', 'azul', 'vermelho']


def espera_botao(b):
    while not b.botao_pressionado(Botoes.P3):
        time.sleep(0.02)
    while b.botao_pressionado(Botoes.P3):
        time.sleep(0.02)


def main():
    cor = CorReflexao(Portas.SERIAL6, arquivo_cores='cores_piso.json')
    cor.usa_cores(CORES)
    b = Botoes()
    for nome in CORES:
        print(f'Coloque o robô sobre o {nome.upper()} e aperte o botão')
        espera_botao(b)
        media, _ = cor.aprende_cor(nome)
        print(f'  {nome}: média {[round(x, 3) for x in media]}')
    cor.salva_cores('cores_piso.json')
    print('Gravado em cores_piso.json. Conferindo (aperte o botão para ler, Ctrl+C sai):')
    while True:
        espera_botao(b)
        print(cor.cores(), '->', cor.cor_piso(), cor.distancias(2)[:2])


if __name__ == '__main__':
    main()
