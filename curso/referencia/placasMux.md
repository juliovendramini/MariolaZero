# `PlacaMuxVl53l0x` e `PlacaMuxTCS34725` — placas multiplexadoras na serial

Arquivos: `libs/placaMuxVl53l0x.py`, `libs/placaMuxTCS34725.py`

## Para que servem

São placas com um microcontrolador que lê **até 4 sensores** sozinhas e mandam tudo junto por uma
**porta serial** (115200 baud). Vantagem: os sensores não ocupam os conectores I2C do Mariola e a
leitura não pesa no Banana Pi. Desvantagem: você depende do firmware da placa (modos fixos).

Hoje o jeito mais comum no Mariola é ligar cada sensor direto num conector I2C (`VL53L0X`,
`TCS34725`). Use as placas mux quando faltar conector I2C ou quando já tiver as placas.

Nas duas, uma **thread** pede os dados periodicamente e os métodos de leitura devolvem o último
valor.

---

## `PlacaMuxVl53l0x(porta_serial)`

`from placaMuxVl53l0x import PlacaMuxVl53l0x`

Placa com 4 entradas de VL53L0X (e 4 botões). Atualiza a cada ~100 ms.

| Método | Devolve |
|---|---|
| `le_distancia(porta)` | distância em mm do sensor 0 a 3 |
| `botao_apertado(porta)` | `True`/`False` do botão 0 a 3 da placa |
| `atualiza()` | faz uma leitura (a thread já faz) |

```python
mux = PlacaMuxVl53l0x(Portas.SERIAL2)
print(mux.le_distancia(0), mux.le_distancia(1))
```

`ValueError` para porta fora de 0–3.

---

## `PlacaMuxTCS34725(porta_serial)`

`from placaMuxTCS34725 import PlacaMuxTCS34725`

> A lib importa `from libs.portas import Portas`. Se der `ModuleNotFoundError: libs`, troque a
> linha para `from portas import Portas` na cópia do seu projeto.

Placa com 4 entradas de TCS34725. Atualiza a cada ~25 ms.

| Constante | Modo |
|---|---|
| `RGB_4X` (0) | ganho 4x, LED aceso (padrão) |
| `RGB_16X` (1) | ganho 16x (alvo escuro ou longe), LED aceso |
| `RGB_4X_LED_OFF` (2) / `RGB_16X_LED_OFF` (3) | LED apagado (medir a luz ambiente) |

| Método | Devolve |
|---|---|
| `set_modo(modo)` | escolhe o modo (`ValueError` fora de 0–3) |
| `le_sensor(porta)` | `(r, g, b, c)` do sensor 0 a 3 |
| `atualiza()` | faz uma leitura |

```python
cores = PlacaMuxTCS34725(Portas.SERIAL3)
r, g, b, c = cores.le_sensor(0)
```

## No simulador

Só o `PlacaMuxVl53l0x` é emulado (opcional no `robo*.json`). O `PlacaMuxTCS34725` não.
