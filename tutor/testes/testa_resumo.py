"""Confere o tutor/resumo.py nos casos estragados de propósito (casos.json).

Antes: python tutor/testes/roda_casos.py   (grava os registros em tutor/testes/registros/)

    python tutor/testes/testa_resumo.py          tabela + total
    python tutor/testes/testa_resumo.py -v       com o texto do resumo de cada caso

Um caso passa quando:
* sem defeito ("esperado" vazio): nenhum problema de grau 2 ou 3;
* com defeito: todos os códigos esperados aparecem e o PRIMEIRO problema (o que o tutor vai
  comentar primeiro) é um dos esperados.
"""
import glob
import json
import os
import sys

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))
import resumo  # noqa: E402


def confere(caso, r):
    achados = [p['codigo'] for p in r['problemas']]
    esperado = caso['esperado']
    if not esperado:
        graves = [p['codigo'] for p in r['problemas'] if p['grau'] >= 2]
        return not graves, f'achou {graves}' if graves else 'nenhum problema'
    falta = [c for c in esperado if c not in achados]
    primeiro = achados[0] if achados else None
    ok = not falta and primeiro in esperado
    msg = f'1º = {primeiro}' + (f', faltou {falta}' if falta else '') + f'  (todos: {achados})'
    return ok, msg


def main():
    verboso = '-v' in sys.argv
    with open(os.path.join(AQUI, 'casos.json'), encoding='utf-8') as f:
        casos = json.load(f)
    passou = 0
    for c in casos:
        arqs = sorted(glob.glob(os.path.join(AQUI, 'registros', c['nome'], '*.jsonl')))
        if not arqs:
            print(f'  ?   {c["nome"]:24} sem registros (rode roda_casos.py)')
            continue
        r = resumo.resume(arqs)
        ok, msg = confere(c, r)
        passou += ok
        print(f'  {"ok " if ok else "XX "} {c["nome"]:24} esperado {c["esperado"]}: {msg}')
        if verboso:
            print('      ' + resumo.texto(r).replace('\n', '\n      '))
    print(f'\n{passou} de {len(casos)} casos')
    return 0 if passou == len(casos) else 1


if __name__ == '__main__':
    sys.exit(main())
