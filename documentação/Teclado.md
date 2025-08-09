# Teclado

A classe `Teclado` oferece uma interface para leitura de botões e controle de LEDs utilizando o expansor de I/O PCF8574A via barramento I2C. Ideal para projetos embarcados, permite monitorar botões, acionar LEDs e até encerrar o programa pressionando um botão específico.

---

## Exemplo de uso

```python
from libs.teclado import Teclado

# Inicializa o teclado no barramento I2C 1 e endereço 0x38
teclado = Teclado()

# Lê o estado do botão 1
estado = teclado.le_botao(1)
print("Botão 1 está", "pressionado" if estado == teclado.APERTADO else "liberado")

# Verifica se o botão 2 está pressionado
if teclado.botao_pressionado(2):
    print("Botão 2 pressionado!")

# Liga o LED 1
teclado.altera_led(1, 1)

# Desliga o LED 2
teclado.altera_led(2, 0)

# Inicia monitoramento para encerrar o programa ao pressionar o botão ENTER (botão 3)
teclado.botao_para_encerrar_programa(teclado.ENTER)
```

---

## Métodos

### `__init__(self, i2c_bus=1, i2c_address=0x38)`
Inicializa o PCF8574A no barramento e endereço I2C especificados.

- **i2c_bus**: número do barramento I2C (padrão: 1)
- **i2c_address**: endereço do PCF8574A (padrão: 0x38)

### `le_botao(self, botao)`
Lê o estado de um botão (1 a 4).

- **botao**: número do botão (1 a 4)
- **Retorno**: 0 se pressionado, 1 se liberado

### `botao_pressionado(self, botao)`
Verifica se um botão está pressionado.

- **botao**: número do botão (1 a 4)
- **Retorno**: `True` se pressionado, `False` caso contrário

### `altera_led(self, led, valor)`
Controla o estado de um LED (1 a 4).

- **led**: número do LED (1 a 4)
- **valor**: 0 para desligar, 1 para ligar

### `botao_para_encerrar_programa(self, botao=3)`
Inicia uma thread que monitora o botão especificado e encerra o programa ao pressioná-lo.

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

- Os 4 primeiros pinos do PCF8574A são usados para botões (entrada), e os 4 últimos para LEDs (saída).
- O método `botao_para_encerrar_programa` executa uma thread que envia um sinal SIGINT ao processo ao detectar o botão pressionado, encerrando o programa de forma segura.
- Utiliza a biblioteca [smbus2](https://pypi.org/project/smbus2/) para comunicação I2C.

---

## Requisitos

- [smbus2](https://pypi.org/project/smbus2/)

---

## Licença

MIT License.