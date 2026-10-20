# Módulo 3 — O primeiro programa

**Objetivo:** escrever, rodar no simulador e no robô um programa que acende os LEDs, anda e para
com segurança; entender a estrutura que **todo** programa do robô vai ter.

Código: [`codigos/01_ola_mariola/main.py`](codigos/01_ola_mariola/main.py)

## 3.1 O programa

```python
import time

from motores import Motores

motores = Motores(True)                       # True = cada comando já vai para a placa
motores.direcao_motor(2, Motores.INVERTIDO)   # o motor 2 está espelhado no robô

try:
    motores.set_led_rgb_all(0, 80, 0)         # tudo verde: o programa começou
    motores.reseta_angulo_motor(1)
    motores.reseta_angulo_motor(2)

    motores.velocidade_motores(40, 40)        # -100..100 (PID de velocidade)
    inicio = time.time()
    while time.time() - inicio < 1.5:
        motores.estado()                      # lê os encoders sem mudar nada
        print('encoders:', motores.angulo_motor(1), motores.angulo_motor(2))
        time.sleep(0.25)

    motores.velocidade_motores(0, 0)
    time.sleep(0.3)
    motores.estado()
    print('andou (contagens):', motores.angulo_motor(1), motores.angulo_motor(2))
    motores.set_led_rgb_all(0, 0, 80)         # azul: terminou
    time.sleep(0.5)
except KeyboardInterrupt:
    print('Interrompido pelo usuário')
finally:
    # acontece SEMPRE: no fim normal, no Ctrl+C e se der erro no meio
    motores.para_motores()
    motores.set_led_rgb_all(0, 0, 0)
    print('Motores parados.')
```

## 3.2 Rodando no simulador

Na pasta `simuladorLine`:
```bash
python simulador.py --robo robo_esteira.json --programa ../curso/codigos/01_ola_mariola/main.py
```
Clique em **▶ Iniciar rodada**. O robô anda um pouco e para; no console de baixo da janela
aparecem os `print`. Sem janela (bom para testar rápido):
```bash
python simulador.py --robo robo_esteira.json --programa ../curso/codigos/01_ola_mariola/main.py --sem-janela --velocidade 4
```
Saída esperada (os números mudam um pouco):
```
[robô] encoders: 0 0
[robô] encoders: 238 239
...
[robô] andou (contagens): 1815 1816
[robô] Motores parados.
```

> Usamos o **robô de esteira** porque ele só tem os dois motores do Mariola. O robô 4x4 tem as
> rodas da frente em placas de motor separadas, que este programa não comanda (veja o módulo 4).

## 3.3 Rodando no robô

Copie `motores.py` e `portas.py` de `libs/` para a pasta, mande com o `envia` e rode pelo menu ou
por `ssh` (módulo 2). Com o robô **suspenso** na primeira vez (rodas no ar): se um lado girar para
trás, o motor invertido no seu robô é o outro.

## 3.4 A estrutura de todo programa

```python
# 1. imports
import time
from motores import Motores

# 2. constantes (o que você vai ajustar): velocidades, ganhos, limiares
VEL = 40

# 3. criar os objetos do hardware — UMA vez
motores = Motores(True)

# 4. funções (pequenas, com nome que diz o que fazem)
def anda(ve, vd):
    ...

# 5. o programa, protegido
try:
    ...                         # o que o robô faz
except KeyboardInterrupt:
    print('Interrompido')
finally:
    motores.para_motores()      # SEMPRE parar
```

### Por que `try / finally`?
Se o programa der erro no meio (ou você apertar `Ctrl+C`), sem o `finally` os motores **continuam
com o último comando** até o timeout de 5 s da placa. Num robô em cima da mesa, 5 s é tempo de
sobra para ele cair. O `finally` roda **sempre**.

### Por que `time.sleep` no laço?
* O robô não precisa (nem consegue) reagir em microssegundos: sensores atualizam a cada 10–30 ms.
* Um laço sem `sleep` gasta 100% do processador à toa e atrapalha as threads dos sensores.
* No simulador, o tempo do programa só anda quando ele espera. Um `time.sleep(0.01)` no laço deixa
  o comportamento igual no robô e no simulador.

Use `sleep` **curto** (5–20 ms) em laços de controle. Esperas longas, só em laço que continua
mandando comando (a regra dos 5 s).

## 3.5 As regras de ouro

1. **Um objeto por placa**, criado no começo.
2. **`try/finally` parando tudo.**
3. **Nunca fique 5 s sem mandar nada ao Mariola** (ele solta os motores e apaga os LEDs). Para
   esperar parado:
   ```python
   def espera(segundos):
       fim = time.time() + segundos
       while time.time() < fim:
           motores.estado()        # "ainda estou aqui"
           time.sleep(0.1)
   ```
4. **Teste no simulador, confirme no robô.** O simulador acha erros de lógica rápido; o robô mostra
   o que o simulador não sabe (atrito real, luz, bateria).
5. **Use os LEDs para saber em que parte do programa o robô está** (verde = seguindo linha, azul =
   área de resgate...). Na pista não dá para ler `print`.

## 3.6 Lendo um erro

Quando o programa quebra, o Python mostra o **traceback**. Leia de **baixo para cima**: a última
linha diz o erro, as de cima dizem onde.
```
Traceback (most recent call last):
  File "main.py", line 12, in <module>
    motores.velocidade_motores(40)
TypeError: Motores.velocidade_motores() missing 1 required positional argument: 'velocidade2'
```
No robô (rodando pelo menu), o traceback vai para `~/logs/NNNNNN_erro.log`.

## 3.7 Threads: coisas acontecendo "ao mesmo tempo"

Até aqui o programa faz **uma coisa de cada vez**, de cima para baixo. Uma **thread** é uma função
que roda **ao lado** do programa principal: enquanto o seu laço segue a linha, uma thread pode
ficar perguntando o ângulo ao giroscópio sem parar.

Pense numa cozinha: o forno assa o bolo **enquanto** você lava a louça. Você não fica parado olhando
o forno; de vez em quando só olha o resultado.

Código: [`codigos/01_ola_mariola/threads.py`](codigos/01_ola_mariola/threads.py)

```python
import threading
import time

contador = 0

def conta():                     # esta função vai rodar na thread
    global contador
    while True:
        contador += 1
        time.sleep(0.1)

threading.Thread(target=conta, daemon=True).start()   # começa a rodar conta() "ao lado"

for i in range(5):
    print(f'volta {i}: contador = {contador}')         # o principal só LÊ o valor
    time.sleep(0.5)
```
```
volta 0: contador = 1
volta 1: contador = 6
volta 2: contador = 11
...
```

O programa principal nunca chama `conta()`, e mesmo assim o contador sobe: ela está rodando na
thread.

* **"Ao mesmo tempo", entre aspas:** no Python as threads se **revezam** muito rápido. Quando uma
  espera (um `sleep`, uma resposta do sensor), outra aproveita. Por isso toda thread com laço
  precisa de um `time.sleep`: sem ele, ela não dá a vez para as outras.
* **`daemon=True`:** a thread termina quando o programa principal termina. Sem isso, o programa
  não fecha.
* **Variável compartilhada:** a thread escreve e o principal lê. É o jeito mais simples de
  conversar entre os dois.
* **Erro numa thread não aparece sozinho:** se `conta()` der erro, a thread morre e o contador
  para, mas o programa principal continua como se nada tivesse acontecido.

**Você já usa threads sem saber:** o giroscópio (módulo 5) e o sensor de linha (módulo 6) criam
uma thread que lê a placa o tempo todo; quando você chama `le_angulo_z()`, recebe na hora o último
valor que ela leu.

**O cuidado mais importante:** duas threads **não podem usar o mesmo equipamento** (o mesmo
barramento I2C, a mesma porta serial) ao mesmo tempo: as conversas se misturam. O módulo 7 (item
7.3) mostra como organizar isso com uma thread só para os sensores.

## Exercícios

1. Faça o robô andar 1 s para frente, 1 s para trás e piscar os LEDs em vermelho no fim.
2. Troque `Motores(True)` por `Motores(False)`. O que para de funcionar? O que você precisa
   acrescentar? (Dica: `atualiza_motores()`.)
3. Coloque um `time.sleep(8)` com os motores ligados, no simulador. O que acontece aos 5 s? Por quê?
4. Provoque um erro de propósito no meio do programa (ex.: `1/0`) e confira que o `finally` parou o
   robô.
