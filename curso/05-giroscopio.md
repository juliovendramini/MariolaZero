# Módulo 5 — Giroscópio: girar certo e andar reto

**Objetivo:** girar ângulos exatos, andar reto corrigindo o desvio e perceber rampas, usando o
giroscópio. Aprender o **controle proporcional**, que vai aparecer em todo o resto do curso.

Referência: [`Giroscopio`](referencia/giroscopio.md). Código:
[`codigos/03_giroscopio/gira_e_anda_reto.py`](codigos/03_giroscopio/gira_e_anda_reto.py).

## 5.1 Lendo o ângulo

```python
from giroscopio import Giroscopio
from portas import Portas

giro = Giroscopio(Portas.SERIAL5)

def z():
    """Ângulo em graus, positivo = esquerda (anti-horário), sem voltar a zero em 360."""
    return -giro.le_angulo_z()
```

* O giroscópio do Mariola dá o Z **positivo no sentido horário**. A função `z()` troca o sinal
  para "positivo = esquerda", que é o padrão da matemática (ângulos crescem no anti-horário) e
  combina com `anda(-v, v)` = girar para a esquerda.
* O Z **acumula**: duas voltas para a esquerda = 720. Isso é bom (veja 5.3).
* A leitura é instantânea (uma thread lê a placa sem parar).

No começo da rodada, com o robô parado na direção que vai ser o "zero":
```python
giro.reseta_z()
time.sleep(0.1)
```

## 5.2 Girar até um ângulo: controle proporcional

O jeito ingênuo — "gire a 40 até passar do alvo" — erra sempre: quando o programa percebe que
passou, o robô já girou mais alguns graus. O jeito certo é **diminuir a velocidade conforme chega
perto**:

```python
def gira_para(alvo, tolerancia=1.5, tempo_max=4.0):
    inicio = time.time()
    while time.time() - inicio < tempo_max:
        erro = alvo - z()
        if abs(erro) <= tolerancia:
            break
        v = max(15, min(50, abs(erro) * 0.8))   # longe: rápido; perto: devagar
        if erro < 0:
            v = -v
        anda(-v, v)                               # esquerda para trás, direita para frente
        time.sleep(0.01)
    anda(0, 0)
```

Isso é um **controlador proporcional (P)**: a ação (`v`) é proporcional ao **erro** (quanto falta).

* `0.8` é o **ganho** (Kp). Maior = mais rápido, mas passa do alvo e volta (oscila). Menor = mais
  suave, mas lento.
* `max(15, ...)`: velocidade mínima. Abaixo dela o atrito vence o motor e o robô para antes do
  alvo.
* `min(50, ...)`: velocidade máxima, para não derrapar.
* `tempo_max`: **sempre** ponha um limite. Se a roda patina ou o robô está preso, o laço não pode
  ficar para sempre.

## 5.3 Alvos acumulados

Compare:

```python
# ERRADO: cada giro parte de onde o anterior parou (os erros se somam)
gira_para(z() + 90)

# CERTO: guarda a direção desejada e soma 90 a cada curva
direcao += 90
gira_para(direcao)
```

Se o primeiro giro parou em 91°, o "errado" vai para 181°, depois 272°... O "certo" vai para 180,
270, 360 — o erro de um giro não passa para o próximo. Isso é essencial na Maze, onde o robô gira
centenas de vezes.

## 5.4 Andar reto

Mesmo com os dois motores na mesma velocidade, o robô desvia (rodas diferentes, chão irregular).
Corrija pelo giroscópio, de novo com um controle proporcional:

```python
def anda_reto(segundos, vel=40):
    alvo = z()
    inicio = time.time()
    while time.time() - inicio < segundos:
        erro = alvo - z()                         # + = robô virou para a direita
        correcao = max(-15, min(15, erro * 2.0))
        anda(vel - correcao, vel + correcao)
        time.sleep(0.01)
    anda(0, 0)
```

Se o robô virou para a direita, `erro` é positivo, a roda direita acelera e a esquerda freia: ele
volta. Junte com o encoder do módulo 4 e você tem o `anda_mm()` dos programas de exemplo.

## 5.5 O tutorial completo: um quadrado

```bash
python simulador.py --robo robo_esteira.json --programa ../curso/codigos/03_giroscopio/gira_e_anda_reto.py
```
```
[robô] alvo 90°, giroscópio 90°
[robô] alvo 180°, giroscópio 181°
[robô] alvo 270°, giroscópio 270°
[robô] alvo 360°, giroscópio 360°
```

## 5.6 Inclinação: rampas e lombadas

`giro.le_angulo_x()` dá a inclinação para frente (no robô de exemplo; confira no seu):

```python
inclinacao = giro.le_angulo_x()
if inclinacao > 8:
    print('subindo a rampa')        # ex.: mais velocidade, não confundir com obstáculo
elif inclinacao < -8:
    print('descendo')               # ex.: menos velocidade, freio HOLD
```

Usos na Line: aumentar a velocidade na subida, frear na descida, **não aceitar "prata"** com o
robô inclinado (no pé da rampa o sensor chega perto do chão e o branco parece prata), perceber a
gangorra virando.

## 5.7 Deriva e calibração

Parado, o Z pode "andar" devagar (fração de grau por minuto). Em 8 minutos de Maze isso vira
vários graus. Soluções:

* `giro.calibra()` com o robô **imóvel** (fica gravado na placa; não precisa em todo programa);
* **corrigir com o mundo**: encostar na parede (para-choque com os dois botões apertados) ou medir
  o ângulo da parede com dois VL53 do mesmo lado, e ajustar a `direcao` (o exemplo da Maze faz
  isso). Na Line, a própria linha corrige.

## Exercícios

1. Mude o ganho `0.8` para `3.0` e para `0.2`. Descreva o giro nos dois casos.
2. Tire o `max(15, ...)` da velocidade. O que acontece perto do alvo?
3. Faça o robô andar em "8" (dois quadrados, um para cada lado) e voltar ao início. Quanto ele
   erra no fim?
4. Escreva `direcao_mais_proxima()` que devolve o múltiplo de 90° mais perto do `z()` atual. Para
   que isso serve depois de uma manobra de desvio?
5. No mapa `completo.json`, imprima `le_angulo_x()` enquanto o robô de exemplo sobe a rampa.
