"""Monta o pacote portátil do simulador para Windows: Python, as bibliotecas e o g++, tudo dentro
da pasta portatil/ do simulador. Nada é instalado no Windows e nada vai para o PATH: serve para
laboratório com o Windows travado (sem administrador).

    portatil/python/   Python 3.12 (python-build-standalone) + pygame, pymunk, numpy, pillow, opencv
    portatil/gcc/      g++ do w64devkit, só com o que o simulador usa (para os programas .ino do Paçoca)

Depois de montado:
    Simulador.bat              abre o simulador com o Python portátil
    Avaliar.bat --lista        roda o avalia.py com o Python portátil
    dist/SimuladorLine-portatil-AAAAMMDD.zip   o simulador inteiro + portatil/, para copiar no laboratório

Uso (num PC com internet; de preferência Windows, que aí o pacote é testado no fim):
    python ferramentas/monta_portatil.py
    python ferramentas/monta_portatil.py --sem-zip         só monta a pasta portatil/
    python ferramentas/monta_portatil.py --so-zip          só refaz o zip (portatil/ já montada)

Sem internet, com os arquivos já baixados:
    --w64devkit w64devkit-x64-2.x.x.7z.exe   (github.com/skeeto/w64devkit/releases)
    --python cpython-3.12.x+AAAAMMDD-x86_64-pc-windows-msvc-install_only_stripped.tar.gz
             (github.com/astral-sh/python-build-standalone/releases)
    --rodas pasta_com_os_whl                (pip download ... --platform win_amd64)

Tudo o que é baixado fica em portatil/_baixados/ (rodar de novo não baixa outra vez).
portatil/ e dist/ estão no .gitignore: não vão para o git.
"""

import argparse
import datetime
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.request
import zipfile

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTATIL = os.path.join(RAIZ, 'portatil')
BAIXADOS = os.path.join(PORTATIL, '_baixados')
CACHE_NUCLEO = os.path.join(PORTATIL, '_cache_nucleo')   # .o do núcleo feitos pelo g++ do pacote
DIST = os.path.join(RAIZ, 'dist')

PY_VERSAO = '3.12'
RE_W64DEVKIT = re.compile(r'^w64devkit-x64-[\d.]+(\.7z)?\.(exe|zip|7z)$')
RE_PYTHON = re.compile(r'^cpython-' + re.escape(PY_VERSAO) +
                       r'\.\d+\+\d+-x86_64-pc-windows-msvc-install_only(_stripped)?\.tar\.gz$')

# g++: o que fica da pasta bin (o resto do w64devkit é gdb, make, vim, busybox, cmake...)
GCC_BIN = {'g++.exe', 'gcc.exe', 'cpp.exe', 'as.exe', 'ld.exe', 'ar.exe'}
# g++: programas internos que não servem (Fortran, LTO, outras linguagens)
GCC_LIBEXEC_FORA = {'f951.exe', 'lto1.exe', 'cc1obj.exe', 'cc1objplus.exe', 'gnat1.exe', 'd21.exe',
                    'go1.exe', 'rust1.exe', 'cobol1.exe', 'crab1.exe', 'm2cc1.exe'}
# g++: pastas que não servem para compilar
GCC_PASTAS_FORA = {'plugin', 'install-tools', 'finclude', 'cmake', 'pkgconfig', 'lib32', 'ccache'}
GCC_LICENCAS = re.compile(r'^(COPYING.*|LICENSE.*|README.*|VERSION.*|Dockerfile)$', re.I)

# Python: o que sai (testes, IDLE, pip, cabeçalhos para compilar extensões...)
PY_FORA = ['Lib/test', 'Lib/idlelib', 'Lib/turtledemo', 'Lib/ensurepip', 'Lib/lib2to3', 'Lib/venv',
           'Lib/pydoc_data', 'include', 'libs', 'Scripts', 'tcl/tk8.6/demos', 'tcl/tix8.4.3/demos']

# zip: o que não vai do simulador (além do .gitignore, quando o git existe)
ZIP_PASTAS_FORA = {'.git', '__pycache__', '.sim_build', 'resultados', 'dist', 'portatil', '.vscode', '.idea'}
ZIP_ARQS_FORA = re.compile(r'(\.pyc|eeprom_pacoca\.bin)$')


def msg(s):
    print(s, flush=True)


def falha(s):
    msg('\nERRO: ' + s)
    sys.exit(1)


# ------------------------------------------------------------------ download
def _abre(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'simuladorLine-monta-portatil'})
    token = os.environ.get('GITHUB_TOKEN')
    if token and 'api.github.com' in url:
        req.add_header('Authorization', 'Bearer ' + token)
    return urllib.request.urlopen(req, timeout=60)


def baixa(url, nome):
    os.makedirs(BAIXADOS, exist_ok=True)
    destino = os.path.join(BAIXADOS, nome)
    if os.path.exists(destino) and os.path.getsize(destino) > 0:
        msg(f'  já baixado: {nome}')
        return destino
    msg(f'  baixando {url}')
    tmp = destino + '.parcial'
    with _abre(url) as r, open(tmp, 'wb') as f:
        total = int(r.headers.get('Content-Length') or 0)
        feito = 0
        ultimo = 0
        while True:
            b = r.read(1 << 20)
            if not b:
                break
            f.write(b)
            feito += len(b)
            if time.time() - ultimo > 2:
                ultimo = time.time()
                pct = f' ({100 * feito // total}%)' if total else ''
                msg(f'    {feito >> 20} MB{pct}')
    os.replace(tmp, destino)
    return destino


def asset_github(repo, regex):
    """(nome, url) do arquivo da última versão (release) de um repositório do GitHub."""
    try:
        with _abre(f'https://api.github.com/repos/{repo}/releases/latest') as r:
            rel = json.load(r)
        assets = list(rel.get('assets', []))
        if not any(regex.match(a['name']) for a in assets):
            pagina = 1
            while True:
                url = f'https://api.github.com/repos/{repo}/releases/{rel["id"]}/assets?per_page=100&page={pagina}'
                with _abre(url) as r:
                    lote = json.load(r)
                if not lote:
                    break
                assets += lote
                if any(regex.match(a['name']) for a in lote):
                    break
                pagina += 1
    except Exception as e:
        falha(f'não consegui consultar o GitHub ({repo}): {e}\n'
              f'Baixe o arquivo à mão em https://github.com/{repo}/releases e passe o caminho '
              f'(veja --help).')
    achados = sorted((a for a in assets if regex.match(a['name'])), key=lambda a: a['name'])
    if not achados:
        falha(f'não achei na última versão de {repo} um arquivo como {regex.pattern}')
    # prefere o _stripped (menor) quando os dois existem
    achados.sort(key=lambda a: ('_stripped' not in a['name'], a['name']))
    a = achados[0]
    return a['name'], a['browser_download_url']


# ------------------------------------------------------------------ utilidades
def apaga(caminho):
    if os.path.isdir(caminho):
        def _tira_somente_leitura(func, p, _):
            os.chmod(p, 0o700)
            func(p)
        shutil.rmtree(caminho, onerror=_tira_somente_leitura)
    elif os.path.exists(caminho):
        os.remove(caminho)


def tamanho(pasta):
    t = 0
    n = 0
    for base, _, arqs in os.walk(pasta):
        for a in arqs:
            t += os.path.getsize(os.path.join(base, a))
            n += 1
    return t, n


def roda_windows(cmd, wine, **kw):
    """Roda um .exe do pacote (no Linux, pelo Wine, só para teste)."""
    if os.name != 'nt':
        if not wine:
            return None
        cmd = ['wine'] + cmd
    return subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', **kw)


def acha_7z():
    for c in ('7z', '7za', '7zz'):
        p = shutil.which(c)
        if p:
            return p
    if os.name == 'nt':
        for base in (os.environ.get('ProgramFiles', r'C:\Program Files'),
                     os.environ.get('ProgramFiles(x86)', r'C:\Program Files (x86)')):
            p = os.path.join(base, '7-Zip', '7z.exe')
            if os.path.exists(p):
                return p
    return None


def extrai_7z(arquivo, destino):
    """O w64devkit vem como .7z autoextraível (.exe). Usa o 7-Zip se tiver; no Windows, o próprio
    .exe sabe se extrair; senão tenta o py7zr (pip install py7zr)."""
    os.makedirs(destino, exist_ok=True)
    if arquivo.lower().endswith('.zip'):
        with zipfile.ZipFile(arquivo) as z:
            z.extractall(destino)
        return
    sete = acha_7z()
    if sete:
        r = subprocess.run([sete, 'x', '-y', '-o' + destino, arquivo], capture_output=True, text=True)
        if r.returncode == 0:
            return
        msg(r.stdout[-2000:] + r.stderr[-2000:])
    if os.name == 'nt' and arquivo.lower().endswith('.exe'):
        msg('  extraindo com o próprio autoextraível...')
        r = subprocess.run([arquivo, '-y', '-o' + destino], capture_output=True, text=True)
        if r.returncode == 0 and os.listdir(destino):
            return
    try:
        import py7zr  # noqa
    except ImportError:
        falha('não consegui extrair o w64devkit: instale o 7-Zip ou rode "python -m pip install py7zr".')
    with py7zr.SevenZipFile(arquivo, 'r') as z:
        z.extractall(destino)


# ------------------------------------------------------------------ g++
def _raiz_gcc(pasta):
    for base, dirs, arqs in os.walk(pasta):
        if os.path.basename(base).lower() == 'bin' and 'g++.exe' in [a.lower() for a in arqs]:
            return os.path.dirname(base)
    falha('o arquivo do w64devkit não tem bin/g++.exe')


def _copia_filtrando(origem, destino):
    """Copia uma árvore do compilador deixando de fora o que não serve para compilar C/C++."""
    for base, dirs, arqs in os.walk(origem):
        dirs[:] = [d for d in dirs if d.lower() not in GCC_PASTAS_FORA]
        rel = os.path.relpath(base, origem)
        alvo = os.path.join(destino, rel) if rel != '.' else destino
        os.makedirs(alvo, exist_ok=True)
        for a in arqs:
            al = a.lower()
            if al in GCC_LIBEXEC_FORA or al.startswith(('libgfortran', 'libcaf_')) or al.endswith('.la'):
                continue
            shutil.copy2(os.path.join(base, a), os.path.join(alvo, a))


def monta_gcc(arquivo):
    msg('\n== g++ (w64devkit)')
    tmp = os.path.join(PORTATIL, '_extraindo_gcc')
    apaga(tmp)
    msg(f'  extraindo {os.path.basename(arquivo)}...')
    extrai_7z(arquivo, tmp)
    raiz = _raiz_gcc(tmp)
    destino = os.path.join(PORTATIL, 'gcc')
    apaga(destino)
    os.makedirs(os.path.join(destino, 'bin'))
    # bin: só o compilador (e DLLs, se algum dia vierem)
    for a in os.listdir(os.path.join(raiz, 'bin')):
        if a.lower() in GCC_BIN or a.lower().endswith('.dll'):
            shutil.copy2(os.path.join(raiz, 'bin', a), os.path.join(destino, 'bin', a))
    for nome in os.listdir(raiz):
        cam = os.path.join(raiz, nome)
        if os.path.isdir(cam):
            if nome.lower() in ('libexec', 'lib', 'include') or nome.lower().endswith('-w64-mingw32'):
                _copia_filtrando(cam, os.path.join(destino, nome))
        elif GCC_LICENCAS.match(nome):
            shutil.copy2(cam, os.path.join(destino, nome))
    apaga(tmp)
    t, n = tamanho(destino)
    msg(f'  portatil/gcc: {n} arquivos, {t / 1e6:.0f} MB')


# ------------------------------------------------------------------ Python
def monta_python(arquivo, rodas):
    msg('\n== Python ' + PY_VERSAO)
    destino = os.path.join(PORTATIL, 'python')
    apaga(destino)
    tmp = os.path.join(PORTATIL, '_extraindo_python')
    apaga(tmp)
    msg(f'  extraindo {os.path.basename(arquivo)}...')
    with tarfile.open(arquivo) as t:
        if hasattr(tarfile, 'data_filter'):
            t.extractall(tmp, filter='data')
        else:
            t.extractall(tmp)
    raiz = None
    for base, _, arqs in os.walk(tmp):
        if 'python.exe' in arqs:
            raiz = base
            break
    if not raiz:
        falha('o arquivo do Python não tem python.exe')
    shutil.move(raiz, destino)
    apaga(tmp)
    for rel in PY_FORA:
        apaga(os.path.join(destino, *rel.split('/')))
    for a in os.listdir(os.path.join(destino, 'DLLs')):
        if a.lower().startswith(('_test', 'xxlimited')):
            apaga(os.path.join(destino, 'DLLs', a))
    site = os.path.join(destino, 'Lib', 'site-packages')
    for a in os.listdir(site) if os.path.isdir(site) else []:
        if a.lower().startswith(('pip', 'setuptools', 'wheel')):
            apaga(os.path.join(site, a))
    os.makedirs(site, exist_ok=True)

    msg('  instalando as bibliotecas (requirements.txt)...')
    for whl in sorted(os.listdir(rodas)):
        if whl.endswith('.whl'):
            instala_roda(os.path.join(rodas, whl), site)
            msg(f'    {whl}')
    t, n = tamanho(destino)
    msg(f'  portatil/python: {n} arquivos, {t / 1e6:.0f} MB')


def instala_roda(whl, site):
    """Instala um .whl só descompactando (é o que o pip faz, tirando os scripts)."""
    with zipfile.ZipFile(whl) as z:
        for info in z.infolist():
            nome = info.filename
            partes = nome.split('/')
            if partes[0].endswith('.data'):
                if len(partes) < 3 or partes[1] not in ('purelib', 'platlib'):
                    continue            # scripts, headers, data: não servem aqui
                nome = '/'.join(partes[2:])
            if nome.endswith('/'):
                continue
            alvo = os.path.join(site, *nome.split('/'))
            os.makedirs(os.path.dirname(alvo), exist_ok=True)
            with z.open(info) as o, open(alvo, 'wb') as d:
                shutil.copyfileobj(o, d)


def baixa_rodas():
    pasta = os.path.join(BAIXADOS, 'rodas_cp' + PY_VERSAO.replace('.', ''))
    apaga(pasta)
    msg('\n== bibliotecas do Python (pip download para Windows)')
    cmd = [sys.executable, '-m', 'pip', 'download', '--only-binary=:all:', '--platform', 'win_amd64',
           '--python-version', PY_VERSAO, '--implementation', 'cp', '-d', pasta,
           '-r', os.path.join(RAIZ, 'requirements.txt')]
    r = subprocess.run(cmd)
    if r.returncode != 0:
        falha('o pip download falhou (precisa de internet e do pip neste Python).')
    return pasta


# ------------------------------------------------------------------ teste
def testa(wine):
    """Testa o pacote de verdade: imports, g++, e uma rodada do exemplo do Paçoca sem janela."""
    py = os.path.join(PORTATIL, 'python', 'python.exe')
    gxx = os.path.join(PORTATIL, 'gcc', 'bin', 'g++.exe')
    if os.name != 'nt' and not wine:
        msg('\n(teste pulado: só dá para testar no Windows; no Linux, use --wine)')
        return
    msg('\n== teste')
    env = dict(os.environ)
    for v in ('PYTHONHOME', 'PYTHONPATH', 'PACOCA_GXX'):
        env.pop(v, None)
    env['PYTHONNOUSERSITE'] = '1'
    r = roda_windows([py, '-c', 'import sys, pygame, pymunk, numpy, PIL, cv2; '
                      'print(sys.version.split()[0], "pygame", pygame.version.ver, "pymunk", pymunk.version, '
                      '"numpy", numpy.__version__, "pillow", PIL.__version__, "opencv", cv2.__version__)'],
                     wine, env=env)
    if r.returncode != 0:
        falha('o Python portátil não importou as bibliotecas:\n' + r.stdout + r.stderr)
    msg('  python: ' + r.stdout.strip().splitlines()[-1])
    r = roda_windows([py, '-c', 'import tkinter; print("tkinter", tkinter.TkVersion)'], wine, env=env)
    msg('  ' + (r.stdout.strip() if r.returncode == 0 else 'AVISO: sem tkinter (o botão "abrir arquivo" não vai funcionar)'))
    if os.path.exists(gxx):
        r = roda_windows([gxx, '--version'], wine, env=env)
        if r.returncode != 0:
            falha('o g++ portátil não rodou:\n' + r.stdout + r.stderr)
        msg('  g++: ' + r.stdout.splitlines()[0])
    # rodadas sem janela, numa cópia dos exemplos (não suja as pastas deles)
    tmp = tempfile.mkdtemp(prefix='teste_portatil_')
    try:
        rodadas = [('exemplo_aluno', 'main.py', 'exemplo em Python (Mariola)')]
        if os.path.exists(gxx):
            rodadas.append(('exemplo_pacoca', 'exemplo_pacoca.ino', 'exemplo do Paçoca (compila com o g++ do pacote)'))
            apaga(CACHE_NUCLEO)
            env['PACOCA_CACHE'] = CACHE_NUCLEO
        for pasta, arq, desc in rodadas:
            ex = os.path.join(tmp, pasta)
            shutil.copytree(os.path.join(RAIZ, pasta), ex,
                            ignore=shutil.ignore_patterns('.sim_build', 'eeprom_pacoca.bin', '__pycache__'))
            msg(f'  rodando o {desc}, 30 s simulados...')
            t0 = time.time()
            r = roda_windows([py, os.path.join(RAIZ, 'simulador.py'), '--programa', os.path.join(ex, arq),
                              '--sem-janela', '--velocidade', '8', '--tempo', '30', '--semente', '1'],
                             wine, env=env, cwd=RAIZ, timeout=900)
            total = [ln for ln in r.stdout.splitlines() if 'TOTAL' in ln]
            if r.returncode != 0 or not total or 'erro de compila' in r.stdout:
                falha('a rodada de teste falhou:\n' + r.stdout[-4000:] + r.stderr[-4000:])
            msg(f'    ok em {time.time() - t0:.0f} s: {total[-1].strip()}')
    finally:
        apaga(tmp)


# ------------------------------------------------------------------ zip
def arquivos_do_simulador():
    """Arquivos do simulador que vão para o zip: os do git (tirando os ignorados) ou, sem git,
    tudo menos build, cache e resultados."""
    try:
        r = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z', '.'],
                           cwd=RAIZ, capture_output=True, timeout=60)
        if r.returncode == 0 and r.stdout:
            lista = [p for p in r.stdout.decode('utf-8').split('\0') if p]
            return [p for p in lista if os.path.isfile(os.path.join(RAIZ, p))
                    and not set(p.split('/')) & ZIP_PASTAS_FORA and not ZIP_ARQS_FORA.search(p)]
    except (OSError, subprocess.SubprocessError):
        pass
    lista = []
    for base, dirs, arqs in os.walk(RAIZ):
        dirs[:] = [d for d in dirs if d not in ZIP_PASTAS_FORA and not (d == '.cache' and
                                                                         os.path.basename(base) == 'pacoca')]
        for a in arqs:
            rel = os.path.relpath(os.path.join(base, a), RAIZ).replace(os.sep, '/')
            if not ZIP_ARQS_FORA.search(rel):
                lista.append(rel)
    return lista


def gera_zip():
    for p in ('python', 'gcc'):
        if not os.path.isdir(os.path.join(PORTATIL, p)):
            falha(f'falta portatil/{p}: monte o pacote antes (sem --so-zip)')
    os.makedirs(DIST, exist_ok=True)
    nome = f'SimuladorLine-portatil-{datetime.date.today():%Y%m%d}.zip'
    destino = os.path.join(DIST, nome)
    msg(f'\n== zip: dist/{nome}')
    pasta_zip = 'SimuladorLine'
    tmp = destino + '.parcial'
    n = 0
    with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for rel in arquivos_do_simulador():
            z.write(os.path.join(RAIZ, *rel.split('/')), f'{pasta_zip}/{rel}')
            n += 1
        for p in ('python', 'gcc'):
            base_p = os.path.join(PORTATIL, p)
            for base, dirs, arqs in os.walk(base_p):
                dirs[:] = [d for d in dirs if d != '__pycache__']
                for a in arqs:
                    cam = os.path.join(base, a)
                    rel = os.path.relpath(cam, RAIZ).replace(os.sep, '/')
                    z.write(cam, f'{pasta_zip}/{rel}')
                    n += 1
        # núcleo do Paçoca já compilado pelo g++ do pacote: a primeira compilação no laboratório é mais rápida
        if os.path.isdir(CACHE_NUCLEO):
            for a in os.listdir(CACHE_NUCLEO):
                if a.endswith('.o'):
                    z.write(os.path.join(CACHE_NUCLEO, a), f'{pasta_zip}/pacoca/.cache/{a}')
                    n += 1
    os.replace(tmp, destino)
    msg(f'  {n} arquivos, {os.path.getsize(destino) / 1e6:.0f} MB')
    return destino


# ------------------------------------------------------------------ principal
def main():
    ap = argparse.ArgumentParser(description='Monta o pacote portátil (Windows) do simulador.')
    ap.add_argument('--w64devkit', help='arquivo do w64devkit já baixado (.7z.exe, .7z ou .zip)')
    ap.add_argument('--python', help='arquivo do python-build-standalone já baixado (.tar.gz)')
    ap.add_argument('--rodas', help='pasta com os .whl de Windows já baixados')
    ap.add_argument('--sem-gcc', action='store_true', help='não monta o g++ (só Python)')
    ap.add_argument('--sem-zip', action='store_true', help='não gera o zip')
    ap.add_argument('--so-zip', action='store_true', help='só gera o zip (portatil/ já montada)')
    ap.add_argument('--sem-teste', action='store_true', help='não testa o pacote no fim')
    ap.add_argument('--wine', action='store_true', help='no Linux: testa o pacote pelo Wine')
    a = ap.parse_args()

    if a.so_zip:
        gera_zip()
        return
    os.makedirs(PORTATIL, exist_ok=True)
    py_arq = a.python or baixa(*reversed(asset_github('astral-sh/python-build-standalone', RE_PYTHON)))
    rodas = a.rodas or baixa_rodas()
    monta_python(py_arq, rodas)
    if not a.sem_gcc:
        gcc_arq = a.w64devkit or baixa(*reversed(asset_github('skeeto/w64devkit', RE_W64DEVKIT)))
        monta_gcc(gcc_arq)
    with open(os.path.join(PORTATIL, 'VERSOES.txt'), 'w', encoding='utf-8') as f:
        f.write(f'montado em {datetime.datetime.now():%Y-%m-%d %H:%M}\n')
        f.write(f'python: {os.path.basename(py_arq)}\n')
        if not a.sem_gcc:
            f.write(f'g++: {os.path.basename(gcc_arq)}\n')
        f.write('bibliotecas: ' + ', '.join(sorted(w for w in os.listdir(rodas) if w.endswith('.whl'))) + '\n')
    if not a.sem_teste:
        testa(a.wine)
    if not a.sem_zip:
        gera_zip()
    msg('\npronto. Para abrir o simulador com o pacote: Simulador.bat')


if __name__ == '__main__':
    main()
