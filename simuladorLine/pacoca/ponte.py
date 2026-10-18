"""Ponte entre o programa do Paçoca (compilado para o PC) e o simulador.

O programa (pacoca/nucleo) manda pela rede local cada coisa que no robô sairia dos pinos:
um byte na serial de um sensor, uma transação I2C, o PWM de um motor, a leitura de um botão.
Cada pedido leva o tempo virtual do programa; a ponte avança a física até esse instante
(relógio sincronizado) e responde como o dispositivo ligado naquela porta responderia.

Os dispositivos de cada porta vêm do robo_pacoca.json ("pacoca" -> "portas"):
    pro1616       sensor de linha/cor (serial 115200): 0x61 -> 16 bytes, 0x62/0x63 calibram
    vl53          VL53L0X (I2C 0x29), mesmo modelo de registradores do simulador do Mariola
    tcs34725      TCS34725 (I2C 0x29) olhando para o lado
    bmi160        BMI160 (I2C 0x68): FIFO, FOC (calibragem do viés), acelerômetro
    ultrassonico  HC-SR04 (pinos ECHO/TRIG da porta)
"""

import math
import os
import socket
import struct
import subprocess
import sys
import time

AQUI = os.path.dirname(os.path.abspath(__file__))
RAIZ = os.path.dirname(AQUI)
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from fake_hw import cliente, dispositivos  # noqa: E402

# pinos do brick Paçoca (portas.h)
PORTAS_SENSOR = {1: (14, 15), 2: (16, 17), 3: (8, 6), 4: (2, 3), 5: (18, 19)}
PORTAS_SERVO = {1: 13, 2: 12, 3: 11, 4: 5}
MOTORES = {'M1': (9, 7), 'M2': (10, 4)}
PINO_BOTAO_BRICK = 20       # A6: botão do brick (analogRead < 100 = apertado)

OP_OLA, OP_SYNC, OP_SERIAL_TX, OP_I2C_ESCREVE, OP_I2C_LE, OP_PINO_SAIDA, OP_PINO_ENTRADA, \
    OP_ANALOGICO, OP_ULTRASSOM, OP_LEDS, OP_SERVO, OP_FIM = range(1, 13)


def _porta_num(p):
    """'1', 1, 'I2C-1', 'SER-1', 'US-1', 'porta1' -> 1"""
    s = str(p)
    dig = ''.join(c for c in s if c.isdigit())
    return int(dig) if dig else None


def _pino(p):
    if isinstance(p, int):
        return p
    s = str(p).upper()
    if s.startswith('A') and s[1:].isdigit():
        return 14 + int(s[1:])
    if s.startswith('D') and s[1:].isdigit():
        return int(s[1:])
    if s.startswith('S') and s[1:].isdigit():
        return PORTAS_SERVO[int(s[1:])]
    return int(s)


class _ConexaoIdx:
    """Conexão com o simulador usada pelos dispositivos.

    * Antes de qualquer pergunta ao mundo (sensor, motor, botão) a física é levada até o tempo
      do programa. Registradores que só dependem do relógio (VL53 "medida pronta?", BMI160
      PMU...) não precisam disso, e é isso que deixa o simulador rápido com laços de espera.
    * Os modelos de VL53/TCS do simulador do Mariola pedem a medida pelo canal do mux; aqui
      cada sensor tem uma porta só dele, e o "canal" negativo carrega o índice do sensor."""

    def __init__(self, conn, ponte):
        self.conn = conn
        self.ponte = ponte

    def chamar(self, op, **kw):
        self.ponte.alcanca()
        if op in ('vl53', 'tcs') and isinstance(kw.get('canal'), int) and kw['canal'] < 0:
            kw = {'idx': -kw['canal'] - 1}
        return self.conn.chamar(op, **kw)


# =========================================================================== dispositivos
class Pro1616:
    BAUD = 115200

    def __init__(self, ponte, cfg):
        self.p = ponte
        sl = ponte.cfg.get('sensor_linha', {})
        self.latencia = float(cfg.get('latencia_ms', 0.5)) / 1000.0
        self.t_branco = float(sl.get('tempo_calibra_branco_s', 7.0))
        self.t_preto = float(sl.get('tempo_calibra_preto_s', 2.2))
        self.ocupado_ate = -1.0
        self.avisos = set()

    def recebe(self, b, t):
        """b chegou inteiro no instante t (s). Devolve [(t_inicio, bytes)]."""
        if t < self.ocupado_ate:
            return []                              # calibrando: não atende
        if b == 0x61:
            v = self.p.conn.chamar('cor')['v']
            return [(t + self.latencia, bytes(v))]
        if b in (0x62, 0x63):
            dur = self.t_branco if b == 0x62 else self.t_preto
            self.ocupado_ate = t + dur
            return [(t + dur, b'\x01')]
        if b not in self.avisos:
            self.avisos.add(b)
            if b <= 7:
                self.p.log(f'[simulador] o Pro1616 recebeu o comando 0x{b:02X} e não respondeu: parece o '
                           'sensorLinha.h da versão antiga. Use o sensorLinha.h novo (comando 0x61).')
            else:
                self.p.log(f'[simulador] o Pro1616 ignorou o byte 0x{b:02X} (comandos: 0x61, 0x62, 0x63)')
        return []


class BMI160:
    """BMI160 no nível de registradores, o bastante para a lib BMI160 do brick:
    PMU, faixa e taxa do giro, FIFO (só giro, giro+acel, com ou sem cabeçalho), FOC do giro,
    registradores de offset, dados do acelerômetro e do giro.

    O giro sai da rotação do robô na física (eixo z = guinada, anti-horário positivo no chip na
    orientação padrão) mais um viés por eixo (bias_dps); o FOC mede o viés e deixa um resíduo
    (erro_foc_dps)."""

    ODR = {6: 25.0, 7: 50.0, 8: 100.0, 9: 200.0, 10: 400.0, 11: 800.0, 12: 1600.0, 13: 3200.0, 5: 12.5}
    SENS = {0: 16.4, 1: 32.8, 2: 65.6, 3: 131.2, 4: 262.4}
    ACC_SENS = {3: 16384.0, 5: 8192.0, 8: 4096.0, 12: 2048.0}
    FIFO_MAX = 1024

    def __init__(self, ponte, cfg):
        self.p = ponte
        self.addr = int(cfg.get('endereco', 0x68))
        self.eixos = cfg.get('eixos', ['frente', 'esquerda', 'cima'])
        self.bias = [float(x) for x in cfg.get('bias_dps', [0.25, -0.2, 0.45])]
        self.erro_foc = [float(x) for x in cfg.get('erro_foc_dps', [0.02, -0.02, 0.03])]
        self.reset()

    def reset(self):
        self.regs = {0x00: 0xD1, 0x40: 0x28, 0x41: 0x03, 0x42: 0x28, 0x43: 0x00, 0x46: 0x80, 0x47: 0x10}
        for r in range(0x71, 0x78):
            self.regs[r] = 0
        self.ptr = 0
        self.acc_pronto = None        # instante em que o acelerômetro fica normal
        self.gyr_pronto = None
        self.fifo = bytearray()
        self.cheia = False
        self.t_ult = None             # instante da última amostra gerada
        self.ang_ult = None
        self.resto = [0.0, 0.0, 0.0]
        self.taxa_ult = [0, 0, 0]
        self.acc_ult = [0.0, 0.0, 1.0]
        self.foc_fim = None

    # ---------------------------------------------------------------- eixos
    def _chip(self, corpo):
        """corpo: dict frente/esquerda/cima -> lista na ordem dos eixos x, y, z do chip"""
        out = []
        for e in self.eixos:
            sinal = -1.0 if e.startswith('-') else 1.0
            out.append(sinal * corpo[e.lstrip('+-')])
        return out

    def _imu(self, t):
        v = self.p.conn.chamar('imu')['v']      # guinada, arfagem (nariz para cima +), rolagem (direita desce +)
        return [float(x) for x in v]

    def _offset_dps(self):
        if not (self.regs.get(0x77, 0) & 0x80):
            return [0.0, 0.0, 0.0]
        msb = self.regs.get(0x77, 0)
        out = []
        for i, reg in enumerate((0x74, 0x75, 0x76)):
            v = self.regs.get(reg, 0) | (((msb >> (2 * i)) & 3) << 8)
            if v & 0x200:
                v -= 0x400
            out.append(v * 0.061)
        return out

    def _ligado(self, pronto, t):
        return pronto is not None and t >= pronto

    def atualiza(self, t):
        if not self._ligado(self.gyr_pronto, t):
            return
        odr = self.ODR.get(self.regs.get(0x42, 0x28) & 0x0F, 100.0)
        if self.t_ult is None:
            self.t_ult = math.floor(t * odr) / odr
            self.ang_ult = self._imu(t)
            return
        k0 = int(round(self.t_ult * odr))
        k1 = int(math.floor(t * odr + 1e-9))
        n = k1 - k0
        if n <= 0:
            return
        ang = self._imu(t)
        sens = self.SENS.get(self.regs.get(0x43, 0) & 7, 16.4)
        acc_sens = self.ACC_SENS.get(self.regs.get(0x41, 3) & 0x0F, 16384.0)
        off = self._offset_dps()
        cfg1 = self.regs.get(0x47, 0x10)
        com_gyr, com_acc, cabecalho = bool(cfg1 & 0x80), bool(cfg1 & 0x40), bool(cfg1 & 0x10)
        dt_total = t - self.t_ult
        ang_ant = self.ang_ult
        pula = max(0, n - (self.FIFO_MAX // 6 + 2))      # amostras que nem caberiam na FIFO
        for j in range(1, n + 1):
            tj = (k0 + j) / odr
            f = (tj - self.t_ult) / dt_total if dt_total > 0 else 1.0
            aj = [a0 + (a1 - a0) * f for a0, a1 in zip(self.ang_ult, ang)]
            if j <= pula:
                if j == pula:
                    ang_ant = aj
                    self.cheia = True
                continue
            # taxa no corpo (graus/s): guinada em z, rolagem em x, -arfagem em y
            dz = (aj[0] - ang_ant[0]) * odr
            dpitch = (aj[1] - ang_ant[1]) * odr
            droll = (aj[2] - ang_ant[2]) * odr
            ang_ant = aj
            taxa = self._chip({'frente': droll, 'esquerda': -dpitch, 'cima': dz})
            bruto = []
            for i in range(3):
                v = (taxa[i] + self.bias[i] + off[i]) * sens + self.resto[i]
                r = int(round(v))
                self.resto[i] = v - r
                bruto.append(max(-32768, min(32767, r)))
            self.taxa_ult = bruto
            pitch, roll = math.radians(aj[1]), math.radians(aj[2])
            acc = self._chip({'frente': math.sin(pitch), 'esquerda': math.sin(roll),
                              'cima': math.cos(pitch) * math.cos(roll)})
            self.acc_ult = acc
            if com_gyr or com_acc:
                quadro = bytearray()
                if cabecalho:
                    quadro.append(0x80 | (0x08 if com_gyr else 0) | (0x04 if com_acc else 0))
                if com_gyr:
                    quadro += struct.pack('<hhh', *bruto)
                if com_acc:
                    quadro += struct.pack('<hhh', *[max(-32768, min(32767, int(round(a * acc_sens)))) for a in acc])
                while len(self.fifo) + len(quadro) > self.FIFO_MAX:
                    del self.fifo[:len(quadro)]
                    self.cheia = True
                self.fifo += quadro
        self.t_ult = k1 / odr
        self.ang_ult = [a0 + (a1 - a0) * ((self.t_ult - (k0 / odr)) / dt_total if dt_total > 0 else 1.0)
                        for a0, a1 in zip(self.ang_ult, ang)]

    # ---------------------------------------------------------------- registradores
    def _r(self, reg, t):
        if reg == 0x03:                         # PMU_STATUS
            v = 0
            if self._ligado(self.acc_pronto, t):
                v |= 0x10
            if self._ligado(self.gyr_pronto, t):
                v |= 0x04
            return v
        if reg == 0x1B:                         # STATUS: drdy_acc, drdy_gyr, nvm_rdy, foc_rdy
            v = 0x10
            if self._ligado(self.acc_pronto, t):
                v |= 0x80
            if self._ligado(self.gyr_pronto, t):
                v |= 0x40
            if self.foc_fim is None or t >= self.foc_fim:
                v |= 0x08
            return v
        if 0x0C <= reg <= 0x11:
            self.atualiza(t)
            i = (reg - 0x0C) // 2
            v = self.taxa_ult[i] & 0xFFFF
            return v & 0xFF if reg % 2 == 0 else v >> 8
        if 0x12 <= reg <= 0x17:
            self.atualiza(t)
            sens = self.ACC_SENS.get(self.regs.get(0x41, 3) & 0x0F, 16384.0)
            i = (reg - 0x12) // 2
            v = max(-32768, min(32767, int(round(self.acc_ult[i] * sens)))) & 0xFFFF
            return v & 0xFF if reg % 2 == 0 else v >> 8
        if reg in (0x22, 0x23):
            self.atualiza(t)
            n = len(self.fifo)
            return n & 0xFF if reg == 0x22 else (n >> 8) & 0x07
        return self.regs.get(reg, 0)

    def _cmd(self, v, t):
        if v == 0xB6:                            # soft reset
            self.reset()
        elif v == 0x11:
            self.acc_pronto = t + 0.004
        elif v == 0x15:
            self.gyr_pronto = t + 0.080
            self.t_ult = None
        elif v in (0x10, 0x12):
            self.acc_pronto = None
        elif v in (0x14, 0x17):
            self.gyr_pronto = None
        elif v == 0xB0:                          # FIFO flush
            self.atualiza(t)
            self.fifo = bytearray()
        elif v == 0x03:                          # START_FOC
            if self.regs.get(0x69, 0) & 0x40:
                for i, reg in enumerate((0x74, 0x75, 0x76)):
                    lsb = int(round(-(self.bias[i] - self.erro_foc[i]) / 0.061))
                    lsb = max(-512, min(511, lsb)) & 0x3FF
                    self.regs[reg] = lsb & 0xFF
                    self.regs[0x77] = (self.regs.get(0x77, 0) & ~(3 << (2 * i))) | ((lsb >> 8) << (2 * i))
            self.foc_fim = t + 0.25

    def escreve(self, dados):
        if not dados:
            return
        t = self.p.agora()
        self.ptr = dados[0] & 0x7F
        for i, v in enumerate(dados[1:]):
            reg = (self.ptr + i) & 0x7F
            if reg == 0x7E:
                self._cmd(v, t)
            elif reg == 0x47 or reg == 0x42 or reg == 0x43 or reg == 0x77:
                self.atualiza(t)                 # amostras antigas usam a configuração antiga
                self.regs[reg] = v
            elif reg not in (0x00, 0x03, 0x1B, 0x22, 0x23, 0x24):
                self.regs[reg] = v

    def le(self, n):
        t = self.p.agora()
        if self.ptr == 0x24:                     # FIFO_DATA: cada leitura tira bytes da FIFO
            self.atualiza(t)
            out = list(self.fifo[:n])
            del self.fifo[:n]
            out += [0x00, 0x80] * ((n - len(out) + 1) // 2)   # FIFO vazia: 0x8000
            return out[:n]
        return [self._r((self.ptr + i) & 0x7F, t) for i in range(n)]


# =========================================================================== ponte
class Ponte:
    def __init__(self, exe, pasta):
        porta = int(os.environ.get('SIM_PORTA', '0'))
        if not porta:
            raise RuntimeError('SIM_PORTA não definida: rode o programa pelo simulador (simulador.py)')
        conn = cliente.Conexao(porta)
        ola = conn.chamar('ola')
        self.cfg = ola['cfg']
        self.conn = _ConexaoIdx(conn, self)
        self.t0 = float(ola['t'])
        self.sinc = bool(ola.get('sinc'))
        self.t_sim = self.t0
        self.t_feito = self.t0
        # relógio: conexão só para o avanço do tempo
        self.rel = cliente.Conexao(porta)
        if self.sinc:
            self.rel.chamar('sinc_inicio')
        # os modelos de dispositivo do simulador do Mariola usam o módulo cliente
        cliente.conexao = self.conn
        cliente.config = self.cfg
        cliente.relogio = self
        self.exe = exe
        self.pasta = pasta
        self.parar = False
        self.avisos = set()
        self._monta_portas()
        self.estado_pino = {}
        self.estat = {} if os.environ.get('PACOCA_ESTAT') else None
        self.n_avanca = 0

    def agora(self):
        return self.t_sim

    def log(self, s):
        print(s, flush=True)

    # ---------------------------------------------------------------- configuração
    def _monta_portas(self):
        pc = self.cfg.get('pacoca', {})
        nomes_vl53 = [s['nome'] for s in self.cfg.get('vl53', [])]
        nomes_tcs = [s['nome'] for s in self.cfg.get('tcs_i2c', [])]
        self.i2c = {}           # (sda, scl) -> [dispositivos] (cada um responde no endereço atual dele)
        self.serial = {}        # (rx, tx) -> dispositivo
        self.us = {}            # (trig, echo) -> índice do sensor em cfg['vl53']
        self.echos = []
        for chave, d in (pc.get('portas') or {}).items():
            num = _porta_num(chave)
            if num not in PORTAS_SENSOR:
                self.log(f'[simulador] robo_pacoca.json: porta "{chave}" não existe (use 1 a 5)')
                continue
            a, b = PORTAS_SENSOR[num]
            lista = d if isinstance(d, list) else [d]
            for item in lista:
                tipo = item.get('tipo')
                if tipo == 'pro1616':
                    self.serial[(a, b)] = Pro1616(self, item)
                elif tipo == 'bmi160':
                    dev = BMI160(self, {**pc.get('bmi160', {}), **item})
                    self.i2c.setdefault((a, b), []).append(dev)
                elif tipo == 'vl53':
                    nome = item.get('sensor')
                    if nome not in nomes_vl53:
                        self.log(f'[simulador] robo_pacoca.json: sensor "{nome}" da porta {num} não está em "vl53"')
                        continue
                    dev = dispositivos.VL53L0X(-(nomes_vl53.index(nome)) - 1)
                    self.i2c.setdefault((a, b), []).append(dev)
                elif tipo == 'tcs34725':
                    nome = item.get('sensor')
                    if nome not in nomes_tcs:
                        self.log(f'[simulador] robo_pacoca.json: sensor "{nome}" da porta {num} não está em "tcs_i2c"')
                        continue
                    dev = dispositivos.TCS34725(-(nomes_tcs.index(nome)) - 1)
                    self.i2c.setdefault((a, b), []).append(dev)
                elif tipo == 'ultrassonico':
                    nome = item.get('sensor')
                    if nome not in nomes_vl53:
                        self.log(f'[simulador] robo_pacoca.json: sensor "{nome}" da porta {num} não está em "vl53"')
                        continue
                    echo, trig = a, b                       # PortaUltrassonico: {echo, trig}
                    self.us[(trig, echo)] = nomes_vl53.index(nome)
                    self.echos.append(echo)
                else:
                    self.log(f'[simulador] robo_pacoca.json: tipo "{tipo}" desconhecido na porta {num}')
        self.entradas = []
        pch = self.cfg.get('para_choque') or {}
        for lado in ('esquerdo', 'direito'):
            if lado in pch:
                self.entradas.append(_pino(pch[lado]['pino']))
        bi = self.cfg.get('botao_inicio')
        if bi:
            self.entradas.append(_pino(bi['pino']))
        for p in pc.get('botoes', []):
            self.entradas.append(_pino(p))
        self.motores = {}
        for nome, (pwm, dir_) in MOTORES.items():
            self.motores[pwm] = nome
            self.motores[dir_] = nome

    # ---------------------------------------------------------------- relógio
    def sincroniza(self, t_ns):
        """Tempo do programa (os dispositivos usam isso); a física só anda em alcanca()."""
        alvo = self.t0 + t_ns / 1e9
        if alvo > self.t_sim:
            self.t_sim = alvo

    def alcanca(self):
        """Leva a física até o tempo do programa."""
        if self.t_sim <= self.t_feito + 1e-12:
            return
        self.n_avanca += 1
        if self.sinc:
            r = self.rel.chamar('avanca', ate=self.t_sim)
            self.t_feito = max(self.t_feito, float(r['t']))
            if r.get('parar'):
                self.parar = True
        else:
            # modo antigo (--tempo-real): espera o relógio do simulador chegar lá
            while True:
                r = self.rel.chamar('relogio')
                if r.get('parar'):
                    self.parar = True
                    return
                if r['t'] >= self.t_sim:
                    self.t_feito = float(r['t'])
                    return
                f = r['f'] or 0.0
                time.sleep(min(0.02, (self.t_sim - r['t']) / f) if f > 0 else 0.01)

    def vigia_parar(self):
        r = self.rel.chamar('relogio')
        if r.get('parar'):
            self.parar = True

    # ---------------------------------------------------------------- operações
    def trata(self, op, t_ns, d):
        self.sincroniza(t_ns)
        if op == OP_SYNC:
            self.alcanca()
            return b''
        if op == OP_OLA:
            pc = self.cfg.get('pacoca', {})
            ent = sorted(set(p for p in self.entradas if p < 32))
            ana = [p for p in ent if p >= 20]
            sai = sorted(self.motores)
            mv = int(pc.get('bateria_mV', 3900))
            return (bytes([len(ent)] + ent) + bytes([len(ana)] + ana) + bytes([len(sai)] + sai)
                    + bytes([len(self.echos)] + self.echos) + struct.pack('<H', mv))
        if op == OP_SERIAL_TX:
            rx, tx = d[0], d[1]
            baud = struct.unpack_from('<I', d, 2)[0]
            t_ini = struct.unpack_from('<q', d, 6)[0]
            b = d[14]
            dev = self.serial.get((rx, tx))
            if dev is None:
                self._aviso(('serial', rx, tx), f'[simulador] nada ligado na serial RX={rx} TX={tx} '
                                                 '(confira as portas no robo_pacoca.json)')
                return struct.pack('<H', 0)
            if baud != dev.BAUD:
                self._aviso(('baud', rx, tx), f'[simulador] a serial RX={rx} TX={tx} está a {baud} bps; '
                                               f'o sensor usa {dev.BAUD}: ele não entende')
                return struct.pack('<H', 0)
            bit = 1.0 / baud
            t_fim = self.t0 + t_ini / 1e9 + 10 * bit       # o sensor tem o byte depois do stop bit
            resp = dev.recebe(b, t_fim)
            out = []
            for (t0, dados) in resp:
                for i, v in enumerate(dados):
                    t = t0 + i * 10 * bit
                    out.append(struct.pack('<qB', int(round((t - self.t0) * 1e9)), v))
            return struct.pack('<H', len(out)) + b''.join(out)
        if op == OP_I2C_ESCREVE:
            sda, scl, addr, n = d[0], d[1], d[2], d[3]
            dev = self._dev_i2c(sda, scl, addr)
            if dev is None:
                return b'\x02'
            dev.escreve(list(d[4:4 + n]))
            return b'\x00'
        if op == OP_I2C_LE:
            sda, scl, addr, n = d[0], d[1], d[2], d[3]
            dev = self._dev_i2c(sda, scl, addr)
            if dev is None:
                return b'\x02\x00'
            v = [int(x) & 0xFF for x in dev.le(n)]
            return bytes([0, len(v)] + v)
        if op == OP_PINO_SAIDA:
            pino, valor = d[0], d[1]
            self.estado_pino[pino] = valor
            nome = self.motores.get(pino)
            if nome:
                self._motor(nome)
            return b''
        if op == OP_PINO_ENTRADA:
            v = self.conn.chamar('gpio_le', pino=d[0])['v']
            return bytes([1 if v else 0])
        if op == OP_ANALOGICO:
            pino = d[0]
            if pino in self.entradas:
                v = self.conn.chamar('gpio_le', pino=pino)['v']
                return struct.pack('<H', 1023 if v else 15)
            return struct.pack('<H', 0)
        if op == OP_ULTRASSOM:
            trig, echo = d[0], d[1]
            idx = self.us.get((trig, echo))
            if idx is None and trig == 0:
                idx = next((i for (tr, ec), i in self.us.items() if ec == echo), None)
            mm = -1
            if idx is not None:
                dist = self.conn.chamar('vl53', idx=idx)['d']
                lim = self._fora_alcance(idx)
                if dist is not None and dist < lim:
                    mm = int(dist)
            return struct.pack('<i', mm)
        if op == OP_LEDS:
            n = d[1]
            cores = [list(d[2 + 3 * i:5 + 3 * i]) for i in range(n)]
            self.conn.chamar('leds', v=cores)
            return b''
        if op in (OP_SERVO, OP_FIM):
            return b''
        return b''

    def _dev_i2c(self, sda, scl, addr):
        # o primeiro que responde nesse endereço (dois com o mesmo endereço = conflito, como no robô)
        for dev in self.i2c.get((sda, scl), ()):
            if dev.addr == addr:
                return dev
        return None

    def _fora_alcance(self, idx):
        sc = self.cfg['vl53'][idx]
        pr = dict(self.cfg.get('vl53_params', {}))
        pr.update(sc.get('params', {}))
        return int(pr.get('fora_alcance', 8190))

    def _motor(self, nome):
        """Ponte H: pino PWM e pino de direção. Frações do tempo em cada estado da ponte."""
        pwm, dir_ = MOTORES[nome]
        a = self.estado_pino.get(pwm, 0) / 255.0
        alto = self.estado_pino.get(dir_, 0) >= 128
        if not alto:
            fr = {'frente': a, 're': 0.0, 'll': 1.0 - a, 'hh': 0.0}
        else:
            fr = {'frente': 0.0, 're': 1.0 - a, 'll': 0.0, 'hh': a}
        self.conn.chamar('motor_dc', porta=nome, **fr)

    def _aviso(self, chave, msg):
        if chave not in self.avisos:
            self.avisos.add(chave)
            self.log(msg)

    # ---------------------------------------------------------------- execução
    def roda(self):
        """Sobe o programa e atende até ele terminar. Devolve o código de saída."""
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.bind(('127.0.0.1', 0))
        srv.listen(2)
        env = dict(os.environ)
        env['PACOCA_PONTE'] = str(srv.getsockname()[1])
        env['PACOCA_EEPROM'] = os.path.join(self.pasta, 'eeprom_pacoca.bin')
        sys.stdout.flush()
        proc = subprocess.Popen([self.exe], cwd=self.pasta, env=env)
        srv.settimeout(15.0)
        socks = {}
        try:
            while len(socks) < 2:
                c, _ = srv.accept()
                c.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                tipo = c.recv(1)
                socks[tipo] = c
        except socket.timeout:
            proc.kill()
            self.log('[simulador] o programa não conectou na ponte')
            return 3
        finally:
            srv.close()
        s = socks.get(b'P')
        vida = socks.get(b'V')
        s.settimeout(0.25)
        buf = bytearray()
        silencio = time.perf_counter()
        try:
            while True:
                if self.parar:
                    break
                try:
                    parte = s.recv(65536)
                except socket.timeout:
                    if proc.poll() is not None:
                        break
                    self.vigia_parar()
                    if self.sinc and time.perf_counter() - silencio > 1.0:
                        # programa calculando sem chamar o Arduino (laço infinito sem espera):
                        # a física segue pelo relógio real, como no simulador do Mariola
                        r = self.rel.chamar('avanca', livre=True)
                        if r.get('parar'):
                            self.parar = True
                    continue
                except OSError:
                    break
                if not parte:
                    break
                silencio = time.perf_counter()
                buf += parte
                while len(buf) >= 4:
                    n = struct.unpack_from('<I', buf, 0)[0]
                    if len(buf) < 4 + n:
                        break
                    msg = bytes(buf[4:4 + n])
                    del buf[:4 + n]
                    op = msg[0]
                    t_ns = struct.unpack_from('<q', msg, 1)[0]
                    try:
                        resp = self.trata(op, t_ns, msg[9:])
                    except RuntimeError as e:
                        if 'LoP' in str(e):          # programa sendo encerrado pelo LoP
                            self.parar = True
                            resp = b''
                        else:
                            raise
                    if self.estat is not None:
                        self.estat[op] = self.estat.get(op, 0) + 1
                    flags = 1 if self.parar else 0
                    s.sendall(struct.pack('<I', len(resp) + 1) + bytes([flags]) + resp)
        finally:
            try:
                vida.sendall(b'P')
            except (OSError, AttributeError):
                pass
            for c in socks.values():
                try:
                    c.close()
                except OSError:
                    pass
            try:
                proc.wait(timeout=1.0)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
        if self.estat is not None:
            self.log(f'[ponte] {self.t_sim - self.t0:.1f} s: operações {self.estat}, avanços {self.n_avanca}')
        return proc.returncode if proc.returncode is not None else 0
