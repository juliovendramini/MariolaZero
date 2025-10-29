# Classe PinosDigitais

Classe para controlar 8 pinos digitais GPIO com configuração flexível de entrada/saída.

## Características

- **8 pinos digitais** (P1 a P8)
- **Entrada ou Saída** configurável para cada pino
- **Compatível** com a classe Botoes (métodos `le_botao` e `botao_pressionado`)
- **Métodos convenientes** para ligar, desligar e inverter pinos

## Pinos Disponíveis

| Constante | GPIO | Descrição |
|-----------|------|-----------|
| P1 | 267 | Pino 1 |
| P2 | 266 | Pino 2 |
| P3 | 265 | Pino 3 |
| P4 | 234 | Pino 4 |
| P5 | 233 | Pino 5 (novo) |
| P6 | 232 | Pino 6 (novo) |
| P7 | 231 | Pino 7 (novo) |
| P8 | 230 | Pino 8 (novo) |

## Valores Lógicos

- `ALTO` / `LIBERADO`: Nível lógico alto (Value.ACTIVE)
- `BAIXO` / `APERTADO`: Nível lógico baixo (Value.INACTIVE)

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

# Verificar se botão está pressionado (compatibilidade com Botoes)
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
    # Erro: Pino 267 não está configurado como SAÍDA
```

## Diferenças da Classe Botoes

| Característica | Botoes | PinosDigitais |
|---------------|--------|---------------|
| Quantidade de pinos | 4 | 8 |
| Direção | Apenas entrada | Entrada **OU** saída |
| Configuração | Fixa | Dinâmica |
| Saída | ❌ Não | ✅ Sim |
| Compatibilidade | Base | Compatível com Botoes |

## Notas Importantes

1. **Configuração Inicial**: Todos os pinos começam como ENTRADA
2. **Reconfiguração**: É possível mudar a direção de um pino a qualquer momento
3. **Liberação de Recursos**: Os pinos são liberados automaticamente quando o objeto é destruído
4. **Thread-Safety**: A classe não é thread-safe, use locks se necessário em ambiente multi-thread

## Ver Também

- `botoes.py` - Classe original para 4 botões
- Exemplos em `exemplos/05-pinosDigitais/`
- Documentação gpiod: https://libgpiod.readthedocs.io/
