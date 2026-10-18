# `Giroscopio` — placa do giroscópio na serial

Arquivo: `libs/giroscopio.py` · `from giroscopio import Giroscopio`

## Para que serve

Saber **para onde o robô está virado** (ângulo Z, em graus) e **se ele está inclinado** (X e Y:
rampa, lombada, gangorra). É o sensor mais importante para:

* girar ângulos exatos (90°, 180°) sem depender do encoder (que patina);
* andar reto (corrigir o desvio);
* atravessar gap na Rescue Line, manter a direção na área de resgate;
* saber em que direção do labirinto o robô está, na Maze.

A placa do giroscópio (com seu próprio microcontrolador) faz a integração e manda os ângulos
prontos pela serial (115200 baud).

## Como funciona

* Ao criar o objeto, a lib inicia uma **thread** que pergunta os ângulos à placa sem parar
  (a cada ~5 ms). Os métodos `le_angulo_*()` só devolvem o último valor recebido: são instantâneos.
* **Z acumula:** girando 2 voltas para o mesmo lado, Z vai a 720 (não volta para 0 em 360). Isso é
  bom: você pode somar 90 no alvo sem se preocupar em "dar a volta".
* **Sentido:** no Mariola o Z **cresce girando no sentido horário** (visto de cima). Muitos
  programas preferem "positivo = esquerda" (padrão da matemática); para isso, use `-le_angulo_z()`.
* **Deriva:** todo giroscópio "anda" um pouco parado (fração de grau por minuto). Por isso, se
  houver uma referência melhor (parede reta, linha), use-a para corrigir (veja a Maze).

## Criando o objeto

### `Giroscopio(porta_serial)`
```python
giro = Giroscopio(Portas.SERIAL5)
```
Lança exceção se a porta não abrir. Começa no modo `GYRO`.

## Constantes

| Constante | Valor | Significado |
|---|---|---|
| `GYRO` | 0 | modo normal: ângulos X, Y, Z |
| `GYRO2` | 1 | igual ao `GYRO`; **trocar entre os dois zera o Z** |
| `GYRO_CAL` | 2 | modo de calibração (uso interno de `calibra()`) |
| `ROS_IMU` | 3 | quaternion + velocidade angular + aceleração (firmware com suporte) |

## Métodos principais

### `le_angulo_z()`
Ângulo de **rumo** (giro no chão), inteiro em graus, acumulando. Positivo = horário.

* **Quando usar:** em todo giro e para andar reto.

### `le_angulo_x()` · `le_angulo_y()`
Inclinação em graus. No robô de exemplo, **X é a inclinação para frente** (positivo = frente
subindo) e Y a lateral — confira no seu, depende de como a placa foi montada.

* **Quando usar:** detectar rampa (subindo/descendo), saber que está em cima de lombada, não
  confundir o pé da rampa com outra coisa, detectar a gangorra virando.

### `reseta_z()`
Zera o Z (troca entre `GYRO` e `GYRO2`, o que faz a placa zerar) e espera 25 ms.

* **Quando usar:** no começo da rodada, logo depois do botão de início, com o robô parado na
  direção que vai virar "zero".
* **Cuidado:** depois de zerar, todos os alvos que você guardou ficam errados. Prefira zerar só uma
  vez e trabalhar com **alvos relativos** (`alvo = z() + 90`).

### `calibra()`
Para a thread, manda a placa calibrar (mede o "zero" do sensor com o robô **parado**), espera a
confirmação (até 5 s) e volta ao modo `GYRO`. `True` se deu certo.

* **Quando usar:** quando o Z deriva muito com o robô parado. A calibração fica gravada na placa;
  não precisa calibrar em todo programa. Se calibrar, **não encoste no robô** enquanto isso.

### `set_modo(modo)`
Escolhe o modo (0 a 3). `ValueError` para outros valores.

### `atualiza()`
Pede e lê um pacote. A thread já faz isso; você não precisa chamar.

## Modo `ROS_IMU` (avançado)

Com `set_modo(Giroscopio.ROS_IMU)` e um firmware que suporte, a placa manda orientação em
quaternion, velocidade angular (rad/s) e aceleração linear (m/s²). Métodos:
`get_quaternion()`, `get_angular_velocity()`, `get_linear_acceleration()`,
`get_orientation_euler()` (roll, pitch, yaw em graus), `get_all_imu_data()` (dict no formato do
ROS), `print_imu_data()`, e as covariâncias `get_*_covariance()`. Útil para quem usa ROS 2 ou
fusão de sensores. Nesse modo, `le_angulo_*()` **não** são atualizados.

## Receitas

**Ângulo com "positivo = esquerda":**
```python
def z():
    return -giro.le_angulo_z()
```

**Girar até um alvo** (proporcional com velocidade mínima):
```python
def gira_para(alvo, tolerancia=1.5):
    while abs(alvo - z()) > tolerancia:
        erro = alvo - z()
        v = max(15, min(50, abs(erro) * 0.8))
        motores.velocidade_motores(-v if erro > 0 else v, v if erro > 0 else -v)
        motores.atualiza_motores()
        time.sleep(0.01)
```

**Alvos acumulados:** guarde a direção desejada e some 90 a cada curva (`direcao += 90`) em vez de
"girar 90 a partir de onde estou". Assim o erro de uma curva não se soma ao da próxima.

**A direção mais próxima de um múltiplo de 90°:** `round(z() / 90) * 90`.

## Erros comuns

| Sintoma | Causa provável |
|---|---|
| Gira para o lado errado | sinal: o Z do Mariola é positivo no sentido horário |
| Passa do alvo e volta (oscila) | ganho alto ou velocidade mínima alta; diminua perto do alvo |
| Fica girando sem parar | o alvo nunca é atingido (tolerância pequena demais / roda patinando): ponha tempo máximo |
| Z "anda" parado | calibre (`calibra()`) com o robô imóvel |

## No simulador

Z em graus acumulando, positivo no horário (`giroscopio` no `robo*.json`: escala, sentido,
deriva, ruído). X/Y mostram a inclinação em rampas, escadas, lombadas e a vibração dos detritos.
