# CorReflexao

A classe `CorReflexao` é responsável por gerenciar a comunicação com um sensor de cor e reflexão conectado via porta serial. Ela permite a leitura de valores de reflexão, RGB, HSV e calibração do sensor.

---

## Funcionalidades

- Leitura de valores de reflexão.
- Leitura de valores RGB e HSV de até 3 sensores.
- Calibração do sensor para branco e preto.
- Atualização periódica dos dados via thread.
- Suporte a diferentes modos de operação.

---

## Atributos da Classe

- **`MODO_RGB_HSV_4X`**: Constante para o modo RGB/HSV com 4x de precisão.
- **`MODO_RGB_HSV_16X`**: Constante para o modo RGB/HSV com 16x de precisão.
- **`MODO_RGB_HSV_AUTO`**: Constante para o modo RGB/HSV automático.
- **`MODO_CALIBRA_BRANCO`**: Constante para o modo de calibração do branco.
- **`MODO_CALIBRA_PRETO`**: Constante para o modo de calibração do preto.
- **`MODO_RAW_AUTO`**: Constante para o modo RAW automático.
- **`modo`**: Modo atual do sensor.
- **`quantidadeBytesModo`**: Quantidade de bytes esperados para o modo atual.
- **`lista`**: Lista de bytes recebidos do sensor.
- **`ser`**: Objeto de comunicação serial.
- **`_thread_ativa`**: Flag para controlar a execução da thread de atualização.
- **`_thread`**: Objeto da thread de atualização.

---

## Métodos da Classe

### `__init__(self, portaSerial)`
Construtor da classe. Inicializa o sensor e inicia a thread de atualização periódica.

- **Parâmetros**:
  - `portaSerial` (str): Porta serial onde o sensor está conectado.

- **Exceções**:
  - Lança uma exceção se a porta serial não puder ser aberta.

---

### `__del__(self)`
Destrutor da classe. Para a thread de atualização e fecha a porta serial.

---

### `_atualizaPeriodicamente(self)`
Função interna que chama o método `atualiza` a cada 25ms. Executada em uma thread separada.

---

### `_iniciarThread(self)`
Inicia a thread para chamar `atualiza` periodicamente.

---

### `_pararThread(self)`
Para a thread que chama `atualiza`.

---

### `setModo(self, modo)`
Define o modo de operação do sensor.

- **Parâmetros**:
  - `modo` (int): Modo desejado (`MODO_RGB_HSV_4X`, `MODO_RGB_HSV_16X`, etc.).

---

### `atualiza(self)`
Atualiza os dados do sensor lendo os bytes necessários via porta serial.

- **Retorno**:
  - (bool): `True` se os dados foram atualizados com sucesso, `False` caso contrário.

---

### `leReflexao(self)`
Lê os valores de reflexão.

- **Retorno**:
  - (list): Lista com os valores de reflexão.

---

### `leRGBC(self, sensor)`
Lê os valores RGB e Clear de um sensor específico.

- **Parâmetros**:
  - `sensor` (int): Número do sensor (1, 2 ou 3).

- **Retorno**:
  - (list): Lista com os valores RGB e Clear do sensor.

---

### `leHSV(self, sensor)`
Lê os valores HSV de um sensor específico.

- **Parâmetros**:
  - `sensor` (int): Número do sensor (1, 2 ou 3).

- **Retorno**:
  - (list): Lista com os valores HSV do sensor.

---

### `calibraBranco(self)`
Realiza a calibração do sensor para branco.

- **Retorno**:
  - (bool): `True` se a calibração foi concluída com sucesso, `False` caso contrário.

---

### `calibraPreto(self)`
Realiza a calibração do sensor para preto.

- **Retorno**:
  - (bool): `True` se a calibração foi concluída com sucesso, `False` caso contrário.

---

## Exemplo de Uso

```python
from sensorCorReflexao import CorReflexao

# Inicializa o sensor na porta serial
sensor = CorReflexao("/dev/ttyUSB0")

# Lê os valores de reflexão
reflexao = sensor.leReflexao()
print(f"Reflexão: {reflexao}")

# Lê os valores RGB e Clear do sensor 1
rgbc = sensor.leRGBC(1)
print(f"RGB e Clear do sensor 1: {rgbc}")

# Lê os valores HSV do sensor 2
hsv = sensor.leHSV(2)
print(f"HSV do sensor 2: {hsv}")

# Realiza a calibração para branco
if sensor.calibraBranco():
    print("Calibração para branco concluída com sucesso!")
else:
    print("Falha na calibração para branco.")

# Realiza a calibração para preto
if sensor.calibraPreto():
    print("Calibração para preto concluída com sucesso!")
else:
    print("Falha na calibração para preto.")

# Finaliza o sensor
del sensor