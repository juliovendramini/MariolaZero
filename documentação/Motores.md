# Motores

A classe `Motores` é responsável por controlar os motores e servos da placa do novo brick. Ela fornece métodos para configurar velocidades, direções, ângulos e modos de operação dos motores e servos, além de realizar a comunicação com a placa via porta serial com suporte a controle PID.

---

## Atributos da Classe

- **`motor_invertido`**: Lista de 4 valores booleanos indicando se cada motor está invertido.
- **`DEBUG`**: Flag para ativar ou desativar mensagens de depuração.
- **`NORMAL`**: Constante para indicar a direção normal do motor.
- **`INVERTIDO`**: Constante para indicar a direção invertida do motor.
- **`angulo_motor1`**: Ângulo atual do motor 1.
- **`angulo_motor2`**: Ângulo atual do motor 2.
- **`modo_freio`**: Modo de frenagem dos motores (`BREAK` ou `HOLD`).
- **`BREAK`**: Constante para o modo de frenagem "break".
- **`HOLD`**: Constante para o modo de frenagem "hold".
- **`angulo_absoluto_motor1`**: Ângulo absoluto do motor 1.
- **`angulo_absoluto_motor2`**: Ângulo absoluto do motor 2.
- **`angulo_delta_motor1`**: Diferença de ângulo do motor 1 desde o último reset.
- **`angulo_delta_motor2`**: Diferença de ângulo do motor 2 desde o último reset.
- **`estado_motores`**: Estado atual dos motores.
- **`PARADO`**: Constante para indicar que o motor está parado.
- **`GIRANDO_NORMAL`**: Constante para indicar que o motor está girando no sentido normal.
- **`GIRANDO_INVERTIDO`**: Constante para indicar que o motor está girando no sentido invertido.
- **`atualiza_instantaneo`**: Flag para ativar ou desativar a atualização instantânea dos motores.
- **`ser`**: Objeto de comunicação serial.
- **`lista_servos`**: Lista de valores para controlar os servos.
- **`lista_motores`**: Lista de valores para controlar os motores.
- **`lista_pid`**: Lista de valores para configurar o controle PID dos motores.

---

## Métodos da Classe

### `__init__(self, atualiza_instantaneo=False)`
Construtor da classe. Inicializa os atributos e configura a comunicação serial com a placa.

- **Parâmetros**:
  - `atualiza_instantaneo` (bool): Define se as atualizações dos motores e servos devem ser instantâneas.

- **Exceções**:
  - Lança uma exceção se a porta serial não puder ser aberta.

---

### `__del__(self)`
Destrutor da classe. Para os motores e fecha a porta serial.

---

### `move_servo(self, servo, angulo)`
Move um servo para o ângulo especificado.

- **Parâmetros**:
  - `servo` (int): Número do servo (1 a 6).
  - `angulo` (int): Ângulo desejado (0 a 180).

---

### `atualiza_servos(self)`
Atualiza os valores dos servos na placa.

- **Exceções**:
  - Lança uma exceção se houver erro ao ler o estado dos servos.

---

### `atualiza_motores(self)`
Atualiza os valores dos motores na placa.

- **Exceções**:
  - Lança uma exceção se houver erro ao ler o estado dos motores.

---

### `estado(self)`
Obtém o estado atual dos motores sem atualizar as velocidades.

- **Exceções**:
  - Lança uma exceção se houver erro ao ler o estado dos motores.

---

### `direcao_motor(self, motor, direcao)`
Define a direção de um motor.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 a 4).
  - `direcao` (int): Direção (`NORMAL` ou `INVERTIDO`).

---

### `desativa_servo(self, servo)`
Desativa um servo.

- **Parâmetros**:
  - `servo` (int): Número do servo (1 a 6).

---

### `velocidade_motor(self, motor, velocidade)`
Define a velocidade de um motor.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 a 4).
  - `velocidade` (int): Velocidade do motor (-120 a 120).

---

### `move_motor(self, motor, velocidade, angulo)`
Move um motor para um ângulo específico com uma velocidade definida.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 ou 2).
  - `velocidade` (int): Velocidade do motor (-120 a 120).
  - `angulo` (int): Ângulo desejado (0 a 65535).

---

### `move_motores(self, velocidade1, angulo1, velocidade2, angulo2)`
Move os motores 1 e 2 simultaneamente para ângulos específicos com velocidades definidas.

- **Parâmetros**:
  - `velocidade1` (int): Velocidade do motor 1 (-120 a 120).
  - `angulo1` (int): Ângulo do motor 1 (0 a 65535).
  - `velocidade2` (int): Velocidade do motor 2 (-120 a 120).
  - `angulo2` (int): Ângulo do motor 2 (0 a 65535).

---

### `velocidade_motores(self, velocidade1, velocidade2)`
Define as velocidades dos motores 1 e 2.

- **Parâmetros**:
  - `velocidade1` (int): Velocidade do motor 1 (-120 a 120).
  - `velocidade2` (int): Velocidade do motor 2 (-120 a 120).

---

### `potencia_motores(self, potencia1, potencia2)`
Define a potência (PWM) dos motores 1 e 2.

- **Parâmetros**:
  - `potencia1` (int): Potência do motor 1 (-100 a 100).
  - `potencia2` (int): Potência do motor 2 (-100 a 100).

---

### `para_motores(self)`
Para todos os motores.

---

### `set_modo_freio(self, modo)`
Define o modo de frenagem dos motores.

- **Parâmetros**:
  - `modo` (int): Modo de frenagem (`BREAK` ou `HOLD`).

---

### `pid_motor(self, kp, ki, kd)`
Configura os parâmetros PID dos motores.

- **Parâmetros**:
  - `kp` (float): Constante proporcional (multiplicada por 100 internamente).
  - `ki` (float): Constante integral (multiplicada por 100 internamente).
  - `kd` (float): Constante derivativa (multiplicada por 100 internamente).

---

### `reseta_angulo_motor(self, motor)`
Reseta o ângulo de um motor.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 ou 2).

---

### `angulo_motor(self, motor)`
Obtém o ângulo atual de um motor, considerando o delta.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 ou 2).

- **Retorno**:
  - (int): Ângulo atual do motor.

---

### `estado_motor(self, motor)`
Obtém o estado atual de um motor.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 ou 2).

- **Retorno**:
  - (int): Estado do motor (`PARADO`, `GIRANDO_NORMAL`, ou `GIRANDO_INVERTIDO`).

---

### `potencia_motor(self, motor, potencia)`
Define a potência (PWM direto, sem PID) de um motor.

- **Parâmetros**:
  - `motor` (int): Número do motor (1 a 4).
  - `potencia` (int): Potência (-100 a 100).

---

### Tração 4x4: `velocidade_motores_4x4(v1, v2)` · `potencia_motores_4x4(p1, p2)` · `move_motores_4x4(v1, angulo1, v2, angulo2)`
Iguais a `velocidade_motores`, `potencia_motores` e `move_motores`, mas o motor 3 (sem encoder)
recebe o mesmo comando do motor 1 e o motor 4 o do motor 2, dentro do firmware. No modo velocidade,
os motores 3 e 4 seguem o PID dos motores 1 e 2.

- **Parâmetros**: velocidades de -100 a 100 (-120 a 120 no `move_motores_4x4`), potências de -100
  a 100, ângulos (contagens do encoder) de 0 a 65535.

---

## LEDs RGB

O Mariola tem uma fita de **10 LEDs RGB** (WS2812B) ligada na coluna **LEDs** do header amarelo (a
5ª coluna, depois dos 4 servos). Os comandos de LED são enviados na hora (não dependem de
`atualiza_instantaneo`). O timeout de 5 s sem comando apaga os LEDs.

### `set_led_rgb_all(self, r, g, b)`
Acende todos os LEDs com a mesma cor (0 a 255 cada).

### `set_led_rgb_one(self, index, r, g, b)`
Acende um LED (`index` de 0 a 9) com a cor dada.

### `set_led_rgb_all_porta4(self, r, g, b)` · `set_led_rgb_one_porta4(self, index, r, g, b)`
Uma **segunda fita** de 10 LEDs na coluna **SERVO 4** do header (firmware de 19/10/2026 ou mais
novo). O primeiro comando desliga o servo 4 e liga a fita; `move_servo(4, angulo)` apaga a fita e a
porta volta a ser servo.

---

## Ventoinha

### `set_ventoinha(self, potencia)` · `desliga_ventoinha(self)`
Liga a ventoinha na coluna **DEBUG/PWM** do header amarelo (a 6ª, pino 11 do ATmega) com potência
de 0 a 100 (%). `desliga_ventoinha()` = `set_ventoinha(0)`.

- O primeiro comando desliga **todos os servos** do Mariola e o serial de debug do ATmega (os servos
  e o PWM da ventoinha usam o mesmo timer). Os servos só voltam depois de reiniciar o brick; com a
  ventoinha ativa, `move_servo` lança exceção.
- O timeout de 5 s **não** desliga a ventoinha. A classe desliga no `__del__`.

---

## Calibração

### `obtem_calibracao_motores(self)`
Retorna `(calibracao_motor1, calibracao_motor2)`: a velocidade (contagens a cada 25 ms) que vale 100.

### `calibra_motores(self)`
Manda a placa medir a velocidade máxima dos motores e gravar a calibração. Os motores giram sozinhos
e a placa fica ~26 s sem responder: faça com o robô suspenso.

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
motores = Motores(atualiza_instantaneo=True)

# Define a velocidade dos motores
motores.velocidade_motor(1, 100)
motores.velocidade_motor(2, -100)

# Move o motor 1 para um ângulo específico
motores.move_motor(1, 50, 360)

# LEDs: todos verdes, o LED 9 vermelho
motores.set_led_rgb_all(0, 80, 0)
motores.set_led_rgb_one(9, 255, 0, 0)

# Para todos os motores
motores.para_motores()