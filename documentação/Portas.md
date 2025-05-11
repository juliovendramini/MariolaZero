# Portas

A classe `Portas` é responsável por gerenciar as portas seriais e I2C de um sistema. Ela fornece métodos para mapear portas seriais para seus caminhos reais no sistema e para abrir conexões seriais com as configurações apropriadas.

---

## Funcionalidades

- Mapeamento de portas seriais para seus caminhos reais no sistema.
- Abertura de conexões seriais com configurações de baud rate e timeout.
- Suporte a múltiplas portas seriais e I2C.

---

## Atributos da Classe

- **Portas seriais**:
  - **`_SERIAL0`**: Porta serial 0.
  - **`SERIAL1`**: Porta serial 1.
  - **`SERIAL2`**: Porta serial 2.
  - **`SERIAL3`**: Porta serial 3.
  - **`SERIAL4`**: Porta serial 4.
  - **`SERIAL5`**: Porta serial 5.
  - **`SERIAL6`**: Porta serial 6.

- **Portas I2C**:
  - **`I2C1`**: Porta I2C 1.
  - **`I2C2`**: Porta I2C 2.
  - **`I2C3`**: Porta I2C 3.
  - **`I2C4`**: Porta I2C 4.
  - **`I2C5`**: Porta I2C 5.
  - **`I2C6`**: Porta I2C 6.
  - **`I2C7`**: Porta I2C 7.
  - **`I2C8`**: Porta I2C 8.

---

## Métodos da Classe

### `portaSerialReal(self, porta)`
Obtém o caminho real da porta serial no sistema.

- **Parâmetros**:
  - `porta` (int): Identificador da porta serial (ex.: `SERIAL1`, `SERIAL2`, etc.).

- **Retorno**:
  - (str): Caminho real da porta serial no sistema (ex.: `/dev/ttyUSB0`).

- **Exceções**:
  - Lança um `RuntimeError` se houver falha ao descobrir a porta serial.
  - Lança um `ValueError` se a porta fornecida for inválida.

---

### `abrePortaSerial(self, porta, baud_rate=115200)`
Abre uma conexão serial com a porta especificada.

- **Parâmetros**:
  - `porta` (int): Identificador da porta serial (ex.: `SERIAL1`, `SERIAL2`, etc.).
  - `baud_rate` (int, opcional): Taxa de transmissão em bits por segundo (padrão: 115200).

- **Retorno**:
  - (serial.Serial): Objeto de comunicação serial, ou `None` se a conexão falhar.

- **Exceções**:
  - Lança um `serial.SerialException` se houver falha ao abrir a porta serial.

---

## Exemplo de Uso

```python
from portas import Portas

# Inicializa a classe Portas
portas = Portas()

# Obtém o caminho real da porta SERIAL1
try:
    caminho_serial1 = portas.portaSerialReal(portas.SERIAL1)
    print(f"Caminho da porta SERIAL1: {caminho_serial1}")
except RuntimeError as e:
    print(f"Erro ao descobrir a porta serial: {e}")
except ValueError as e:
    print(f"Porta inválida: {e}")

# Abre uma conexão serial na porta SERIAL2
serial_connection = portas.abrePortaSerial(portas.SERIAL2, baud_rate=9600)
if serial_connection:
    print("Conexão serial estabelecida com sucesso!")
    # Feche a conexão após o uso
    serial_connection.close()
else:
    print("Falha ao estabelecer a conexão serial.")