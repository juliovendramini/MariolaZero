# Portas

A classe `Portas` fornece uma interface para descobrir e abrir conexões com portas seriais USB no sistema. Automaticamente detecta as portas seriais conectadas e permite abrir comunicação serial com diferentes dispositivos.

---

## Funcionalidades

- Mapeamento automático de portas seriais USB para seus caminhos reais no sistema
- Abertura de conexões seriais com configurações de baud rate e timeout
- Suporte a múltiplas portas seriais USB e portas fixas do sistema
- Detecção automática através do caminho `/dev/serial/by-path/`

---

## Constantes

### Portas seriais USB (auto-detectadas)
- **`_SERIAL0`**: 0 (primeira porta USB - usb-0:1.1)
- **`SERIAL1`**: 1 (segunda porta USB - usb-0:1.2)  
- **`SERIAL2`**: 2 (terceira porta USB - usb-0:1.3)
- **`SERIAL3`**: 3 (quarta porta USB - usb-0:1.4)

### Portas seriais fixas do sistema
- **`SERIAL4`**: 4 (`/dev/ttyS4`)
- **`SERIAL5`**: 5 (`/dev/ttyS2`) 
- **`SERIAL6`**: 6 (`/dev/ttyS5`)

### Identificadores I2C (para referência)
- **`I2C1`** a **`I2C8`**: 0 a 7

---

## Métodos da Classe

### `porta_serial_real(self, porta)`
Descobre a porta serial real do sistema correspondente ao identificador.

- **Parâmetros**:
  - `porta` (int): Identificador da porta serial (ex.: `_SERIAL0`, `SERIAL1`, etc.).

- **Retorno**:
  - (str): Caminho real da porta serial no sistema (ex.: `/dev/ttyUSB0`).

- **Exceções**:
  - Lança `RuntimeError` se houver falha ao descobrir a porta serial.
  - Lança `ValueError` se a porta fornecida for inválida.

---

### `abre_porta_serial(self, porta, baud_rate=115200)`
Abre uma conexão serial com a porta especificada.

- **Parâmetros**:
  - `porta` (int): Identificador da porta serial (ex.: `_SERIAL0`, `SERIAL1`, etc.).
  - `baud_rate` (int, opcional): Taxa de transmissão em bits por segundo (padrão: 115200).

- **Retorno**:
  - (serial.Serial): Objeto de comunicação serial, ou `None` se a conexão falhar.

- **Comportamento**:
  - Timeout configurado para 0.01 segundos
  - Exibe mensagens de sucesso ou erro no console

---

## Exemplo de Uso

```python
from libs.portas import Portas

# Inicializa a classe Portas
portas = Portas()

# Obtém o caminho real da porta SERIAL1
try:
    caminho_serial1 = portas.porta_serial_real(portas.SERIAL1)
    print(f"Caminho da porta SERIAL1: {caminho_serial1}")
except RuntimeError as e:
    print(f"Erro ao descobrir a porta serial: {e}")
except ValueError as e:
    print(f"Porta inválida: {e}")

# Abre uma conexão serial na porta SERIAL2
serial_connection = portas.abre_porta_serial(portas.SERIAL2, baud_rate=9600)
if serial_connection:
    print("Conexão serial estabelecida com sucesso!")
    # Feche a conexão após o uso
    serial_connection.close()
else:
    print("Falha ao estabelecer a conexão serial.")
```

---

## Detalhes Técnicos

- As portas USB são detectadas dinamicamente através de `/dev/serial/by-path/`
- Utiliza o padrão `usb-0:1.x` para identificar diferentes conectores USB
- Timeout padrão de 0.01 segundos para operações seriais
- Suporte tanto para portas USB quanto para portas UART fixas do sistema

---

## Requisitos

- [pyserial](https://pypi.org/project/pyserial/)
- Sistema Linux com suporte a `/dev/serial/by-path/`

---

## Licença

MIT License.
