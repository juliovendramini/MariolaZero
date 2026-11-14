"""Linux do brick: temperatura, memória, disco, rede, conversores USB do hub interno e o dmesg."""

import glob
import os
import shutil
import socket
import subprocess
import sys

from contexto import USB_PARA_PORTA, PORTAS_USB


def _le(caminho):
    try:
        with open(caminho) as f:
            return f.read().strip()
    except OSError:
        return None


def _roda(cmd, timeout=5):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout
    except (OSError, subprocess.SubprocessError):
        return None, ''


def dmesg():
    """Texto do dmesg (tenta sem e com sudo -n). None se não deu para ler."""
    for cmd in (['dmesg'], ['sudo', '-n', 'dmesg']):
        codigo, saida = _roda(cmd)
        if codigo == 0 and saida:
            return saida
    return None


def eventos_usb(texto):
    """Conta, no dmesg, os resets e desconexões do hub USB interno (onde ficam o brick e os conversores)."""
    if texto is None:
        return None
    resets = desconexoes = 0
    for linha in texto.splitlines():
        if 'reset' in linha and 'USB device' in linha and 'usb 1-1' in linha:
            resets += 1
        elif 'USB disconnect' in linha and 'usb 1-1' in linha:
            desconexoes += 1
    return resets, desconexoes


def conversores_usb():
    """{porta do Mariola: '/dev/ttyUSBn'} dos conversores que estão no hub agora."""
    achados = {}
    for link in glob.glob('/dev/serial/by-path/*'):
        nome = os.path.basename(link)
        for lugar, porta in USB_PARA_PORTA.items():
            if f'usb-0:{lugar}' in nome:
                achados[porta] = os.path.realpath(link)
    return achados


def portas_usb_do_perfil(perfil):
    usadas = {'_SERIAL0'}
    bar = perfil.get('barramento') or {}
    if bar.get('porta'):
        usadas.add(bar['porta'])
    if perfil.get('giroscopio'):
        usadas.add(perfil['giroscopio'])
    for s in perfil.get('sensores_linha', []):
        usadas.add(s['porta'])
    return [p for p in PORTAS_USB if p in usadas]


def roda(ctx):
    rel = ctx.rel
    ui = ctx.ui
    ui.mensagem('SISTEMA', 'lendo temperatura, memoria, disco e USB...')
    if not sys.platform.startswith('linux'):
        rel.pulou(f'não é o Linux do brick ({sys.platform}): sem temperatura, USB e dmesg')
        return

    # temperatura da CPU
    temps = []
    for zona in sorted(glob.glob('/sys/class/thermal/thermal_zone*/temp')):
        v = _le(zona)
        if v and v.lstrip('-').isdigit():
            temps.append(int(v) / 1000)
    if temps:
        t = max(temps)
        if t >= 80:
            rel.falha(f'CPU a {t:.0f} °C', 'muito quente: o H618 reduz a velocidade acima de ~85 °C')
        elif t >= 70:
            rel.aviso(f'CPU a {t:.0f} °C', 'quente parado: confira a ventilação')
        else:
            rel.ok(f'CPU a {t:.0f} °C')
    else:
        rel.info('temperatura da CPU não encontrada')

    # memória
    mem = {}
    for linha in (_le('/proc/meminfo') or '').splitlines():
        partes = linha.split()
        if len(partes) >= 2 and partes[1].isdigit():
            mem[partes[0].rstrip(':')] = int(partes[1]) // 1024
    if 'MemAvailable' in mem:
        livre = mem['MemAvailable']
        txt = f'memória livre {livre} MB de {mem.get("MemTotal", "?")} MB'
        (rel.aviso(txt, 'algum programa ficou rodando? (ps aux)') if livre < 150 else rel.ok(txt))

    # disco
    for ponto in ('/', '/home'):
        try:
            uso = shutil.disk_usage(ponto)
        except OSError:
            continue
        livre = uso.free / 1e6
        txt = f'disco {ponto}: {livre:.0f} MB livres'
        if ponto == '/home' and livre < 50:
            rel.falha(txt, 'a /home cheia impede gravar logs e programas (apague ~/logs antigos)')
        elif livre < 100:
            rel.aviso(txt)
        else:
            rel.ok(txt)
    montagem = _le('/proc/mounts') or ''
    for linha in montagem.splitlines():
        p = linha.split()
        if len(p) >= 4 and p[1] == '/':
            rel.info('raiz ' + ('somente leitura (ro)' if 'ro' in p[3].split(',') else 'gravável (rw)'))

    # rede
    codigo, saida = _roda(['hostname', '-I'])
    ips = saida.split() if codigo == 0 else []
    rel.info(f'{socket.gethostname()}: IP {" ".join(ips) if ips else "nenhum (sem rede)"}')
    _, carga = _roda(['uptime'])
    if carga:
        rel.info('uptime: ' + carga.strip())

    # conversores USB do hub interno
    achados = conversores_usb()
    for p in PORTAS_USB:
        if p in achados:
            rel.info(f'{p}: {achados[p]}')
    for p in portas_usb_do_perfil(ctx.perfil):
        if p not in achados:
            nome = 'o brick (ATmega)' if p == '_SERIAL0' else p
            rel.falha(f'o conversor USB de {nome} não aparece no hub',
                      'cabo USB/conversor solto ou queimado (ls -l /dev/serial/by-path)')
        else:
            rel.ok(f'conversor USB de {p} presente')
    for tty in ('/dev/ttyS2', '/dev/ttyS4', '/dev/ttyS5'):
        if not os.path.exists(tty):
            rel.aviso(f'{tty} não existe', 'overlay da UART faltando no /boot/armbianEnv.txt (INSTALACAO.md)')
    for i2c in ('/dev/i2c-0', '/dev/i2c-1'):
        if not os.path.exists(i2c):
            rel.falha(f'{i2c} não existe', 'overlay do I2C faltando (INSTALACAO.md, seção 5)')

    # dmesg: resets do hub (o problema de 12/11/2026 da Maze), erros de I2C
    texto = dmesg()
    ctx.usb_inicio = eventos_usb(texto)
    if texto is None:
        rel.pulou('não deu para ler o dmesg (sem permissão)', 'rode com sudo ou libere o dmesg_restrict')
    else:
        resets, desc = ctx.usb_inicio
        if resets or desc:
            rel.aviso(f'hub USB: {resets} resets e {desc} desconexões desde que ligou',
                      'queda dos 5 V ou ruído dos motores; o teste de estresse ajuda a achar')
        else:
            rel.ok('hub USB sem resets desde que ligou')
        erros_i2c = sum(1 for l in texto.splitlines() if 'i2c' in l.lower() and
                        ('timeout' in l.lower() or 'error' in l.lower()))
        if erros_i2c:
            rel.aviso(f'{erros_i2c} linhas de erro de I2C no dmesg')
