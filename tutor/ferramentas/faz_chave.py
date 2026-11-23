"""Gera a tutor/chave_tutor.dll com a chave da API embaralhada (19/11/2026, pedido do Julio).

    python tutor/ferramentas/faz_chave.py

Lê a chave do mesmo lugar que o robô de casa (CEREBRO_CHAVE_API, variável de ambiente ou registro do
Windows), embaralha com uma sequência pseudoaleatória, escreve um .c temporário, compila com o gcc do
Dev-C++ (64 bits, sem depender de outras DLLs) e apaga o .c. A chave não aparece na tela nem fica em
nenhum arquivo de texto. A DLL fica fora do git (tutor/.gitignore): o repositório é público.

ATENÇÃO: embaralhar não é proteger. Quem tiver a DLL e souber usar um depurador tira a chave. Use uma
chave só do tutor, com limite de gasto no Console da Anthropic, e troque se vazar (rode este script de
novo com a chave nova e distribua a DLL nova).
"""
import os
import random
import subprocess
import sys
import tempfile

AQUI = os.path.dirname(os.path.abspath(__file__))
TUTOR = os.path.dirname(AQUI)
REPO = os.path.dirname(TUTOR)
SAIDA = os.path.join(TUTOR, 'chave_tutor.dll')
GCC = os.environ.get('GCC', r'C:\Dev-Cpp\MinGW64\bin\gcc.exe')

C = r'''
#include <string.h>
static const unsigned char D[%(n)d] = {%(bytes)s};
static unsigned int passo(unsigned int *s) {
    unsigned int x = *s; x ^= x << 13; x ^= x >> 17; x ^= x << 5; *s = x; return x;
}
/* escreve a chave em buf (com o 0 do fim) e devolve o tamanho; -1 se buf for pequeno */
__declspec(dllexport) int tutor_chave(char *buf, int n) {
    unsigned int s = %(semente)uu;
    int i;
    if (n < %(n)d + 1) return -1;
    for (i = 0; i < %(n)d; i++)
        buf[i] = (char)(D[%(n)d - 1 - i] ^ (passo(&s) & 0xFF));
    buf[%(n)d] = 0;
    return %(n)d;
}
__declspec(dllexport) int tutor_versao(void) { return 1; }
'''


def xorshift(s):
    while True:
        s ^= (s << 13) & 0xFFFFFFFF
        s ^= s >> 17
        s ^= (s << 5) & 0xFFFFFFFF
        yield s


def main():
    sys.path.insert(0, os.path.join(REPO, 'simuladorCasa', 'exemplo_casa'))
    import cerebro
    chave = cerebro.chave_da_api()
    if not chave:
        raise SystemExit('não achei a chave (CEREBRO_CHAVE_API)')
    dados = chave.encode('ascii')
    semente = random.SystemRandom().randrange(1, 2**32)
    fluxo = xorshift(semente)
    emb = bytes(b ^ (next(fluxo) & 0xFF) for b in dados)[::-1]
    fonte = C % {'n': len(emb), 'bytes': ','.join(str(b) for b in emb), 'semente': semente}
    with tempfile.TemporaryDirectory() as tmp:
        arq = os.path.join(tmp, 'k.c')
        with open(arq, 'w') as f:
            f.write(fonte)
        r = subprocess.run([GCC, '-shared', '-O2', '-s', '-static-libgcc', '-o', SAIDA, arq],
                           capture_output=True, text=True)
        if r.returncode:
            raise SystemExit('o gcc falhou:\n' + r.stderr)
    del fonte, chave
    sys.path.insert(0, TUTOR)
    import chave as ch
    ok = ch.da_dll() == cerebro.chave_da_api()
    print(f'{os.path.relpath(SAIDA, REPO)}: {os.path.getsize(SAIDA)} bytes, '
          f'{"confere com a chave" if ok else "NÃO CONFERE"}')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
