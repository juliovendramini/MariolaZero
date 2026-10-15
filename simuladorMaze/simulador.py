"""Simulador RoboCupJunior Rescue Maze para o robô com brick Mariola.

Uso:
    python simulador.py --programa ../meuRobo/main.py --mapa mapas/exemplo1.json

    # sem janela (para testes em lote): roda uma rodada e imprime o placar
    python simulador.py --programa exemplo_aluno/main.py --mapa mapas/exemplo1.json --sem-janela --velocidade 4
"""

import argparse
import os
import sys
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

from sim.app import Simulacao, carregar_cfg  # noqa: E402
from sim.mapa import Mapa  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='Simulador RoboCupJunior Rescue Maze (Mariola)')
    ap.add_argument('--mapa', default=os.path.join(RAIZ, 'mapas', 'exemplo1.json'))
    ap.add_argument('--programa', default=os.path.join(RAIZ, 'exemplo_aluno', 'main.py'),
                    help='main.py do programa do robô')
    ap.add_argument('--robo', default=os.path.join(RAIZ, 'robo.json'), help='configuração do robô')
    ap.add_argument('--sem-janela', action='store_true', help='roda uma rodada sem interface gráfica')
    ap.add_argument('--velocidade', type=float, default=1.0, help='fator de tempo (ex.: 2 = 2x mais rápido)')
    ap.add_argument('--tempo', type=float, default=480, help='(sem janela) duração máxima da rodada em s simulados')
    ap.add_argument('--semente', type=int, default=None, help='semente do ruído (repetibilidade)')
    ap.add_argument('--porta', type=int, default=0, help='porta TCP local (0 = automática)')
    ap.add_argument('--lop', choices=['reiniciar', 'botao'], default='reiniciar')
    a = ap.parse_args()

    cfg = carregar_cfg(a.robo)
    mapa = Mapa.carregar(a.mapa) if a.mapa and os.path.exists(a.mapa) else Mapa()
    programa = a.programa if a.programa and os.path.exists(a.programa) else None
    if a.programa and not programa:
        print(f'aviso: programa {a.programa} não encontrado')
    sim = Simulacao(mapa, cfg, programa, a.porta, a.semente)
    sim.modo_lop = a.lop
    sim.set_fator(a.velocidade)

    if a.sem_janela:
        roda_sem_janela(sim, a.tempo)
    else:
        from sim.gui import Interface
        Interface(sim, os.path.join(RAIZ, 'mapas')).rodar()


def roda_sem_janela(sim, tempo):
    sim.nova_rodada()
    sim.iniciar_rodada()
    j = sim.juiz
    t_real = time.time()
    try:
        while not j.fim and j.tempo < tempo:
            time.sleep(0.2)
            if not sim.programa_rodando() and not sim.em_lop and time.time() - t_real > 3:
                time.sleep(1.0)
                if not sim.programa_rodando() and not sim.em_lop:
                    print('[simulador] o programa terminou')
                    break
    except KeyboardInterrupt:
        pass
    total, partes, info = j.placar()
    sim.encerrar()
    print('\n================ RESULTADO ================')
    for (t, txt, p) in j.eventos:
        print(f'{int(t // 60)}:{t % 60:05.2f}  {p:+4d}  {txt}' if p else f'{int(t // 60)}:{t % 60:05.2f}        {txt}')
    print('-------------------------------------------')
    for k, v in partes.items():
        print(f'{k:>15}: {v}')
    print(f'{"TOTAL":>15}: {total}   {info}   tempo {j.tempo:.1f} s   (real {time.time() - t_real:.1f} s)')


if __name__ == '__main__':
    main()
