"""Estúdio de voz do robô (17/11/2026, pedido do Julio): uma página com 4 vozes lado a lado, cada uma
com os seus botões (motor, tom, velocidade, rouquidão, metal, rádio, brinquedo, tremido). Mexeu, ela
fala de novo. A que ficar boa ele guarda (botão "Guardar") e o Claude lê depois em
resultados/estudio_voz/escolhas.json.

Tudo gerado no PC, sem internet:
  piper   cadu e faber (vozes/*.onnx)
  kokoro  pf_dora, pm_alex, pm_santa (vozes/kokoro/)
  f5      a voz do Julio, do projeto D:\\voz_claude (outro Python: estudio_voz_f5.py fica carregado num
          processo à parte; carregar leva de ~10 s a ~3 min)

    python ferramentas/estudio_voz.py            abre http://127.0.0.1:8770 no navegador
      --porta N        outra porta
      --rede           aceita outros aparelhos da rede (celular); o firewall do Windows pode barrar
      --sem-julio      não carrega a voz do Julio
      --sem-navegador  não abre o navegador

Os efeitos estão em voz.receita() (exemplo_casa/voz.py), para a voz guardada ser a mesma no robô."""
import argparse
import datetime
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
CASA = os.path.dirname(AQUI)
sys.path.insert(0, os.path.join(CASA, 'exemplo_casa'))
import numpy as np  # noqa: E402
import voz  # noqa: E402

PAGINA = os.path.join(AQUI, 'estudio_voz.html')
SAIDA = os.path.join(CASA, 'resultados', 'estudio_voz')
ESCOLHAS = os.path.join(SAIDA, 'escolhas.json')
PASTA_JULIO = os.environ.get('VOZ_JULIO_PASTA', r'D:\voz_claude')
PYTHON_JULIO = os.path.join(PASTA_JULIO, '.venv', 'Scripts', 'python.exe')

trava = threading.Lock()          # um motor de cada vez (Piper e Kokoro não gostam de duas threads)
_piper, _kokoro, _guardadas = {}, [None], {}


class VozJulio:
    """O processo do F5 (estudio_voz_f5.py), carregado uma vez e reaproveitado."""

    def __init__(self):
        self.estado, self.refs, self.erro = 'sem', [], ''
        self._p = None
        self._trava = threading.Lock()
        self._respostas = queue.Queue()

    def liga(self):
        if not os.path.exists(PYTHON_JULIO):
            self.estado, self.erro = 'sem', f'não achei {PYTHON_JULIO}'
            return
        self.estado = 'carregando'
        self.inicio = time.monotonic()
        os.makedirs(SAIDA, exist_ok=True)
        self._log = open(os.path.join(SAIDA, 'f5.log'), 'w', encoding='utf-8', errors='replace')
        self._p = subprocess.Popen([PYTHON_JULIO, '-u', os.path.join(AQUI, 'estudio_voz_f5.py')],
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=self._log,
                                   text=True, encoding='utf-8', cwd=PASTA_JULIO)
        threading.Thread(target=self._le, daemon=True).start()

    def _le(self):
        for linha in self._p.stdout:
            try:
                d = json.loads(linha)
            except ValueError:
                continue
            if 'pronto' in d:
                if d['pronto']:
                    self.estado, self.refs = 'pronto', d['refs']
                    print(f'[estúdio] sua voz carregou em {time.monotonic() - self.inicio:.0f} s', flush=True)
                else:
                    self.estado, self.erro = 'erro', d.get('erro', '')
                    print(f'[estúdio] a sua voz não carregou: {self.erro}', flush=True)
            else:
                self._respostas.put(d)
        if self.estado != 'erro':
            self.estado, self.erro = 'erro', 'o processo do F5 fechou (veja resultados/estudio_voz/f5.log)'

    def gera(self, texto, ref, nfe, speed, semente):
        if self.estado != 'pronto':
            raise RuntimeError({'carregando': 'sua voz ainda está carregando', 'sem': 'sua voz está desligada'}
                               .get(self.estado, f'sua voz deu erro: {self.erro}'))
        with self._trava:
            arq = os.path.join(tempfile.gettempdir(), 'estudio_voz_f5.wav')
            self._p.stdin.write(json.dumps({'texto': texto, 'ref': ref, 'nfe': nfe, 'speed': speed,
                                            'semente': semente, 'saida': arq}) + '\n')
            self._p.stdin.flush()
            d = self._respostas.get(timeout=120)
            if not d.get('ok'):
                raise RuntimeError(d.get('erro', 'erro no F5'))
            import soundfile as sf
            a, taxa = sf.read(arq, dtype='float32')
            return a, taxa

    def desliga(self):
        if self._p:
            self._p.kill()


julio = VozJulio()


def vozes_piper():
    return sorted(f[:-5] for f in os.listdir(voz.PASTA_VOZES) if f.endswith('.onnx'))


VOZES_KOKORO = ['pf_dora', 'pm_alex', 'pm_santa']


def sintetiza(p, texto):
    """A fala crua (sem os efeitos), com o tom e a velocidade: (áudio, taxa, aviso). Guarda as últimas 40."""
    agudo = 2.0 ** (float(p['tom']) / 12.0)
    ritmo = float(p['velocidade']) / agudo     # fala mais devagar (ou mais rápido) e depois encolhe de volta
    chave = (p['motor'], p['voz'], int(p['nfe']), int(p['semente']), round(agudo, 4), round(ritmo, 4), texto)
    if chave in _guardadas:
        return _guardadas[chave]
    aviso = ''
    if p['motor'] == 'piper':
        with trava:
            if p['voz'] not in _piper:
                from piper import PiperVoice
                _piper[p['voz']] = PiperVoice.load(os.path.join(voz.PASTA_VOZES, p['voz'] + '.onnx'))
            from piper import SynthesisConfig
            pv = _piper[p['voz']]
            taxa = int(pv.config.sample_rate)
            partes = [c.audio_int16_array for c in pv.synthesize(texto, SynthesisConfig(length_scale=1.0 / ritmo))]
        a = np.concatenate(partes).astype(np.float32) / 32768.0 if partes else np.zeros(1, np.float32)
    elif p['motor'] == 'kokoro':
        if not 0.5 <= ritmo <= 2.0:
            aviso = 'o Kokoro só vai de 0,5 a 2 no ritmo: a velocidade saiu diferente do pedido'
        with trava:
            if _kokoro[0] is None:
                from kokoro_onnx import Kokoro
                k = os.path.join(voz.PASTA_VOZES, 'kokoro')
                _kokoro[0] = Kokoro(os.path.join(k, 'kokoro-v1.0.onnx'), os.path.join(k, 'voices-v1.0.bin'))
            a, taxa = _kokoro[0].create(texto, voice=p['voz'], speed=min(2.0, max(0.5, ritmo)), lang='pt-br')
        a = np.asarray(a, np.float32)
    elif p['motor'] == 'f5':
        a, taxa = julio.gera(texto, p['voz'], int(p['nfe']), ritmo, int(p['semente']))
    else:
        raise ValueError(f'motor {p["motor"]!r} não existe')
    if agudo != 1.0:
        a = voz.reamostra(a, taxa * agudo, taxa)
    if len(_guardadas) >= 40:
        _guardadas.pop(next(iter(_guardadas)))
    _guardadas[chave] = (a, taxa, aviso)
    return a, taxa, aviso


def gera(p, texto):
    p = {**voz.RECEITA_NEUTRA, **p}
    t = time.perf_counter()
    a, taxa, aviso = sintetiza(p, texto)
    a = voz.receita(a, taxa, p)
    return voz.wav_bytes(a, taxa), time.perf_counter() - t, aviso


def guarda(d):
    os.makedirs(SAIDA, exist_ok=True)
    try:
        with open(ESCOLHAS, encoding='utf-8') as f:
            todas = json.load(f)
    except (OSError, ValueError):
        todas = []
    n = len(todas) + 1
    nome = ''.join(c if c.isalnum() else '_' for c in d.get('nome', 'voz'))[:40]
    wav = f'{n:02d}_{nome}.wav'
    dados, _, _ = gera(d['parametros'], d['texto'])
    with open(os.path.join(SAIDA, wav), 'wb') as f:
        f.write(dados)
    todas.append({'quando': datetime.datetime.now().isoformat(timespec='seconds'), 'nome': d.get('nome', ''),
                  'nota': d.get('nota', ''), 'texto': d['texto'], 'wav': wav, 'parametros': d['parametros']})
    with open(ESCOLHAS, 'w', encoding='utf-8') as f:
        json.dump(todas, f, ensure_ascii=False, indent=1)
    return n, wav


class Pedido(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _manda(self, codigo, corpo, tipo='application/json; charset=utf-8', extra=None):
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(corpo, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(corpo)))
        self.send_header('Cache-Control', 'no-store')
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            with open(PAGINA, 'rb') as f:
                self._manda(200, f.read(), 'text/html; charset=utf-8')
        elif self.path == '/estado':
            self._manda(200, {'piper': vozes_piper(), 'kokoro': VOZES_KOKORO, 'julio': julio.estado,
                              'julio_refs': julio.refs, 'julio_erro': julio.erro,
                              'neutra': voz.RECEITA_NEUTRA})
        else:
            self._manda(404, {'erro': 'não existe'})

    def do_POST(self):
        try:
            d = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))) or b'{}')
            if self.path == '/gera':
                dados, s, aviso = gera(d['parametros'], d['texto'])
                self._manda(200, dados, 'audio/wav', {'X-Tempo': f'{s:.2f}', 'X-Aviso': aviso.encode('ascii', 'xmlcharrefreplace').decode()})
            elif self.path == '/guarda':
                n, wav = guarda(d)
                print(f'[estúdio] guardada a {n}: {d.get("nome", "")} ({wav})', flush=True)
                self._manda(200, {'n': n, 'wav': wav})
            else:
                self._manda(404, {'erro': 'não existe'})
        except Exception as e:
            self._manda(500, {'erro': f'{type(e).__name__}: {e}'})


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--porta', type=int, default=8770)
    ap.add_argument('--rede', action='store_true')
    ap.add_argument('--sem-julio', action='store_true')
    ap.add_argument('--sem-navegador', action='store_true')
    a = ap.parse_args()
    if not a.sem_julio:
        julio.liga()
    srv = ThreadingHTTPServer(('0.0.0.0' if a.rede else '127.0.0.1', a.porta), Pedido)
    url = f'http://127.0.0.1:{a.porta}'
    print(f'[estúdio] aberto em {url}' + (' (e pela rede, no IP deste PC)' if a.rede else ''), flush=True)
    if julio.estado == 'carregando':
        print('[estúdio] carregando a sua voz (F5) em segundo plano: de ~10 s a ~3 min', flush=True)
    if not a.sem_navegador:
        import webbrowser
        webbrowser.open(url)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        julio.desliga()


if __name__ == '__main__':
    main()
