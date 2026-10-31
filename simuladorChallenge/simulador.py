"""Simulador da RCB Challenge (CBR 2026) para robôs com o brick Mariola.

Uso:
    python simulador.py                                       # janela, robô mecanum, cenário de exemplo
    python simulador.py --cenario cenarios/vazio.json --programa ../meuRobo/main.py
    python simulador.py --sortear 7                           # cenário sorteado (semente 7)

    # sem janela (para testes em lote): roda uma partida e imprime o placar
    python simulador.py --programa exemplo_aluno/main.py --sem-janela --velocidade 4
"""

import argparse
import json
import os
import random
import sys
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

# Windows: com a saída redirecionada (arquivo, pipe) o Python escreve em cp1252, que não tem todos
# os símbolos que o programa do aluno pode imprimir. No terminal já sai Unicode.
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(errors='replace', **({} if _f.isatty() else {'encoding': 'utf-8'}))
    except Exception:
        pass

from sim import arena as A  # noqa: E402
from sim.app import Simulacao, carregar_cfg  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='Simulador RCB Challenge (Mariola)')
    ap.add_argument('--cenario', default=os.path.join(RAIZ, 'cenarios', 'exemplo.json'),
                    help='cubos, plataformas e início do robô (cenarios/*.json)')
    ap.add_argument('--sortear', type=int, default=None, metavar='SEMENTE',
                    help='sorteia o cenário dentro da regra (a mesma semente dá o mesmo cenário)')
    ap.add_argument('--programa', default=None, help='main.py do programa do robô')
    ap.add_argument('--robo', default='robo_garra.json', help='configuração do robô')
    ap.add_argument('--sem-janela', action='store_true', help='roda uma partida sem interface gráfica')
    ap.add_argument('--velocidade', type=float, default=1.0, help='fator de tempo (ex.: 2 = 2x mais rápido)')
    ap.add_argument('--tempo', type=float, default=720, help='(sem janela) duração máxima da partida em s simulados')
    ap.add_argument('--semente', type=int, default=1,
                    help='semente do ruído: a mesma semente repete a partida igual (-1 = sorteia a cada partida)')
    ap.add_argument('--tempo-real', action='store_true',
                    help='modo antigo: o programa corre no relógio real (o resultado muda com a velocidade e o PC)')
    ap.add_argument('--porta', type=int, default=0, help='porta TCP local (0 = automática)')
    ap.add_argument('--resultado', default=None,
                    help='(sem janela) grava o placar da partida neste arquivo JSON')
    a = ap.parse_args()

    robo = a.robo
    if not os.path.exists(robo) and os.path.exists(os.path.join(RAIZ, robo)):
        robo = os.path.join(RAIZ, robo)
    cfg = carregar_cfg(robo)
    cfg['_arquivo'] = os.path.abspath(robo)
    if a.sortear is not None:
        cenario = A.sorteia(random.Random(a.sortear))
        cenario.nome = f'sorteado {a.sortear}'
    elif a.cenario and os.path.exists(a.cenario):
        cenario = A.Cenario.carregar(a.cenario)
    else:
        if a.cenario:
            print(f'aviso: cenário {a.cenario} não encontrado: pista vazia')
        cenario = A.Cenario()
    for aviso in cenario.validar():
        print('aviso do cenário:', aviso)
    programa = a.programa if a.programa and os.path.exists(a.programa) else None
    if a.programa and not programa:
        print(f'aviso: programa {a.programa} não encontrado')
    if a.programa is None:
        padrao = os.path.join(RAIZ, 'exemplo_aluno', 'main.py')
        programa = padrao if os.path.exists(padrao) else None
    sim = Simulacao(cenario, cfg, programa, a.porta, None if a.semente < 0 else a.semente)
    sim.sincronizado = not a.tempo_real
    sim.set_fator(a.velocidade)

    if a.sem_janela:
        roda_sem_janela(sim, a.tempo, a.resultado)
    else:
        from sim.gui import Interface
        ui = Interface(sim, os.path.join(RAIZ, 'cenarios'))
        ui.rodar()


def roda_sem_janela(sim, tempo, arq_resultado=None):
    sim.enter_automatico = True          # ninguém para apertar Enter: o input() do programa segue na hora
    sim.nova_rodada()
    sim.iniciar_rodada()
    j = sim.juiz
    t_real = time.time()
    motivo = None
    try:
        while not j.fim and j.tempo < tempo:
            time.sleep(0.2)
            if not sim.programa_rodando() and not sim.em_reinicio and time.time() - t_real > 3:
                time.sleep(1.0)
                if not sim.programa_rodando() and not sim.em_reinicio:
                    print('[simulador] o programa terminou')
                    motivo = 'o programa terminou'
                    break
    except KeyboardInterrupt:
        pass
    total, partes, info = j.placar()
    motivo = j.fim or motivo or ('acabou o tempo' if j.tempo >= tempo else 'interrompido')
    x, y, a = sim.robo.pose()
    sim.encerrar()
    if arq_resultado:
        res = {
            'total': total, 'partes': partes, 'info': info, 'tempo': round(j.tempo, 2), 'fim': motivo,
            'pose_final': [round(x, 1), round(y, 1), round(a * 57.29578, 1)],
            'eventos': [[round(t, 2), txt, p] for (t, txt, p) in j.eventos],
        }
        with open(arq_resultado, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print('\n================ RESULTADO ================')
    for (t, txt, p) in j.eventos:
        print(f'{int(t // 60)}:{t % 60:05.2f}  {p:+4d}  {txt}' if p else f'{int(t // 60)}:{t % 60:05.2f}        {txt}')
    print('-------------------------------------------')
    for k, v in partes.items():
        print(f'{k:>15}: {v}')
    print(f'{"TOTAL":>15}: {total}   {info}   tempo {j.tempo:.1f} s   (real {time.time() - t_real:.1f} s)')
    print(f'{"pose final":>15}: x={x:.0f} y={y:.0f} ângulo={a * 57.29578:.1f}°')


if __name__ == '__main__':
    main()
