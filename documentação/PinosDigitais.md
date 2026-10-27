# Classe PinosDigitais

Classe para controlar 8 pinos digitais GPIO com configuração flexível de entrada/saída.

## Características

- **8 pinos digitais** (P1 a P8)
- **Entrada ou Saída** configurável para cada pino
- **Botões**: `le_botao` e `botao_pressionado` (a antiga classe `Botoes` foi juntada a esta)
- **Métodos convenientes** para ligar, desligar e inverter pinos
- **Instância única**: `PinosDigitais()` chamado de novo devolve o mesmo objeto (não reserva as
  linhas duas vezes; a classe `Lidar` do exemplo 06 usa isso)
- **Pino 8 com PWM**: se a linha do P8 já estiver em uso (ex.: o PWM da ventoinha na imagem do
  @Work), ele fica indisponível (`PWM = True`) e os outros 7 continuam funcionando

## Pinos Disponíveis

Linhas do PIO principal do H618 (`300b000.pinctrl`). A lib acha o `gpiochip` sozinha
(`acha_chip_gpio()`): ele era o `gpiochip0` no kernel 6.6 e é o
`gpiochip1` no 6.18 (Bookworm) e na imagem Noble, onde o `gpiochip0` é o `7022000.pinctrl`
(R_PIO, 32 linhas). Conferido num brick em 27/10/2026 (6.18.42).

| Constante | Linha GPIO | Pino do H618 |
|-----------|------|-----------|
| P1 | 259 | PI3 |
| P2 | 260 | PI4 |
| P3 | 71 | PC7 |
| P4 | 234 | PH10 |
| P5 | 228 | PH4 |
| P6 | 265 | PI9 |
| P7 | 266 | PI10 |
| P8 | 267 | PI11 |

## Valores Lógicos

- `ALTO` / `LIBERADO`: Nível lógico alto (Value.ACTIVE)
- `BAIXO` / `APERTADO`: Nível lógico baixo (Value.INACTIVE)
- `SAIDA` / `ENTRADA`: direções (Direction.OUTPUT / Direction.INPUT)

## Uso Básico

### Importação

```python
from libs.pinosDigitais import PinosDigitais
from gpiod.line import Direction

pinos = PinosDigitais()
```

### Configuração de Direção

Por padrão, todos os pinos são inicializados como **ENTRADA**.

```python
# Configurar como saída
pinos.configura_pino(pinos.P5, Direction.OUTPUT)

# Configurar como entrada (redundante, já é padrão)
pinos.configura_pino(pinos.P1, Direction.INPUT)
```

### Leitura (Entrada)

```python
# Ler valor do pino
valor = pinos.le_pino(pinos.P1)

if valor == pinos.ALTO:
    print("Pino em nível alto")
else:
    print("Pino em nível baixo")

# Verificar se botão está pressionado
if pinos.botao_pressionado(pinos.P1):
    print("Botão P1 pressionado!")
```

### Escrita (Saída)

```python
# Primeiro configurar como saída
pinos.configura_pino(pinos.P5, Direction.OUTPUT)

# Escrever valor específico
pinos.escreve_pino(pinos.P5, pinos.ALTO)   # Liga
pinos.escreve_pino(pinos.P5, pinos.BAIXO)  # Desliga

# Métodos convenientes
pinos.liga_pino(pinos.P5)      # Liga
pinos.desliga_pino(pinos.P5)   # Desliga
pinos.inverte_pino(pinos.P5)   # Inverte estado atual
```

## Exemplos Completos

### Exemplo 1: Botão controla LED

```python
from libs.pinosDigitais import PinosDigitais
from gpiod.line import Direction
import time

pinos = PinosDigitais()

# P1 como entrada (botão)
# P5 como saída (LED)
pinos.configura_pino(pinos.P5, Direction.OUTPUT)

while True:
    if pinos.botao_pressionado(pinos.P1):
        pinos.liga_pino(pinos.P5)
    else:
        pinos.desliga_pino(pinos.P5)
    time.sleep(0.1)
```

### Exemplo 2: LED Piscante

```python
from libs.pinosDigitais import PinosDigitais
from gpiod.line import Direction
import time

pinos = PinosDigitais()
pinos.configura_pino(pinos.P5, Direction.OUTPUT)

while True:
    pinos.inverte_pino(pinos.P5)  # Inverte estado
    time.sleep(0.5)
```

### Exemplo 3: Corrida de LEDs

```python
from libs.pinosDigitais import PinosDigitais
from gpiod.line import Direction
import time

pinos = PinosDigitais()

# Configurar P5-P8 como saída
for pin in [pinos.P5, pinos.P6, pinos.P7, pinos.P8]:
    pinos.configura_pino(pin, Direction.OUTPUT)

leds = [pinos.P5, pinos.P6, pinos.P7, pinos.P8]

while True:
    for led in leds:
        pinos.liga_pino(led)
        time.sleep(0.2)
        pinos.desliga_pino(led)
```

### Exemplo 4: Múltiplos Botões e LEDs

```python
from libs.pinosDigitais import PinosDigitais
from gpiod.line import Direction
import time

pinos = PinosDigitais()

# P1-P4: Entrada (botões)
# P5-P8: Saída (LEDs)
for pin in [pinos.P5, pinos.P6, pinos.P7, pinos.P8]:
    pinos.configura_pino(pin, Direction.OUTPUT)

# Mapear botões para LEDs
mapa = {
    pinos.P1: pinos.P5,
    pinos.P2: pinos.P6,
    pinos.P3: pinos.P7,
    pinos.P4: pinos.P8,
}

while True:
    for botao, led in mapa.items():
        if pinos.botao_pressionado(botao):
            pinos.liga_pino(led)
        else:
            pinos.desliga_pino(led)
    time.sleep(0.05)
```

## Métodos Disponíveis

### Configuração

- `configura_pino(pin, direcao)` - Configura um pino como entrada ou saída
- `get_direcao(pin)` - Retorna a direção atual de um pino

### Leitura (Entrada)

- `le_pino(pin)` - Lê o valor de um pino de entrada
- `le_botao(pin)` - Alias de `le_pino()` para compatibilidade
- `botao_pressionado(pin)` - Verifica se botão está pressionado

### Escrita (Saída)

- `escreve_pino(pin, valor)` - Escreve um valor em um pino de saída
- `liga_pino(pin)` - Liga um pino (nível ALTO)
- `desliga_pino(pin)` - Desliga um pino (nível BAIXO)
- `inverte_pino(pin)` - Inverte o estado de um pino

## Tratamento de Erros

A classe valida automaticamente:

- **Pino inválido**: Levanta `ValueError` se usar pino inexistente
- **Direção incorreta**: Levanta `ValueError` se tentar:
  - Ler um pino configurado como saída
  - Escrever em um pino configurado como entrada

```python
try:
    pinos.escreve_pino(pinos.P1, pinos.ALTO)  # P1 está como entrada!
except ValueError as e:
    print(f"Erro: {e}")
    # Erro: Pino 259 não está configurado como SAÍDA
```

## A antiga classe Botoes

Até 27/10/2026 havia também a classe `Botoes` (`botoes.py`), só de entrada, nos mesmos pinos. As
duas davam "Device or resource busy" juntas, e ela foi juntada a esta: `le_botao`,
`botao_pressionado`, `LIBERADO`/`APERTADO` e `P1`-`P8` são os mesmos. Programa antigo: troque
`from botoes import Botoes` por `from pinosDigitais import PinosDigitais` e `Botoes` por
`PinosDigitais` (veja [`Botoes.md`](Botoes.md)).

## Notas Importantes

1. **Configuração Inicial**: Todos os pinos começam como ENTRADA
2. **Reconfiguração**: É possível mudar a direção de um pino a qualquer momento
3. **Liberação de Recursos**: Os pinos são liberados automaticamente quando o objeto é destruído
4. **Thread-Safety**: A classe não é thread-safe, use locks se necessário em ambiente multi-thread

## Ver Também

- Exemplos em `exemplos/05-pinosDigitais/` (e `04-vl53l0x/`, que lê os botões)
- Documentação gpiod: https://libgpiod.readthedocs.io/
