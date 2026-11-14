"""Mede a voz no próprio Mariola: falar (Piper) e ouvir (faster-whisper), com o voz.py do robô.

Roda no brick com o venv dele e os pacotes da voz numa pasta do /home (a raiz é somente leitura):

    cd ~/robo_casa
    export PYTHONPATH=~/robo_casa/pacotes HF_HOME=~/robo_casa/hf
    /meu_venv/bin/python testa_voz.py --fala "Oi, eu sou o Bombertinho."      (gera saida/fala.wav)
    /meu_venv/bin/python testa_voz.py --fala "Oi" --toca                     (e toca no conector AUDIO)
    /meu_venv/bin/python testa_voz.py --ouve 5                               (grava 5 s do microfone e transcreve)
    /meu_venv/bin/python testa_voz.py --circuito                             (fala e transcreve a própria fala)
    /meu_venv/bin/python testa_voz.py --ouve 5 --modelos tiny,base

Sem sounddevice (o brick não tem a PortAudio e a raiz é somente leitura): grava com o arecord e toca
com o aplay. Mostra quanto tempo cada parte leva: é o que decide o que roda no robô e o que vai
para o PC.
"""

import argparse
import os
import subprocess
import sys
import time
import wave

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
os.environ.setdefault('VOZ_PASTA', os.path.join(AQUI, 'vozes'))
from voz import Boca, Ouvido, le_wav  # noqa: E402

# o microfone da webcam UC60. Ele só manda 8 bits sem sinal (U8), estéreo, a 22, 44 ou 48 kHz, com um
# estalo forte no primeiro segundo e um nível contínuo que vai mudando: gravado assim, cru, e limpo
# depois (voz.le_wav()). Pelo plughw a 16 kHz o Whisper (com o filtro de voz) não achava fala nenhuma.
MICROFONE = 'hw:CARD=Video,DEV=0'
FORMATO_MIC = ['-f', 'U8', '-c', '2', '-r', '48000']
ESTALO_S = 1.2                             # o começo da gravação que é jogado fora
ALTO_FALANTE = 'plughw:CARD=Codec,DEV=0'   # o conector AUDIO do brick (L_OUT)
FRASES = ['Bombertinho, vai para a cozinha.', 'Guarda o carrinho vermelho na caixa.',
          'Oi, eu sou o Bombertinho. Já arrumei a sala!']


def duracao(caminho):
    with wave.open(caminho) as w:
        return w.getnframes() / w.getframerate()


def fala(boca, texto, toca):
    t = time.perf_counter()
    caminho = boca.grava(texto, os.path.join(AQUI, 'saida', 'fala.wav'))
    gasto = time.perf_counter() - t
    d = duracao(caminho)
    print(f'falar "{texto}": {gasto:.2f} s para gerar {d:.2f} s de fala ({gasto / d:.2f} s por segundo de fala)')
    if toca:
        subprocess.run(['aplay', '-q', '-D', ALTO_FALANTE, caminho], check=False)
    return caminho


def ouve(ouvidos, caminho, pula_s=0.0):
    d = duracao(caminho) - pula_s
    audio = le_wav(caminho, pula_s)
    for o in ouvidos:
        t = time.perf_counter()
        texto = o.transcreve(audio)
        gasto = time.perf_counter() - t
        print(f'  ouvir com {o.nome:6}: {gasto:.2f} s para {d:.1f} s de áudio -> "{texto}"')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--fala', help='texto para o robô falar')
    ap.add_argument('--toca', action='store_true', help='toca a fala no conector AUDIO')
    ap.add_argument('--ouve', type=float, help='grava estes segundos do microfone e transcreve')
    ap.add_argument('--wav', help='transcreve este arquivo')
    ap.add_argument('--pula', type=float, default=0.0, help='com --wav: segundos do começo a jogar fora (o estalo)')
    ap.add_argument('--circuito', action='store_true', help='fala as frases de teste e transcreve as falas')
    ap.add_argument('--modelos', default='tiny,base', help='modelos do whisper (tiny, base, small...)')
    a = ap.parse_args()
    os.makedirs(os.path.join(AQUI, 'saida'), exist_ok=True)

    boca = None
    if a.fala or a.circuito:
        t = time.perf_counter()
        boca = Boca()
        print(f'voz {boca.nome} ({boca.efeito}) carregada em {time.perf_counter() - t:.1f} s')
    ouvidos = []
    if a.ouve or a.wav or a.circuito:
        for m in a.modelos.split(','):
            t = time.perf_counter()
            ouvidos.append(Ouvido(modelo=m.strip(), dispositivo='cpu', palavras=['cozinha', 'sala', 'caixa']))
            print(f'whisper {m} carregado em {time.perf_counter() - t:.1f} s')

    if a.fala:
        fala(boca, a.fala, a.toca)
    if a.circuito:
        for frase in FRASES:
            ouve(ouvidos, fala(boca, frase, a.toca))
    if a.ouve:
        caminho = os.path.join(AQUI, 'saida', 'microfone.wav')
        print(f'gravando {a.ouve:.0f} s do microfone: fale agora...')
        subprocess.run(['arecord', '-q', '-D', MICROFONE, *FORMATO_MIC,
                        '-d', str(int(round(a.ouve + ESTALO_S))), caminho], check=True)
        print('pronto.')
        ouve(ouvidos, caminho, ESTALO_S)
    if a.wav:
        ouve(ouvidos, a.wav, a.pula)


if __name__ == '__main__':
    main()
