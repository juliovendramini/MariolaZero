# Módulo 6 — O sensor de linha: ler, calibrar e seguir

**Objetivo:** entender os valores do Pro1616, calcular onde está a linha, construir um seguidor
liga-desliga, depois um P e um PD, e reconhecer cores (verde, vermelho, prata) sem se enganar.

Referência: [`CorReflexao`](referencia/sensorCorReflexao.md). Códigos:
[`codigos/04_linha/`](codigos/04_linha/). Mapa: `mapas/curso_pista.json` (também em
`simuladorLine/mapas/`; só retas e curvas, sem interseção).

## 6.1 O que o sensor vê

![O sensor Pro1616 visto de baixo](imagens/sensor_linha.jpg)

Na foto, a face que fica virada para o chão:

* a fileira de sensores IR (a faixa preta comprida);
* logo atrás dela, os três sensores de cor TCS34725, cada um entre dois LEDs brancos SMD;
* abaixo de cada TCS, um LED branco de 5 mm de alto brilho (as lentes redondas). Ele reforça a
  iluminação e é o que permite ler a reflexão alta das superfícies refletivas, como a fita prata;
* no canto de cima, o botão de reset da placa.

Visto de baixo, a esquerda e a direita do robô aparecem trocadas. Visto de cima, com a frente do
robô para cima:

```
              ← esquerda do robô                     direita →
 IR:   [canal 0: 3 ITR] [canal 1: 3 ITR] [canal 2: 3 ITR] [canal 3: 3 ITR]
 TCS:        [TCS 1]           [TCS 2 (meio)]          [TCS 3]
```

* **IR (4 canais):** `0 = preto`, `~100 = branco`, `> 100 = prata`. Rápido (~50 leituras/s). É
  com ele que se segue a linha.
* **TCS (3 sensores de cor):** R, G, B, C com **branco ≈ 127**. É com eles que se veem as cores.

Rode [`le_sensor.py`](codigos/04_linha/le_sensor.py) e arraste o robô (no simulador) por cima da
linha, do verde, da fita prata e da vermelha:

```bash
python simulador.py --programa ../curso/codigos/04_linha/le_sensor.py
```
```
IR [0, 0, 0, 0] | TCS [[0, 0, 0, 0], [0, 0, 0, 0], [0, 0, 0, 0]] | cores ['preto', 'preto', 'preto']
IR [98, 35, 36, 104] | TCS [[125, 126, 126, 127], [5, 6, 4, 4], [126, 126, 124, 126]] | cores ['branco', 'preto', 'branco']
```

Repare na **primeira linha: tudo zero**. A thread do sensor ainda não tinha recebido nada. O robô
"veria preto" no primeiro instante. Por isso, logo depois de criar o sensor:

```python
while not sensor.conectado:
    time.sleep(0.01)
```

## 6.2 Calibrar

Dois níveis de calibração, com propósitos diferentes:

1. **Do firmware** (`calibra_branco()` no branco, `calibra_preto()` no preto): define o que é "0" e
   "100" no IR e "127" no TCS. Faça quando o sensor for novo, quando mudar a altura dele ou quando
   o branco estiver lendo longe de 100. Fica gravado no sensor.
2. **Das cores** (`aprende_cor()`): ensina à lib como cada cor aparece **naquele campo, com aquela
   luz**. Faça no **tempo de calibração** de cada competição. Programa pronto:
   `simuladorLine/exemplo_aluno/calibra_cores.py` (branco com os 3 TCS; preto, verde e vermelho só
   com o TCS do meio, porque a fita é estreita).

## 6.3 Onde está a linha?

Com 4 canais, dá para calcular a posição da linha com uma **média ponderada**: cada canal "vota"
na sua posição, com peso igual a "quão preto" ele vê.

```python
Y_CANAIS = [26.6, 8.9, -8.9, -26.6]     # mm do centro (+ = esquerda), no Pro1616

def posicao_linha():
    ir = sensor.le_reflexao()
    pesos = [max(0, min(100, 100 - v)) / 100 for v in ir]   # 1 = preto, 0 = branco
    if sum(pesos) < 0.3:
        return None                                       # não vê linha
    return sum(p * y for p, y in zip(pesos, Y_CANAIS)) / sum(pesos)
```

* Linha embaixo dos canais 1 e 2 → posição ≈ 0 (centro).
* Linha mais no canal 0 → posição positiva (à esquerda).
* Isso dá um número **contínuo** (não só "esquerda/direita"), ótimo para o controle proporcional.

## 6.4 Seguidor 1: liga-desliga

[`seguidor_liga_desliga.py`](codigos/04_linha/seguidor_liga_desliga.py)

```python
ir = sensor.le_reflexao()
esq_preto = ir[1] < PRETO
dir_preto = ir[2] < PRETO
if esq_preto and not dir_preto:
    anda(5, 35)
elif dir_preto and not esq_preto:
    anda(35, 5)
else:
    anda(30, 30)
```

Funciona nas retas, mas **balança** o tempo todo e se perde nas curvas fechadas (no
`curso_pista.json` ele leva 4 LoPs). Só tem três "intensidades" de correção: nenhuma ou toda.

## 6.5 Seguidor 2: proporcional (P)

A correção passa a ser **proporcional ao erro** (a posição da linha):

```python
erro = posicao_linha()              # mm; queremos 0
correcao = KP * erro
anda(VEL - correcao, VEL + correcao)
```

Linha 10 mm à esquerda, `KP = 1.4` → correção 14: roda esquerda 21, direita 49 → curva suave para
a esquerda. Linha 2 mm à esquerda → correção quase nenhuma.

* `KP` pequeno: o robô "atrasa" nas curvas e sai delas.
* `KP` grande: zigue-zague na reta (passa do centro de um lado para o outro).

## 6.6 Seguidor 3: proporcional-derivativo (PD)

O zigue-zague acontece porque o P só olha **onde** a linha está, não **para onde ela está indo**.
O termo **derivativo** olha a **variação** do erro:

```python
correcao = KP * erro + KD * (erro - erro_anterior)
erro_anterior = erro
```

Se o erro está diminuindo rápido (o robô está voltando para a linha), `erro - erro_anterior` é
negativo e **freia** a correção antes de passar do ponto. É o que amortece o balanço.

Código completo: [`seguidor_p.py`](codigos/04_linha/seguidor_p.py) (com `KD = 0` vira só P).
Com `KP = 1.4` e `KD = 5.0`, o robô de esteira completa o `curso_pista.json` **sem LoP** e para na
chegada:

```bash
python simulador.py --robo robo_esteira.json --mapa mapas/curso_pista.json --programa ../curso/codigos/04_linha/seguidor_p.py
```

### Como ajustar KP e KD (receita)
1. `KD = 0`. Aumente `KP` até o robô fazer as curvas, mesmo balançando.
2. Aumente `KD` até o balanço sumir. Se o robô começar a "tremer", `KD` passou do ponto.
3. Aumente `VEL` e repita. Mais velocidade pede mais `KD`.
4. Ajuste **no simulador**, confirme **no robô** (as constantes quase sempre mudam um pouco).

> **E o I (integral)?** Num seguidor de linha ele quase não ajuda (a linha muda o tempo todo) e
> atrapalha nas curvas. O PID dos motores (dentro da placa) é que usa o I.

### Quando a linha some
`posicao_linha()` devolve `None`: o robô saiu da linha (curva fechada demais) ou chegou num **gap**
(até 20 cm sem linha). O exemplo gira para o lado em que viu a linha por último. Num programa
completo, primeiro anda reto um pouco pelo giroscópio (pode ser gap) — veja o módulo 14.

## 6.7 Cores: verde, vermelho e prata

```python
sensor.usa_cores(['branco', 'preto', 'verde', 'vermelho', 'prata'])
cores = sensor.cores()          # ['branco', 'verde', 'preto'] → [TCS1, TCS2, TCS3]
```

* **Verde** antes de uma interseção: `cores()[0] == 'verde'` = marcador à esquerda,
  `cores()[2] == 'verde'` = à direita, os dois = meia-volta.
* **Vermelho** (2 ou mais TCS): fita da chegada → parar mais de 5 s.
* **Prata**: fita da entrada da área de resgate.

### A pegadinha: o TCS fica atrás do IR

Numa curva, os IR já estão no branco enquanto o TCS ainda está na linha preta. Quando a lib usava
o IR do lado de cada TCS para classificar a cor, essa mistura (escuro no TCS, claro no IR) caía em
**"vermelho" ou "verde"**: no `curso_pista.json`, o seguidor parava "na chegada" no meio da pista.
Por isso o IR agora vem **desligado** na classificação (`usar_ir=False`, o padrão), e o escuro vai
para o preto.

Mesmo assim, **uma leitura só não basta para decisões grandes** (parar na chegada, virar numa
interseção): a borda de uma fita, um reflexo ou um palito podem enganar uma leitura. Confirme em
2–3 leituras seguidas, ou pelo RGB, como o `seguidor_p.py` faz:

```python
def eh_vermelho(tcs):
    r, g, b, c = sensor.le_rgbc(tcs)
    return sensor.cor(tcs) == 'vermelho' and r > 1.8 * g and r > 1.8 * b and c > 20

def eh_verde(tcs):
    r, g, b, c = sensor.le_rgbc(tcs)
    return sensor.cor(tcs) == 'verde' and g > 1.4 * r and g > 1.15 * b and c > 20
```

### Prata x lombada x rampa
O IR passa de 100 no prata, mas também quando o sensor chega **mais perto do chão** (em cima da
lombada, no pé da rampa). O exemplo da Line só aceita a entrada da área com 3 canais entre 140 e
235, o robô nivelado (giroscópio) e 2 TCS dizendo "prata".

## Exercícios

1. Rode o `seguidor_p.py` com `KD = 0` e depois com `KD = 5`. Conte os LoPs e o tempo de prova.
2. Aumente `VEL` para 50 e reajuste `KP` e `KD` até completar sem LoP.
3. Imprima `posicao_linha()` numa reta e numa curva. Qual a faixa de valores?
4. Troque `Y_CANAIS` pelo índice dos canais (`[1.5, 0.5, -0.5, -1.5]`). O que muda nos ganhos?
5. Faça o robô parar 6 s em qualquer fita vermelha e depois continuar (útil para testar a
   detecção sem acabar a rodada).
6. Use `sensor.distancias(2)` para ver o quão perto o verde fica do preto no seu robô.
