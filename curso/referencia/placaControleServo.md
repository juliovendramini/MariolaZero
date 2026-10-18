# `PlacaControleServo` — servos inteligentes (MG90S + placa de controle)

Arquivo: `libs/placaControleServo.py` · `from placaControleServo import PlacaControleServo`

> Esta é a versão **unificada** (17/10/2026). Ela precisa do firmware unificado
> (`placaControleServo.ino` da mesma data) para `consulta_posicao()`, `define_id()` e a calibração
> do tempo de trava. Com firmware antigo, `consulta_posicao()` e `define_id()` mandam o servo para
> 1023 — atualize as placas antes.

## Para que serve

Um servo comum só recebe "vá para X graus" e você nunca sabe se ele chegou. O **servo
inteligente** é um MG90S cujo potenciômetro interno é lido por uma placinha (ATtiny) que:

* move o motor até a **posição pedida** (leitura do potenciômetro, 0 a 1023);
* **devolve a posição real** a cada comando;
* percebe quando o servo **travou** (está forçando e não se mexe) e desliga o motor para não
  queimar;
* fica num **barramento serial de um fio** com um **ID**: vários servos (e as placas de motor) no
  mesmo conector.

Uso típico: a **garra** e a **caçamba** da área de resgate.

## Como o firmware se comporta (para entender o que acontece no robô)

* **Controle liga-desliga com zona morta:** fora da zona (`alvo ± zona_morta`) a placa aplica a
  `potencia` para o lado certo; dentro, desliga o motor. Ou seja, **parado no alvo o servo não faz
  força**. Se algo empurrar para fora da zona, ele volta a corrigir.
* **Trava:** se o motor está ligado e a posição não muda por mais que o **tempo de trava** (1 s de
  fábrica, ajustável de 1 a 5 s), a placa desliga o motor por **2 s** e depois tenta de novo.
  Exemplo: dedos fechando numa bolinha param encostados nela → depois do tempo de trava o motor
  desliga e **a bolinha deixa de ser apertada**.
* **5 s sem nenhum pacote para a placa:** potência vai a 0 (motor desligado).
* **10 s sem pacote:** a placa reinicia (ID e tempo de trava continuam gravados na EEPROM).
* **Potência 0** = motor desligado (um braço com peso cai).

## Criando o objeto

### `PlacaControleServo(porta_serial, id_equipamento, baud_rate=250000)`
Recebe o **número da porta** (ex.: `Portas.SERIAL1`) e abre a serial sozinho.

```python
braco = PlacaControleServo(Portas.SERIAL1, 70)
dedo_esq = PlacaControleServo(Portas.SERIAL1, 71)
```

* Cada objeto abre a porta de novo (no Linux, abrir o mesmo dispositivo várias vezes funciona).
  Não use os servos ao mesmo tempo em **threads** diferentes: os pacotes se misturam no fio.
* Pode estar no mesmo barramento das placas de motor, desde que os IDs sejam diferentes.

## Constantes

| Constante | Valor | Uso |
|---|---|---|
| `ID_BROADCAST` | 254 | pacote para todas as placas (nenhuma responde) |
| `COMANDO_CALIBRACAO` | 65000 | uso interno (calibrar tempo de trava) |
| `COMANDO_CONSULTA` | 65001 | uso interno (consultar posição) |
| `TEMPO_DETECTA_TRAVA_MIN/MAX` | 1000 / 5000 | limites do tempo de trava (ms) |
| `DEBUG` | False | imprime cada pacote |
| `ultima_posicao` | — | última posição recebida |

## Movimento

### `move_servo(posicao, potencia=255, zona_morta=5)`
Manda ir para `posicao` (0 a 1023) com `potencia` (0 a 255). Devolve a **posição atual** (antes de
se mover), ou `None` se não respondeu.

* **`potencia`**: 255 = o mais rápido/forte. Menos potência = mais lento e mais suave (bom para
  baixar o braço sem bater). Abaixo de ~60 o MG90S nem sai do lugar.
* **`zona_morta`**: tolerância. Pequena demais e o servo fica "tremendo" em volta do alvo; grande
  demais e ele para longe.
* **Quando usar:** sempre que quiser mover; e também **para manter** uma posição por mais de 5 s
  (reenvie o mesmo comando de vez em quando, senão a placa desliga o motor).
* `move_servo` não espera chegar. Para esperar, veja `consulta_posicao`.

### `consulta_posicao(tentativas=3)`
Lê a posição **sem mudar o comando** (o servo continua indo para onde estava indo).

* **Quando usar:** para esperar um movimento terminar:

```python
def espera_chegar(servo, alvo, tolerancia=25, tempo_max=2.0):
    fim = time.time() + tempo_max
    while time.time() < fim:
        pos = servo.consulta_posicao()
        if pos is not None and abs(pos - alvo) <= tolerancia:
            return True
        time.sleep(0.02)
    return False          # travou no caminho (ou demorou demais)
```

* Também serve para **detectar se pegou algo**: dedos que fecharam mas pararam longe do
  "fechado" estão segurando um objeto.

### `le_posicao()`
Lê a posição mandando **potência 0**: **desliga o motor** até o próximo `move_servo`.

* **Quando usar:** só com firmware antigo, ou quando você quer mesmo soltar o servo.

### `para_servo()`
Potência 0 (motor desligado). Devolve a posição.

* **Quando usar:** no fim do programa, ou para soltar um mecanismo de propósito.

### `envia_comando(posicao, potencia, zona_morta=5, tentativas=3)`
O envio "cru"; devolve `{'id', 'posicao', 'potencia', 'zona_morta'}` ou `None`.

## Todas as placas de uma vez

### `envia_broadcast(posicao, potencia, zona_morta=5)`
Manda o mesmo comando para **todas** as placas do barramento (ninguém responde).

* **Quando usar:** raramente (ex.: desligar todos os servos de uma vez: `envia_broadcast(512, 0)`).
  Cuidado: placas de motor no mesmo fio também recebem o pacote (ID 254 não é delas, mas confira).

### `calibrar_tempo_detecta_trava_todos(tempo_ms)`
Grava o tempo de trava em todas as placas (broadcast, sem confirmação).

## Configuração (uma vez por placa)

### `PlacaControleServo.buscar_servos(porta_serial, baud_rate=250000)` *(estático)*
Varre os IDs 0 a 253 e devolve `[{'id', 'posicao'}, ...]`. **Deixa cada servo encontrado com o
motor desligado.**

* **Quando usar:** para descobrir os IDs dos servos ligados.

### `define_id(novo_id)`
Grava um novo ID (0 a 253) na placa que hoje tem o ID do objeto, e passa a usar o novo.
`True` se o pacote foi enviado.

* **Como trocar o ID de uma placa nova:** ligue **só ela** no barramento, descubra o ID com
  `buscar_servos`, crie o objeto com esse ID e chame `define_id(...)`. Rode `buscar_servos` de novo
  para conferir.

### `calibrar_tempo_detecta_trava(tempo_ms, tentativas=3)`
Grava o tempo de trava desta placa (1000 a 5000 ms). `True` se confirmou.

* **Quando aumentar:** dedos de garra que precisam continuar apertando um objeto enquanto o braço
  se move. Com 1 s, eles soltam a bolinha 1 s depois de encostar nela. O robô de exemplo usa 3000.

## Calibrando as posições do seu mecanismo

As posições não são graus: são a leitura do potenciômetro **montado no seu robô**. Para cada
servo, anote as leituras nas posições que importam (braço embaixo/em cima, dedo aberto/fechado,
porta fechada/abrindo para cada lado):

1. `para_servo()` (motor solto) e coloque o mecanismo **com a mão** na posição desejada;
2. `consulta_posicao()` e anote;
3. teste com `move_servo(valor_anotado)`.

Guarde os valores como constantes no topo do seu `robo.py` (e no `resgate` do `robo_4x4.json` do
simulador).

## Erros comuns

| Sintoma | Causa provável |
|---|---|
| Servo vai para 1023 ao consultar/trocar ID | firmware antigo na placa |
| Dedos soltam a bolinha sozinhos | tempo de trava curto (calibre para 2–3 s) ou o braço se mexeu depois da trava |
| Braço cai quando o programa espera | 5 s sem pacote ou `le_posicao()`/`para_servo()`; ou parado na zona morta com peso |
| Servo treme parado | zona morta pequena ou potência alta demais |
| `None` em tudo | ID errado, porta errada ou firmware/baud diferente |

## No simulador

O simulador da Line emula o firmware unificado (`resgate` no `robo_4x4.json`: IDs 70 a 73,
posições, velocidade do MG90S, tempo de trava 3000). O braço cai sem força a não ser todo
levantado, e os dedos só seguram enquanto empurram.
