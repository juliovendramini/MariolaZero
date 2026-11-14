"""Ligação do Python com o emulador (avremu.cpp) e as funções que imitam o que a lib do Mariola manda.

O emulador é compilado sozinho na primeira vez (precisa de um g++; ver o LEIAME.md)."""
import ctypes
import glob
import os
import shutil
import struct
import subprocess
import sys

import numpy as np

AQUI = os.path.dirname(os.path.abspath(__file__))
BUILDS = os.path.join(AQUI, 'builds')
COLS = 11
PB, PC, PD, PE = 0, 1, 2, 3
NOME_INO = {'brick': 'placaBrickVendra.ino', 'placa': 'placaControleMotor.ino'}


def _acha_gxx():
    candidatos = [os.environ.get('EMU_GXX'),
                  os.path.join(AQUI, '..', '..', 'simuladorLine', 'portatil', 'gcc', 'bin', 'g++.exe'),
                  shutil.which('g++')]
    for c in candidatos:
        if c and os.path.exists(c):
            return os.path.abspath(c)
    sys.exit('Não achei um g++ para compilar o emulador (ver o LEIAME.md).')


def _biblioteca():
    """compila o avremu.cpp se a biblioteca não existe ou está mais velha que o fonte"""
    os.makedirs(BUILDS, exist_ok=True)
    fonte = os.path.join(AQUI, 'avremu.cpp')
    lib = os.path.join(BUILDS, 'avremu.dll' if os.name == 'nt' else 'avremu.so')
    if not os.path.exists(lib) or os.path.getmtime(lib) < os.path.getmtime(fonte):
        gxx = _acha_gxx()
        amb = dict(os.environ)
        amb['PATH'] = os.path.dirname(gxx) + os.pathsep + amb.get('PATH', '')
        cmd = [gxx, '-std=c++17', '-O2', '-shared', '-o', lib, fonte]
        cmd[3:3] = ['-static'] if os.name == 'nt' else ['-fPIC']
        r = subprocess.run(cmd, env=amb, capture_output=True, text=True)
        if r.returncode:
            sys.exit('Erro ao compilar o emulador:\n' + r.stderr)
    return lib


dll = ctypes.CDLL(_biblioteca())
dll.emu_roda.argtypes = [ctypes.c_uint64]
dll.emu_ciclos.restype = ctypes.c_uint64
dll.emu_fcpu.restype = ctypes.c_double
dll.emu_erro.restype = ctypes.c_char_p
dll.emu_resets.restype = ctypes.c_uint64
dll.emu_motor_param.argtypes = [ctypes.c_double] * 3
dll.emu_mao.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double]
dll.emu_falha.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_double]
dll.emu_mem.argtypes = [ctypes.c_uint16, ctypes.c_char_p, ctypes.c_int, ctypes.c_int]


def firmware(placa, qual):
    """(hex, elf) do firmware 'antigo' ou 'novo' do 'brick' ou da 'placa' (compilados pelo compila.py)"""
    base = os.path.join(BUILDS, '%s_%s' % (placa, qual), NOME_INO[placa])
    if not os.path.exists(base + '.hex'):
        sys.exit('Falta o firmware %s do %s: rode "python compila.py" primeiro.' % (qual, placa))
    return base + '.hex', (base + '.elf' if os.path.exists(base + '.elf') else None)


def le_hex(arq):
    mem = bytearray(b'\xff' * 0x10000)
    base = 0
    fim = 0
    for linha in open(arq):
        linha = linha.strip()
        if not linha.startswith(':'):
            continue
        n = int(linha[1:3], 16)
        end = int(linha[3:7], 16)
        tipo = int(linha[7:9], 16)
        dados = bytes.fromhex(linha[9:9 + 2 * n])
        if tipo == 0:
            mem[base + end:base + end + n] = dados
            fim = max(fim, base + end + n)
        elif tipo == 2:
            base = int(linha[9:13], 16) * 16
        elif tipo == 4:
            base = int(linha[9:13], 16) << 16
    return bytes(mem[:fim])


def simbolos(elf):
    """nome -> endereço de dados (sem o 0x800000 que o avr-gcc soma). Vazio se não houver avr-nm."""
    nm = shutil.which('avr-nm')
    if not nm:
        achados = glob.glob(os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Arduino15', 'packages', 'arduino',
                                         'tools', 'avr-gcc', '*', 'bin', 'avr-nm.exe'))
        nm = achados[0] if achados else None
    if not nm:
        return {}
    saida = subprocess.run([nm, elf], capture_output=True, text=True).stdout
    tab = {}
    for linha in saida.splitlines():
        p = linha.split()
        if len(p) == 3:
            end = int(p[0], 16)
            tab[p[2]] = end - 0x800000 if end >= 0x800000 else end
    return tab


class Emu:
    def __init__(self, hexa, elf=None, tipo=0, eeprom=None):
        dll.emu_inicia(tipo)
        dados = le_hex(hexa)
        dll.emu_carrega(dados, len(dados))
        self.f = dll.emu_fcpu()
        self.sim = simbolos(elf) if elf else {}
        self.tipo = tipo
        if eeprom is not None:
            dll.emu_eeprom(bytes(eeprom), len(eeprom), 1)
        elif tipo == 0:
            dll.emu_eeprom(b'\xff' * 1024, 1024, 1)
        self.linhas = []
        self.rx = []

    # ------------------------------------------------------------ tempo
    @property
    def t(self):
        return dll.emu_ciclos() / self.f

    def roda(self, dt):
        self.ate(self.t + dt)

    def ate(self, t):
        if dll.emu_roda(int(t * self.f)):
            raise RuntimeError(dll.emu_erro().decode())
        self._colhe()

    def _colhe(self):
        n = dll.emu_traco_linhas()
        if n:
            buf = np.zeros((n, COLS))
            dll.emu_traco_le(buf.ctypes.data_as(ctypes.POINTER(ctypes.c_double)), n)
            self.linhas.append(buf)
        b = ctypes.create_string_buffer(4096)
        t = (ctypes.c_double * 4096)()
        n = dll.emu_serial_le(b, t, 4096)
        for i in range(n):
            self.rx.append((t[i], b.raw[i]))

    def traco(self):
        """colunas: t, u1..u4 (tensão média na ponte, -1 a 1), th1, th2 (contagens), w1, w2, pinos, extra"""
        if not self.linhas:
            return np.zeros((0, COLS))
        tudo = np.vstack(self.linhas)
        self.linhas = [tudo]
        return tudo

    def passos_traco(self, n):
        """uma linha do traço a cada n passos da física (16 us cada)"""
        self._colhe()
        dll.emu_traco_passos(n)

    # ------------------------------------------------------------ serial
    def envia(self, dados):
        dados = bytes(dados)
        dll.emu_serial_envia(dados, len(dados))

    def recebe(self, n, limite=0.05):
        """espera n bytes da placa (até 'limite' segundos); devolve os bytes recebidos"""
        self.rx = []
        fim = self.t + limite
        while len(self.rx) < n and self.t < fim:
            self.roda(0.0002)
        return bytes(b for _, b in self.rx)

    def comando(self, dados, n_resp=10, limite=0.05):
        self.envia(dados)
        return self.recebe(n_resp, limite)

    # ------------------------------------------------------------ memória e modelo
    def le(self, nome, fmt='<i'):
        """variável global do firmware (precisa do .elf e do avr-nm)"""
        tam = struct.calcsize(fmt)
        b = ctypes.create_string_buffer(tam)
        dll.emu_mem(self.sim[nome], b, tam, 0)
        return struct.unpack(fmt, b.raw)[0]

    def eeprom(self, n=1024):
        b = ctypes.create_string_buffer(n)
        dll.emu_eeprom(b, n, 0)
        return b.raw

    def motor(self, m):
        """(posição em contagens, velocidade em contagens/s) do eixo do motor m"""
        th, w = ctypes.c_double(), ctypes.c_double()
        dll.emu_motor(m, ctypes.byref(th), ctypes.byref(w))
        return th.value, w.value

    def mao(self, m, vel=None):
        """gira o eixo do motor m com a mão a 'vel' contagens/s; None solta"""
        dll.emu_mao(m, 0 if vel is None else 1, 0.0 if vel is None else float(vel))

    def ligacao(self, m, motor_trocado=False, encoder_trocado=False, falha=0, fator_re=0.0):
        """como o motor m está ligado: fios trocados, falha (1 = canal A do encoder solto, 2 = canal B
        solto, 4 = motor desligado) e motor mais fraco para trás (fator_re, 0 = igual)"""
        dll.emu_polaridade(m, int(motor_trocado), int(encoder_trocado))
        dll.emu_falha(m, falha, float(fator_re))


# ---------------------------------------------------------------- protocolo do Mariola (libs/motores.py)
ENVIA_SERVOS, ENVIA_MOTORES, ATUALIZA, POTENCIA, MOTORES_4X4 = 0xFD, 0xFC, 0xFB, 0xFA, 0xF8
BREAK, HOLD = 0, 1


def msg_motores(m1, m2, m3=0, m4=0, ang1=0, ang2=0, freio=BREAK, cmd=ENVIA_MOTORES):
    return bytes([cmd, m1 & 0xFF, m2 & 0xFF, m3 & 0xFF, m4 & 0xFF,
                  (ang1 >> 8) & 0xFF, ang1 & 0xFF, (ang2 >> 8) & 0xFF, ang2 & 0xFF, freio])


def resposta(r):
    if len(r) != 10:
        return None
    return r[0], struct.unpack('>i', r[1:5])[0], struct.unpack('>i', r[5:9])[0], r[9]


class Mariola(Emu):
    """brick com a lib falando a cada 'periodo' segundos, como um programa de aluno"""

    def motores(self, m1, m2, m3=0, m4=0, freio=BREAK, cmd=ENVIA_MOTORES, ang1=0, ang2=0):
        r = self.comando(msg_motores(m1, m2, m3, m4, ang1, ang2, freio, cmd))
        return resposta(r)

    def anda(self, dur, m1, m2, m3=0, m4=0, freio=BREAK, cmd=ENVIA_MOTORES, periodo=0.02):
        """repete o mesmo comando por 'dur' segundos"""
        fim = self.t + dur
        ult = None
        while self.t < fim:
            prox = self.t + periodo
            ult = self.motores(m1, m2, m3, m4, freio, cmd)
            if self.t < prox:
                self.ate(min(prox, fim))
        return ult
