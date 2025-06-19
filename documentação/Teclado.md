# Teclado

A classe `Teclado` oferece uma interface para leitura de botões e controle de LEDs utilizando para o MariolaZero.

---

## Exemplo de uso

```python
from teclado import Teclado

# Inicializa o teclado no barramento I2C 1 e endereço 0x38
teclado = Teclado()

# Lê o estado do botão 1
estado = teclado.leBotao(1)
print("Botão 1 está", "pressionado" if estado == teclado.APERTADO else "liberado")

# Verifica se o botão 2 está pressionado
if teclado.botaoPressionado(2):
    print("Botão 2 pressionado!")

# Liga o LED 1
teclado.alteraLed(1, 1)

# Desliga o LED 2
teclado.alteraLed(2, 0)

# Inicia monitoramento para encerrar o programa ao pressionar o botão ENTER (botão 3)
teclado.botaoParaEncerrarPrograma(teclado.ENTER)
```

---

## Métodos

### `__init__(self, i2c_bus=1, i2c_address=0x38)`
Inicializa o teclado no barramento e endereço I2C especificados.

- **i2c_bus**: número do barramento I2C (padrão: 1)
- **i2c_address**: endereço do PCF8574A (padrão: 0x38)

### `leBotao(self, botao)`
Lê o estado de um botão (1 a 4).

- **botao**: número do botão (1 a 4)
- **Retorno**: 0 se pressionado, 1 se liberado

### `botaoPressionado(self, botao)`
Verifica se um botão está pressionado.

- **botao**: número do botão (1 a 4)
- **Retorno**: `True` se pressionado, `False` caso contrário

### `alteraLed(self, led, valor)`
Controla o estado de um LED (1 a 4).

- **led**: número do LED (1 a 4)
- **valor**: 0 para desligar, 1 para ligar

### `botaoParaEncerrarPrograma(self, botao=3)`
Inicia uma thread que monitora o botão especificado e encerra o programa ao pressioná-lo. É possível então escolher qual botão vai finalizar a aplicação que está rodando

- **botao**: número do botão (1 a 4, padrão: 3 - ENTER)

---

## Constantes

- `LIBERADO`: 1 (botão não pressionado)
- `APERTADO`: 0 (botão pressionado)
- `ENTER`: 3
- `ESC`: 4
- `CIMA`: 2
- `BAIXO`: 1

---

## Detalhes

- O método `botaoParaEncerrarPrograma` executa uma thread que envia um sinal SIGINT ao processo ao detectar o botão pressionado, encerrando o programa de forma segura.
- Utiliza a biblioteca [smbus2](https://pypi.org/project/smbus2/) para comunicação I2C.

---

## Requisitos

- [smbus2](https://pypi.org/project/smbus2/)

---