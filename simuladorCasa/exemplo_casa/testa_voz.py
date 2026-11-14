"""Testes da voz do robô (voz.py), sem robô e sem simulador.

    python exemplo_casa/testa_voz.py                    teste fechado: o Piper fala cada comando e o whisper transcreve
    python exemplo_casa/testa_voz.py --ruido 10         o mesmo com ruído por cima (relação sinal/ruído em dB)
    python exemplo_casa/testa_voz.py --amostras pasta   grava um .wav de cada voz para ouvir e escolher
    python exemplo_casa/testa_voz.py --microfone 5      grava 5 frases do microfone e mostra o que entendeu
    python exemplo_casa/testa_voz.py --fala "Oi, eu sou o Bombertinho"

O teste fechado confere o encaixe e mede o tempo, mas é fácil demais: fala de máquina, limpa, sem
sotaque e sem eco. O que vale é o --microfone com a sua voz, de longe e com barulho.
"""

import argparse
import difflib
import os
import sys
import time

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from voz import Boca, Ouvido, boca_do_robo, chamou, reamostra, _sem_acento, PASTA_VOZES, TAXA_OUVIDO  # noqa: E402

COMODOS = ['Sala de estar', 'Sala de jantar', 'Cozinha', 'Quarto 1', 'Quarto 2', 'Quarto casal', 'Closet',
           'Banheiro social', 'Banheiro casal', 'Área de serviço', 'Lavanderia', 'Área de lazer', 'Deck',
           'Piscina', 'Garagem']
FRASES = [
    'Bombertinho, vai para a cozinha.',
    'Bombertinho, onde você está agora?',
    'Bombertinho, vai para o banheiro social.',
    'Bombertinho, tem alguma coisa no chão do quarto dois?',
    'Bombertinho, pega o objeto vermelho aí da sala e guarda.',
    'Bombertinho, arruma o quarto um.',
    'Bombertinho, dá uma arrumada na cozinha e na sala de jantar.',
    'Bombertinho, arruma a casa inteira.',
    'Bombertinho, leva o objeto azul do quarto um pra cozinha e deixa lá.',
    'Bombertinho, pode voltar pra sua base.',
    'Bombertinho, vai no quarto do casal.',
    'Bombertinho, vai para a área de serviço.',
    'Bombertinho, quantos banheiros tem nesta casa?',
    'Então guarda.',
    'O social.',
    'Hoje o jogo foi muito bom, você viu?',          # conversa da casa, sem chamar o robô
]


def normal(s):
    s = _sem_acento(s)
    for a, b in (('quarto 1', 'quarto um'), ('quarto 2', 'quarto dois'), ('pra', 'para')):
        s = s.replace(a, b)
    return ' '.join(''.join(c if c.isalnum() else ' ' for c in s).split())


def parecido(a, b):
    return difflib.SequenceMatcher(None, normal(a), normal(b)).ratio()


def fechado(vozes, ruido_db):
    t0 = time.perf_counter()
    ouvido = Ouvido(palavras=COMODOS)
    print(f'ouvido: {ouvido.nome} em {ouvido.dispositivo}, carregado em {time.perf_counter() - t0:.1f} s')
    ouvido.transcreve(np.zeros(TAXA_OUVIDO, np.float32))          # primeira chamada: aquece
    rng = np.random.default_rng(1)
    for nome in vozes:
        t0 = time.perf_counter()
        boca = Boca(nome, efeito='nenhum')         # aqui a voz faz o papel da pessoa falando com o robô
        print(f'\n===== voz {nome} ({boca.taxa} Hz, carregada em {time.perf_counter() - t0:.1f} s)'
              + (f', ruído a {ruido_db:g} dB' if ruido_db is not None else '') + ' =====')
        certos = nome_ok = 0
        t_fala = t_ouve = dur = 0.0
        com_nome = 0
        for frase in FRASES:
            t0 = time.perf_counter()
            a = boca.audio(frase)
            t1 = time.perf_counter()
            a = reamostra(a, boca.taxa, TAXA_OUVIDO)
            if ruido_db is not None:
                pot = float(np.mean(a ** 2))
                a = a + rng.normal(0, np.sqrt(pot / 10 ** (ruido_db / 10)), len(a)).astype(np.float32)
            t2 = time.perf_counter()
            texto = ouvido.transcreve(a)
            t3 = time.perf_counter()
            t_fala += t1 - t0
            t_ouve += t3 - t2
            dur += len(a) / TAXA_OUVIDO
            p = parecido(frase, texto)
            esperava = chamou(frase) is not None
            ouviu = chamou(texto) is not None
            com_nome += esperava
            nome_ok += esperava == ouviu
            certos += p >= 0.9
            print(f'  {"ok   " if p >= 0.9 and esperava == ouviu else "FALHA"} {p * 100:3.0f}%  {frase!r} -> {texto!r}'
                  + ('' if esperava == ouviu else '   <- errou se era com ele'))
        n = len(FRASES)
        print(f'  {certos}/{n} frases entendidas (90% ou mais iguais); soube se era com ele em {nome_ok}/{n}')
        print(f'  falar: {t_fala / n:.2f} s por frase ({t_fala / dur:.2f} s por segundo de áudio); '
              f'ouvir: {t_ouve / n:.2f} s por frase')


def microfone(n):
    ouvido = Ouvido(palavras=COMODOS)
    print(f'ouvido: {ouvido.nome} em {ouvido.dispositivo}. Fale {n} frases; comece com "Bombertinho" para ele obedecer.')
    for i in range(n):
        a = ouvido.grava_frase(espera_s=30, avisa=print)
        if a is None:
            print('  ninguém falou em 30 s')
            continue
        t0 = time.perf_counter()
        texto = ouvido.transcreve(a)
        c = chamou(texto)
        print(f'  {i + 1}) {len(a) / TAXA_OUVIDO:.1f} s de áudio, {time.perf_counter() - t0:.2f} s para entender: {texto!r}'
              + (f'   -> comando: {c!r}' if c is not None else '   -> não era com o robô'))


APRESENTACAO = ['Oi Bombertinho, sou eu, pode gravar a minha voz.', 'Bombertinho, vai para a cozinha e vê se tem alguma coisa no chão.',
                'Hoje o dia está bonito e eu quero a casa arrumada.']
PROVA = ['Bombertinho, vai para a cozinha.', 'Bombertinho, onde você está agora?', 'Bombertinho, arruma a sala de estar.',
         'Bombertinho, tem alguma coisa no chão do quarto dois?', 'Bombertinho, pode voltar pra sua base.',
         'Bombertinho, esquece, vai pra garagem.', 'Então guarda e volta.', 'O social.', 'Para, para!', 'Sim, pode continuar.']


def quem_fechado():
    """Reconhecimento de quem fala com 'pessoas' de mentira (vozes do Piper e do Kokoro): cada uma se
    apresenta com 3 frases e é posta à prova com outras 10. Depois, uma de cada vez fica de fora, como
    visita: o robô não pode dizer que ela é alguém da casa."""
    from voz import Quem, vozes_de_teste
    pessoas = vozes_de_teste()
    arq = os.path.join(AQUI, '..', 'resultados', 'vozes_teste.json')
    os.makedirs(os.path.dirname(arq), exist_ok=True)
    if os.path.exists(arq):
        os.remove(arq)
    t0 = time.perf_counter()
    q = Quem(arq)
    print(f'reconhecedor carregado em {time.perf_counter() - t0:.1f} s; pessoas de mentira: {", ".join(pessoas)}')
    for nome, b in pessoas.items():
        for f in APRESENTACAO:
            q.apresenta(nome, b.audio(f), b.taxa)
    provas = {nome: [(f, b.audio(f), b.taxa) for f in PROVA] for nome, b in pessoas.items()}
    certos = errados = nao_sei = 0
    da_casa, t_total, n_total = [], 0.0, 0
    for nome, itens in provas.items():
        for f, a, taxa in itens:
            t0 = time.perf_counter()
            notas = q.notas(a, taxa)
            achou, s = q.quem(a, taxa)
            t_total += time.perf_counter() - t0
            n_total += 1
            if not notas:
                nao_sei += 1
                print(f'   {nome:>6}: {f!r} curta demais ({len(a) / taxa:.1f} s)')
                continue
            da_casa.append(dict(notas).get(nome) if False else next(v for v, n in notas if n == nome))
            if achou == nome:
                certos += 1
            elif achou is None:
                nao_sei += 1
                print(f'   {nome:>6}: {f!r} -> não soube dizer (mais parecida: {notas[0][1]} {notas[0][0]:.2f})')
            else:
                errados += 1
                print(f'   {nome:>6}: {f!r} -> ERROU, disse {achou} ({s:.2f})')
    n = certos + errados + nao_sei
    print(f'todos apresentados: {certos}/{n} certos, {nao_sei} "não sei", {errados} trocados; '
          f'{t_total / n_total * 1000:.0f} ms por frase')
    print(f'   semelhança com a própria voz: média {np.mean(da_casa):.2f}, mínima {np.min(da_casa):.2f}, '
          f'10% mais baixas até {np.percentile(da_casa, 10):.2f}')
    # visita: cada pessoa fica de fora uma vez
    enganos, total, visitas = 0, 0, []
    guardadas = dict(q.pessoas)
    for nome in pessoas:
        q.pessoas = {k: v for k, v in guardadas.items() if k != nome}
        for f, a, taxa in provas[nome]:
            notas = q.notas(a, taxa)
            if not notas:
                continue
            total += 1
            visitas.append(notas[0][0])
            achou, s = q.quem(a, taxa)
            if achou is not None:
                enganos += 1
                print(f'   visita {nome}: {f!r} -> confundida com {achou} ({s:.2f})')
    q.pessoas = guardadas
    print(f'visitas (voz que ele não conhece): confundiu {enganos} de {total} frases com alguém da casa')
    print(f'   semelhança da visita com a pessoa mais parecida: média {np.mean(visitas):.2f}, máxima {np.max(visitas):.2f}')
    print(f'   limite em uso: {q.LIMITE} (folga {q.FOLGA}). Vozes de máquina são mais diferentes entre si que as de uma família.')
    os.remove(arq)


def apresenta_no_microfone(nome, n=3):
    from voz import Quem
    ouvido = Ouvido(palavras=COMODOS)
    q = Quem()
    print(f'{nome}, fale {n} frases compridas (uns 4 segundos cada), uma de cada vez. Já conheço: {", ".join(q.nomes()) or "ninguém"}.')
    for i in range(n):
        a = ouvido.grava_frase(espera_s=30, avisa=print)
        if a is None:
            print('  ninguém falou em 30 s')
            continue
        total = q.apresenta(nome, a)
        print(f'  {i + 1}) {len(a) / TAXA_OUVIDO:.1f} s: {ouvido.transcreve(a)!r} -> {total} amostra(s) de {nome}')
    print(f'gravado em {q.caminho}')


def quem_no_microfone(n):
    from voz import Quem
    ouvido = Ouvido(palavras=COMODOS)
    q = Quem()
    print(f'conheço: {", ".join(q.nomes()) or "ninguém (use --apresenta NOME antes)"}. Falem {n} frases, cada um na sua vez.')
    for i in range(n):
        a = ouvido.grava_frase(espera_s=30, avisa=print)
        if a is None:
            print('  ninguém falou em 30 s')
            continue
        nome, s = q.quem(a)
        notas = ', '.join(f'{nm} {v:.2f}' for v, nm in q.notas(a))
        print(f'  {i + 1}) {ouvido.transcreve(a)!r} -> {nome or "não sei quem é"} ({notas or "frase curta demais"})')


def main():
    ap = argparse.ArgumentParser(description='Testes da voz do robô')
    ap.add_argument('--quem', action='store_true', help='teste fechado do reconhecimento de quem fala, com vozes de máquina')
    ap.add_argument('--apresenta', default=None, metavar='NOME', help='grava a voz de uma pessoa pelo microfone (3 frases)')
    ap.add_argument('--quem-fala', type=int, default=0, metavar='N', help='grava N frases do microfone e diz quem falou cada uma')
    ap.add_argument('--vozes', default='', help='vozes do teste, separadas por vírgula (padrão: todas da pasta vozes/)')
    ap.add_argument('--ruido', type=float, default=None, help='ruído branco por cima da fala, em dB de sinal/ruído')
    ap.add_argument('--amostras', default=None, help='pasta onde gravar um .wav de cada voz')
    ap.add_argument('--microfone', type=int, default=0, help='quantas frases gravar do microfone')
    ap.add_argument('--fala', default=None, help='fala este texto pelo alto-falante')
    a = ap.parse_args()
    for f in (sys.stdout, sys.stderr):
        try:
            f.reconfigure(encoding='utf-8', errors='replace')
        except Exception:
            pass
    vozes = [v.strip() for v in a.vozes.split(',') if v.strip()] or \
        sorted(f[:-5] for f in os.listdir(PASTA_VOZES) if f.endswith('.onnx'))
    if a.quem:
        quem_fechado()
    elif a.apresenta:
        apresenta_no_microfone(a.apresenta)
    elif a.quem_fala:
        quem_no_microfone(a.quem_fala)
    elif a.fala:
        boca_do_robo().fala(a.fala)                # a voz do robô (VOZ_ROBO troca)
    elif a.amostras:
        os.makedirs(a.amostras, exist_ok=True)
        for v in vozes:
            arq = Boca(v, efeito='nenhum').grava('Oi, eu sou o Bombertinho. Guardei o objeto laranja na caixa e já voltei para a base, '
                                'na sala de estar. Tem dois banheiros na casa: qual deles você quer?',
                                os.path.join(a.amostras, v + '.wav'))
            print('gravei', arq)
    elif a.microfone:
        microfone(a.microfone)
    else:
        fechado(vozes, a.ruido)


if __name__ == '__main__':
    main()
