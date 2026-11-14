"""Teste do servidor de voz com o Mariola: a pessoa fala, o brick manda a frase para o PC, o PC devolve o
texto, e o robô responde ("Entendi: ...") com a fala gerada no PC.

No PC (dois terminais, ou o segundo comando faz tudo junto):

    python exemplo_casa/servidor_voz.py
    ssh -R 8765:127.0.0.1:8765 banana@192.168.2.110 "cd ~/robo_casa && PYTHONPATH=~/robo_casa/pacotes /meu_venv/bin/python conversa_eco.py"

O -R do ssh é o túnel: no brick, http://127.0.0.1:8765 vai dar no servidor de voz do PC.

Mostra quanto demora cada parte: do fim da fala até o texto chegar, e do texto até a resposta estar
pronta. Grava o que ouviu e o que respondeu em saida/eco_N_*.wav. Sem caixa de som ligada, a resposta
toca no conector AUDIO do mesmo jeito (não atrapalha) e fica no arquivo.
"""

import argparse
import os
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from voz import chamou  # noqa: E402
from voz_brick import AltoFalante, Microfone, VozRemota  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--frases', type=int, default=4, help='para depois de responder a tantas frases')
    ap.add_argument('--tempo', type=float, default=90.0, help='para depois de tantos segundos')
    ap.add_argument('--sem-som', action='store_true', help='não toca a resposta (só grava o arquivo)')
    ap.add_argument('--apresenta', metavar='NOME',
                    help='as primeiras frases (--amostras) são guardadas como a voz dessa pessoa, por este microfone')
    ap.add_argument('--amostras', type=int, default=3)
    a = ap.parse_args()
    faltam_amostras = a.amostras if a.apresenta else 0

    os.makedirs(os.path.join(AQUI, 'saida'), exist_ok=True)
    remota = VozRemota()
    saude = remota.saude()
    print(f'servidor de voz: {saude or "NÃO RESPONDE (a resposta vai ser gerada no brick)"}', flush=True)
    boca = AltoFalante(remota)
    mic = Microfone()
    print(f'microfone pronto (ruído de fundo {mic.ruido:.1f}). Pode falar.', flush=True)
    fim = time.monotonic() + a.tempo
    n = 0
    k = 0                        # número dos arquivos e das linhas (todas as frases, até as que não contam)
    while n < a.frases and time.monotonic() < fim:
        wav = mic.frase(espera_s=max(1.0, fim - time.monotonic()))
        if wav is None:
            break
        t_fim_fala = time.perf_counter()
        n += 1
        k += 1
        with open(os.path.join(AQUI, 'saida', f'eco_{k}_ouvido.wav'), 'wb') as f:
            f.write(wav)
        try:
            ouvido = remota.ouve(wav)
        except Exception as e:
            print(f'{k}: não consegui mandar para o PC ({e})', flush=True)
            continue
        t_texto = time.perf_counter() - t_fim_fala
        quem = f' [{ouvido.quem} {ouvido.certeza:.2f}]' if ouvido.quem else ''
        print(f'{k}: ouvi{quem}: "{ouvido}"  (texto {t_texto:.2f} s depois do fim da fala; '
              f'{ouvido.segundos:.2f} s no PC; nome no começo: {chamou(ouvido) is not None})', flush=True)
        if not ouvido.strip():
            # barulho que passou do limite do microfone, não fala: não conta. (Sem o filtro de voz do
            # servidor, o Whisper "ouve" nesses trechos a própria dica: "Bombertinho, me ajuda.")
            n -= 1
            continue
        t = time.perf_counter()
        resposta = f'Entendi, {ouvido.quem}: {ouvido}' if ouvido.quem else f'Entendi: {ouvido}'
        if faltam_amostras:
            try:
                total = remota.apresenta(a.apresenta, wav)
                faltam_amostras -= 1
                n -= 1                     # a apresentação não conta nas frases
                print(f'   guardada como voz de {a.apresenta} ({total} amostras no total)', flush=True)
                resposta = (f'Guardei a sua voz, {a.apresenta}.' if not faltam_amostras
                            else 'Anotado. Fala mais uma frase.')
            except Exception as e:
                print(f'   não guardei a voz: {e}', flush=True)
        wav_r, onde, _ = boca.gera(resposta)
        t_resp = time.perf_counter() - t
        with open(os.path.join(AQUI, 'saida', f'eco_{k}_resposta.wav'), 'wb') as f:
            f.write(wav_r)
        print(f'   resposta pronta em {t_resp:.2f} s ({onde}); do fim da fala até poder falar: '
              f'{t_texto + t_resp:.2f} s', flush=True)
        if not a.sem_som:
            boca.toca(wav_r, mic)
    mic.fecha()
    print('fim', flush=True)


if __name__ == '__main__':
    main()
