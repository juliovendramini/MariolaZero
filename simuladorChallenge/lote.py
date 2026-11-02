"""Lote de partidas sem janela, várias sementes em paralelo, e um resumo no fim.

    python lote.py --programa ../meuRobo/main.py --robo robo_bombertinho.json --sementes 1-10
    python lote.py --programa ../meuRobo/main.py --sortear --sementes 1-20 --inicio 380,150,0

    --sementes 1-10 | 1,3,5   sementes do ruído (a mesma semente repete a partida igual)
    --sortear                 cada semente sorteia também o cenário (cubos e plataformas dentro da regra);
                              sem isso, todas usam o --cenario (padrão: cenarios/exemplo.json)
    --inicio X,Y,ÂNGULO       põe o robô sempre neste lugar da área verde (mm e graus; o sorteio
                              escolhe a altura e o ângulo, e alguns programas só funcionam de um lugar)
    --tempo 720               duração de cada partida (s simulados)
    --paralelo N              partidas ao mesmo tempo (padrão: metade dos núcleos do PC)

Cada partida fica em resultados/lote_DATA/: semente_N.log (o que o programa imprimiu), semente_N.json
(placar e eventos) e cenario_N.json. O resumo (resumo.txt e resumo.csv) separa as partidas com
problema (penalidade, erro no programa, programa que parou antes da hora) e dá o comando para rever
cada uma na janela, igual ao que aconteceu.
"""

import argparse
import concurrent.futures as cf
import csv
import datetime
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, RAIZ)
from sim import arena as A  # noqa: E402

for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(errors='replace')
    except Exception:
        pass


def sementes(texto):
    out = []
    for parte in texto.split(','):
        if '-' in parte:
            a, b = parte.split('-')
            out.extend(range(int(a), int(b) + 1))
        elif parte.strip():
            out.append(int(parte))
    return out


PASTA_MAX_MB = 50


def pasta_rodada(programa):
    """Cópia da pasta do programa para ser a pasta de trabalho de uma partida (None = não copia).

    As partidas correm em paralelo e o programa grava arquivos com caminho relativo na pasta em que
    roda (checkpoint, mapa): com uma pasta só, uma partida lia o arquivo da outra ou morria gravando
    (no Windows o os.replace falha se outro processo mexe nele). O programa continua rodando do
    lugar original (imports e caminhos a partir de __file__ não mudam); só os caminhos relativos
    caem na cópia. Pasta muito grande (> PASTA_MAX_MB) não é copiada. Igual ao avalia.py da Line e
    da Maze."""
    orig = os.path.dirname(os.path.abspath(programa))
    fora = shutil.ignore_patterns('__pycache__', '.git', '.sim_build', '.cache', 'resultados')
    total = 0
    for raiz, pastas, arqs in os.walk(orig):
        pastas[:] = [d for d in pastas if not fora(raiz, [d])]
        total += sum(os.path.getsize(os.path.join(raiz, a)) for a in arqs)
        if total > PASTA_MAX_MB * 1e6:
            return None
    destino = os.path.join(tempfile.mkdtemp(prefix='rodada_'), os.path.basename(orig))
    shutil.copytree(orig, destino, ignore=fora)
    return destino


def roda(args, s, pasta):
    """Uma partida: devolve o dicionário do resumo."""
    if args.sortear:
        cen = A.sorteia(random.Random(s))
        cen.nome = f'sorteado {s}'
    else:
        cen = A.Cenario.carregar(args.cenario)
    if args.inicio:
        x, y, ang = (float(v) for v in args.inicio.split(','))
        cen.inicio = {'esq': [x, y, ang], 'dir': [A.LARGURA - x, A.ALTURA - y, ang + 180.0]}
    arq_cen = os.path.join(pasta, f'cenario_{s}.json')
    cen.salvar(arq_cen)
    arq_res = os.path.join(pasta, f'semente_{s}.json')
    cmd = [sys.executable, os.path.join(RAIZ, 'simulador.py'), '--sem-janela', '--velocidade', str(args.velocidade),
           '--tempo', str(args.tempo), '--robo', args.robo, '--programa', args.programa,
           '--cenario', arq_cen, '--semente', str(s), '--resultado', arq_res]
    trabalho = pasta_rodada(args.programa)
    if trabalho:
        cmd += ['--pasta-trabalho', trabalho]
    t0 = time.time()
    try:
        with open(os.path.join(pasta, f'semente_{s}.log'), 'w', encoding='utf-8', errors='replace') as log:
            p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=os.getcwd(),
                               env=dict(os.environ, PYTHONIOENCODING='utf-8'))
    finally:
        if trabalho:
            shutil.rmtree(os.path.dirname(trabalho), ignore_errors=True)
    with open(os.path.join(pasta, f'semente_{s}.log'), encoding='utf-8', errors='replace') as f:
        texto = f.read()
    r = {'semente': s, 'real_s': round(time.time() - t0)}
    try:
        res = json.load(open(arq_res, encoding='utf-8'))
    except (OSError, ValueError):
        res = None
    problemas = []
    if res is None:
        problemas.append(f'o simulador não terminou (código {p.returncode})')
        res = {'total': 0, 'partes': {}, 'info': {}, 'tempo': 0, 'fim': '?', 'eventos': []}
    partes = res.get('partes', {})
    info = res.get('info', {})
    r.update(total=res.get('total', 0), positivos=partes.get('positivos', 0),
             negativos=partes.get('negativos', 0), tempo=res.get('tempo', 0), fim=res.get('fim', ''))
    for k in ('entregues', 'identificados', 'saídas', 'plataformas', 'brancos', 'perdidos', 'obstáculos',
              'derrubados', 'reinícios'):
        r[k] = info.get(k, 0)
    if 'Traceback' in texto:
        linhas = [l for l in texto.splitlines() if l.strip() and not l.startswith('[robô]   ')]
        erro = next((l for l in reversed(linhas) if 'Error' in l or 'Exception' in l), 'Traceback')
        problemas.append('erro no programa: ' + erro.replace('[robô]', '').strip()[:120])
    if res.get('fim') == 'o programa terminou' and res.get('tempo', 0) < args.tempo - 5:
        problemas.append(f'o programa parou aos {res["tempo"]:.0f} s')
    for t, txt, pts in res.get('eventos', []):
        if pts < 0:
            problemas.append(f'{int(t // 60)}:{t % 60:04.1f} {pts:+d} {txt}')
    if not problemas and r['total'] == 0:
        problemas.append('nenhum ponto')
    r['problemas'] = problemas
    r['rever'] = (f'python simulador.py --robo {args.robo} --programa {args.programa} '
                  f'--cenario {os.path.relpath(arq_cen)} --semente {s} --enter-automatico')
    return r


def main():
    ap = argparse.ArgumentParser(description='Lote de partidas sem janela (várias sementes)')
    ap.add_argument('--programa', required=True, help='main.py do programa do robô')
    ap.add_argument('--robo', default='robo_bombertinho.json')
    ap.add_argument('--cenario', default=os.path.join(RAIZ, 'cenarios', 'exemplo.json'))
    ap.add_argument('--sortear', action='store_true', help='cada semente sorteia o cenário')
    ap.add_argument('--inicio', default=None, metavar='X,Y,ÂNGULO')
    ap.add_argument('--sementes', default='1-6')
    ap.add_argument('--tempo', type=float, default=720)
    ap.add_argument('--velocidade', type=float, default=8)
    ap.add_argument('--paralelo', type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument('--saida', default=None, help='pasta dos resultados (padrão: resultados/lote_DATA)')
    args = ap.parse_args()

    lista = sementes(args.sementes)
    pasta = args.saida or os.path.join(RAIZ, 'resultados', datetime.datetime.now().strftime('lote_%Y%m%d_%H%M%S'))
    os.makedirs(pasta, exist_ok=True)
    print(f'{len(lista)} partidas de {args.tempo:.0f} s, {args.paralelo} ao mesmo tempo -> {os.path.relpath(pasta)}')
    res = []
    with cf.ThreadPoolExecutor(args.paralelo) as ex:
        futuros = {ex.submit(roda, args, s, pasta): s for s in lista}
        for fu in cf.as_completed(futuros):
            r = fu.result()
            res.append(r)
            marca = 'ok ' if not r['problemas'] else 'PROBLEMA'
            print(f'  semente {r["semente"]:3d}: {r["total"]:4d} pontos ({r["entregues"]} entregues) '
                  f'{marca}  [{len(res)}/{len(lista)}, {r["real_s"]} s]', flush=True)
    res.sort(key=lambda r: r['semente'])

    colunas = ['semente', 'total', 'positivos', 'negativos', 'entregues', 'identificados', 'saídas', 'plataformas',
               'brancos', 'perdidos', 'obstáculos', 'derrubados', 'reinícios', 'tempo', 'fim', 'problemas']
    with open(os.path.join(pasta, 'resumo.csv'), 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.writer(f, delimiter=';')
        w.writerow(colunas)
        for r in res:
            w.writerow([r[c] if c != 'problemas' else ' | '.join(r[c]) for c in colunas])

    ok = [r for r in res if not r['problemas']]
    ruins = [r for r in res if r['problemas']]
    linhas = [f'LOTE {os.path.basename(pasta)}: programa {args.programa}, robô {args.robo}, '
              f'{"cenário sorteado por semente" if args.sortear else "cenário " + args.cenario}'
              f'{", início " + args.inicio if args.inicio else ""}, {args.tempo:.0f} s', '']
    totais = [r['total'] for r in res]
    linhas.append(f'{len(res)} partidas: média {sum(totais) / len(totais):.0f} pontos, mínimo {min(totais)}, '
                  f'máximo {max(totais)}; {len(ok)} sem problema, {len(ruins)} com problema')
    linhas.append('')
    linhas.append('SEM PROBLEMA: ' + (', '.join(f'{r["semente"]} ({r["total"]})' for r in ok) or 'nenhuma'))
    linhas.append('')
    for r in ruins:
        linhas.append(f'SEMENTE {r["semente"]}: {r["total"]} pontos ({r["positivos"]} {r["negativos"]}), '
                      f'{r["entregues"]} entregues')
        for pr in r['problemas'][:12]:
            linhas.append(f'    {pr}')
        if len(r['problemas']) > 12:
            linhas.append(f'    ... mais {len(r["problemas"]) - 12}')
        linhas.append(f'    rever: {r["rever"]}')
        linhas.append('')
    texto = '\n'.join(linhas)
    with open(os.path.join(pasta, 'resumo.txt'), 'w', encoding='utf-8') as f:
        f.write(texto + '\n')
    print('\n' + texto)
    print(f'resumo em {os.path.relpath(os.path.join(pasta, "resumo.txt"))} (e resumo.csv para a planilha)')


if __name__ == '__main__':
    main()
