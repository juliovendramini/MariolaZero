# `PinosDigitais` — os 8 pinos como entrada ou saída

Arquivo: `libs/pinosDigitais.py` · `from pinosDigitais import PinosDigitais` ·
`from gpiod.line import Direction`

## Para que serve

Os 8 pinos digitais, cada um como **entrada ou saída** (para botões, veja também
[botões e chaves](botoes.md); a antiga classe `Botoes` foi juntada a esta em 27/10/2026):

* **saída:** ligar um LED de sinalização, um relé (ex.: o motor do lidar), um buzzer, um
  transistor que liga um eletroímã;
* **entrada:** botões, chaves, sensores digitais (fim de curso, sensor indutivo, saída digital de
  outro microcontrolador).

Os pinos aceitam 5 V e têm proteção (veja o módulo 1).

## Constantes

`P1`…`P8` (pinos), `ALTO`/`BAIXO` (níveis), `LIBERADO`/`APERTADO` (botões: o que `le_botao` devolve),
`SAIDA`/`ENTRADA` (direções: o mesmo que `Direction.OUTPUT`/`Direction.INPUT`).

## Métodos

### `PinosDigitais()`
Reserva os 8 pinos, todos como **entrada**.

* Chamar `PinosDigitais()` de novo no mesmo programa devolve **o mesmo objeto** (não reserva os
  pinos duas vezes). Por isso a classe `Lidar` e o seu programa podem usar `PinosDigitais` juntos.
* Se o pino 8 já estiver em uso por outro programa do sistema (ex.: o PWM da ventoinha na imagem
  do @Work), ele fica indisponível: `pinos.PWM` vira `True` e usar o `P8` dá `ValueError`.
* A lib acha sozinha o `gpiochip` dos pinos (no kernel do brick é o `/dev/gpiochip1`).

### `configura_pino(pino, direcao)`
`PinosDigitais.SAIDA` ou `PinosDigitais.ENTRADA` (ou `Direction.OUTPUT`/`Direction.INPUT`).
```python
pinos.configura_pino(PinosDigitais.P5, PinosDigitais.SAIDA)
```

### Entrada
| Método | Faz |
|---|---|
| `le_pino(pino)` | `ALTO` ou `BAIXO` (`ValueError` se o pino não for entrada) |
| `botao_pressionado(pino)` | `True` se está em nível baixo (apertado) |
| `le_botao(pino)` | igual a `le_pino` |

### Saída
| Método | Faz |
|---|---|
| `escreve_pino(pino, valor)` | `ALTO` ou `BAIXO` (`ValueError` se o pino não for saída) |
| `liga_pino(pino)` / `desliga_pino(pino)` | atalhos para `ALTO` / `BAIXO` |
| `inverte_pino(pino)` | troca o estado (pisca-pisca) |

### `get_direcao(pino)`
Devolve a direção atual.

## Receita: botões nos pinos 1–4, LEDs nos 5–8

```python
pinos = PinosDigitais()
for p in (PinosDigitais.P5, PinosDigitais.P6, PinosDigitais.P7, PinosDigitais.P8):
    pinos.configura_pino(p, Direction.OUTPUT)
while True:
    if pinos.botao_pressionado(PinosDigitais.P1):
        pinos.liga_pino(PinosDigitais.P5)
    else:
        pinos.desliga_pino(PinosDigitais.P5)
    time.sleep(0.02)
```

(Exemplo completo: `exemplos/05-pinosDigitais/`.)

* **Cuidado com corrente:** um pino de saída acende um LED (com resistor), mas **não** liga motor,
  eletroímã ou relé grande direto. Use um transistor/módulo de relé.

## No simulador

As linhas GPIO são emuladas (entrada e saída). Um LED de vítima num pino pode ser configurado
na Maze (`"led_vitima": "gpio:P5"`).
