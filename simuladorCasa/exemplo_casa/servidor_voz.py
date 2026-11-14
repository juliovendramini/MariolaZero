"""Servidor de voz: roda no PC e faz para o robô o que o Mariola não dá conta (ou faz devagar).

    python exemplo_casa/servidor_voz.py                 (porta 8765, só para este PC)

O Mariola não consegue ouvir na velocidade de uma conversa (o Whisper base leva ~1,5 vez o tempo da
fala; teste_brick/LEIAME.md) e falar ocupa os 4 núcleos dele por uns 2 s a cada frase. Então:

* POST /ouve      corpo = um .wav (o que o microfone gravou; 8 ou 16 bits, qualquer taxa).
                  ?pula=1.2 joga fora o começo. Devolve JSON: texto, quem (nome ou null), certeza,
                  palpite, curta, segundos (de processamento) e duracao (da fala).
* POST /fala      corpo = JSON {"texto": "..."}. Devolve o .wav da fala (voz do robô: cadu, "desenho").
* POST /apresenta ?nome=Ana, corpo = um .wav: guarda mais uma amostra da voz dessa pessoa.
* POST /esquece   ?nome=Ana: apaga a voz dessa pessoa.
* GET  /saude     o que está carregado.

Escuta só em 127.0.0.1 (VOZ_ENDERECO para mudar): nada fica aberto na rede. O brick chega aqui por um
túnel do SSH aberto pelo PC (o PC já fala com o brick por SSH; o contrário esbarraria no firewall do
Windows):

    ssh -R 8765:127.0.0.1:8765 banana@192.168.2.110

e no brick o servidor fica em http://127.0.0.1:8765 (voz_brick.VozRemota).

As vozes guardadas (memoria/vozes.json) continuam só neste PC: o brick manda o som da frase e recebe o
nome de volta, nunca a assinatura.
"""

import json
import os
import sys
import threading
import time
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
import voz  # noqa: E402

PORTA = int(os.environ.get('VOZ_PORTA', '8765'))
ENDERECO = os.environ.get('VOZ_ENDERECO', '127.0.0.1')
MAX_BYTES = 8 * 1024 * 1024         # ~4 min de áudio de 16 kHz: mais que isso não é uma frase


class Voz:
    """O que o servidor tem carregado. Uma coisa por vez na placa de vídeo (trava)."""

    def __init__(self, palavras=()):
        t = time.perf_counter()
        self.ouvido = voz.Ouvido(palavras=palavras)
        print(f'[voz] ouvido: whisper {self.ouvido.nome} em {self.ouvido.dispositivo} '
              f'({time.perf_counter() - t:.1f} s)')
        t = time.perf_counter()
        self.boca = voz.boca_do_robo()
        print(f'[voz] boca: {self.boca.nome} ({self.boca.efeito}), {time.perf_counter() - t:.1f} s')
        self.quem = None
        if os.environ.get('VOZ_QUEM', '1') not in ('0', 'nao', 'não'):
            try:
                t = time.perf_counter()
                self.quem = voz.Quem()
                print(f'[voz] quem: {len(self.quem.pessoas)} voz(es) guardada(s) ({", ".join(self.quem.pessoas) or "nenhuma"}), '
                      f'{time.perf_counter() - t:.1f} s')
            except Exception as e:                        # sem o speechbrain: ouve, mas não sabe quem é
                print(f'[voz] sem reconhecer quem fala ({type(e).__name__}: {e})')
        self.trava = threading.Lock()

    def ouve(self, wav, pula_s):
        audio = voz.le_wav(wav, pula_s)
        with self.trava:
            t = time.perf_counter()
            texto = self.ouvido.transcreve(audio) if len(audio) else ''
            f = voz.ouvida(texto, audio, self.quem if texto else None)
            gasto = time.perf_counter() - t
        return {'texto': str(f), 'quem': f.quem, 'certeza': round(float(f.certeza), 3), 'palpite': f.palpite,
                'curta': bool(f.curta), 'segundos': round(gasto, 3), 'duracao': round(len(audio) / voz.TAXA_OUVIDO, 2),
                'fala': round(self.ouvido.fala_s, 2) if len(audio) else 0.0}

    def fala(self, texto):
        with self.trava:
            a = self.boca.audio(texto)
        return voz.wav_bytes(a, self.boca.taxa)


class Pedido(BaseHTTPRequestHandler):
    servidor_voz = None          # Voz, posto pelo main()

    def log_message(self, fmt, *args):        # o log padrão é uma linha por pedido em inglês: o nosso é abaixo
        pass

    def _responde(self, codigo, corpo, tipo='application/json; charset=utf-8', extra=None):
        if isinstance(corpo, (dict, list)):
            corpo = json.dumps(corpo, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', tipo)
        self.send_header('Content-Length', str(len(corpo)))
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(corpo)

    def _corpo(self):
        n = int(self.headers.get('Content-Length') or 0)
        if n > MAX_BYTES:
            raise ValueError(f'pedido grande demais ({n} bytes)')
        return self.rfile.read(n) if n else b''

    def do_GET(self):
        v = self.servidor_voz
        if urllib.parse.urlparse(self.path).path == '/saude':
            self._responde(200, {'ouvido': f'{v.ouvido.nome} ({v.ouvido.dispositivo})',
                                 'boca': f'{v.boca.nome} ({v.boca.efeito})',
                                 'pessoas': v.quem.nomes() if v.quem else None})
        else:
            self._responde(404, {'erro': 'não existe'})

    def do_POST(self):
        v = self.servidor_voz
        url = urllib.parse.urlparse(self.path)
        q = {k: vs[0] for k, vs in urllib.parse.parse_qs(url.query).items()}
        try:
            corpo = self._corpo()
            if url.path == '/ouve':
                r = v.ouve(corpo, float(q.get('pula', 0)))
                print(f'[voz] ouviu ({r["duracao"]:.1f} s de áudio, {r["fala"]:.1f} s de fala, {r["segundos"]:.2f} s): "{r["texto"]}"'
                      + (f'  [{r["quem"]} {r["certeza"]:.2f}]' if r['quem'] else ''))
                self._responde(200, r)
            elif url.path == '/fala':
                texto = json.loads(corpo.decode('utf-8'))['texto']
                t = time.perf_counter()
                wav = v.fala(texto)
                gasto = time.perf_counter() - t
                print(f'[voz] falou ({gasto:.2f} s): "{texto}"')
                self._responde(200, wav, 'audio/wav', {'X-Segundos': f'{gasto:.3f}'})
            elif url.path == '/apresenta':
                if v.quem is None:
                    raise RuntimeError('o reconhecimento de voz não está ligado neste PC')
                nome = q['nome']
                antes = v.quem.quem(voz.le_wav(corpo))[0]
                if antes is not None and voz._sem_acento(antes) != voz._sem_acento(nome):
                    raise RuntimeError(f'esta voz já está guardada como {antes}')
                with v.trava:
                    total = v.quem.apresenta(nome, voz.le_wav(corpo))
                self._responde(200, {'nome': nome, 'amostras': total})
            elif url.path == '/esquece':
                if v.quem is None:
                    raise RuntimeError('o reconhecimento de voz não está ligado neste PC')
                self._responde(200, {'nome': v.quem.esquece(q['nome'])})
            else:
                self._responde(404, {'erro': 'não existe'})
        except Exception as e:
            print(f'[voz] erro em {url.path}: {type(e).__name__}: {e}')
            self._responde(400, {'erro': f'{e}'})


def main():
    palavras = []
    try:                                     # os cômodos da casa entram na dica do Whisper
        from mapa import Mapa
        palavras = Mapa(com_caixa=False).lugares()
    except Exception:
        pass
    Pedido.servidor_voz = Voz(palavras)
    srv = ThreadingHTTPServer((ENDERECO, PORTA), Pedido)
    print(f'[voz] servidor de voz em http://{ENDERECO}:{PORTA}  (Ctrl+C para parar)', flush=True)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
