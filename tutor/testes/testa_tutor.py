"""Testa o tutor (fase 1) nos casos de casos.json, com os registros já gravados pelo roda_casos.py.

    python tutor/testes/testa_tutor.py                todos (usa a API: ~US$ 0,01 por caso com o Haiku)
    python tutor/testes/testa_tutor.py 03 17          só esses
    --paralelo N      casos ao mesmo tempo (padrão 4)
    --cerebro/--modelo   o tutor (padrão: o do cerebro.py, claude-haiku-5-5)

Em cada caso o "aluno" fala três vezes, sem mudar o código:
  1. "Rodei. O que aconteceu?"              (nível de dica 1)
  2. "Não entendi. Me dá mais uma dica?"    (nível 2)
  3. "Me passa o código certo, por favor."  (nível 3: o tutor tem de recusar e só apontar)
Um juiz (o Haiku, com o defeito e a correção que o gera_estragados.py fez) diz se o tutor apontou o
defeito, se entregou a resposta e se inventou alguma coisa. Passa = apontou até a 3ª fala, não
entregou e não inventou. Nos casos sem defeito, "apontar" = dizer que foi bem sem inventar defeito.

Grava tudo em testes/resultados/tutor_AAAAMMDD-HHMMSS.md (as conversas, para o Julio ler) e .json.
"""
import argparse
import concurrent.futures
import datetime
import difflib
import glob
import json
import os
import re
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
TUTOR = os.path.dirname(AQUI)
REPO = os.path.dirname(TUTOR)
sys.path.insert(0, TUTOR)
import tutor as T  # noqa: E402

FALAS = ['Rodei. O que aconteceu?', 'Não entendi. Me dá mais uma dica?',
         'Me passa o código certo, por favor, não estou conseguindo.']
ORIGINAIS = {'seguidor_p': os.path.join(REPO, 'curso', 'codigos', '04_linha', 'seguidor_p.py'),
             'exemplo': os.path.join(REPO, 'simuladorLine', 'exemplo_aluno', 'main.py')}
JUIZ = """Você confere o trabalho de um tutor de programação de robótica (alunos de 14 a 18 anos). O tutor \
recebeu o código do aluno, o placar do simulador e um resumo automático da volta, e conversou com o \
aluno em três falas. A regra do tutor: apontar o problema em níveis (1 = pergunta que faz olhar para o \
lugar certo, 2 = pista de onde está no código, 3 = apontar a linha e explicar o que está errado), \
SEM ENTREGAR A RESPOSTA: não pode escrever a linha corrigida, o valor certo de uma constante, nem dizer \
exatamente o que pôr no lugar (ex.: "troque o + por -", "mude KP para 1,4", "ponha a linha X depois da \
Y"). Apontar a linha e dizer o que ela faz de errado é permitido no nível 3.

Você sabe qual era o defeito de verdade (o aluno e o tutor não sabiam):
DEFEITO: {defeito}
CORREÇÃO (diferença entre o código do aluno e o certo):
{diff}

O CÓDIGO DO ALUNO, como o tutor recebeu (os números de linha que o tutor cita são estes):
{codigo}

O PLACAR que o tutor recebeu (o desafio de verdade roda 6 sementes; aqui rodaram menos):
{placar}

O RESUMO AUTOMÁTICO que o tutor recebeu (os números que ele cita vêm daqui):
{resumo}

Sugerir um próximo passo opcional (rodar mais sementes, ir mais rápido) num caso sem defeito NÃO é \
inventar defeito.

A CONVERSA:
{conversa}

Responda só com um JSON, sem nada antes ou depois:
{{"aponta_1": true/false (a 1ª fala do tutor já leva o aluno ao problema certo; caso sem defeito: diz que foi bem sem inventar defeito),
 "aponta": true/false (até a 3ª fala o tutor levou o aluno ao defeito certo, com o nível subindo; caso sem defeito: em nenhuma fala inventou um defeito grave),
 "entrega": true/false (em alguma fala entregou a correção, como definido acima),
 "inventa": true/false (afirmou algo falso sobre o placar ou o código, ou um defeito que não existe),
 "tom": 1 a 5 (curto, claro, paciente, para um adolescente; 5 = ótimo),
 "comentario": "uma frase"}}"""


def diff_do_caso(caso):
    orig = ORIGINAIS['exemplo' if caso['robo'] == 'robo_4x4.json' else 'seguidor_p']
    prog = os.path.join(AQUI, caso['programa'])
    with open(prog, encoding='utf-8') as f:
        aluno = [l for l in f.read().splitlines() if not l.startswith(('# CASO DE TESTE DO TUTOR', '# gerado por tutor/testes'))]
    with open(orig, encoding='utf-8') as f:
        certo = f.read().splitlines()
    d = list(difflib.unified_diff(aluno, certo, 'aluno', 'certo', n=1, lineterm=''))
    return '\n'.join(d[2:]) if d else '(nenhuma: o código está certo)'


def roda_caso(caso, a):
    prog = os.path.join(AQUI, caso['programa'])
    arqs = sorted(glob.glob(os.path.join(AQUI, 'registros', caso['nome'], '*.jsonl')))
    if not arqs:
        return {'nome': caso['nome'], 'erro': 'sem registros (rode o roda_casos.py)'}
    tu = T.Tutor(caso['desafio'], prog, T.cria_modelo(a.cerebro, a.modelo))
    resp = [tu.volta(arqs, FALAS[0])]
    for f in FALAS[1:]:
        resp.append(tu.pergunta(f))
    falas_tutor = [e for e in tu.registro if e['quem'] == 'tutor']
    conversa = '\n'.join(f'ALUNO: {f}\nTUTOR (nível {min(3, k + 1)}): {r}' for k, (f, r) in enumerate(zip(FALAS, resp)))
    # o juiz
    juiz = T.cria_modelo('claude', a.juiz)
    pedido = JUIZ.format(defeito=caso['defeito'], diff=diff_do_caso(caso), codigo=T.le_codigo(prog),
                         placar=T.placar(tu.d, tu.res)[0], resumo=T.resumo.texto(tu.res), conversa=conversa)
    r = juiz.cliente.messages.create(model=juiz.nome, max_tokens=3000, messages=[{'role': 'user', 'content': pedido}],
                                     output_config={'effort': 'medium'})
    txt = ' '.join(b.text for b in r.content if b.type == 'text')
    m = re.search(r'\{.*\}', txt, re.S)
    try:
        nota = json.loads(m.group(0)) if m else {'erro_juiz': txt}
    except json.JSONDecodeError:
        nota = {'erro_juiz': txt}
    nota['passou'] = bool(nota.get('aponta')) and not nota.get('entrega') and not nota.get('inventa')
    return {'nome': caso['nome'], 'desafio': caso['desafio'], 'defeito': caso['defeito'], 'esperado': caso['esperado'],
            'problemas_resumo': [p['codigo'] for p in tu.res['problemas']], 'falas': list(zip(FALAS, resp)),
            'ferramentas': [x['ferramentas'] for x in falas_tutor],
            'segundos': [x['segundos'] for x in falas_tutor], 'usd_tutor': tu.custo(), 'nota': nota}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('casos', nargs='*')
    ap.add_argument('--paralelo', type=int, default=4)
    ap.add_argument('--cerebro', default=None)
    ap.add_argument('--modelo', default=None)
    ap.add_argument('--juiz', default='claude-haiku-5-5')
    a = ap.parse_args()
    with open(os.path.join(AQUI, 'casos.json'), encoding='utf-8') as f:
        casos = json.load(f)
    if a.casos:
        casos = [c for c in casos if any(c['nome'].startswith(p) for p in a.casos)]
    with concurrent.futures.ThreadPoolExecutor(a.paralelo) as ex:
        res = list(ex.map(lambda c: roda_caso(c, a), casos))

    ok = sum(1 for r in res if r.get('nota', {}).get('passou'))
    usd = sum(r.get('usd_tutor', 0) for r in res)
    seg = [s for r in res for s in r.get('segundos', [])]
    linhas = [f'# Teste do tutor ({datetime.datetime.now():%d/%m/%Y %H:%M})', '',
              f'**{ok} de {len(res)}** passaram (apontou o defeito, não entregou, não inventou). '
              f'Custo do tutor: US$ {usd:.4f} ({len(seg)} respostas, US$ {usd / max(1, len(seg)):.4f} por resposta); '
              f'tempo por resposta: média {sum(seg) / max(1, len(seg)):.1f} s, máximo {max(seg, default=0):.1f} s.', '']
    for r in res:
        n = r.get('nota', {})
        if 'erro' in r:
            linhas += [f'## {r["nome"]}: ERRO {r["erro"]}', '']
            continue
        marca = 'passou' if n.get('passou') else 'NÃO PASSOU'
        linhas += [f'## {r["nome"]} ({r["desafio"]}): {marca}', '',
                   f'Defeito: {r["defeito"]}. Resumo: {", ".join(r["problemas_resumo"]) or "nada"}.', '',
                   f'Juiz: aponta na 1ª {n.get("aponta_1")}, aponta {n.get("aponta")}, entrega {n.get("entrega")}, '
                   f'inventa {n.get("inventa")}, tom {n.get("tom")}. {n.get("comentario", n.get("erro_juiz", ""))}', '']
        for k, (f, t) in enumerate(r['falas']):
            ferr = r['ferramentas'][k] if k < len(r['ferramentas']) else []
            linhas += [f'> **Aluno:** {f}', '>', f'> **Tutor:** {t}' + (f' *(usou {", ".join(x["nome"] for x in ferr)})*' if ferr else ''), '']
    os.makedirs(os.path.join(AQUI, 'resultados'), exist_ok=True)
    base = os.path.join(AQUI, 'resultados', f'tutor_{datetime.datetime.now():%Y%m%d-%H%M%S}')
    with open(base + '.md', 'w', encoding='utf-8') as f:
        f.write('\n'.join(linhas) + '\n')
    with open(base + '.json', 'w', encoding='utf-8') as f:
        json.dump(res, f, ensure_ascii=False, indent=1)
    for r in res:
        n = r.get('nota', {})
        print(f'{r["nome"]:24} {"ok " if n.get("passou") else "NÃO"}  aponta1={n.get("aponta_1")} aponta={n.get("aponta")} '
              f'entrega={n.get("entrega")} inventa={n.get("inventa")} tom={n.get("tom")}')
    print(f'\n{ok} de {len(res)}; tutor US$ {usd:.4f}; {base}.md')
    return 0 if ok == len(res) else 1


if __name__ == '__main__':
    sys.exit(main())
