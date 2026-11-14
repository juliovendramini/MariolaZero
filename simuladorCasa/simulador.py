"""Simulador do robô de casa (Bombertinho com uma pinça e uma câmera) para o brick Mariola.

Uso:
    python simulador.py                                   # janela, casa de exemplo, programa de exemplo
    python simulador.py --casa casas/minha_casa.json --programa ../meuRobo/main.py

    # sem janela (para testes): roda uma rodada e imprime o resultado
    python simulador.py --programa exemplo_casa/main.py --sem-janela --velocidade 4
"""

import argparse
import json
import os
import sys
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)

# Windows: com a saída redirecionada (arquivo, pipe) o Python escreve em cp1252, que não tem todos
# os símbolos que o programa pode imprimir. No terminal já sai Unicode.
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(errors='replace', **({} if _f.isatty() else {'encoding': 'utf-8'}))
    except Exception:
        pass

from sim import casa as A  # noqa: E402
from sim.app import Simulacao, carregar_cfg  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description='Simulador do robô de casa (Mariola)')
    ap.add_argument('--casa', default=os.path.join(RAIZ, 'casas', 'casa_exemplo.json'),
                    help='planta, móveis, objetos e início do robô (casas/*.json)')
    ap.add_argument('--programa', default=None, help='main.py do programa do robô')
    ap.add_argument('--robo', default='robo_casa.json', help='configuração do robô')
    ap.add_argument('--sem-janela', action='store_true', help='roda uma rodada sem interface gráfica')
    ap.add_argument('--velocidade', type=float, default=1.0, help='fator de tempo (ex.: 2 = 2x mais rápido)')
    ap.add_argument('--tempo', type=float, default=600, help='(sem janela) duração máxima da rodada em s simulados')
    ap.add_argument('--semente', type=int, default=1,
                    help='semente do ruído: a mesma semente repete a rodada igual (-1 = sorteia a cada rodada)')
    ap.add_argument('--tempo-real', action='store_true',
                    help='o programa corre no relógio real (o resultado muda com a velocidade e o PC)')
    ap.add_argument('--porta', type=int, default=0, help='porta TCP local (0 = automática)')
    ap.add_argument('--resultado', default=None, help='(sem janela) grava o resultado neste arquivo JSON')
    ap.add_argument('--pasta-trabalho', default=None,
                    help='pasta em que o programa roda (padrão: a pasta do programa)')
    ap.add_argument('--enter-automatico', action='store_true',
                    help='o input() do programa segue na hora, como sem janela')
    ap.add_argument('--mapa', default=None,
                    help='mapa que o programa do robô carrega, quando não é a própria casa (para testar com a casa '
                         'diferente do mapa: móveis fora do lugar, coisas que não estão na planta)')
    ap.add_argument('--ajuste', default='',
                    help='troca valores do robo.json só nesta execução, para testar um robô diferente do que o '
                         'programa supõe: "rodas.diametro=56,rodas.eficiencia_lateral=0.8,giroscopio.deriva_graus_min=3"')
    a = ap.parse_args()

    robo = a.robo
    if not os.path.exists(robo) and os.path.exists(os.path.join(RAIZ, robo)):
        robo = os.path.join(RAIZ, robo)
    cfg = carregar_cfg(robo)
    cfg['_arquivo'] = os.path.abspath(robo)
    for item in filter(None, (i.strip() for i in a.ajuste.split(','))):
        chave, valor = item.split('=', 1)
        d = cfg
        *caminho, ultima = chave.strip().split('.')
        for parte in caminho:
            d = d[parte]
        if ultima not in d:
            sys.exit(f'--ajuste: "{chave}" não existe no {os.path.basename(robo)}')
        d[ultima] = json.loads(valor)
        print(f'ajuste do robô: {chave} = {d[ultima]}')
    if a.casa and os.path.exists(a.casa):
        casa = A.Casa.carregar(a.casa)
        # o programa do robô (exemplo_casa/mapa.py) carrega o mapa da casa que está aberta
        os.environ['CASA_MAPA'] = os.path.abspath(a.mapa or a.casa)
        if a.mapa and not os.path.exists(a.mapa):
            sys.exit(f'--mapa: {a.mapa} não existe')
    else:
        if a.casa:
            print(f'aviso: casa {a.casa} não encontrada: cômodo vazio')
        casa = A.Casa()
    for aviso in casa.validar():
        print('aviso da casa:', aviso)
    programa = a.programa if a.programa and os.path.exists(a.programa) else None
    if a.programa and not programa:
        print(f'aviso: programa {a.programa} não encontrado')
    if a.programa is None:
        padrao = os.path.join(RAIZ, 'exemplo_casa', 'main.py')
        programa = padrao if os.path.exists(padrao) else None
    sim = Simulacao(casa, cfg, programa, a.porta, None if a.semente < 0 else a.semente)
    sim.sincronizado = not a.tempo_real
    sim.set_fator(a.velocidade)
    sim.pasta_trabalho = a.pasta_trabalho

    if a.sem_janela:
        roda_sem_janela(sim, a.tempo, a.resultado)
    else:
        from sim.gui import Interface
        sim.enter_automatico = a.enter_automatico
        ui = Interface(sim, os.path.join(RAIZ, 'casas'))
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
    t_sim = j.tempo
    eventos = list(j.eventos)
    erro = dict(sim.robo.debug.get('erro') or {})
    sobraram = [(o.cor, o.estado, float(o.corpo.position.x), float(o.corpo.position.y),
                 sim.mundo.cenario.comodo(o.corpo.position.x, o.corpo.position.y))
                for o in sim.mundo.objetos if o.estado != 'guardado' and not o.grande]
    grandes = [(o.pos, float(o.corpo.position.x), float(o.corpo.position.y), o.deslocamento(),
                sim.mundo.cenario.comodo(o.corpo.position.x, o.corpo.position.y))
               for o in sim.mundo.objetos if o.grande]
    sim.encerrar()
    if arq_resultado:
        res = {'guardados': total, 'info': info, 'tempo': round(t_sim, 2), 'fim': motivo,
               'localizacao': erro or None,
               'pose_final': [round(x, 1), round(y, 1), round(a * 57.29578, 1)],
               'eventos': [[round(t, 2), txt, p] for (t, txt, p) in eventos]}
        with open(arq_resultado, 'w', encoding='utf-8') as f:
            json.dump(res, f, ensure_ascii=False, indent=1)
    print('\n================ RESULTADO ================')
    for (t, txt, p) in eventos:
        print(f'{int(t // 60)}:{t % 60:05.2f}  {txt}')
    print('-------------------------------------------')
    print(f'{"guardados":>12}: {info["guardados"]}   pegos {info["pegos"]}   largados no chão {info["largados no chão"]}')
    print(f'{"fim":>12}: {motivo}   tempo {t_sim:.1f} s   (real {time.time() - t_real:.1f} s)')
    print(f'{"pose final":>12}: x={x:.0f} y={y:.0f} ângulo={a * 57.29578:.1f}°')
    for cor, estado, ox, oy, comodo in sobraram:
        print(f'{"ficou":>12}: {cor} {"na pinça" if estado == "preso" else "no chão"} em ({ox:.0f}, {oy:.0f}), {comodo}')
    for nome, ox, oy, mexeu, comodo in grandes:
        # coisa grande: o robô não pega, só desvia e avisa. "empurrado" = ele esbarrou nela
        print(f'{"grande":>12}: {nome} em ({ox:.0f}, {oy:.0f}), {comodo}'
              + (f', empurrado {mexeu:.0f} mm' if mexeu > 20 else ', não foi tocado'))
    if erro.get('n'):
        # o programa informou onde acha que está (simdebug.pose): erro em relação à pose real
        print(f'{"localização":>12}: erro médio {erro["soma"] / erro["n"]:.0f} mm (máx {erro["max"]:.0f}, '
              f'no fim {erro["mm"]:.0f}); rumo médio {erro["soma_g"] / erro["n"]:.1f}° (máx {erro["max_g"]:.1f}°); '
              f'{erro["n"]} amostras')


if __name__ == '__main__':
    main()
