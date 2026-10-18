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

## 7.3 Tutorial: parar a 8 cm da parede

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

## 7.4 Seguir uma parede

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

## 7.5 Dois sensores do mesmo lado: o ângulo da parede

Na Maze, com um VL53 na frente e outro atrás do mesmo lado, separados por `D` mm:

```python
angulo = math.degrees(math.atan2(d_tras - d_frente, D))   # + = robô girado para a esquerda
```

Isso diz se o robô está torto em relação à parede, e serve para **corrigir a deriva do
giroscópio** (o exemplo da Maze faz isso a cada ladrilho com parede).

## 7.6 Limites do sensor

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
