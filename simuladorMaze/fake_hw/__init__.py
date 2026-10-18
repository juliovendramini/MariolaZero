"""Instala o hardware virtual no processo do aluno.

Troca apenas a camada mais baixa (serial, smbus2, gpiod, relógio) e a descoberta de
portas USB em portas.py. As bibliotecas do Mariola (motores.py, vl53.py, ...)
rodam exatamente como estão no robô.
"""

import importlib
import os
import sys
import types


def _como_modulo(nome, mod):
    m = types.ModuleType(nome)
    for k, v in vars(mod).items():
        if not k.startswith('__'):
            setattr(m, k, v)
    return m


def instalar(pasta_programa, pasta_libs):
    from . import cliente
    cliente.conectar()
    cliente.relogio.instala()

    from . import fake_serial, fake_smbus2, fake_gpiod, sim_modulos

    serial_mod = _como_modulo('serial', fake_serial)
    serial_mod.__path__ = []
    sys.modules['serial'] = serial_mod
    sys.modules['smbus2'] = _como_modulo('smbus2', fake_smbus2)
    gp = _como_modulo('gpiod', fake_gpiod)
    gp.__path__ = []
    sys.modules['gpiod'] = gp
    sys.modules['gpiod.line'] = fake_gpiod.line
    for nome, mod in sim_modulos.modulos().items():
        sys.modules[nome] = mod
    # tela OLED (luma.oled) e a fonte DejaVu que a tela.py abre pelo caminho do Linux
    from . import fake_luma
    for nome, mod in fake_luma.modulos().items():
        sys.modules[nome] = mod
    fake_luma.instala_fontes()

    # caminho de import: pasta do programa primeiro, libs do Mariola como reserva
    sys.path.insert(0, pasta_programa)
    if pasta_libs not in sys.path:
        sys.path.append(pasta_libs)

    # pacote "libs" (algumas libs fazem "from libs.portas import Portas")
    if 'libs' not in sys.modules:
        caminhos = [p for p in (os.path.join(pasta_programa, 'libs'), pasta_programa, pasta_libs)
                    if os.path.isdir(p)]
        libs = types.ModuleType('libs')
        libs.__path__ = caminhos
        sys.modules['libs'] = libs

    # portas.py real, só trocando a descoberta das portas USB/ttyS
    portas = importlib.import_module('portas')

    def porta_serial_real(self, porta):
        return f'sim://SERIAL{int(porta)}'

    portas.Portas.porta_serial_real = porta_serial_real
    sys.modules['libs.portas'] = portas
