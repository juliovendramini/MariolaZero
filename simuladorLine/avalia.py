"""Avalia o programa do robô em várias rodadas e diz se ele cumpriu a meta de um desafio.

Uma rodada só não diz se o programa é bom: o ruído dos sensores muda a cada semente e uma
rodada de sorte engana. O avalia.py roda o programa em várias sementes (sem janela), mostra a
média, a pior rodada e os LoPs, e confere a meta do desafio.

Uso:
    python avalia.py --lista                                     # desafios disponíveis
    python avalia.py --desafio L01 --programa ../meuRobo/main.py # roda o desafio e confere a meta
    python avalia.py --programa ../meuRobo/main.py --mapa mapas/completo.json --sementes 1-6
    python avalia.py --programa ../meuRobo/main.py --surpresa medio --mapas 6

Opções úteis:
    --sementes 1-6 | 1,3,5    sementes do ruído (padrão: as do desafio, ou 1-6)
    --paralelo N              rodadas ao mesmo tempo (padrão: metade dos núcleos do PC)
    --aluno "Nome"            vai no relatório (resultados/*.json)
    --semente-mapas N         (pista surpresa) muda as pistas sorteadas. O professor pode usar
                              uma semente que os alunos não conhecem no dia da avaliação.

O relatório de cada avaliação fica em resultados/ (com o placar de cada rodada e uma "impressão
digital" dos arquivos .py do programa). As pistas surpresa ficam em resultados/mapas/: abra a
que deu errado no simulador com janela para ver o que aconteceu.
"""
import argparse
import concurrent.futures
import datetime
import glob
import hashlib
import json
import os
import statistics
import subprocess
import sys
import tempfile
import time

RAIZ = os.path.dirname(os.path.abspath(__file__))
LINE = os.path.exists(os.path.join(RAIZ, 'sim', 'resgate.py'))   # simulador da Line ou da Maze
NOME_SIM = 'Rescue Line' if LINE else 'Rescue Maze'
ROBO_PADRAO = 'robo_4x4.json' if LINE else 'robo.json'
ARQ_DESAFIOS = os.path.join(RAIZ, 'desafios', 'desafios.json')
PASTA_RES = os.path.join(RAIZ, 'resultados')

try:
    sys.stdout.reconfigure(errors='replace')
except Exception:
    pass


# ------------------------------------------------------------------ desafios
def carrega_desafios():
    if not os.path.exists(ARQ_DESAFIOS):
        return {}
    with open(ARQ_DESAFIOS, encoding='utf-8') as f:
        d = json.load(f)
    return {k: v for k, v in d.items() if not k.startswith('_')}


def lista_desafios():
    ds = carrega_desafios()
    if not ds:
        print('nenhum desafio em desafios/desafios.json')
        return
    print(f'Desafios do simulador da {NOME_SIM}:\n')
    nivel = None
    for k, d in ds.items():
        if d.get('nivel') != nivel:
            nivel = d.get('nivel')
            print(f'  {nivel}')
        print(f'    {k:5} {d["titulo"]}')
        print(f'          meta: {d["meta_texto"]}')
    print('\nRode com: python avalia.py --desafio ID --programa CAMINHO/main.py')


# ------------------------------------------------------------------ rodadas
def le_sementes(txt):
    out = []
    for parte in str(txt).split(','):
        parte = parte.strip()
        if '-' in parte:
            a, b = parte.split('-')
            out.extend(range(int(a), int(b) + 1))
        elif parte:
            out.append(int(parte))
    return out


def caminho(p):
    """Caminho relativo à pasta atual ou, se não existir, à pasta do simulador."""
    if p is None or os.path.isabs(p) or os.path.exists(p):
        return p and os.path.abspath(p)
    q = os.path.join(RAIZ, p)
    return q if os.path.exists(q) else os.path.abspath(p)


def gera_surpresa(nivel, semente):
    """Gera (ou reaproveita) a pista/labirinto surpresa e devolve o caminho do arquivo."""
    sys.path.insert(0, RAIZ)
    sys.path.insert(0, os.path.join(RAIZ, 'ferramentas'))
    if LINE:
        import pista_surpresa as ger
    else:
        import labirinto_surpresa as ger
    pasta = os.path.join(PASTA_RES, 'mapas')
    os.makedirs(pasta, exist_ok=True)
    m = ger.gera(semente, nivel)
    arq = os.path.join(pasta, m.nome + '.json')
    m.salvar(arq)
    return arq


def roda(job):
    """Uma rodada sem janela. Devolve o dicionário do resultado (ou o erro)."""
    os.makedirs(os.path.join(PASTA_RES, 'logs'), exist_ok=True)
    fd, arq_json = tempfile.mkstemp(suffix='.json', prefix='rodada_')
    os.close(fd)
    nome_log = f'{job["rotulo"]}_s{job["semente"]}.log'.replace(os.sep, '_')
    log = os.path.join(PASTA_RES, 'logs', nome_log)
    cmd = [sys.executable, os.path.join(RAIZ, 'simulador.py'), '--sem-janela',
           '--robo', job['robo'], '--mapa', job['mapa'], '--programa', job['programa'],
           '--semente', str(job['semente']), '--tempo', str(job['tempo']),
           '--velocidade', str(job['velocidade']), '--resultado', arq_json]
    t0 = time.time()
    env = dict(os.environ, PYTHONIOENCODING='utf-8')
    try:
        with open(log, 'w', encoding='utf-8', errors='replace') as f:
            subprocess.run(cmd, stdout=f, stderr=subprocess.STDOUT, cwd=RAIZ, env=env,
                           timeout=job['tempo'] * 3 + 300)
        with open(arq_json, encoding='utf-8') as f:
            r = json.load(f)
    except subprocess.TimeoutExpired:
        r = {'erro': 'a rodada travou (passou do tempo limite)'}
    except (OSError, ValueError):
        r = {'erro': 'o simulador não gravou o resultado (veja o log)'}
    finally:
        try:
            os.remove(arq_json)
        except OSError:
            pass
    try:
        with open(log, encoding='utf-8', errors='replace') as f:
            txt = f.read()
        if 'Traceback (most recent call last)' in txt:
            r['erro_programa'] = True
    except OSError:
        pass
    r.update({'i': job['i'], 'semente': job['semente'], 'mapa': os.path.relpath(job['mapa'], RAIZ),
              'log': os.path.relpath(log, RAIZ), 'real_s': round(time.time() - t0, 1)})
    return r


def metricas(r):
    """Números de uma rodada que as metas dos desafios usam."""
    if 'erro' in r:
        return None
    m = {'total': r['total'], 'lop': r.get('lop', 0), 'tempo': r['tempo'],
         'erro_programa': bool(r.get('erro_programa'))}
    if LINE:
        passos = max(1, r.get('passos', 1))
        m.update({'passo': r.get('passo', 0), 'passos': passos, 'progresso': r.get('passo', 0) / passos,
                  'chegou': bool(r.get('chegou')), 'vivas': r.get('vivas', 0), 'mortas': r.get('mortas', 0),
                  'vitimas': r.get('vivas', 0) + r.get('mortas', 0),
                  'linha': r.get('info', {}).get('linha', r['total'])})
    else:
        info = r.get('info', {})
        m.update({'svi': info.get('SVI', 0), 'srd': info.get('SRD', 0), 'sbv': info.get('SBV', 0),
                  'ssn': info.get('SSN', 0), 'vitimas': info.get('SVI', 0), 'saida': bool(r.get('saida')),
                  'erros': r.get('erros', 0)})
    return m


def avalia_expr(expr, valores):
    return bool(eval(expr, {'__builtins__': {}, 'abs': abs, 'min': min, 'max': max}, dict(valores)))


def confere_meta(meta, lista):
    """(aprovado, explicação) para a meta de um desafio."""
    validas = [m for m in lista if m is not None]
    linhas = []
    ok = True
    if 'rodada' in meta:
        minimo = int(meta.get('minimo', len(lista)))
        boas = sum(1 for m in validas if avalia_expr(meta['rodada'], m))
        passou = boas >= minimo
        ok &= passou
        linhas.append(f'{boas} de {len(lista)} rodadas cumpriram "{meta["rodada"]}" (precisa {minimo})')
        if len(lista) < minimo:
            linhas.append(f'só rodaram {len(lista)} rodadas: para conferir a meta, rode sem --sementes')
    if 'media' in meta:
        if validas:
            medias = {k: statistics.mean(float(m[k]) for m in validas) for k in validas[0]}
            passou = avalia_expr(meta['media'], medias) and len(validas) == len(lista)
        else:
            medias, passou = {}, False
        ok &= passou
        usadas = [k for k in medias if k in meta['media']]
        txt = ', '.join(f'{k} médio {medias[k]:.2f}' for k in usadas)
        linhas.append(f'média: {txt or "-"} (precisa {meta["media"]})')
    return ok, linhas


# ------------------------------------------------------------------ saída
def linha_tabela(r):
    if 'erro' in r:
        return f'  {r["semente"]:>4}  ERRO: {r["erro"]}  ({r["log"]})'
    m = metricas(r)
    aviso = '  << erro no programa (veja o log)' if m['erro_programa'] else ''
    if LINE:
        vit = f'{m["vivas"]}v+{m["mortas"]}m' if r.get('area') else '  -  '
        return (f'  {r["semente"]:>4}  {m["total"]:>5}  {m["lop"]:>3}  {m["passo"]:>3}/{m["passos"]:<3} '
                f'{"sim" if m["chegou"] else "não":>6}  {vit:>6}  {m["tempo"]:>6.1f}  '
                f'{os.path.basename(r["mapa"])[:24]:24}  {r["fim"]}{aviso}')
    return (f'  {r["semente"]:>4}  {m["total"]:>5}  {m["lop"]:>3}  {m["svi"]:>3}  {m["srd"]:>3}  {m["sbv"]:>3}  '
            f'{"sim" if m["saida"] else "não":>5}  {m["erros"]:>5}  {m["tempo"]:>6.1f}  '
            f'{os.path.basename(r["mapa"])[:24]:24}  {r["fim"]}{aviso}')


def cabecalho():
    if LINE:
        return ('  sem.  total  LoP  passo   chegou  vítim.   tempo  mapa                      fim')
    return ('  sem.  total  LoP  SVI  SRD  SBV  saída  erros   tempo  mapa                      fim')


def impressao_digital(programa):
    """Hash dos fontes da pasta do programa (.py; .ino/.h/.cpp do Paçoca) para o professor
    conferir que é o mesmo código."""
    pasta = os.path.dirname(os.path.abspath(programa))
    h = hashlib.sha256()
    arqs = []
    for ext in ('py', 'ino', 'h', 'hpp', 'c', 'cpp'):
        arqs += glob.glob(os.path.join(pasta, '**', '*.' + ext), recursive=True)
    for arq in sorted(arqs):
        if '__pycache__' in arq or '.sim_build' in arq:
            continue
        h.update(os.path.relpath(arq, pasta).replace(os.sep, '/').encode())
        with open(arq, 'rb') as f:
            h.update(f.read())
    return h.hexdigest()[:16]


# ------------------------------------------------------------------ principal
def main():
    ap = argparse.ArgumentParser(description=f'Avalia o programa em várias rodadas ({NOME_SIM})')
    ap.add_argument('--lista', action='store_true', help='mostra os desafios')
    ap.add_argument('--desafio', help='ID do desafio (veja --lista)')
    ap.add_argument('--programa', default=os.path.join(RAIZ, 'exemplo_aluno', 'main.py'))
    ap.add_argument('--robo', default=None)
    ap.add_argument('--mapa', default=None)
    ap.add_argument('--surpresa', choices=['facil', 'medio', 'dificil'], default=None,
                    help='usa pistas/labirintos sorteados deste nível (uma por rodada)')
    ap.add_argument('--mapas', type=int, default=None, help='quantas pistas surpresa (padrão 6)')
    ap.add_argument('--semente-mapas', type=int, default=None, help='primeira semente das pistas surpresa')
    ap.add_argument('--sementes', default=None, help='sementes do ruído, ex.: 1-6 ou 1,4,9')
    ap.add_argument('--tempo', type=float, default=None, help='tempo máximo da rodada (s simulados)')
    ap.add_argument('--paralelo', type=int, default=None)
    ap.add_argument('--velocidade', type=float, default=None)
    ap.add_argument('--aluno', default='')
    a = ap.parse_args()

    if a.lista:
        lista_desafios()
        return 0

    d = {}
    if a.desafio:
        ds = carrega_desafios()
        chave = a.desafio.upper()
        if chave not in ds:
            print(f'desafio {a.desafio} não existe. Use --lista.')
            return 2
        d = ds[chave]
    ino = a.programa.lower().endswith('.ino')
    robo_desafio = d.get('robo')
    if ino and robo_desafio and not robo_desafio.startswith('robo_pacoca'):
        robo_desafio = None              # programa do Paçoca: o desafio vale com o robô do Paçoca
    robo = caminho(a.robo or robo_desafio or ('robo_pacoca_amarelo.json' if ino else ROBO_PADRAO))
    tempo = a.tempo or d.get('tempo', 480)
    surpresa = a.surpresa or d.get('surpresa')
    if a.sementes:
        sementes = le_sementes(a.sementes)
    elif d.get('sementes'):
        sementes = le_sementes(d['sementes'])
    else:
        sementes = list(range(1, (a.mapas or 6) + 1))
    programa = caminho(a.programa)
    if not os.path.exists(programa):
        print(f'programa não encontrado: {programa}')
        return 2
    if not os.path.exists(robo):
        print(f'robô não encontrado: {robo}')
        return 2
    if ino:
        # compila uma vez aqui (as rodadas em paralelo só usam o executável pronto)
        sys.path.insert(0, RAIZ)
        from pacoca import compila
        try:
            compila.compila(programa, log=print)
        except compila.ErroCompilacao as e:
            print('erro de compilação:\n' + str(e))
            return 1

    # mapas: um fixo, ou uma pista surpresa por rodada
    if surpresa:
        n = a.mapas or d.get('mapas') or len(sementes)
        base = a.semente_mapas if a.semente_mapas is not None else d.get('semente_mapas', 1)
        if len(sementes) < n:
            sementes = (sementes * n)[:n]
        sementes = sementes[:n]
        print(f'gerando {n} {"pistas" if LINE else "labirintos"} surpresa ({surpresa}, sementes {base}..{base + n - 1})...')
        mapas = [gera_surpresa(surpresa, base + i) for i in range(n)]
    else:
        mapa = caminho(a.mapa or d.get('mapa') or os.path.join('mapas', 'treino.json' if LINE else 'exemplo1.json'))
        if not os.path.exists(mapa):
            print(f'mapa não encontrado: {mapa}')
            return 2
        mapas = [mapa] * len(sementes)

    # o relógio é sincronizado: rodadas ao mesmo tempo não mudam o resultado
    paralelo = a.paralelo or max(1, min(4, (os.cpu_count() or 2) // 2))
    velocidade = a.velocidade or 8
    rotulo = (a.desafio.upper() if a.desafio else
              (f'surpresa_{surpresa}' if surpresa else os.path.splitext(os.path.basename(mapas[0]))[0]))

    titulo = f'{rotulo}: {d["titulo"]}' if d else rotulo
    print(f'\n=== {titulo} ===')
    if d.get('descricao'):
        print(d['descricao'])
    print(f'programa: {programa}\nrobô: {os.path.basename(robo)}   rodadas: {len(sementes)}   '
          f'tempo máx.: {tempo:.0f} s   em paralelo: {paralelo}\n')
    print(cabecalho())

    jobs = [{'i': i, 'rotulo': rotulo, 'semente': s, 'mapa': mp, 'robo': robo, 'programa': programa,
             'tempo': tempo, 'velocidade': velocidade} for i, (s, mp) in enumerate(zip(sementes, mapas))]
    t0 = time.time()
    resultados = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=paralelo) as ex:
        futuros = [ex.submit(roda, j) for j in jobs]
        for fu in concurrent.futures.as_completed(futuros):
            r = fu.result()
            resultados.append(r)
            print(linha_tabela(r), flush=True)
    resultados.sort(key=lambda r: r['i'])

    ms = [metricas(r) for r in resultados]
    totais = [m['total'] for m in ms if m]
    print()
    if totais:
        dp = statistics.pstdev(totais) if len(totais) > 1 else 0.0
        print(f'  média {statistics.mean(totais):.1f}   pior {min(totais)}   melhor {max(totais)}   '
              f'desvio {dp:.1f}   LoPs {sum(m["lop"] for m in ms if m)}   ({time.time() - t0:.0f} s)')
    erros = [r for r in resultados if 'erro' in r or r.get('erro_programa')]
    if erros:
        print(f'  atenção: {len(erros)} rodada(s) com erro. Veja o log (ex.: {erros[0]["log"]}).')

    aprovado = None
    explicacao = []
    if d.get('meta'):
        aprovado, explicacao = confere_meta(d['meta'], ms)
        print(f'\n  meta: {d["meta_texto"]}')
        for e in explicacao:
            print(f'    - {e}')
        print('\n  >>> DESAFIO CUMPRIDO <<<' if aprovado else '\n  >>> ainda não: continue tentando <<<')
    if surpresa:
        pior = min((r for r in resultados if 'erro' not in r), key=lambda r: r['total'], default=None)
        if pior:
            print(f'\n  para ver a pior rodada com janela:\n    python simulador.py --robo {os.path.basename(robo)} '
                  f'--mapa {pior["mapa"]} --semente {pior["semente"]} --programa {programa}')

    # relatório
    os.makedirs(PASTA_RES, exist_ok=True)
    agora = datetime.datetime.now()
    rel = {
        'simulador': NOME_SIM, 'desafio': a.desafio.upper() if a.desafio else None,
        'titulo': d.get('titulo'), 'meta': d.get('meta_texto'), 'aprovado': aprovado,
        'explicacao': explicacao, 'aluno': a.aluno, 'data': agora.isoformat(timespec='seconds'),
        'programa': programa, 'impressao_digital': impressao_digital(programa),
        'robo': os.path.basename(robo), 'surpresa': surpresa,
        'media': round(statistics.mean(totais), 1) if totais else None,
        'rodadas': [{k: v for k, v in r.items() if k not in ('eventos', 'i')} for r in resultados],
    }
    arq = os.path.join(PASTA_RES, f'{rotulo}_{agora:%Y%m%d-%H%M%S}.json')
    with open(arq, 'w', encoding='utf-8') as f:
        json.dump(rel, f, ensure_ascii=False, indent=1)
    print(f'\n  relatório: {os.path.relpath(arq, RAIZ)}')
    return 0 if aprovado in (None, True) else 1


if __name__ == '__main__':
    sys.exit(main())
