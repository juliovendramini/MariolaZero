# PlacaMuxTCS34725

A classe `PlacaMuxTCS34725` permite controlar múltiplos sensores de cor TCS34725 através de uma placa multiplexadora via comunicação serial. Ideal para projetos que precisam ler cores de vários sensores simultaneamente com atualização automática em background.

---

## Exemplo de uso

```python
from libs.placaMuxTCS34725 import PlacaMuxTCS34725
from libs.portas import Portas

# Inicializa a placa multiplexadora na porta serial 1
placa_mux = PlacaMuxTCS34725(Portas.SERIAL1)

# Configura o modo de operação (ganho 4x)
placa_mux.set_modo(placa_mux.RGB_4X)

# Lê os valores do sensor na porta 0
red, green, blue, clear = placa_mux.le_sensor(0)
print(f"Sensor 0 - R: {red}, G: {green}, B: {blue}, C: {clear}")

# Lê valores de todos os sensores (0 a 3)
for porta in range(4):
    r, g, b, c = placa_mux.le_sensor(porta)
    print(f"Sensor {porta} - R: {r}, G: {g}, B: {b}, C: {c}")
```

---

## Métodos

### `__init__(self, porta_serial)`
Inicializa a placa multiplexadora na porta serial especificada.

- **porta_serial**: porta serial para comunicação (usar constantes da classe Portas)

### `set_modo(self, modo)`
Define o modo de operação dos sensores.

- **modo**: modo de operação (0-3, usar constantes RGB_4X, RGB_16X, etc.)

### `atualiza(self)`
Atualiza manualmente os dados de todos os sensores.

- **Retorno**: `True` se a atualização foi bem-sucedida, `False` caso contrário

### `le_sensor(self, porta)`
Lê os valores de cor de um sensor específico.

- **porta**: número da porta do sensor (0 a 3)
- **Retorno**: tupla `(red, green, blue, clear)` com os valores dos canais

---

## Constantes

- `RGB_4X`: 0 (modo RGB com ganho 4x)
- `RGB_16X`: 1 (modo RGB com ganho 16x)
- `RGB_4X_LED_OFF`: 2 (modo RGB com ganho 4x e LED desligado)
- `RGB_16X_LED_OFF`: 3 (modo RGB com ganho 16x e LED desligado)

---

## Detalhes

- Atualiza automaticamente os dados em background a cada 25ms através de uma thread.
- Suporta até 4 sensores TCS34725 simultaneamente.
- A thread é automaticamente encerrada no destrutor da classe.
- Retorna valores signed de 16 bits para cada canal de cor.
- Lança `ValueError` para portas ou modos inválidos.

---

## Requisitos

- Placa multiplexadora compatível conectada via serial
- [pyserial](https://pypi.org/project/pyserial/)

---

## Licença

MIT License.
