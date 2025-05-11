# Giroscopio

A classe `Giroscopio` é responsável por gerenciar a comunicação com um giroscópio conectado via porta serial. Ela permite a leitura dos ângulos em três eixos (X, Y, Z), calibração do sensor e atualização periódica dos dados.

---

## Funcionalidades

- Leitura dos ângulos em X, Y e Z.
- Calibração do giroscópio.
- Atualização periódica dos dados via thread.
- Suporte a diferentes modos de operação.

---

## Atributos da Classe

- **`GYRO`**: Constante para o modo padrão do giroscópio.
- **`GYRO2`**: Constante para o segundo modo do giroscópio.
- **`GYRO_CAL`**: Constante para o modo de calibração.
- **`modo`**: Modo atual do giroscópio.
- **`quantidadeBytesModo`**: Quantidade de bytes esperados para o modo atual.
- **`lista`**: Lista de bytes recebidos do giroscópio.
- **`ser`**: Objeto de comunicação serial.
- **`_thread_ativa`**: Flag para controlar a execução da thread de atualização.
- **`_thread`**: Objeto da thread de atualização.

---

## Métodos da Classe

### `__init__(self, portaSerial)`
Construtor da classe. Inicializa o giroscópio e inicia a thread de atualização periódica.

- **Parâmetros**:
  - `portaSerial` (str): Porta serial onde o giroscópio está conectado.

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
Define o modo de operação do giroscópio.

- **Parâmetros**:
  - `modo` (int): Modo desejado (`GYRO`, `GYRO2` ou `GYRO_CAL`).

- **Exceções**:
  - Lança um `ValueError` se o modo for inválido.

---

### `atualiza(self)`
Atualiza os dados do giroscópio lendo os bytes necessários via porta serial.

- **Retorno**:
  - (bool): `True` se os dados foram atualizados com sucesso, `False` caso contrário.

---

### `leAnguloX(self)`
Lê o ângulo no eixo X.

- **Retorno**:
  - (int): Ângulo no eixo X (inteiro com sinal de 16 bits).

---

### `leAnguloY(self)`
Lê o ângulo no eixo Y.

- **Retorno**:
  - (int): Ângulo no eixo Y (inteiro com sinal de 16 bits).

---

### `leAnguloZ(self)`
Lê o ângulo no eixo Z.

- **Retorno**:
  - (int): Ângulo no eixo Z (inteiro com sinal de 16 bits).

---

### `resetaZ(self)`
Alterna o modo entre `GYRO` e `GYRO2` para resetar o eixo Z.

---

### `calibra(self)`
Realiza a calibração do giroscópio.

- **Comportamento**:
  - Para a thread de atualização.
  - Envia o comando de calibração e aguarda 5 segundos.
  - Reinicia a thread de atualização.

- **Retorno**:
  - (bool): `True` se a calibração foi concluída com sucesso, `False` caso contrário.

---

## Exemplo de Uso

```python
from giroscopio import Giroscopio

# Inicializa o giroscópio na porta serial
giroscopio = Giroscopio("/dev/ttyUSB0")

# Lê os ângulos nos eixos X, Y e Z
angulo_x = giroscopio.leAnguloX()
angulo_y = giroscopio.leAnguloY()
angulo_z = giroscopio.leAnguloZ()

print(f"Ângulo X: {angulo_x}")
print(f"Ângulo Y: {angulo_y}")
print(f"Ângulo Z: {angulo_z}")

# Realiza a calibração do giroscópio
if giroscopio.calibra():
    print("Calibração concluída com sucesso!")
else:
    print("Falha na calibração.")

# Finaliza o giroscópio
del giroscopio