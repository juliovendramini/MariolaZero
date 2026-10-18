# Módulo 4 — Motores e encoders

**Objetivo:** controlar as rodas por velocidade e por potência, medir quanto o robô andou com o
encoder, andar distâncias exatas e montar a tração 4x4 com as placas de motor.

Referência: [`Motores`](referencia/motores.md), [`PlacaControleMotor`](referencia/placaControleMotor.md).
Códigos: [`codigos/02_motores/`](codigos/02_motores/).

## 4.1 Velocidade ou potência?

| | `velocidade_motores(v1, v2)` | `potencia_motores(p1, p2)` |
|---|---|---|
| O que manda | a **velocidade** que você quer | a **força** (PWM) |
| Quem garante | o PID da placa ajusta a força sozinho | ninguém |
| Na subida | mantém a velocidade | fica mais lento |
| Use para | quase tudo: seguir linha, andar, girar | empurrar, testar motor, motor sem encoder |

Escala da velocidade: **100 = velocidade de calibração** (gravada na placa; ~80% da rotação livre
do motor). Velocidades negativas = para trás.

## 4.2 Uma função `anda()` para o programa inteiro

Em vez de espalhar `motores.velocidade_motores(...)` pelo código, crie uma função. Se a tração
mudar (4x4, esteira), você muda **um lugar só**.

```python
motores = Motores(False)                       # eu decido quando enviar
motores.direcao_motor(2, Motores.INVERTIDO)

def anda(ve, vd):
    """Velocidade dos lados esquerdo e direito, -100 a 100."""
    ve = int(max(-100, min(100, ve)))
    vd = int(max(-100, min(100, vd)))
    motores.velocidade_motores(ve, vd)
    motores.atualiza_motores()                 # envia E lê os encoders: 1 pacote só
```

Com `Motores(False)`, mudar os dois motores e enviar **um** pacote é mais rápido e os dois mudam
juntos. E o `atualiza_motores()` já traz a contagem dos encoders de graça.

Como o robô se move com `anda(ve, vd)`:

| `anda(40, 40)` | `anda(20, 60)` | `anda(-30, 30)` | `anda(0, 40)` |
|---|---|---|---|
| reto | curva para a esquerda | gira no lugar para a esquerda | gira em volta da roda esquerda |

## 4.3 Encoder: quanto o robô andou

O encoder conta pulsos enquanto a roda gira. Para converter em milímetros você precisa de três
números **do seu robô**:

```python
import math
DIAMETRO = 70.0                      # mm (meça a roda com paquímetro)
CONTAGENS_POR_VOLTA = 17 * 34 * 2    # pulsos do encoder × redução × 2 (o Mariola conta 2 bordas)
MM_POR_CONTAGEM = math.pi * DIAMETRO / CONTAGENS_POR_VOLTA
```

> **Como medir `CONTAGENS_POR_VOLTA` de verdade:** marque a roda, zere o encoder, gire **uma volta**
> com a mão e leia `angulo_motor(1)` (depois de um `estado()`). Faça 3 vezes e tire a média.

Lendo a distância:
```python
motores.estado()                     # pede a contagem atual
mm = (motores.angulo_motor(1) + motores.angulo_motor(2)) / 2 * MM_POR_CONTAGEM
```

* `angulo_motor` devolve o valor do **último pacote**: chame `estado()` ou `atualiza_motores()`
  antes.
* A média dos dois lados é a distância do centro do robô. A **diferença** dá quanto ele girou
  (mas o giroscópio é melhor para isso: as rodas patinam no giro).

## 4.4 Tutorial: andar uma distância exata

[`codigos/02_motores/anda_mm.py`](codigos/02_motores/anda_mm.py)

```python
def anda_mm(distancia, vel_max=50):
    motores.estado()                 # pega a contagem atual antes de zerar
    motores.reseta_angulo_motor(1)
    motores.reseta_angulo_motor(2)
    sentido = 1 if distancia > 0 else -1
    while True:
        falta = abs(distancia) - abs(andado_mm())
        if falta <= 2:
            break
        # perto do fim vai mais devagar (controle proporcional simples)
        vel = max(15, min(vel_max, falta * 0.5))
        motores.velocidade_motores(sentido * vel, sentido * vel)
        motores.atualiza_motores()   # envia E lê os encoders
        time.sleep(0.01)
    motores.velocidade_motores(0, 0)
    motores.atualiza_motores()
```

Repare no `vel = max(15, min(vel_max, falta * 0.5))`: é um **controle proporcional**. Longe do
alvo, velocidade máxima; perto, diminui; mas nunca abaixo de 15 (senão o robô para antes de
chegar). Resultado no simulador: `pedi 300 mm, andou 301 mm`.

Rode:
```bash
python simulador.py --robo robo_esteira.json --programa ../curso/codigos/02_motores/anda_mm.py
```

## 4.5 Tutorial: girar a roda um número certo de contagens

[`codigos/02_motores/move_motor_angulo.py`](codigos/02_motores/move_motor_angulo.py)

A placa sabe parar sozinha numa contagem: `move_motores(v1, contagens1, v2, contagens2)`.

```python
motores.move_motores(40, 1156, 40, 1156)        # 1 volta da roda
while True:
    motores.estado()                            # só LÊ, não reenvia a velocidade
    if (motores.estado_motor(1) == Motores.PARADO and
            motores.estado_motor(2) == Motores.PARADO):
        break
    time.sleep(0.02)
motores.velocidade_motores(0, 0)                # IMPORTANTE (veja abaixo)
```

> **A armadilha:** quando chega no alvo, o motor para, mas a placa **guarda a velocidade 40**. O
> próximo pacote de motor (qualquer `velocidade_motor`, `atualiza_motores`...) faz o motor voltar a
> girar **sem parar**. Por isso: acompanhe com `estado()` (que não reenvia) e zere a velocidade
> logo depois de chegar.

Também é normal passar um pouco do alvo (no simulador: 1178 em vez de 1156), pela inércia.

**Quando usar `move_motores` e quando usar o laço do 4.4?** `move_motores` é cômodo para
movimentos simples. O laço dá mais controle: corrigir a direção pelo giroscópio enquanto anda,
parar se aparecer uma parede, desacelerar. Os programas de competição quase sempre usam o laço.

## 4.6 Tutorial: tração 4x4 com placas de motor

[`codigos/02_motores/tracao_4x4.py`](codigos/02_motores/tracao_4x4.py)

O robô 4x4 do curso tem as rodas traseiras no Mariola e as dianteiras em **duas placas de
controle de motor** no barramento da SERIAL1:

```python
barramento = Portas().abre_porta_serial(Portas.SERIAL1, 250000, timeout=0.005)
frente_esq = PlacaControleMotor(barramento, 8)     # ID gravado na placa
frente_dir = PlacaControleMotor(barramento, 51)
frente_esq.reset()
frente_dir.reset()
frente_dir.direcao_motor(PlacaControleMotor.INVERTIDO)

def anda(ve, vd):
    motores.velocidade_motores(ve, vd)
    motores.atualiza_motores()
    frente_esq.velocidade_motor(ve)
    frente_dir.velocidade_motor(vd)
```

O resto do programa não muda: ele só chama `anda()`.

Duas diferenças das placas que você precisa saber:

* **Encoder ×4:** a placa conta em quadratura. A mesma roda dá **o dobro de contagens** do
  Mariola (no simulador: 1211 no Mariola × 2420 na placa). Use os encoders do Mariola para medir
  distância, ou converta.
* **Timeout:** 5 s sem pacote, o motor para; **10 s, a placa reinicia** e a contagem volta a zero.

Se você não sabe os IDs das suas placas: `PlacaControleMotor.buscar_motores(Portas.SERIAL1)`.

## 4.7 Freio, PID e calibração

* **Freio:** `motores.set_modo_freio(Motores.HOLD)` faz o motor **segurar** quando a velocidade é 0
  (bom para não escorregar na rampa). Nas placas: `set_freio(PlacaControleMotor.FREIO_TRAVADO)`.
* **PID:** `motores.pid_motor(kp, ki, kd)` grava novas constantes na placa. Só mexa se o motor
  oscilar ou demorar a atingir a velocidade.
* **Calibração:** se o robô anda torto com `anda(40, 40)` mesmo sem patinar, os motores podem estar
  com calibrações diferentes. `obtem_calibracao_motores()` mostra; `calibra_motores()` mede de
  novo (robô **suspenso**, ~26 s).

## 4.8 LEDs e servos comuns

```python
motores.set_led_rgb_all(255, 0, 0)        # todos vermelhos
motores.set_led_rgb_one(3, 0, 0, 255)     # LED 3 azul
motores.move_servo(1, 90)                 # servo comum no conector SERVOS 1
motores.atualiza_servos()                 # (com Motores(False))
```

## Exercícios

1. Meça `CONTAGENS_POR_VOLTA` e o diâmetro da roda do seu robô. Faça `anda_mm(500)` e meça com a
   trena. Qual o erro? Ele muda com a velocidade?
2. Faça o robô andar um quadrado de 30 cm usando só o encoder para girar (90° = quanto de diferença
   entre as rodas?). Compare com o resultado do módulo 5 (giroscópio).
3. No 4x4, crie a função `encoder_mm()` que usa a média das 4 rodas (converta a contagem das
   placas).
4. Faça o robô subir a rampa do mapa `completo.json` com `potencia_motores(40, 40)` e depois com
   `velocidade_motores(40, 40)`. Compare o tempo de subida.
