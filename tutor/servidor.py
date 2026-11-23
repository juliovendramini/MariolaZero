"""Página do aluno (fase 2 do tutor/PLANO.md, 19/11/2026): editor de Python, Rodar e a conversa com o tutor.

    python tutor/servidor.py               abre http://127.0.0.1:8780 no navegador
      --porta N         outra porta
      --sem-navegador   não abre o navegador
      --sementes 1-2    quantas rodadas a cada Rodar (padrão 1-2)
      --cerebro local   modelo local (Ollama) no lugar do Claude

Roda no PC do aluno (ou em casa): só escuta em 127.0.0.1, nada da rede entra. Para a internet vai só o
pedido ao tutor (código, placar, resumo e o texto da conversa; nada de nome). O editor é o Monaco (o do
VS Code) e o complemento de código é o Jedi, os dois dentro de tutor/terceiros/ (sem internet).

O que o aluno faz fica em tutor/trabalhos/LXX/main.py (um programa por desafio) e cada conversa em
tutor/conversas/ (como no tutor.py). Limite de respostas do tutor por dia neste PC: TUTOR_LIMITE_DIA (150).
"""
import argparse
import datetime
import json
import os
import subprocess
import sys
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
sys.path.insert(0, os.path.join(AQUI, 'terceiros', 'python'))
import chave  # noqa: E402
import tutor as T  # noqa: E402

PAGINA = os.path.join(AQUI, 'pagina')
MONACO = os.path.join(AQUI, 'terceiros', 'monaco')
TRABALHOS = os.path.join(AQUI, 'trabalhos')
LIBS = os.path.join(T.LINE, 'libs_mariola')
USO = os.path.join(TRABALHOS, 'uso.json')
LIMITE_DIA = int(os.environ.get('TUTOR_LIMITE_DIA', '150'))

TIPOS = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
         '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml',
         '.ttf': 'font/ttf', '.png': 'image/png', '.txt': 'text/plain; charset=utf-8'}

MODELO_PROGRAMA = '''\
"""Desafio {id}: {titulo}

{descricao}
Meta: {meta}
"""
import time

from motores import Motores
from portas import Portas
from sensorCorReflexao import CorReflexao

motores = Motores(False)
motores.direcao_motor(2, Motores.INVERTIDO)
sensor = CorReflexao(Portas.SERIAL6)

while not sensor.conectado:      # espera a primeira leitura chegar do sensor
    time.sleep(0.01)

# escreva o seu programa aqui

motores.velocidade_motores(0, 0)
motores.atualiza_motores()
'''

ARGS = None
trava_uso = threading.Lock()


# ---------------------------------------------------------------------- desafios e trabalhos
def desafios():
    sys.path.insert(0, T.LINE)
    import avalia
    return avalia.carrega_desafios()


def pasta_do(desafio):
    return os.path.join(TRABALHOS, desafio)


def programa_do(desafio, d=None):
    arq = os.path.join(pasta_do(desafio), 'main.py')
    if not os.path.exists(arq):
        d = d or desafios()[desafio]
        os.makedirs(pasta_do(desafio), exist_ok=True)
        with open(arq, 'w', encoding='utf-8', newline='\n') as f:
            f.write(MODELO_PROGRAMA.format(id=desafio, titulo=d.get('titulo'), descricao=d.get('descricao'),
                                           meta=d.get('meta_texto')))
    return arq


def le(arq):
    with open(arq, encoding='utf-8', errors='replace') as f:
        return f.read()


def grava_codigo(desafio, codigo):
    arq = programa_do(desafio)
    with open(arq, 'w', encoding='utf-8', newline='\n') as f:
        f.write(codigo.replace('\r\n', '\n'))
    return arq


def conta_resposta():
    """Conta uma resposta do tutor hoje; False se o limite do dia acabou."""
    hoje = datetime.date.today().isoformat()
    with trava_uso:
        try:
            uso = json.loads(le(USO))
        except Exception:
            uso = {}
        if uso.get(hoje, 0) >= LIMITE_DIA:
            return False
        uso[hoje] = uso.get(hoje, 0) + 1
        os.makedirs(TRABALHOS, exist_ok=True)
        with open(USO, 'w', encoding='utf-8') as f:
            json.dump(uso, f)
        return True


# ---------------------------------------------------------------------- uma sessão por desafio
class Sessao:
    def __init__(self, desafio):
        self.desafio = desafio
        self.d = desafios()[desafio]
        self.programa = programa_do(desafio, self.d)
        self.tutor = None
        self.tentativa = 0
        self.codigo_volta = None        # o código da última volta (para saber se ele mudou depois)
        self.estado = {'fase': 'parado'}
        self.falas = []                 # para a página: {quem, texto, nivel?}
        self.trava = threading.Lock()
        agora = datetime.datetime.now()
        self.pasta = os.path.join(T.CONVERSAS, f'{agora:%Y%m%d-%H%M%S}_{desafio}')
        self.data = agora

    def _tutor(self):
        if self.tutor is None:
            modelo = T.cria_modelo(ARGS.cerebro, ARGS.modelo)
            self.tutor = T.Tutor(self.desafio, self.programa, modelo, registrar=self._grava)
        return self.tutor

    def _grava(self):
        t = self.tutor
        os.makedirs(self.pasta, exist_ok=True)
        with open(os.path.join(self.pasta, 'conversa.json'), 'w', encoding='utf-8') as f:
            json.dump({'desafio': self.desafio, 'programa': self.programa, 'pagina': True,
                       'data': self.data.isoformat(timespec='seconds'), 'custo_usd': round(t.custo(), 5),
                       'falas': t.registro}, f, ensure_ascii=False, indent=1)
        print(f'[tutor] {self.desafio}: {len([e for e in t.registro if e["quem"] == "tutor"])} respostas, '
              f'US$ {t.custo():.4f} nesta conversa', flush=True)

    def _fala_tutor(self, texto):
        self.falas.append({'quem': 'tutor', 'texto': texto, 'nivel': self.tutor.nivel if self.tutor else None})

    # ---- Rodar (numa thread: o simulador leva ~1 min)
    def roda(self, codigo):
        with self.trava:
            if self.estado['fase'] in ('rodando', 'pensando'):
                return {'erro': 'já está rodando'}
            grava_codigo(self.desafio, codigo)
            erro = T.erro_de_sintaxe(codigo)
            if erro:
                return {'sintaxe': erro}
            self.tentativa += 1
            self.estado = {'fase': 'rodando', 'inicio': time.time(), 'tentativa': self.tentativa}
        threading.Thread(target=self._roda, args=(codigo,), daemon=True).start()
        return {'ok': True}

    def _roda(self, codigo):
        try:
            pasta_reg = os.path.join(self.pasta, f'tentativa{self.tentativa}')
            arqs = T.roda_simulador(self.desafio, self.programa, pasta_reg, ARGS.sementes)
            tutor = self._tutor()
            self.codigo_volta = codigo
            fala = T.PERGUNTA_PADRAO if self.tentativa == 1 else 'Mudei o código e rodei de novo.'
            self.estado.update(fase='pensando')
            # o placar sai do resumo, antes da IA: dá para mostrar já
            res = T.resumo.resume(arqs)
            txt, aprovado = T.placar(tutor.d, res)
            self.estado.update(placar=txt, aprovado=aprovado, rodadas=[
                {k: rd[k] for k in ('semente', 'total', 'lop', 'chegou', 'tempo')} for rd in res['rodadas']])
            self.falas.append({'quem': 'aluno', 'texto': f'(rodou a tentativa {self.tentativa})', 'rodou': True})
            if conta_resposta():
                resposta = tutor.volta(arqs, fala, self.tentativa)
            else:
                tutor.mensagem_volta(arqs, fala, self.tentativa)     # guarda a volta para a próxima conversa
                resposta = 'Por hoje acabaram as conversas com o tutor neste computador. O placar continua valendo!'
            self._fala_tutor(resposta)
            self.estado.update(fase='pronto', fala=resposta, nivel=tutor.nivel)
        except Exception as e:
            traceback.print_exc()
            self.estado.update(fase='erro', erro=str(e)[-1500:])

    # ---- conversa sem rodar
    def pergunta(self, texto, codigo):
        with self.trava:
            if self.estado['fase'] in ('rodando', 'pensando'):
                return {'erro': 'espere a volta terminar'}
            grava_codigo(self.desafio, codigo)
            self.falas.append({'quem': 'aluno', 'texto': texto})
            if not conta_resposta():
                r = 'Por hoje acabaram as conversas com o tutor neste computador.'
                self._fala_tutor(r)
                return {'fala': r}
            tutor = self._tutor()
            mudou = codigo if (self.codigo_volta is not None and codigo.strip() != self.codigo_volta.strip()) else None
            if tutor.arqs:
                r = tutor.pergunta(texto, mudou)
            else:
                r = tutor.sem_volta(texto, codigo)
            self._fala_tutor(r)
            return {'fala': r, 'nivel': tutor.nivel}

    def ver_volta(self, semente):
        """Abre a janela do simulador com o programa salvo, na semente pedida (a mesma rodada do Rodar)."""
        mapa = self.d.get('mapa')
        if not mapa:
            return {'erro': 'este desafio usa pista surpresa: a janela ainda não abre por aqui'}
        cmd = [sys.executable, 'simulador.py', '--robo', self.d.get('robo') or 'robo_esteira.json',
               '--mapa', mapa, '--programa', self.programa, '--semente', str(int(semente))]
        subprocess.Popen(cmd, cwd=T.LINE, env=chave.ambiente_sem_chave())
        return {'ok': True}


SESSOES = {}
trava_sessoes = threading.Lock()


def sessao(desafio):
    desafio = desafio.upper()
    with trava_sessoes:
        if desafio not in SESSOES:
            SESSOES[desafio] = Sessao(desafio)
        return SESSOES[desafio]


# ---------------------------------------------------------------------- complemento (Jedi)
_jedi = {}


def jedi_script(codigo, desafio):
    import jedi
    if 'proj' not in _jedi:
        _jedi['amb'] = jedi.InterpreterEnvironment()      # não abre outro processo
        _jedi['proj'] = jedi.Project(path=TRABALHOS, added_sys_path=[LIBS], smart_sys_path=False)
    caminho = os.path.join(pasta_do(desafio or 'L01'), 'main.py')
    return jedi.Script(codigo, path=caminho, project=_jedi['proj'], environment=_jedi['amb'])


TIPO_JEDI = {'module': 'modulo', 'class': 'classe', 'instance': 'variavel', 'function': 'funcao',
             'param': 'variavel', 'path': 'arquivo', 'keyword': 'palavra', 'property': 'propriedade',
             'statement': 'variavel'}


def _doc(nome, limite=600):
    try:
        d = nome.docstring(raw=True) or ''
    except Exception:
        d = ''
    return d[:limite]


def completa(codigo, linha, coluna, desafio):
    s = jedi_script(codigo, desafio)
    itens = []
    for c in s.complete(linha, coluna)[:80]:
        if c.name.startswith('_') and not c.name.startswith('__'):
            continue
        try:
            assin = c.get_signatures()
            detalhe = assin[0].to_string() if assin else c.description
        except Exception:
            detalhe = c.description
        itens.append({'nome': c.name, 'tipo': TIPO_JEDI.get(c.type, 'variavel'), 'detalhe': detalhe,
                      'doc': _doc(c, 400)})
    return itens


def assinatura(codigo, linha, coluna, desafio):
    s = jedi_script(codigo, desafio)
    out = []
    for a in s.get_signatures(linha, coluna):
        out.append({'texto': a.to_string(), 'params': [p.to_string() for p in a.params],
                    'ativo': a.index if a.index is not None else 0, 'doc': _doc(a, 600)})
    return out


def ajuda(codigo, linha, coluna, desafio):
    s = jedi_script(codigo, desafio)
    for n in s.help(linha, coluna):
        doc = _doc(n, 1200)
        try:
            assin = n.get_signatures()
            cab = assin[0].to_string() if assin else n.description
        except Exception:
            cab = n.description
        if doc or cab:
            return {'titulo': cab, 'doc': doc}
    return None


# ---------------------------------------------------------------------- HTTP
class Pedido(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, codigo=200):
        b = json.dumps(obj, ensure_ascii=False).encode('utf-8')
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(b)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(b)

    def _arquivo(self, raiz, rel):
        arq = os.path.normpath(os.path.join(raiz, rel))
        if not arq.startswith(os.path.normpath(raiz)) or not os.path.isfile(arq):
            self.send_error(404)
            return
        with open(arq, 'rb') as f:
            b = f.read()
        self.send_response(200)
        self.send_header('Content-Type', TIPOS.get(os.path.splitext(arq)[1].lower(), 'application/octet-stream'))
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_GET(self):
        u = urlparse(self.path)
        q = {k: v[0] for k, v in parse_qs(u.query).items()}
        try:
            if u.path in ('/', '/index.html'):
                return self._arquivo(PAGINA, 'index.html')
            if u.path.startswith('/monaco/'):
                return self._arquivo(MONACO, u.path[len('/monaco/'):])
            if u.path.startswith('/pagina/'):
                return self._arquivo(PAGINA, u.path[len('/pagina/'):])
            if u.path == '/api/desafios':
                return self._json([{'id': k, 'titulo': d.get('titulo'), 'nivel': d.get('nivel'),
                                    'descricao': d.get('descricao'), 'meta': d.get('meta_texto'),
                                    'robo': d.get('robo'), 'janela': bool(d.get('mapa'))}
                                   for k, d in desafios().items()])
            if u.path == '/api/abre':
                s = sessao(q['desafio'])
                return self._json({'codigo': le(s.programa), 'falas': s.falas, 'estado': s.estado,
                                   'arquivo': os.path.relpath(s.programa, T.REPO)})
            if u.path == '/api/estado':
                s = sessao(q['desafio'])
                e = dict(s.estado)
                if 'inicio' in e:
                    e['segundos'] = round(time.time() - e['inicio'])
                return self._json(e)
        except Exception as e:
            traceback.print_exc()
            return self._json({'erro': str(e)}, 500)
        self.send_error(404)

    def do_POST(self):
        u = urlparse(self.path)
        try:
            n = int(self.headers.get('Content-Length') or 0)
            p = json.loads(self.rfile.read(n) or b'{}')
            if u.path == '/api/salva':
                grava_codigo(p['desafio'].upper(), p['codigo'])
                return self._json({'ok': True})
            if u.path == '/api/roda':
                return self._json(sessao(p['desafio']).roda(p['codigo']))
            if u.path == '/api/pergunta':
                return self._json(sessao(p['desafio']).pergunta(p['texto'].strip()[:1000], p['codigo']))
            if u.path == '/api/ver':
                return self._json(sessao(p['desafio']).ver_volta(p.get('semente', 1)))
            if u.path == '/api/sintaxe':
                return self._json({'erro': T.erro_de_sintaxe(p['codigo'])})
            if u.path in ('/api/completa', '/api/assinatura', '/api/ajuda'):
                f = {'/api/completa': completa, '/api/assinatura': assinatura, '/api/ajuda': ajuda}[u.path]
                try:
                    r = f(p['codigo'], int(p['linha']), int(p['coluna']), p.get('desafio'))
                except Exception as e:      # o Jedi às vezes se perde no meio da digitação: sem complemento
                    print(f'[jedi] {type(e).__name__}: {e}', flush=True)
                    r = None
                return self._json({'r': r})
        except Exception as e:
            traceback.print_exc()
            return self._json({'erro': str(e)}, 500)
        self.send_error(404)


def main():
    global ARGS
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--porta', type=int, default=8780)
    ap.add_argument('--sem-navegador', action='store_true')
    ap.add_argument('--sementes', default='1-2')
    ap.add_argument('--cerebro', default=None)
    ap.add_argument('--modelo', default=None)
    ARGS = ap.parse_args()
    if not os.path.isdir(os.path.join(MONACO, 'vs')):
        raise SystemExit('falta o editor em tutor/terceiros/monaco/vs (ver tutor/LEIAME.md)')
    srv = ThreadingHTTPServer(('127.0.0.1', ARGS.porta), Pedido)
    url = f'http://127.0.0.1:{ARGS.porta}/'
    print(f'Tutor: {url}  (feche esta janela para parar)', flush=True)
    if not ARGS.sem_navegador:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
