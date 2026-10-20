"""Tutorial 5c — uma thread só para os sensores I2C (VL53L0X + TCS34725).

    python simulador.py --robo robo_4x4.json --programa CAMINHO/05_distancia/thread_sensores.py

Todos os sensores I2C do Mariola ficam no mesmo barramento, atrás do mesmo multiplexador: só UMA
thread pode conversar com eles. Ela lê tudo em sequência e guarda os valores em atributos; o resto
do programa só lê esses atributos e nunca fala com o I2C.
"""
import threading
import time

from portas import Portas
from tcs34725 import TCS34725
from vl53 import VL53L0X


class SensoresI2C:
    """Lê todos os sensores I2C numa thread própria. Use os atributos `dist`, `cor`, `idade()`."""

    def __init__(self):
        self.vl53 = {
            'esquerda': VL53L0X(Portas.I2C1),
            'garra': VL53L0X(Portas.I2C2),
            'direita': VL53L0X(Portas.I2C3),
            'frente': VL53L0X(Portas.I2C5),
        }
        self.tcs = {
            'frente': TCS34725(Portas.I2C6),
            'tras': TCS34725(Portas.I2C7),
        }
        # o que o resto do programa lê
        self.dist = {nome: 8190 for nome in self.vl53}
        self.cor = {nome: (0, 0, 0, 0) for nome in self.tcs}
        self.t_leitura = 0.0       # quando as medidas de `dist` foram pedidas
        self.voltas = 0            # quantas leituras completas a thread já fez
        self.erro = None           # último erro de I2C (a thread não para por causa dele)
        self.rodando = False
        self.thread = None

    def le_tudo(self):
        """Uma volta: dispara os VL53, lê os TCS enquanto eles medem, depois pega os VL53."""
        t = time.time()
        for s in self.vl53.values():                    # 1) pede a medida em todos (~33 ms cada,
            s.solicita_leitura()                        #    mas eles medem ao mesmo tempo)
        cor = {nome: s.le_valores() for nome, s in self.tcs.items()}   # 2) TCS no meio da espera
        dist = {nome: s.leitura_mm() for nome, s in self.vl53.items()}  # 3) resultados (se ainda
        self.dist = dist                                                #    não ficou pronto, espera)
        self.cor = cor             # troca o dicionário inteiro de uma vez: quem lê nunca vê metade
        self.t_leitura = t
        self.voltas += 1

    def idade(self):
        """Há quantos segundos as distâncias atuais foram pedidas."""
        return time.time() - self.t_leitura

    def inicia(self):
        self.rodando = True
        self.thread = threading.Thread(target=self._laco, daemon=True)
        self.thread.start()

    def para(self):
        self.rodando = False
        if self.thread:
            self.thread.join(timeout=1.0)

    def _laco(self):
        while self.rodando:
            try:
                self.le_tudo()
            except (OSError, TimeoutError) as e:
                self.erro = e      # um erro numa thread não aparece sozinho: guarde e olhe no programa
                time.sleep(0.05)
            time.sleep(0.002)      # folga para as outras threads


def compara(sensores, n=5):
    """Mede quanto tempo leva uma volta completa de três jeitos (ainda sem a thread)."""
    vl, tcs = sensores.vl53, sensores.tcs

    def simples():
        for s in vl.values():
            s.read_range_single_millimeters()           # cada uma espera a própria medida
        for s in tcs.values():
            s.le_valores()

    def dividido():
        for s in vl.values():
            s.solicita_leitura()
        for s in vl.values():
            s.leitura_mm()
        for s in tcs.values():
            s.le_valores()                              # TCS depois de tudo

    for nome, funcao in (('uma de cada vez', simples), ('dividido', dividido),
                         ('dividido + TCS no meio', sensores.le_tudo)):
        inicio = time.time()
        for _ in range(n):
            funcao()
        print(f'{nome:>24}: {(time.time() - inicio) / n * 1000:5.1f} ms por volta')


sensores = SensoresI2C()
compara(sensores)

sensores.inicia()
try:
    # o programa principal NÃO chama nenhum método de VL53 ou TCS: só lê os atributos
    inicio = time.time()
    voltas_main = 0
    while time.time() - inicio < 2.0:
        voltas_main += 1                 # aqui ficaria o controle do robô (motores, decisões)
        if voltas_main % 50 == 0:
            d, c = sensores.dist, sensores.cor
            print(f"frente {d['frente']} mm, garra {d['garra']} mm, C do TCS da frente {c['frente'][3]}"
                  f" (leitura de {sensores.idade() * 1000:.0f} ms atrás)")
        time.sleep(0.01)
    dur = time.time() - inicio
    print(f'em {dur:.1f} s: o laço principal deu {voltas_main} voltas, '
          f'a thread leu os sensores {sensores.voltas} vezes ({sensores.voltas / dur:.0f} por segundo)')
    if sensores.erro:
        print('último erro da thread:', sensores.erro)
finally:
    sensores.para()
