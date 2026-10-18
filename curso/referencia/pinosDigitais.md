# `PinosDigitais` — os 8 pinos como entrada ou saída

Arquivo: `libs/pinosDigitais.py` · `from pinosDigitais import PinosDigitais` ·
`from gpiod.line import Direction`

## Para que serve

A mesma coisa que [`Botoes`](botoes.md), mas cada pino pode ser **entrada ou saída**:

* **saída:** ligar um LED de sinalização, um relé (ex.: o motor do lidar), um buzzer, um
  transistor que liga um eletroímã;
* **entrada:** botões, chaves, sensores digitais (fim de curso, sensor indutivo, saída digital de
  outro microcontrolador).

Os pinos aceitam 5 V e têm proteção (veja o módulo 1).

## Constantes

`P1`…`P8` (pinos), `ALTO`/`BAIXO` (níveis), `LIBERADO`/`APERTADO` (compatíveis com `Botoes`).

## Métodos

### `PinosDigitais()`
Reserva os 8 pinos, todos como **entrada**. Não use junto com `Botoes()` (os dois querem os mesmos
pinos).

### `configura_pino(pino, direcao)`
`Direction.OUTPUT` ou `Direction.INPUT`.
```python
pinos.configura_pino(PinosDigitais.P5, Direction.OUTPUT)
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
