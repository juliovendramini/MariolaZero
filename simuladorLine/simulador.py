"""Simulador RoboCupJunior Rescue Line (só a linha, sem zona de resgate) para robôs com o brick Mariola.

Uso:
    python simulador.py                                   # janela, robô 4x4, mapa de treino
    python simulador.py --robo robo_esteira.json --mapa mapas/completo.json
    python simulador.py --programa ../meuRobo/main.py

    # sem janela (para testes em lote): roda uma rodada e imprime o placar
    python simulador.py --programa exemplo_aluno/main.py --sem-janela --velocidade 4
"""

import argparse
import json
import os
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

from sim.app import Simulacao, carregar_cfg, eh_pacoca, programa_do_robo  # noqa: E402
from sim.mapa import Mapa  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='Simulador RoboCupJunior Rescue Line (Mariola)')
    ap.add_argument('--mapa', default=os.path.join(RAIZ, 'mapas', 'treino.json'))
    ap.add_argument('--programa', default=None,
                    help='main.py do programa do robô (Mariola) ou o .ino (brick Paçoca)')
    ap.add_argument('--robo', default=None,
                    help='configuração do robô (robo_4x4.json, robo_esteira.json, robo_pacoca_amarelo.json...)')
    ap.add_argument('--sem-janela', action='store_true', help='roda uma rodada sem interface gráfica')
    ap.add_argument('--velocidade', type=float, default=1.0, help='fator de tempo (ex.: 2 = 2x mais rápido)')
    ap.add_argument('--tempo', type=float, default=480, help='(sem janela) duração máxima da rodada em s simulados')
    ap.add_argument('--semente', type=int, default=1,
                    help='semente do ruído: a mesma semente repete a rodada igual (-1 = sorteia a cada rodada)')
    ap.add_argument('--tempo-real', action='store_true',
                    help='modo antigo: o programa corre no relógio real (o resultado muda com a velocidade e o PC)')
    ap.add_argument('--porta', type=int, default=0, help='porta TCP local (0 = automática)')
    ap.add_argument('--lop', choices=['reiniciar', 'botao'], default='reiniciar')
    ap.add_argument('--resultado', default=None,
                    help='(sem janela) grava o placar da rodada neste arquivo JSON (usado pelo avalia.py)')
    ap.add_argument('--editor', action='store_true', help='abre direto no editor de mapas')
    a = ap.parse_args()

    robo = a.robo
    if robo is None:
        # programa .ino = brick Paçoca
        robo = 'robo_pacoca_amarelo.json' if (a.programa or '').lower().endswith('.ino') else 'robo_4x4.json'
    if not os.path.exists(robo) and os.path.exists(os.path.join(RAIZ, robo)):
        robo = os.path.join(RAIZ, robo)
    cfg = carregar_cfg(robo)
    cfg['_arquivo'] = os.path.abspath(robo)
    mapa = Mapa.carregar(a.mapa) if a.mapa and os.path.exists(a.mapa) else Mapa()
    programa = a.programa if a.programa and os.path.exists(a.programa) else None
    if a.programa and not programa:
        print(f'aviso: programa {a.programa} não encontrado')
    if a.programa is None:
        programa = programa_do_robo(cfg, None)
    elif programa and programa.lower().endswith('.ino') != eh_pacoca(cfg):
        print(f'aviso: o robô {os.path.basename(robo)} usa programa '
              f'{".ino (brick Paçoca)" if eh_pacoca(cfg) else ".py (brick Mariola)"}; '
              f'o {os.path.basename(programa)} não vai rodar nele')
    sim = Simulacao(mapa, cfg, programa, a.porta, None if a.semente < 0 else a.semente)
    sim.sincronizado = not a.tempo_real
    sim.modo_lop = a.lop
    sim.set_fator(a.velocidade)

    if a.sem_janela:
        roda_sem_janela(sim, a.tempo, a.resultado)
    else:
        from sim.gui import Interface
        ui = Interface(sim, os.path.join(RAIZ, 'mapas'), RAIZ)
        if a.editor:
            ui._muda_modo('editar')
        ui.rodar()


def roda_sem_janela(sim, tempo, arq_resultado=None):
    sim.nova_rodada()
    sim.iniciar_rodada()
    j = sim.juiz
    t_real = time.time()
    motivo = None
    try:
        while not j.fim and j.tempo < tempo:
            time.sleep(0.2)
            if not sim.programa_rodando() and not sim.em_lop and time.time() - t_real > 3:
                time.sleep(1.0)
                if not sim.programa_rodando() and not sim.em_lop:
                    print('[simulador] o programa terminou')
                    motivo = 'o programa terminou'
                    break
    except KeyboardInterrupt:
        pass
    total, partes, info = j.placar()
    motivo = j.fim or motivo or ('acabou o tempo' if j.tempo >= tempo else 'interrompido')
    sim.encerrar()
    if arq_resultado:
        res = {
            'total': total, 'partes': partes, 'info': info, 'tempo': round(j.tempo, 2), 'fim': motivo,
            'lop': info.get('LoP', 0),
            'passo': j.idx, 'passos': max(0, j.n - 1), 'chegou': j.fim == 'robô parou na chegada',
            'vivas': sum(1 for t, _ in j.resgates if t == 'viva'),
            'mortas': sum(1 for t, _ in j.resgates if t != 'viva'),
            'area': j.idx_zona is not None,
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


if __name__ == '__main__':
    main()
