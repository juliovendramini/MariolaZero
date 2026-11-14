"""Compila os firmwares para o emulador, em builds/:
  novo   = as pastas dos firmwares como estão agora (Documents/Arduino/placaBrickVendra e placaControleMotor)
  antigo = um commit do git de cada pasta (padrão: o estado de antes das correções de 10/11/2026)

    python compila.py                      os quatro
    python compila.py --so-novo            só os novos (depois de mexer num .ino)
    python compila.py --antigo-brick HEAD  compara com o último commit do brick
"""
import argparse
import io
import os
import shutil
import subprocess
import sys
import zipfile

AQUI = os.path.dirname(os.path.abspath(__file__))
BUILDS = os.path.join(AQUI, 'builds')
ARDUINO = os.path.normpath(os.path.join(AQUI, '..', '..', '..'))       # Documents/Arduino
# pasta do firmware, placa para o arduino-cli, commit "antigo"
PLACAS = {
    'brick': ('placaBrickVendra', 'arduino:avr:nano328pb:cpu=atmega328', '595fd9c'),
    'placa': ('placaControleMotor', 'megaTinyCore:megaavr:atxy6:chip=1616,clock=20internal,millis=enabled', 'ab5a195'),
}


def acha_cli():
    for c in (os.environ.get('ARDUINO_CLI'), r'C:\Arduino\arduino-cli.exe', shutil.which('arduino-cli')):
        if c and os.path.exists(c):
            return c
    sys.exit('Não achei o arduino-cli (defina ARDUINO_CLI com o caminho dele).')


def compila(cli, fonte, fqbn, nome, destino):
    tmp = os.path.join(BUILDS, 'tmp_' + os.path.basename(destino))
    r = subprocess.run([cli, 'compile', '-b', fqbn, '--build-path', tmp, fonte], capture_output=True, text=True)
    hexa = os.path.join(tmp, nome + '.ino.hex')
    # no megaTinyCore o passo final de cópia falha no arduino-cli, mas o .hex sai: vale o arquivo
    if not os.path.exists(hexa) or os.path.getmtime(hexa) < inicio:
        sys.exit('Erro ao compilar %s:\n%s\n%s' % (fonte, r.stdout[-2000:], r.stderr[-2000:]))
    os.makedirs(destino, exist_ok=True)
    for ext in ('.ino.hex', '.ino.elf'):
        shutil.copy2(os.path.join(tmp, nome + ext), destino)
    print('%-13s %6d bytes de .hex  (%s)' % (os.path.basename(destino), os.path.getsize(hexa), fonte))


def fonte_do_commit(repo, commit, nome):
    """extrai o commit numa pasta com o nome do sketch (o arduino-cli exige) e devolve o caminho"""
    r = subprocess.run(['git', '-C', repo, 'archive', '--format=zip', commit], capture_output=True)
    if r.returncode:
        sys.exit('git archive %s em %s falhou: %s' % (commit, repo, r.stderr.decode(errors='replace')))
    pasta = os.path.join(BUILDS, 'fonte_%s_antigo' % nome, nome)
    shutil.rmtree(pasta, ignore_errors=True)
    os.makedirs(pasta)
    with zipfile.ZipFile(io.BytesIO(r.stdout)) as z:
        for item in z.namelist():
            if '/' not in item and item.endswith(('.ino', '.h', '.cpp', '.c')):
                z.extract(item, pasta)
    return pasta


if __name__ == '__main__':
    import time
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--so-novo', action='store_true')
    ap.add_argument('--antigo-brick', default=PLACAS['brick'][2], metavar='COMMIT')
    ap.add_argument('--antigo-placa', default=PLACAS['placa'][2], metavar='COMMIT')
    args = ap.parse_args()
    cli = acha_cli()
    os.makedirs(BUILDS, exist_ok=True)
    inicio = time.time() - 2
    for placa, (nome, fqbn, _) in PLACAS.items():
        repo = os.path.join(ARDUINO, nome)
        compila(cli, repo, fqbn, nome, os.path.join(BUILDS, placa + '_novo'))
        if not args.so_novo:
            commit = args.antigo_brick if placa == 'brick' else args.antigo_placa
            compila(cli, fonte_do_commit(repo, commit, nome), fqbn, nome, os.path.join(BUILDS, placa + '_antigo'))
