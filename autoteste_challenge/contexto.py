"""O que os testes dividem: a interface, o relatório, o perfil do robô e o hardware já aberto
(o brick e a porta do barramento são abertos uma vez só e fechados no fim)."""

import time

from portas import Portas

# canal do mux TCA9548A -> nome da porta no Mariola (as constantes I2Cn da Portas)
NOME_CANAL = {getattr(Portas, f'I2C{n}'): f'I2C{n}' for n in range(1, 9)}
# porta USB do hub interno (lugar no /dev/serial/by-path) -> porta do Mariola
USB_PARA_PORTA = {'1.1': '_SERIAL0', '1.4': 'SERIAL1', '1.3': 'SERIAL2', '1.2': 'SERIAL3'}
PORTAS_USB = ('_SERIAL0', 'SERIAL1', 'SERIAL2', 'SERIAL3')
PORTAS_SERIAIS = ('SERIAL1', 'SERIAL2', 'SERIAL3', 'SERIAL4', 'SERIAL5', 'SERIAL6')


def porta(nome):
    """'SERIAL2' ou 'I2C5' -> a constante da Portas."""
    return getattr(Portas, nome)


class Contexto:
    def __init__(self, ui, rel, perfil, automatico=False, motores=False, raiz='.'):
        self.ui = ui
        self.rel = rel
        self.perfil = perfil
        self.automatico = automatico
        self.pode_motores_automatico = motores
        self.raiz = raiz
        self.rodas_no_ar = False
        self._brick = None
        self._erro_brick = None
        self._barramento = {}
        self.placas_abertas = []     # PlacaControleMotor usadas (para parar no fim)
        self.servos_abertos = []

    # ------------------------------------------------------------------ hardware compartilhado
    def brick(self):
        """O Motores(True) do brick, ou None se ele não respondeu (o motivo fica em erro_brick)."""
        if self._brick is None and self._erro_brick is None:
            try:
                from motores import Motores
                self._brick = Motores(True)
            except Exception as erro:
                self._erro_brick = str(erro) or type(erro).__name__
        return self._brick

    @property
    def erro_brick(self):
        return self._erro_brick

    def barramento(self, nome_porta):
        """Porta serial do barramento das placas de motor (aberta uma vez)."""
        if nome_porta not in self._barramento:
            ser = None
            try:
                ser = Portas().abre_porta_serial(porta(nome_porta), 250000, timeout=0.01)
            except Exception as erro:
                print(f'[barramento] {nome_porta}: {erro}')
            self._barramento[nome_porta] = ser
        return self._barramento[nome_porta]

    # ------------------------------------------------------------------ segurança
    def pode_mover(self, o_que='os motores'):
        """Pergunta (uma vez por execução) se as rodas estão no ar antes de girar motores."""
        if self.automatico:
            return self.pode_motores_automatico
        if self.rodas_no_ar:
            return True
        r = self.ui.pergunta('ATENCAO', f'Rodas no ar? Vou girar {o_que}.')
        if r:
            self.rodas_no_ar = True
        return bool(r)

    def para_tudo(self):
        """Para motores e servos (chamado no fim e quando um teste dá erro)."""
        b = self._brick
        if b is not None:
            try:
                b.para_motores()
                b.atualiza_motores()
            except Exception:
                pass
        for placa in self.placas_abertas:
            try:
                placa.envia_comando(placa.MODO_PID, 0, tentativas=1)
            except Exception:
                pass

    def fecha(self):
        self.para_tudo()
        b = self._brick
        if b is not None:
            try:
                b.set_led_rgb_all(0, 0, 0)
            except Exception:
                pass
            try:
                if b.buzzer_ativo:
                    b.para_buzzer()
            except Exception:
                pass

    # ------------------------------------------------------------------ utilidades
    @staticmethod
    def espera(segundos, ui=None):
        """sleep que pode ser interrompido pelo VOLTAR. Devolve True se interrompeu."""
        fim = time.monotonic() + segundos
        while time.monotonic() < fim:
            if ui is not None and ui.cancelou():
                return True
            time.sleep(0.02)
        return False
