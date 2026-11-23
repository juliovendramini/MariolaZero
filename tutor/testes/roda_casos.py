"""Roda os casos de casos.json no simulador da Line e guarda os registros da volta.

    python tutor/testes/roda_casos.py                 todos, sementes 1-2
    python tutor/testes/roda_casos.py 03 11 --sementes 1-6

Os registros ficam em tutor/testes/registros/NOME/ (fora do git). Depois:
    python tutor/testes/testa_resumo.py
"""
import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(AQUI))
LINE = os.path.join(REPO, 'simuladorLine')
REGISTROS = os.path.join(AQUI, 'registros')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('casos', nargs='*', help='começo do nome dos casos (padrão: todos)')
    ap.add_argument('--sementes', default='1-2')
    ap.add_argument('--paralelo', type=int, default=3, help='casos ao mesmo tempo (cada um roda 2 rodadas juntas)')
    a = ap.parse_args()
    with open(os.path.join(AQUI, 'casos.json'), encoding='utf-8') as f:
        casos = json.load(f)
    if a.casos:
        casos = [c for c in casos if any(c['nome'].startswith(p) for p in a.casos)]
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    with concurrent.futures.ThreadPoolExecutor(max_workers=a.paralelo) as ex:
        list(ex.map(lambda c: roda(c, a.sementes, env), casos))


def roda(c, sementes, env):
    pasta = os.path.join(REGISTROS, c['nome'])
    os.makedirs(pasta, exist_ok=True)
    for arq in os.listdir(pasta):
        os.remove(os.path.join(pasta, arq))
    t0 = time.time()
    cmd = [sys.executable, 'avalia.py', '--desafio', c['desafio'], '--robo', c['robo'],
           '--programa', os.path.join(AQUI, c['programa']), '--sementes', sementes, '--registros', pasta,
           '--paralelo', '2']
    r = subprocess.run(cmd, cwd=LINE, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    linhas = [x for x in r.stdout.splitlines() if x.strip().startswith(('média', '>>>'))]
    print(f'{c["nome"]:24} {time.time() - t0:5.0f} s  ' + ' | '.join(x.strip() for x in linhas), flush=True)


if __name__ == '__main__':
    main()
