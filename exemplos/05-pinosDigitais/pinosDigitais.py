import glob

import gpiod
from gpiod.line import Direction, Value
# 2026-08-15 - Pino 8 é detectado automaticamente: se a linha já estiver em uso (ex.: driver pwm da ventoinha), o pino 8 fica indisponível para uso digital.
# 2026-10-27 - O gpiochip é escolhido sozinho (acha_chip_gpio): os 8 pinos ficam no PIO principal do
#              H618 (300b000.pinctrl), que era o gpiochip0 no kernel 6.6 e é o gpiochip1 no 6.18
#              (Bookworm) e na imagem Noble. Esta versão (a do exemplo 06-lidar) passou a ser a de libs/.
# 2026-10-27 - A classe Botoes (botoes.py) foi juntada a esta: as duas queriam os mesmos 8 pinos e davam
#              "Device or resource busy" quando usadas juntas. Programa antigo: troque
#              "from botoes import Botoes" por "from pinosDigitais import PinosDigitais" e Botoes por
#              PinosDigitais (P1-P8, LIBERADO/APERTADO, le_botao e botao_pressionado são os mesmos).

ROTULO_PIO_PRINCIPAL = '300b000.pinctrl'  # o outro chip, 7022000.pinctrl (R_PIO), só tem 32 linhas


def acha_chip_gpio():
    """Caminho do gpiochip onde estão os pinos P1-P8 (o PIO principal do H618)."""
    candidatos = sorted(glob.glob('/dev/gpiochip*')) or ['/dev/gpiochip0', '/dev/gpiochip1']
    maior = None
    for caminho in candidatos:
        try:
            with gpiod.Chip(caminho) as chip:
                info = chip.get_info()
        except Exception:
            continue
        if ROTULO_PIO_PRINCIPAL in info.label:
            return caminho
        if maior is None or info.num_lines > maior[1]:
            maior = (caminho, info.num_lines)
    if maior is not None and maior[1] > PinosDigitais.P1:   # sem o rótulo: o chip que tem a linha 259
        return maior[0]
    raise RuntimeError('Não achei o gpiochip dos pinos digitais (' + ROTULO_PIO_PRINCIPAL + ')')

class PinosDigitais:
    """
    Classe para controlar os 8 pinos digitais (GPIO) com configuração de entrada/saída.
    Também é a classe dos botões (botão de início, para-choque): começa com os 8 pinos como entrada
    e tem le_botao() e botao_pressionado() (era a antiga classe Botoes).
    - Suporte a entrada E saída
    - Configuração individual de direção para cada pino
    """
    
    P1 = 259
    P2 = 260
    P3 = 71
    P4 = 234
    P5 = 228
    P6 = 265
    P7 = 266
    P8 = 267

    # Valores lógicos
    ALTO = Value.ACTIVE
    BAIXO = Value.INACTIVE
    
    # Botões (pull-up): solto = nível alto, apertado (ligado ao GND) = nível baixo
    LIBERADO = Value.ACTIVE
    APERTADO = Value.INACTIVE

    SAIDA = Direction.OUTPUT
    ENTRADA = Direction.INPUT
    
    # Objetos de controle dos pinos
    PINO1 = None
    PINO2 = None
    PINO3 = None
    PINO4 = None
    PINO5 = None
    PINO6 = None
    PINO7 = None
    PINO8 = None
    PWM = False  # Indica se o pino 8 será usado para PWM
    chip = None
    
    # Dicionário para mapear direções dos pinos
    _direcoes = {}

    # Instância única (padrão singleton) — todas as chamadas a PinosDigitais(...)
    # retornam o mesmo objeto, evitando requisitar as mesmas linhas gpiod duas vezes.
    _instancia = None

    def __new__(cls, *args, **kwargs):
        if cls._instancia is None:
            cls._instancia = super().__new__(cls)
            cls._instancia._inicializado = False
        return cls._instancia

    def __init__(self):
        """
        Inicializa todos os 8 pinos como ENTRADA por padrão.
        Use configura_pino() para mudar para saída.
        """
        if self._inicializado:  # já inicializado (singleton) — ignora novas chamadas
            return
        self._inicializado = True
        chip_name = acha_chip_gpio()
        self.chip_name = chip_name
        self.chip = gpiod.Chip(chip_name)
        
        # Inicializar todos os pinos como entrada
        self.PINO1 = gpiod.request_lines(
            chip_name,
            config={
                self.P1: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self._direcoes[self.P1] = Direction.INPUT
        
        self.PINO2 = gpiod.request_lines(
            chip_name,
            config={
                self.P2: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self._direcoes[self.P2] = Direction.INPUT
        
        self.PINO3 = gpiod.request_lines(
            chip_name,
            config={
                self.P3: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self._direcoes[self.P3] = Direction.INPUT
        
        self.PINO4 = gpiod.request_lines(
            chip_name,
            config={
                self.P4: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self._direcoes[self.P4] = Direction.INPUT
        
        self.PINO5 = gpiod.request_lines(
            chip_name,
            config={
                self.P5: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self._direcoes[self.P5] = Direction.INPUT
        
        self.PINO6 = gpiod.request_lines(
            chip_name,
            config={
                self.P6: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self._direcoes[self.P6] = Direction.INPUT
        
        self.PINO7 = gpiod.request_lines(
            chip_name,
            config={
                self.P7: gpiod.LineSettings(
                    direction=Direction.INPUT,
                ),
            },
        )
        self._direcoes[self.P7] = Direction.INPUT

        try:  # tenta alocar o pino 8; se já estiver em uso (ex.: pwm da ventoinha), fica indisponível
            self.PINO8 = gpiod.request_lines(
                chip_name,
                config={
                    self.P8: gpiod.LineSettings(
                        direction=Direction.INPUT,
                    ),
                },
            )
            self._direcoes[self.P8] = Direction.INPUT
            self.PWM = False
        except Exception:
            self.PINO8 = None
            self.PWM = True

    def _get_pino_obj(self, pin):
        """Retorna o objeto do pino correspondente."""
        pinos_map = {
            self.P1: self.PINO1,
            self.P2: self.PINO2,
            self.P3: self.PINO3,
            self.P4: self.PINO4,
            self.P5: self.PINO5,
            self.P6: self.PINO6,
            self.P7: self.PINO7,
        }
        if not self.PWM:
            pinos_map[self.P8] = self.PINO8
        return pinos_map.get(pin)

    def _validar_pino(self, pin):
        """Valida se o pino é válido."""
        pinos_validos = {self.P1, self.P2, self.P3, self.P4, self.P5, self.P6, self.P7, self.P8}
        if self.PWM:
            pinos_validos.remove(self.P8)  # Remove P8 se estiver em modo PWM
        if pin not in pinos_validos:
            raise ValueError(f'Pino inválido: {pin}. Use P1-P8.')

    def configura_pino(self, pin, direcao):
        """
        Configura um pino como entrada ou saída.
        
        Args:
            pin: Número do pino (P1, P2, ... P8)
            direcao: Direction.INPUT ou Direction.OUTPUT
            
        Exemplo:
            pinos.configura_pino(pinos.P5, Direction.OUTPUT)
        """
        self._validar_pino(pin)

        chip_name = self.chip_name

        # Liberar o pino atual
        pino_obj = self._get_pino_obj(pin)
        if pino_obj:
            pino_obj.release()
        
        # Reconfigurar com nova direção
        novo_pino = gpiod.request_lines(
            chip_name,
            config={
                pin: gpiod.LineSettings(
                    direction=direcao,
                ),
            },
        )
        
        # Atualizar referência
        if pin == self.P1:
            self.PINO1 = novo_pino
        elif pin == self.P2:
            self.PINO2 = novo_pino
        elif pin == self.P3:
            self.PINO3 = novo_pino
        elif pin == self.P4:
            self.PINO4 = novo_pino
        elif pin == self.P5:
            self.PINO5 = novo_pino
        elif pin == self.P6:
            self.PINO6 = novo_pino
        elif pin == self.P7:
            self.PINO7 = novo_pino
        elif pin == self.P8 and not self.PWM:
            self.PINO8 = novo_pino
        
        self._direcoes[pin] = direcao

    def le_pino(self, pin):
        """
        Lê o valor de um pino configurado como ENTRADA.
        
        Args:
            pin: Número do pino (P1-P8)
            
        Returns:
            Value.ACTIVE (ALTO) ou Value.INACTIVE (BAIXO)
            
        Exemplo:
            valor = pinos.le_pino(pinos.P1)
            if valor == pinos.ALTO:
                print("Pino em nível alto")
        """
        self._validar_pino(pin)
        
        if self._direcoes.get(pin) != Direction.INPUT:
            raise ValueError(f'Pino {pin} não está configurado como ENTRADA')
        
        pino_obj = self._get_pino_obj(pin)
        return pino_obj.get_value(pin)

    def escreve_pino(self, pin, valor):
        """
        Escreve um valor em um pino configurado como SAÍDA.
        
        Args:
            pin: Número do pino (P1-P8)
            valor: Value.ACTIVE (ALTO) ou Value.INACTIVE (BAIXO)
            
        Exemplo:
            pinos.escreve_pino(pinos.P5, pinos.ALTO)  # Liga o pino
            pinos.escreve_pino(pinos.P5, pinos.BAIXO) # Desliga o pino
        """
        self._validar_pino(pin)
        
        if self._direcoes.get(pin) != Direction.OUTPUT:
            raise ValueError(f'Pino {pin} não está configurado como SAÍDA')
        
        pino_obj = self._get_pino_obj(pin)
        pino_obj.set_value(pin, valor)

    def liga_pino(self, pin):
        """
        Liga um pino (coloca em nível ALTO).
        Atalho para escreve_pino(pin, ALTO).
        """
        self.escreve_pino(pin, self.ALTO)

    def desliga_pino(self, pin):
        """
        Desliga um pino (coloca em nível BAIXO).
        Atalho para escreve_pino(pin, BAIXO).
        """
        self.escreve_pino(pin, self.BAIXO)

    def inverte_pino(self, pin):
        """
        Inverte o estado de um pino de saída.
        Se estava ALTO, fica BAIXO. Se estava BAIXO, fica ALTO.
        """
        self._validar_pino(pin)
        
        if self._direcoes.get(pin) != Direction.OUTPUT:
            raise ValueError(f'Pino {pin} não está configurado como SAÍDA')
        
        pino_obj = self._get_pino_obj(pin)
        valor_atual = pino_obj.get_value(pin)
        novo_valor = self.BAIXO if valor_atual == self.ALTO else self.ALTO
        pino_obj.set_value(pin, novo_valor)

    # ========== Botões (os métodos da antiga classe Botoes) ==========

    def le_botao(self, pin):
        """
        Lê um pino como se fosse um botão: APERTADO ou LIBERADO.
        """
        return self.le_pino(pin)

    def botao_pressionado(self, pin):
        """
        True se o botão (pino de entrada) está pressionado (nível baixo).
        """
        return self.le_pino(pin) == self.APERTADO

    def get_direcao(self, pin):
        """
        Retorna a direção atual de um pino.
        
        Returns:
            Direction.INPUT ou Direction.OUTPUT
        """
        self._validar_pino(pin)
        return self._direcoes.get(pin)

    def __del__(self):
        """Libera os recursos ao destruir o objeto."""
        pinos = [self.PINO1, self.PINO2, self.PINO3, self.PINO4,
                 self.PINO5, self.PINO6, self.PINO7, self.PINO8]
        for pino in pinos:
            if pino:
                try:
                    pino.release()
                except:
                    pass

