# Motores

A classe `Motores` é responsável por controlar os motores e servos da placa do novo brick. Ela fornece métodos para configurar velocidades, direções, ângulos e modos de operação dos motores e servos, além de realizar a comunicação com a placa via porta serial.

---

## Atributos da Classe

- **`motorInvertido`**: Lista de 4 valores booleanos indicando se cada motor está invertido.
- **`DEBUG`**: Flag para ativar ou desativar mensagens de depuração.
- **`NORMAL`**: Constante para indicar a direção normal do motor.
- **`INVERTIDO`**: Constante para indicar a direção invertida do motor.
- **`anguloMotor1`**: Ângulo atual do motor 1.
- **`anguloMotor2`**: Ângulo atual do motor 2.
- **`modoFreio`**: Modo de frenagem dos motores (`BREAK` ou `HOLD`).
- **`BREAK`**: Constante para o modo de frenagem "break".
- **`HOLD`**: Constante para o modo de frenagem "hold".
- **`anguloAbsolutoMotor1`**: Ângulo absoluto do motor 1.
- **`anguloAbsolutoMotor2`**: Ângulo absoluto do motor 2.
- **`anguloDeltaMotor1`**: Diferença de ângulo do motor 1 desde o último reset.
- **`anguloDeltaMotor2`**: Diferença de ângulo do motor 2 desde o último reset.
- **`estadoMotores`**: Estado atual dos motores.
- **`PARADO`**: Constante para indicar que o motor está parado.
- **`GIRANDO_NORMAL`**: Constante para indicar que o motor está girando no sentido normal.
- **`GIRANDO_INVERTIDO`**: Constante para indicar que o motor está girando no sentido invertido.
- **`atualizaInstantaneo`**: Flag para ativar ou desativar a atualização instantânea dos motores.
- **`ser`**: Objeto de comunicação serial.
- **`listaServos`**: Lista de valores para controlar os servos.
- **`listaMotores`**: Lista de valores para controlar os motores.

---

## Métodos da Classe

### `__init__(self, atualizaInstantaneo=False)`
Construtor da classe. Inicializa os atributos e configura a comunicação serial com a placa.

- **Parâmetros**:
  - `atualizaInstantaneo` (bool): Define se as atualizações dos motores e servos devem ser instantâneas.

- **Exceções**:
  - Lança uma exceção se a porta serial não puder ser aberta.

---

### `__del__(self)`
Destrutor da classe. Para os motores e fecha a porta serial.

---

### `moveServo(self, servo, angulo)`
Move um servo para o ângulo especificado.

- **Parâmetros**:
  - `servo` (int): Número do servo (1 a 6).
  - `angulo` (int): Ângulo desejado (0 a 180).

---

### `atualizaServos(self)`
Atualiza os valores dos servos na placa.

- **Exceções**:
  - Lança uma exceção se houver erro ao ler o estado dos servos.

---

### `atualizaMotores(self)`
Atualiza os valores dos motores na placa.

- **Exceções**:
  - Lança uma exceção se houver erro ao ler o estado dos motores.

---

### `estado(self)`
Obtém o estado atual dos motores sem atualizar as velocidades.

- **Exceções**:
  - Lança uma exceção se houver erro ao ler o estado dos motores.

---

### `direcaoMotor(self, motor, direcao)`
Define a direção de um motor.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 a 4).
  - `direcao` (int): Direção (`NORMAL` ou `INVERTIDO`).

---

### `desativaServo(self, servo)`
Desativa um servo.

- **Parâmetros**:
  - `servo` (int): Número do servo (1 a 6).

---

### `velocidadeMotor(self, motor, velocidade)`
Define a velocidade de um motor.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 a 4).
  - `velocidade` (int): Velocidade do motor (-120 a 120).

---

### `moveMotor(self, motor, velocidade, angulo)`
Move um motor para um ângulo específico com uma velocidade definida.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 ou 2).
  - `velocidade` (int): Velocidade do motor (-120 a 120).
  - `angulo` (int): Ângulo desejado (0 a 65535).

---

### `moveMotores(self, velocidade1, angulo1, velocidade2, angulo2)`
Move os motores 1 e 2 simultaneamente para ângulos específicos com velocidades definidas.

- **Parâmetros**:
  - `velocidade1` (int): Velocidade do motor 1 (-120 a 120).
  - `angulo1` (int): Ângulo do motor 1 (0 a 65535).
  - `velocidade2` (int): Velocidade do motor 2 (-120 a 120).
  - `angulo2` (int): Ângulo do motor 2 (0 a 65535).

---

### `velocidadeMotores(self, velocidade1, velocidade2)`
Define as velocidades dos motores 1 e 2.

- **Parâmetros**:
  - `velocidade1` (int): Velocidade do motor 1 (-120 a 120).
  - `velocidade2` (int): Velocidade do motor 2 (-120 a 120).

---

### `paraMotores(self)`
Para todos os motores.

---

### `modoFreio(self, modo)`
Define o modo de frenagem dos motores.

- **Parâmetros**:
  - `modo` (int): Modo de frenagem (`BREAK` ou `HOLD`).

---

### `resetaAnguloMotor(self, motor)`
Reseta o ângulo de um motor.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 ou 2).

---

### `anguloMotor(self, motor)`
Obtém o ângulo atual de um motor, considerando o delta.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 ou 2).

- **Retorno**:
  - (int): Ângulo atual do motor.

---

### `estadoMotor(self, motor)`
Obtém o estado atual de um motor.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 ou 2).

- **Retorno**:
  - (int): Estado do motor (`PARADO`, `GIRANDO_NORMAL`, ou `GIRANDO_INVERTIDO`).

---

## Exceções
A classe pode lançar exceções em várias situações, como:
- Erros de comunicação serial.
- Valores inválidos para ângulos, velocidades ou números de motores/servos.

---

## Exemplo de Uso

```python
from motores import Motores

# Inicializa a classe Motores
motores = Motores(atualizaInstantaneo=True)

# Define a velocidade dos motores
motores.velocidadeMotor(1, 100)
motores.velocidadeMotor(2, -100)

# Move o motor 1 para um ângulo específico
motores.moveMotor(1, 50, 360)

# Para todos os motores
motores.paraMotores()