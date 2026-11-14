"""A voz do robô no Mariola: o microfone, o servidor de voz do PC e o alto-falante.

* Microfone: escuta o tempo todo (arecord numa thread) e devolve cada frase dita, do primeiro som até
  o silêncio, como os bytes de um .wav mono de 16 kHz. Não usa sounddevice: o brick não tem a
  PortAudio e a raiz dele é somente leitura.
* VozRemota: fala com o servidor de voz do PC (servidor_voz.py): manda a frase gravada e recebe o texto
  e quem falou; manda um texto e recebe a fala pronta.
* AltoFalante: fala pelo PC e toca no conector AUDIO (aplay). Sem o PC, gera a fala no próprio brick
  com o Piper (voz.Boca), mais devagar (~0,8 s por segundo de fala).

Só precisa de numpy e do voz.py (e do Piper para falar sem o PC).
"""

import collections
import json
import os
import queue
import subprocess
import threading
import time
import urllib.error
import urllib.request

import numpy as np

import voz

MICROFONE = os.environ.get('VOZ_MICROFONE', 'hw:CARD=Video,DEV=0')      # o da webcam UC60
FORMATO_MIC = os.environ.get('VOZ_FORMATO', 'U8:2:48000')                 # formato:canais:taxa
ALTO_FALANTE = os.environ.get('VOZ_ALTO_FALANTE', 'plughw:CARD=Codec,DEV=0')   # o conector AUDIO
SERVIDOR = os.environ.get('VOZ_SERVIDOR', 'http://127.0.0.1:8765')


class Microfone:
    """Escuta contínua com o arecord. frase() devolve a próxima frase dita (.wav em bytes) ou None.

    O começo de uma frase é o volume passar de LIMIAR vezes o ruído de fundo por 3 blocos seguidos
    (90 ms); o fim, SILENCIO_S abaixo de FIM vezes o ruído. O ruído de fundo é medido o tempo todo,
    nos trechos quietos. surdo = True enquanto o robô fala (ele não se ouve)."""

    BLOCO_S = 0.03
    LIMIAR = 3.0
    FIM = 2.0
    MINIMO = 4.0                 # volume mínimo de fala (desvio padrão, na escala de 8 bits: -128 a 127)
    SILENCIO_S = 0.8
    MAX_S = 12.0
    ANTES_S = 0.3                # o que vem antes do começo detectado também vai (o começo da 1ª sílaba)
    ESTALO_S = 1.2               # o microfone da webcam liga com um estalo: jogado fora

    def __init__(self, dispositivo=MICROFONE, formato=FORMATO_MIC):
        fmt, canais, taxa = formato.split(':')
        self.canais, self.taxa = int(canais), int(taxa)
        self.oito_bits = fmt.upper() == 'U8'
        self.n = int(self.taxa * self.BLOCO_S)
        self.bytes_bloco = self.n * self.canais * (1 if self.oito_bits else 2)
        self.proc = subprocess.Popen(['arecord', '-q', '-D', dispositivo, '-f', fmt, '-c', canais, '-r', taxa,
                                      '-t', 'raw'], stdout=subprocess.PIPE, bufsize=0)
        self.fila = queue.Queue()
        self.surdo = False
        self.vivo = True
        threading.Thread(target=self._le, daemon=True).start()
        for _ in range(int(self.ESTALO_S / self.BLOCO_S)):
            self._bloco()
        self.ruido = max(1.0, float(np.median([self._energia(self._bloco()) for _ in range(15)])))

    def _le(self):
        """Thread: lê o arecord sem parar (senão ele perde áudio enquanto o programa pensa)."""
        while self.vivo:
            dados = b''
            while len(dados) < self.bytes_bloco:
                pedaco = self.proc.stdout.read(self.bytes_bloco - len(dados))
                if not pedaco:
                    self.fila.put(None)
                    return
                dados += pedaco
            if self.oito_bits:
                x = np.frombuffer(dados, np.uint8).astype(np.float32) - 128.0
            else:
                x = np.frombuffer(dados, np.int16).astype(np.float32) / 256.0        # na mesma escala
            self.fila.put(x.reshape(-1, self.canais).mean(axis=1))

    def _bloco(self, espera=None):
        x = self.fila.get(timeout=espera)
        if x is None:
            raise RuntimeError('o microfone parou (arecord terminou)')
        return x

    @staticmethod
    def _energia(x):
        return float(np.std(x))           # sem a média do bloco: o nível de fundo que vai mudando não conta

    def descarta(self):
        """Joga fora o que foi gravado até agora (depois de o robô falar, por exemplo)."""
        while True:
            try:
                self.fila.get_nowait()
            except queue.Empty:
                return

    def frase(self, espera_s=None):
        """A próxima frase dita, como .wav (bytes, mono, 16 kHz, 16 bits). None se ninguém começou a
        falar em espera_s segundos."""
        antes = collections.deque(maxlen=int(self.ANTES_S / self.BLOCO_S))
        gravado, falando, altos, quietos = [], False, 0, 0
        t0 = time.monotonic()
        while True:
            try:
                x = self._bloco(espera=0.5)
            except queue.Empty:
                x = None
            if x is None or self.surdo:
                antes.clear()
                gravado, falando, altos = [], False, 0
                if espera_s is not None and time.monotonic() - t0 > espera_s:
                    return None
                continue
            e = self._energia(x)
            if not falando:
                antes.append(x)
                if e > max(self.ruido * self.LIMIAR, self.MINIMO):
                    altos += 1
                else:
                    altos = 0
                    self.ruido = 0.97 * self.ruido + 0.03 * max(e, 0.5)
                if altos >= 3:
                    falando, gravado, quietos = True, list(antes), 0
                elif espera_s is not None and time.monotonic() - t0 > espera_s:
                    return None
            else:
                gravado.append(x)
                quietos = quietos + 1 if e < max(self.ruido * self.FIM, self.MINIMO * 0.6) else 0
                if quietos * self.BLOCO_S >= self.SILENCIO_S or len(gravado) * self.BLOCO_S >= self.MAX_S:
                    a = np.concatenate(gravado)
                    passo = max(1, self.taxa // voz.TAXA_OUVIDO)           # 48 kHz -> 16 kHz: média de 3
                    if passo > 1:
                        a = a[:len(a) // passo * passo].reshape(-1, passo).mean(axis=1)
                    return voz.wav_bytes(a / 128.0, self.taxa // passo)

    def fecha(self):
        self.vivo = False
        self.proc.terminate()


class VozRemota:
    """O servidor de voz do PC (servidor_voz.py)."""

    def __init__(self, url=SERVIDOR, tempo_s=20.0):
        self.url = url.rstrip('/')
        self.tempo_s = tempo_s

    def _pede(self, caminho, corpo=None, tipo='application/octet-stream'):
        req = urllib.request.Request(self.url + caminho, data=corpo, headers={'Content-Type': tipo},
                                     method='POST' if corpo is not None else 'GET')
        try:
            with urllib.request.urlopen(req, timeout=self.tempo_s) as r:
                return r.read(), r.headers
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode('utf-8')).get('erro')
            except Exception:
                msg = str(e)
            raise RuntimeError(f'o servidor de voz recusou: {msg}') from None

    def saude(self):
        """O que o servidor tem carregado, ou None se ele não responde."""
        try:
            return json.loads(self._pede('/saude')[0].decode('utf-8'))
        except Exception:
            return None

    def ouve(self, wav, pula_s=0.0):
        """O texto de uma frase gravada, como voz.Fala (com quem, certeza, palpite e curta)."""
        dados, _ = self._pede(f'/ouve?pula={pula_s}', wav, 'audio/wav')
        r = json.loads(dados.decode('utf-8'))
        f = voz.Fala(r['texto'])
        f.quem, f.certeza, f.palpite, f.curta = r['quem'], r['certeza'], r['palpite'], r['curta']
        f.audio = wav                     # para apresentar a voz depois (apresenta())
        f.segundos = r['segundos']
        return f

    def fala(self, texto):
        """O .wav (bytes) da fala do robô."""
        return self._pede('/fala', json.dumps({'texto': texto}).encode('utf-8'), 'application/json')[0]

    def apresenta(self, nome, wav):
        import urllib.parse
        r = self._pede('/apresenta?nome=' + urllib.parse.quote(nome), wav, 'audio/wav')[0]
        return json.loads(r.decode('utf-8'))['amostras']

    def esquece(self, nome):
        import urllib.parse
        return json.loads(self._pede('/esquece?nome=' + urllib.parse.quote(nome), b'')[0].decode('utf-8'))['nome']


class AltoFalante:
    """Fala pelo PC e toca no conector AUDIO; sem o PC, gera a fala no brick (voz.Boca)."""

    def __init__(self, remota=None, dispositivo=ALTO_FALANTE, local=True):
        self.remota = remota
        self.dispositivo = dispositivo
        self.local = local
        self._boca = None

    def gera(self, texto):
        """(.wav em bytes, 'pc' ou 'brick', segundos)."""
        t = time.perf_counter()
        if self.remota is not None:
            try:
                return self.remota.fala(texto), 'pc', time.perf_counter() - t
            except Exception as e:
                if not self.local:
                    raise
                print(f'[voz] o PC não respondeu ({e}): falo pelo brick')
        if self._boca is None:
            self._boca = voz.Boca()
        a = self._boca.audio(texto)
        return voz.wav_bytes(a, self._boca.taxa), 'brick', time.perf_counter() - t

    def toca(self, wav, microfone=None):
        """Toca e espera terminar. Com o microfone, ele fica surdo enquanto isso (não se ouve)."""
        if microfone is not None:
            microfone.surdo = True
        try:
            subprocess.run(['aplay', '-q', '-D', self.dispositivo, '-'], input=wav, check=False)
        finally:
            if microfone is not None:
                time.sleep(0.2)
                microfone.descarta()
                microfone.surdo = False

    def fala(self, texto, microfone=None):
        wav, onde, gasto = self.gera(texto)
        self.toca(wav, microfone)
        return wav, onde, gasto
