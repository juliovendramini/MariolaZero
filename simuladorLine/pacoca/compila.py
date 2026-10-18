"""Compila o programa Arduino do Paçoca (.ino) para rodar no PC, ligado ao simulador.

O .ino e as bibliotecas do brick (brickSimples.h, BMI160.cpp, VL53L0X.cpp, ...) compilam com o
g++ do PC sem mudança. Por baixo entram:
  * pacoca/nucleo/  um Arduino.h simulado (relógio virtual, pinos, Serial, EEPROM)
  * pacoca/troca/   SoftwareSerial, SoftWire, Servo, ultrassom... que falam com o simulador

Ordem dos arquivos (o último ganha):
  1. pacoca/libs_pacoca/  cópia do brickSimples (reserva, para quem só tem o .ino)
  2. a pasta do programa (o aluno pode ter a lib dele, inclusive modificada)
  3. pacoca/troca/        sempre

Assembly do AVR (asm volatile) é retirado; o "jmp 0x0000" do reset vira sim_reset().

Uso manual:  python pacoca/compila.py caminho/do/programa.ino
"""

import hashlib
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

AQUI = os.path.dirname(os.path.abspath(__file__))
NUCLEO = os.path.join(AQUI, 'nucleo')
TROCA = os.path.join(AQUI, 'troca')
LIBS = os.path.join(AQUI, 'libs_pacoca')
CACHE_NUCLEO = os.path.join(AQUI, '.cache')
VERSAO = '1'          # muda quando o núcleo muda de um jeito que invalida os .o antigos

# .cpp da lib que o simulador troca (o .h da pasta troca/ tem a implementação)
CPP_TROCADOS = {'softwire.cpp', 'softwareserial.cpp', 'servo.cpp'}
EXTENSOES = ('.h', '.hpp', '.c', '.cpp', '.ino', '.tpp', '.ipp')
FONTES_NUCLEO = ['sim_core.cpp', 'sim_rede.cpp', 'sim_softserial.cpp', 'sim_softwire.cpp']

FLAGS = ['-std=gnu++17', '-O1', '-fsigned-char', '-fno-strict-aliasing', '-w', '-fdiagnostics-color=never']


class ErroCompilacao(Exception):
    pass


# ------------------------------------------------------------------ compilador
def acha_gxx():
    """g++ do PATH, ou um dos lugares comuns no Windows (MSYS2, w64devkit)."""
    env = os.environ.get('PACOCA_GXX')
    if env:
        return env
    achado = shutil.which('g++')
    if achado:
        return achado
    if os.name == 'nt':
        home = os.path.expanduser('~')
        candidatos = [
            r'C:\msys64\ucrt64\bin\g++.exe', r'C:\msys64\mingw64\bin\g++.exe',
            os.path.join(home, 'msys2', 'ucrt64', 'bin', 'g++.exe'),
            os.path.join(home, 'msys2', 'mingw64', 'bin', 'g++.exe'),
            os.path.join(home, 'msys64', 'ucrt64', 'bin', 'g++.exe'),
            os.path.join(home, 'w64devkit', 'bin', 'g++.exe'),
            r'C:\w64devkit\bin\g++.exe',
            os.path.join(AQUI, 'w64devkit', 'bin', 'g++.exe'),
        ]
        for c in candidatos:
            if os.path.exists(c):
                return c
    raise ErroCompilacao(
        'não achei o g++. No Windows, instale o MSYS2 (pacote mingw-w64-ucrt-x86_64-gcc) ou o '
        'w64devkit e ponha a pasta bin no PATH (ou defina a variável PACOCA_GXX com o caminho do g++.exe).')


def _versao_gxx(gxx):
    try:
        r = subprocess.run([gxx, '--version'], capture_output=True, text=True, timeout=20)
        return r.stdout.splitlines()[0] if r.stdout else gxx
    except Exception:
        return gxx


# ------------------------------------------------------------------ transformações de texto
_RE_ASM = re.compile(r'\b(?:__asm__|asm)\s*(?:__volatile__|volatile)?\s*(?:goto\s*)?\(')


def _fecha_parenteses(txt, i):
    """i aponta para '('; devolve o índice logo depois do ')' correspondente (pula strings)."""
    nivel = 0
    n = len(txt)
    while i < n:
        c = txt[i]
        if c == '"' or c == "'":
            q = c
            i += 1
            while i < n and txt[i] != q:
                if txt[i] == '\\':
                    i += 1
                i += 1
        elif c == '(':
            nivel += 1
        elif c == ')':
            nivel -= 1
            if nivel == 0:
                return i + 1
        i += 1
    return n


def tira_asm(txt):
    """Troca cada asm(...) por ((void)0); o reset (jmp 0) vira sim_reset()."""
    out = []
    pos = 0
    for m in _RE_ASM.finditer(txt):
        if m.start() < pos:
            continue
        ini = m.end() - 1
        fim = _fecha_parenteses(txt, ini)
        corpo = txt[ini:fim]
        out.append(txt[pos:m.start()])
        if re.search(r'jmp\s+0', corpo):
            out.append('sim_reset()')
        else:
            out.append('((void)0)')
        # mantém as quebras de linha para os números de linha dos erros não mudarem
        out.append('\n' * corpo.count('\n'))
        pos = fim
    out.append(txt[pos:])
    return ''.join(out)


def gancho_leds(txt):
    """led.h do brick: manda as cores para o simulador quando a fita é atualizada."""
    alvo = 'LED_RGB* colors = buffer;'
    if alvo not in txt or 'sim_leds' in txt:
        return txt
    gancho = (alvo + ' { uint8_t __rgb[30]; uint8_t __n = numLeds > 10 ? 10 : numLeds; '
              'for (uint8_t __i = 0; __i < __n; __i++) { __rgb[3*__i] = buffer[__i].red; '
              '__rgb[3*__i+1] = buffer[__i].green; __rgb[3*__i+2] = buffer[__i].blue; } '
              'sim_leds(pino, __rgb, __n); }')
    txt = txt.replace(alvo, gancho, 1)
    if '#include "sim_ponte.h"' not in txt:
        txt = '#include "sim_ponte.h"\n' + txt
        txt = txt.replace('#include "sim_ponte.h"\n', '#include "sim_ponte.h"\n#line 1\n', 1)
    return txt


# ------------------------------------------------------------------ protótipos do .ino
_PALAVRAS_NAO_FUNCAO = {'if', 'for', 'while', 'switch', 'do', 'else', 'return', 'class', 'struct', 'namespace',
                        'enum', 'union', 'typedef', 'template', 'operator', 'catch', 'try'}


def _sem_comentarios(txt):
    """Troca comentários e strings por espaços (mantém posições e quebras de linha)."""
    out = list(txt)
    i, n = 0, len(txt)
    while i < n:
        c = txt[i]
        if txt.startswith('//', i):
            j = txt.find('\n', i)
            j = n if j < 0 else j
            for k in range(i, j):
                out[k] = ' '
            i = j
        elif txt.startswith('/*', i):
            j = txt.find('*/', i + 2)
            j = n if j < 0 else j + 2
            for k in range(i, j):
                if out[k] != '\n':
                    out[k] = ' '
            i = j
        elif c == '"' or c == "'":
            q = c
            j = i + 1
            while j < n and txt[j] != q and txt[j] != '\n':
                if txt[j] == '\\':
                    j += 1
                j += 1
            for k in range(i + 1, min(j, n)):
                if out[k] != '\n':
                    out[k] = ' '
            i = j + 1
        else:
            i += 1
    return ''.join(out)


_RE_ASSINATURA = re.compile(r'^([A-Za-z_][\w:<>\s\*&,]*?[\s\*&])([A-Za-z_]\w*)\s*\(([^;{}()]*)\)\s*(const)?\s*$', re.S)


def prototipos(txt):
    """Funções definidas no nível de cima do .ino -> (protótipos, posição do primeiro corpo)."""
    limpo = _sem_comentarios(txt)
    # linhas de pré-processador não fazem parte de declarações
    limpo = re.sub(r'(?m)^[ \t]*#.*$', lambda m: ' ' * len(m.group(0)), limpo)
    protos = []
    primeira = None
    nivel = 0
    inicio = 0
    for i, c in enumerate(limpo):
        if c == '{':
            if nivel == 0:
                cab = limpo[inicio:i].strip()
                m = _RE_ASSINATURA.match(cab)
                if m:
                    tipo, nome, params = m.group(1).strip(), m.group(2), m.group(3)
                    primeira_palavra = tipo.split()[0] if tipo.split() else ''
                    ok = (nome not in _PALAVRAS_NAO_FUNCAO and primeira_palavra not in _PALAVRAS_NAO_FUNCAO
                          and '=' not in params and '::' not in nome and 'template' not in tipo
                          and not tipo.endswith('::'))
                    if ok:
                        p = f'{" ".join(tipo.split())} {nome}({" ".join(params.split())})'
                        if m.group(4):
                            p += ' const'
                        if p + ';' not in protos:
                            protos.append(p + ';')
                        if primeira is None:
                            # começo da declaração no texto original
                            primeira = inicio + (len(limpo[inicio:i]) - len(limpo[inicio:i].lstrip()))
            nivel += 1
        elif c == '}':
            nivel = max(0, nivel - 1)
            if nivel == 0:
                inicio = i + 1
        elif c == ';' and nivel == 0:
            inicio = i + 1
        elif c == '\n' and nivel == 0 and limpo[inicio:i].strip() == '':
            inicio = i + 1
    return protos, primeira


def monta_ino(arquivos_ino, destino):
    """Junta os .ino (o principal primeiro) num .cpp com #include <Arduino.h> e protótipos."""
    partes = ['#include <Arduino.h>\n']
    protos_todos = []
    textos = []
    for caminho in arquivos_ino:
        with open(caminho, 'r', encoding='utf-8', errors='replace') as f:
            t = f.read()
        textos.append((caminho, t))
        ps, _ = prototipos(t)
        protos_todos += [p for p in ps if p not in protos_todos]
    inseriu = False
    for caminho, t in textos:
        nome = caminho.replace('\\', '/')
        _, primeira = prototipos(t)
        if not inseriu and primeira is not None:
            antes = t[:primeira]
            depois = t[primeira:]
            linha_depois = antes.count('\n') + 1
            partes.append(f'#line 1 "{nome}"\n')
            partes.append(antes)
            if not antes.endswith('\n'):
                partes.append('\n')
            partes.append('\n'.join(protos_todos) + '\n')
            partes.append(f'#line {linha_depois} "{nome}"\n')
            partes.append(depois)
            inseriu = True
        else:
            partes.append(f'#line 1 "{nome}"\n')
            partes.append(t)
        partes.append('\n')
    with open(destino, 'w', encoding='utf-8') as f:
        f.write(''.join(partes))


# ------------------------------------------------------------------ montagem
def _hash(*partes):
    h = hashlib.sha1()
    for p in partes:
        h.update(p.encode('utf-8', 'replace') if isinstance(p, str) else p)
        h.update(b'\0')
    return h.hexdigest()[:16]


def _lista_fontes(pasta):
    res = {}
    if os.path.isdir(pasta):
        for nome in os.listdir(pasta):
            caminho = os.path.join(pasta, nome)
            if os.path.isfile(caminho) and nome.lower().endswith(EXTENSOES):
                res[nome] = caminho
    return res


def _escreve_se_mudou(caminho, txt):
    try:
        with open(caminho, 'r', encoding='utf-8') as f:
            if f.read() == txt:
                return
    except (OSError, UnicodeDecodeError):
        pass
    with open(caminho, 'w', encoding='utf-8') as f:
        f.write(txt)


def _roda_gxx(cmd, origem_de, log):
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    saida = (r.stdout or '') + (r.stderr or '')
    for de, para in origem_de.items():
        saida = saida.replace(de, para)
    if r.returncode != 0:
        raise ErroCompilacao(saida.strip() or 'erro do g++')
    if saida.strip() and log:
        log(saida.strip())


def compila(ino, log=print, forcar=False):
    """Compila o .ino; devolve o caminho do executável. Levanta ErroCompilacao com a mensagem do g++."""
    ino = os.path.abspath(ino)
    if not os.path.exists(ino):
        raise ErroCompilacao(f'arquivo não encontrado: {ino}')
    pasta = os.path.dirname(ino)
    build = os.path.join(pasta, '.sim_build')
    os.makedirs(build, exist_ok=True)
    gxx = acha_gxx()
    versao = _versao_gxx(gxx)
    flags = FLAGS + (['-pthread'] if os.name != 'nt' else [])

    # 1) arquivos: libs_pacoca < pasta do programa < troca
    fontes = {}
    for pasta_src in (LIBS, pasta, TROCA):
        for nome, caminho in _lista_fontes(pasta_src).items():
            # o nome pode diferir em maiúsculas (Windows): a última pasta ganha
            for k in [k for k in fontes if k.lower() == nome.lower()]:
                del fontes[k]
            fontes[nome] = caminho
    # .ino: só os da pasta do programa (o principal primeiro)
    inos = sorted(n for n in os.listdir(pasta) if n.lower().endswith('.ino'))
    principal = os.path.basename(ino)
    inos = [principal] + [n for n in inos if n != principal]
    for n in list(fontes):
        if n.lower().endswith('.ino'):
            del fontes[n]
    for n in list(fontes):
        if n.lower() in CPP_TROCADOS:
            del fontes[n]

    origem_de = {}
    nomes_build = set()
    for nome, caminho in fontes.items():
        with open(caminho, 'r', encoding='utf-8', errors='replace') as f:
            txt = f.read()
        txt = tira_asm(txt)
        if nome.lower() == 'led.h':
            txt = gancho_leds(txt)
        destino = os.path.join(build, nome)
        _escreve_se_mudou(destino, txt)
        nomes_build.add(nome)
        origem_de[destino] = caminho
    # tira do build o que não existe mais
    for nome in os.listdir(build):
        cam = os.path.join(build, nome)
        if os.path.isfile(cam) and nome.lower().endswith(EXTENSOES) and nome not in nomes_build \
                and not nome.startswith('_programa.ino.cpp'):
            os.remove(cam)

    sketch_cpp = os.path.join(build, '_programa.ino.cpp')
    novo = f'{sketch_cpp}.{os.getpid()}.novo'
    monta_ino([os.path.join(pasta, n) for n in inos], novo)
    with open(novo, 'r', encoding='utf-8') as f:
        _escreve_se_mudou(sketch_cpp, f.read())
    os.remove(novo)

    # 2) compila (cada .o depende do texto de todos os cabeçalhos do build: simples e seguro)
    cabecalhos = ''.join(sorted(_hash(open(os.path.join(build, n), 'rb').read())
                                for n in nomes_build if not n.lower().endswith(('.c', '.cpp'))))
    nucleo_txt = ''.join(_hash(open(os.path.join(d, n), 'rb').read())
                         for d in (NUCLEO, TROCA) for n in sorted(os.listdir(d))
                         if os.path.isfile(os.path.join(d, n)))
    incs = ['-I', build, '-I', NUCLEO]
    tarefas = []
    objs = []
    unidades = [sketch_cpp] + [os.path.join(build, n) for n in sorted(nomes_build)
                               if n.lower().endswith(('.c', '.cpp'))]
    for src in unidades:
        h = _hash(VERSAO, versao, ' '.join(flags), open(src, 'rb').read(), cabecalhos, nucleo_txt)
        obj = os.path.join(build, os.path.basename(src) + f'.{h}.o')
        objs.append(obj)
        if forcar or not os.path.exists(obj):
            tarefas.append([gxx] + flags + incs + ['-c', src, '-o', obj])
    os.makedirs(CACHE_NUCLEO, exist_ok=True)
    for src in FONTES_NUCLEO:
        cam = os.path.join(NUCLEO, src)
        h = _hash(VERSAO, versao, ' '.join(flags), open(cam, 'rb').read(), nucleo_txt)
        obj = os.path.join(CACHE_NUCLEO, src + f'.{h}.o')
        objs.append(obj)
        if forcar or not os.path.exists(obj):
            tarefas.append([gxx] + flags + ['-I', NUCLEO, '-I', TROCA, '-I', LIBS, '-c', cam, '-o', obj])
    if tarefas:
        log(f'[simulador] compilando {len(tarefas)} arquivo(s) com {os.path.basename(gxx)}...')
        with ThreadPoolExecutor(max_workers=max(1, min(8, os.cpu_count() or 2))) as ex:
            erros = []
            for fut in [ex.submit(_roda_gxx, t, origem_de, log) for t in tarefas]:
                try:
                    fut.result()
                except ErroCompilacao as e:
                    erros.append(str(e))
            if erros:
                raise ErroCompilacao('\n'.join(erros))
    # limpa .o velhos do build
    validos = set(objs)
    for nome in os.listdir(build):
        cam = os.path.join(build, nome)
        if nome.endswith('.o') and cam not in validos:
            try:
                os.remove(cam)
            except OSError:
                pass

    # 3) liga
    exe = os.path.join(build, 'programa' + ('.exe' if os.name == 'nt' else ''))
    h_link = _hash(*[os.path.basename(o) for o in objs])
    marca = exe + '.hash'
    if forcar or not os.path.exists(exe) or not os.path.exists(marca) or open(marca).read() != h_link:
        cmd = [gxx] + objs + ['-o', exe]
        if os.name == 'nt':
            cmd += ['-static', '-lws2_32']
        else:
            cmd += ['-pthread']
        _roda_gxx(cmd, origem_de, log)
        with open(marca, 'w') as f:
            f.write(h_link)
    return exe


def main():
    if len(sys.argv) < 2:
        print('uso: python pacoca/compila.py caminho/do/programa.ino')
        sys.exit(2)
    try:
        exe = compila(sys.argv[1], forcar='--forcar' in sys.argv)
    except ErroCompilacao as e:
        print(e)
        sys.exit(1)
    print(exe)


if __name__ == '__main__':
    main()
