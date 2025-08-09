# PlacaMuxVl53l0x

A classe `PlacaMuxVl53l0x` permite controlar múltiplos sensores de distância VL53L0X através de uma placa multiplexadora via comunicação serial. Ideal para projetos que precisam medir distâncias de vários pontos simultaneamente com atualização automática em background.

---

## Exemplo de uso

```python
from libs.placaMuxVl53l0x import PlacaMuxVl53l0x
from libs.portas import Portas

# Inicializa a placa multiplexadora na porta serial 2
placa_mux = PlacaMuxVl53l0x(Portas.SERIAL2)

# Lê a distância do sensor na porta 0
distancia = placa_mux.le_distancia(0)
print(f"Distância sensor 0: {distancia} mm")

# Verifica se o botão da porta 1 está pressionado
if placa_mux.botao_apertado(1):
    print("Botão da porta 1 está pressionado!")

# Lê distâncias de todos os sensores (0 a 3)
for porta in range(4):
    dist = placa_mux.le_distancia(porta)
    botao = placa_mux.botao_apertado(porta)
    print(f"Porta {porta} - Distância: {dist} mm, Botão: {'Sim' if botao else 'Não'}")
```

---

## Métodos

### `__init__(self, porta_serial)`
Inicializa a placa multiplexadora na porta serial especificada.

- **porta_serial**: porta serial para comunicação (usar constantes da classe Portas)

### `atualiza(self)`
Atualiza manualmente os dados de todos os sensores.

- **Retorno**: `True` se a atualização foi bem-sucedida, `False` caso contrário

### `le_distancia(self, porta)`
Lê a distância medida por um sensor específico.

- **porta**: número da porta do sensor (0 a 3)
- **Retorno**: distância em milímetros (valor inteiro)

### `botao_apertado(self, porta)`
Verifica se o botão associado a uma porta está pressionado.

- **porta**: número da porta do sensor (0 a 3)
- **Retorno**: `True` se o botão estiver pressionado, `False` caso contrário

---

## Constantes

- `DISTANCIA_4_PORTAS`: 0 (modo de operação para 4 sensores de distância)

---

## Detalhes

- Atualiza automaticamente os dados em background a cada 100ms através de uma thread.
- Suporta até 4 sensores VL53L0X simultaneamente.
- Cada porta possui um sensor de distância e um botão associado.
- A thread é automaticamente encerrada no destrutor da classe.
- Retorna valores signed de 16 bits para as distâncias.
- Lança `ValueError` para portas inválidas.

---

## Requisitos

- Placa multiplexadora VL53L0X compatível conectada via serial
- [pyserial](https://pypi.org/project/pyserial/)

---

## Licença

MIT License.
