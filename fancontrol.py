#!/usr/bin/env python3
"""
Controle de cooler PWM por temperatura do SoC - BPI-M4-Zero (H618)

Cooler de 4 fios ligado ao PWM1 (PI11), overlay 'pwm1-pi11'.

Le a zona 'cpu-thermal' localizada pelo nome, nao pelo numero, porque a
ordem das zonas muda entre versoes de kernel. No 6.18 as zonas sao:
  zone0 gpu-thermal / zone1 ve-thermal / zone2 cpu-thermal / zone3 ddr-thermal

Opcionalmente eleva os trips de throttling passivo, que por padrao ficam
em 60 e 70 graus.
"""

import time
from pathlib import Path

# --- Configuracao ---------------------------------------------------------

TEMP_MIN = 50.0        # abaixo disso o cooler fica parado
TEMP_MAX = 68.0        # a partir daqui, rotacao maxima (antes do trip)
HISTERESE = 5.0        # so desliga quando cair abaixo de (TEMP_MIN - HISTERESE)

DUTY_MIN = 0.30        # 30% - abaixo disso o cooler pode nem sair do lugar
DUTY_MAX = 1.00

# Elevar os trips de throttling. Use False para manter o padrao de fabrica.
AJUSTAR_TRIPS = True
TRIP_PASSIVE_1 = 70000   # padrao 60000
TRIP_PASSIVE_2 = 80000   # padrao 70000

PERIODO_NS = 40000     # 25 kHz, conforme especificacao de cooler de 4 fios
INTERVALO = 3.0        # segundos entre leituras

PWM_CHIP = Path("/sys/class/pwm/pwmchip0")
PWM_CANAL = PWM_CHIP / "pwm1"
THERMAL = Path("/sys/class/thermal")


# --- Zona termica ---------------------------------------------------------

def achar_zona(nome: str = "cpu-thermal") -> Path:
    """Localiza a zona pelo campo 'type', nao pelo numero."""
    for zona in sorted(THERMAL.glob("thermal_zone*")):
        try:
            if (zona / "type").read_text().strip() == nome:
                return zona
        except OSError:
            continue
    raise RuntimeError(f"zona termica '{nome}' nao encontrada")


def ajustar_trips(zona: Path) -> None:
    """Eleva os trips de throttling passivo. Nao falha se estiver read-only."""
    for indice, valor in ((0, TRIP_PASSIVE_1), (1, TRIP_PASSIVE_2)):
        alvo = zona / f"trip_point_{indice}_temp"
        tipo = zona / f"trip_point_{indice}_type"
        try:
            if tipo.read_text().strip() != "passive":
                continue
            alvo.write_text(str(valor))
        except OSError as erro:
            print(f"aviso: nao foi possivel ajustar {alvo.name}: {erro}")


# --- PWM ------------------------------------------------------------------

def escrever(caminho: Path, valor) -> None:
    caminho.write_text(str(valor))


def preparar_pwm() -> None:
    """Exporta o canal e configura o periodo. Idempotente."""
    if not PWM_CANAL.exists():
        escrever(PWM_CHIP / "export", 1)
        time.sleep(0.2)

    escrever(PWM_CANAL / "duty_cycle", 0)
    escrever(PWM_CANAL / "period", PERIODO_NS)
    escrever(PWM_CANAL / "enable", 1)


def aplicar_duty(fracao: float) -> None:
    ns = int(PERIODO_NS * max(0.0, min(1.0, fracao)))
    escrever(PWM_CANAL / "duty_cycle", ns)


# --- Controle -------------------------------------------------------------

def calcular_duty(temp: float, girando: bool) -> float:
    """Rampa linear entre TEMP_MIN e TEMP_MAX, com histerese na parada."""
    limite_parada = TEMP_MIN - HISTERESE if girando else TEMP_MIN

    if temp < limite_parada:
        return 0.0

    if temp >= TEMP_MAX:
        return DUTY_MAX

    proporcao = (temp - TEMP_MIN) / (TEMP_MAX - TEMP_MIN)
    return DUTY_MIN + proporcao * (DUTY_MAX - DUTY_MIN)


# --- Principal ------------------------------------------------------------

def main() -> None:
    zona = achar_zona("cpu-thermal")
    temp_path = zona / "temp"

    if AJUSTAR_TRIPS:
        ajustar_trips(zona)

    preparar_pwm()
    girando = False
    ultimo_duty = -1.0

    try:
        while True:
            temp = int(temp_path.read_text().strip()) / 1000.0
            duty = calcular_duty(temp, girando)

            # so escreve no sysfs quando a mudanca e relevante
            if abs(duty - ultimo_duty) > 0.01:
                aplicar_duty(duty)
                ultimo_duty = duty
                girando = duty > 0

            time.sleep(INTERVALO)

    except KeyboardInterrupt:
        pass
    finally:
        # ao sair, deixa o cooler no maximo por seguranca
        aplicar_duty(DUTY_MAX)


if __name__ == "__main__":
    main()
