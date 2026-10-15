"""dispensadorKits.py — versão do ROBÔ REAL (modelo para a equipe completar).

Interface usada pelo programa (igual no simulador):

    d = DispensadorKits()
    n = d.deposita(2, 'esquerda')   # devolve quantos kits saíram
    d.restantes()

TODO: ajustar para o mecanismo real (servo do Mariola via Motores.move_servo,
PlacaControleServo, etc.). Abaixo um exemplo com dois servos do Mariola.
"""

import time

CAPACIDADE = 8


class DispensadorKits:
    ESQUERDA = 'esquerda'
    DIREITA = 'direita'

    def __init__(self, motores=None, servo_esq=1, servo_dir=2, capacidade=CAPACIDADE):
        self.motores = motores          # objeto Motores já aberto (reaproveite o do robô)
        self.servo = {'esquerda': servo_esq, 'direita': servo_dir}
        self._restantes = capacidade

    def _um_kit(self, lado):
        if self.motores is None:
            raise NotImplementedError('passe o objeto Motores ou implemente o seu mecanismo')
        s = self.servo[lado]
        self.motores.move_servo(s, 150)     # TODO: ângulos reais do mecanismo
        self.motores.atualiza_servos()
        time.sleep(0.35)
        self.motores.move_servo(s, 30)
        self.motores.atualiza_servos()
        time.sleep(0.35)

    def deposita(self, quantidade=1, lado='esquerda'):
        if lado not in ('esquerda', 'direita'):
            raise ValueError("lado deve ser 'esquerda' ou 'direita'")
        n = 0
        for _ in range(int(quantidade)):
            if self._restantes <= 0:
                break
            self._um_kit(lado)
            self._restantes -= 1
            n += 1
        return n

    def restantes(self):
        return self._restantes
