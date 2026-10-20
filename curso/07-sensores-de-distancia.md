# Módulo 7 — Sensores de distância (VL53L0X)

**Objetivo:** ler vários VL53L0X sem deixar o robô lento, parar a uma distância certa da parede,
seguir uma parede e entender os limites do sensor (cone, alcance, altura, leitura velha).

Referência: [`VL53L0X`](referencia/vl53.md). Códigos:
[`codigos/05_distancia/`](codigos/05_distancia/).

## 7.1 Vários sensores, do jeito simples e do jeito rápido

[`le_distancias.py`](codigos/05_distancia/le_distancias.py)

```python
sensores = {
    'esquerda': VL53L0X(Portas.I2C1),
    'direita': VL53L0X(Portas.I2C3),
    'frente': VL53L0X(Portas.I2C5),
}

# simples: uma medida de cada vez (cada uma espera ~33 ms)
for nome, s in sensores.items():
    print(nome, s.read_range_single_millimeters())

# rápido: dispara todos, espera UMA vez, lê todos
for s in sensores.values():
    s.solicita_leitura()
time.sleep(0.034)
leituras = {nome: s.leitura_mm() for nome, s in sensores.items()}
```

No simulador: 132 ms (simples) contra 73 ms (rápido) para três sensores. Com 5 sensores a
diferença é maior. **8190** significa "nada à vista".

## 7.2 Ler sem parar o laço

No seguidor de linha você não pode esperar 33 ms a cada volta. Peça a medida, continue o laço e
só pegue o resultado quando ele já estiver pronto:

```python
frente.solicita_leitura()
t_pedido = time.time()
dist_frente = 8190
while True:
    if time.time() - t_pedido > 0.036:
        dist_frente = frente.leitura_mm()    # medida pedida na volta anterior: já pronta
        frente.solicita_leitura()            # pede a próxima
        t_pedido = time.time()
    ...                                      # segue a linha usando dist_frente
    time.sleep(0.01)
```

O `robo.py` do exemplo da Line faz isso no método `distancia(nome)`.

> **Leitura velha:** a medida descreve o mundo **de quando foi pedida**. Depois de girar 90°, a
> primeira leitura ainda é da parede antiga. Descarte-a ou use `read_range_single_millimeters()`.

## 7.3 Uma thread só para os sensores I2C

[`thread_sensores.py`](codigos/05_distancia/thread_sensores.py) (simulador da Line, robô 4x4)

Se você ainda não sabe o que é uma thread, leia antes o [módulo 3, item 3.7](03-primeiro-programa.md).

### A regra: o I2C só pode ser usado por uma thread

Todos os VL53L0X e TCS34725 do Mariola estão no **mesmo barramento** (I2C 1), atrás do **mesmo
multiplexador**. Cada leitura é uma conversa em vários passos: escolher o canal no mux, escrever
um registrador, ler a resposta. Se duas threads usam o I2C ao mesmo tempo, os passos se misturam:

```
thread A: escolhe o canal 1 (VL53 da esquerda)
thread B: escolhe o canal 6 (TCS da frente)
thread A: lê a distância          ← está lendo do canal 6: valor errado ou OSError
```

O erro não acontece sempre, só quando as duas se cruzam: é o tipo de problema que some na bancada
e aparece na competição. Por isso: **todos os sensores I2C são lidos por uma thread só.** O mesmo
vale para a tela e o teclado (outro barramento, o I2C 0) e para a serial dos motores.

### A solução: uma thread lê tudo e guarda em atributos

Uma classe cria os sensores, e uma thread dela lê **todos em sequência**, sem parar, e guarda os
valores em atributos. O resto do programa (seguir linha, decidir, mexer os motores) **só lê os
atributos** e nunca chama um método do VL53 ou do TCS:

```python
class SensoresI2C:
    def __init__(self):
        self.vl53 = {'esquerda': VL53L0X(Portas.I2C1), 'frente': VL53L0X(Portas.I2C5), ...}
        self.tcs = {'frente': TCS34725(Portas.I2C6), ...}
        self.dist = {nome: 8190 for nome in self.vl53}   # o que o programa lê
        self.cor = {nome: (0, 0, 0, 0) for nome in self.tcs}
        self.t_leitura = 0.0
        self.erro = None

    def le_tudo(self):
        t = time.time()
        for s in self.vl53.values():               # 1) pede a medida em TODOS os VL53
            s.solicita_leitura()
        cor = {n: s.le_valores() for n, s in self.tcs.items()}    # 2) lê os TCS enquanto eles medem
        dist = {n: s.leitura_mm() for n, s in self.vl53.items()}  # 3) pega os resultados
        self.dist = dist                            # troca o dicionário inteiro de uma vez
        self.cor = cor
        self.t_leitura = t

    def _laco(self):                                # roda na thread
        while self.rodando:
            try:
                self.le_tudo()
            except (OSError, TimeoutError) as e:
                self.erro = e
                time.sleep(0.05)
            time.sleep(0.002)
```

E no programa:

```python
sensores = SensoresI2C()
sensores.inicia()                       # cria e começa a thread
while True:
    if sensores.dist['frente'] < 100:   # só lê o atributo: instantâneo
        desvia()
    segue_linha()
    time.sleep(0.01)
```

Por que cada detalhe:

* **Trocar o dicionário inteiro** (`self.dist = dist`) em vez de mudar uma chave de cada vez: quem
  lê nunca pega metade velha e metade nova.
* **`t_leitura`** diz de quando é a medida. Se você precisa de uma leitura **depois** de um giro,
  espere `t_leitura` passar do momento em que o giro acabou.
* **`try/except` dentro da thread:** um erro numa thread não para o programa nem aparece na tela;
  a thread simplesmente morre e os valores congelam. Guarde o erro num atributo e olhe por ele.
* **`time.sleep` no laço da thread:** sem ele, a thread ocupa o processador e atrapalha o resto
  (e, no simulador, o relógio não anda).

### O truque do VL53: pedir, fazer outra coisa, pegar

Uma medida do VL53 leva ~33 ms, e quase todo esse tempo é o sensor trabalhando **sozinho**: o
programa só fica esperando. A função que pede e espera (`read_range_single_millimeters()`) joga
esse tempo fora. Por isso a volta da thread é **partida em três**:

1. `solicita_leitura()` em **todos** os VL53: os sensores começam a medir juntos;
2. **enquanto eles medem, faz outra coisa**: no exemplo, ler os TCS; poderia ser outro sensor
   I2C, uma conta, filtrar as leituras anteriores... qualquer coisa que não dependa dessa medida;
3. `leitura_mm()` em cada VL53, em sequência: a essa altura a medida já está pronta (se não
   estiver, ela espera só o que falta).

Tempo de uma volta com os 4 VL53 e os 2 TCS do robô 4x4 (simulador, que imita os 33 ms do VL53):

| Jeito | Tempo por volta |
|---|---|
| `read_range_single_millimeters()` um de cada vez, depois os TCS | ~152 ms |
| pede todos, pega todos, depois os TCS | ~54 ms |
| pede todos, **TCS no meio**, pega todos | ~54 ms no simulador |

A grande diferença está entre a primeira e a segunda linha: em vez de quatro esperas de 33 ms, uma
só. A terceira mostra **onde** pôr o resto do trabalho: dentro da espera, ele sai "de graça". Ler um
TCS é rápido (só algumas leituras de registrador), então no simulador, onde a conversa I2C não gasta
tempo, a terceira linha dá igual à segunda; no robô ela fica um pouco menor. Quanto mais trabalho você
puser no meio, mais ganha.

Com a thread, o laço principal do exemplo dá ~100 voltas por segundo enquanto a thread lê todos os
sensores ~20 vezes por segundo, cada um no seu ritmo.

## 7.4 Tutorial: parar a 8 cm da parede

[`para_na_parede.py`](codigos/05_distancia/para_na_parede.py) (simulador da **Maze**, que tem
paredes por todo lado)

```python
frente.solicita_leitura()
while True:
    time.sleep(0.035)
    d = frente.leitura_mm()
    frente.solicita_leitura()
    falta = d - ALVO
    if falta <= 0:
        break
    vel = max(12, min(50, falta * 0.3))       # proporcional de novo!
    anda(vel, vel)
anda(0, 0)
```
```
parei a 79 mm da parede
```

## 7.5 Seguir uma parede

Com um sensor do lado, o mesmo controle proporcional mantém o robô a uma distância da parede:

```python
DIST = 60                                    # mm da parede, do lado direito
erro = d_direita - DIST                       # + = longe da parede
correcao = max(-15, min(15, erro * 0.4))
anda(VEL + correcao, VEL - correcao)          # longe: vira para a direita
```

Cuidados que o exemplo da área de resgate teve que resolver:

* **Limite o ângulo:** se a correção for grande, o robô fica de lado e o sensor passa a medir
  "na diagonal" (mais longe do que é), e ele vira ainda mais. Limite a diferença entre o rumo atual
  e o rumo da parede (no exemplo, ±12°, pelo giroscópio).
* **Fim da parede:** a leitura salta para longe (canto aberto, vão de saída). Trate isso como um
  evento ("acabou a parede"), não como erro grande.
* **Parede na frente:** pare e gire antes de bater (sensor da frente).

## 7.6 Dois sensores do mesmo lado: o ângulo da parede

Na Maze, com um VL53 na frente e outro atrás do mesmo lado, separados por `D` mm:

```python
angulo = math.degrees(math.atan2(d_tras - d_frente, D))   # + = robô girado para a esquerda
```

Isso diz se o robô está torto em relação à parede, e serve para **corrigir a deriva do
giroscópio** (o exemplo da Maze faz isso a cada ladrilho com parede).

## 7.7 Limites do sensor

| Limite | Consequência | O que fazer |
|---|---|---|
| Cone de ~25° | perto de quinas, vê a outra parede | leia longe das quinas; confirme com outro sensor |
| Alcance ~1,2–2 m | 8190 no campo aberto | trate 8190 como "longe" |
| Ruído de alguns mm | alinhamento treme | média de 3–4 leituras |
| **Altura** | um VL53 a 5 cm do chão não vê uma bolinha de 4,5 cm | use o sensor baixo (na garra) para vítimas |
| Objetos escuros/espelhados | leitura falha | teste com os materiais do campo |

## Exercícios

1. Faça o robô parar a 5 cm, 10 cm e 20 cm da parede. Meça com a régua o erro de cada um.
2. No simulador da Maze, faça o robô andar pelo corredor mantendo-se no centro (use os dois lados:
   `erro = d_esquerda - d_direita`).
3. Faça a função `tem_parede(lado)` que usa 3 leituras e devolve `True` se a maioria for menor que
   150 mm.
4. **No robô**, peça uma medida (`solicita_leitura()`), gire 90° e imprima a primeira
   `leitura_mm()` depois do giro e a segunda. Elas diferem? Por quê? (O simulador mede na hora em
   que o resultado é lido, então lá a primeira leitura já é a nova: veja as limitações no módulo 11.)
5. Faça o erro do 7.3 de propósito: deixe a thread da `SensoresI2C` rodando e, no programa
   principal, leia o VL53 da frente direto com `read_range_single_millimeters()` durante 3 s (com
   `try/except`). Compare com a thread sozinha: quantas voltas por segundo ela dá e quantos erros
   aparecem nas duas threads?
