# `PlacaControleServo` — servos inteligentes (MG90S + placa de controle)

Arquivo: `libs/placaControleServo.py` · `from placaControleServo import PlacaControleServo`

> Versão de **22/10/2026**, para o firmware `placaControleServo.ino` de **21/10/2026** (controle
> proporcional e polaridade). Com o firmware unificado de 17/10, o movimento, a consulta, a troca
> de ID e a calibração da trava funcionam, mas as funções de controle e de polaridade devolvem
> `None`/`False`. Com firmware **mais antigo** que 17/10, `consulta_posicao()` e `define_id()`
> mandam o servo para 1023: atualize as placas antes.

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

* **Zona morta:** dentro de `alvo ± zona_morta` a placa desliga o motor. Ou seja, **parado no alvo
  o servo não faz força**. Se algo empurrar para fora da zona, ele volta a corrigir.
* **Dois modos de controle** fora da zona (veja "Controle de posição", abaixo):
  * **proporcional** (padrão de fábrica): a força diminui conforme chega perto do alvo e freia se
    está chegando rápido demais; não passa do ponto nem fica vibrando em volta do alvo. Depois de
    parar, só volta a corrigir quando o erro passa da zona morta mais a **histerese** (4 contagens);
  * **liga-desliga** (o comportamento antigo): `potencia` cheia até entrar na zona morta. Chega
    mais rápido, mas vibra em volta do alvo.
  A `potencia` do comando é sempre o **teto** de força, nos dois modos.
* **Polaridade:** em alguns servos o motor está ligado ao contrário do potenciômetro. Na primeira
  vez que liga, a placa dá dois pulsos curtos, descobre o lado certo sozinha e grava (veja
  "Polaridade", abaixo).
* **Trava:** se o motor está ligado e a posição não muda por mais que o **tempo de trava** (1 s de
  fábrica, ajustável de 1 a 5 s), a placa desliga o motor por **2 s** e depois tenta de novo.
  Exemplo: dedos fechando numa bolinha param encostados nela → depois do tempo de trava o motor
  desliga e **a bolinha deixa de ser apertada**.
* **5 s sem nenhum pacote para a placa:** potência vai a 0 (motor desligado).
* **10 s sem pacote:** a placa reinicia (ID, tempo de trava, polaridade e configuração do controle
  continuam gravados na EEPROM).
* **Potência 0** = motor desligado (um braço com peso cai).

## Criando o objeto

### `PlacaControleServo(porta_serial, id_equipamento, baud_rate=250000, porta_fixa=None, timeout_porta_fixa=0.05)`
Recebe o **número da porta** (ex.: `Portas.SERIAL1`) e abre a serial sozinho.

* **`porta_fixa`** (para testar a placa direto no computador, com um conversor USB-serial): o nome
  da porta no sistema (`'COM7'`, `'/dev/ttyUSB0'`). Aí a `porta_serial` é ignorada e a classe
  `Portas` nem precisa existir: `PlacaControleServo(None, 5, porta_fixa='COM7')`. O
  `timeout_porta_fixa` é maior que o normal porque conversores USB no Windows têm ~16 ms de atraso.

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
| `COMANDO_POLARIDADE` / `COMANDO_CONTROLE` | 65002 / 65003 | uso interno (polaridade, controle) |
| `TEMPO_DETECTA_TRAVA_MIN/MAX` | 1000 / 5000 | limites do tempo de trava (ms) |
| `MODO_LIGA_DESLIGA` / `MODO_PROPORCIONAL` | 0 / 1 | modos de controle |
| `POLARIDADE_NORMAL` / `POLARIDADE_INVERTIDA` / `POLARIDADE_NAO_CALIBRADA` | 0 / 1 / 255 | polaridade lida da placa |
| `AUTODETECCAO_NAO_RODOU` / `_SUCESSO` / `_FALHOU` | 0 / 1 / 2 | resultado da última autodetecção |
| `ESCALA_GANHO` | 16 | KP, KD e KI são gravados em 1/16 |
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

### `PlacaControleServo.buscar_servos(porta_serial, baud_rate=250000, porta_fixa=None, timeout_porta_fixa=0.05)` *(estático)*
Varre os IDs 0 a 253 e devolve `[{'id', 'posicao'}, ...]`. **Deixa cada servo encontrado com o
motor desligado.** Com `porta_fixa='COM7'`, varre direto pelo computador.

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

## Controle de posição

A configuração fica gravada na placa (EEPROM): ajuste uma vez, na bancada, e não precisa repetir
no programa da competição.

| Parâmetro | Padrão | O que é |
|---|---|---|
| `modo` | `MODO_PROPORCIONAL` | ou `MODO_LIGA_DESLIGA` |
| `kp` | 3.0 | força por contagem de erro (0 a 15.9, em passos de 1/16) |
| `kd` | 8.0 | freio proporcional à velocidade (0 a 15.9) |
| `pwm_minimo` | 60 | força mínima para vencer o atrito (0 a 255) |
| `histerese` | 4 | contagens além da zona morta para voltar a corrigir depois de parar |
| `periodo_ms` | 5 | de quanto em quanto tempo a velocidade é medida (1 a 100 ms) |
| `ki` | 0.0 (desligado) | termo I: soma força aos poucos enquanto o erro continua (0 a 15.9) |
| `faixa_integral` | 40 | o termo I só acumula com o erro até aqui; alvo novo mais longe que isso zera o termo I |
| `limite_integral` | 150 | força máxima do termo I |

No modo proporcional: força = `kp`·erro − `kd`·velocidade + termo I, entre o `pwm_minimo` e a
`potencia` do comando. Se o servo está chegando rápido demais, a conta troca de sinal e a placa
**freia** em vez de empurrar.

### `configura_controle(modo=None, kp=None, kd=None, pwm_minimo=None, histerese=None, periodo_ms=None, ki=None, faixa_integral=None, limite_integral=None, tentativas=3)`
Muda **só** o que for passado e grava. `True` se a placa confirmou todos os valores.

```python
braco.configura_controle(kp=3, kd=8, ki=0.25)
```

* **Como ajustar (na bancada):** `kp` alto ou `kd` baixo demais = passa do ponto; `kd` alto demais
  = chega devagar, aos trancos; `pwm_minimo` baixo demais = para antes do alvo. Ligue o `ki` por
  último, com valores pequenos (ex.: 0.25), se um peso constante (o braço) deixar o servo parado
  antes do alvo; `ki` alto demais = oscila devagar em volta do alvo.

### `define_modo_controle(modo, tentativas=3)`
Atalho para `configura_controle(modo=...)`.

* **Quando usar o liga-desliga:** quando chegar rápido importa mais que parar suave.

### `le_configuracao_controle(tentativas=3)`
Devolve um `dict` com os 9 parâmetros (`kp`, `kd` e `ki` em número com vírgula), ou `None`.

### `restaura_controle_padrao(tentativas=3)`
Volta tudo aos valores da tabela. `True` se confirmou.

### `configura_controle_todos(...)`
Igual ao `configura_controle`, para todas as placas do barramento (broadcast, sem confirmação).

## Polaridade

Se o motor de um servo estiver ligado ao contrário do potenciômetro, o controle empurra o servo
**para longe** do alvo (até o fim de curso). A placa descobre isso sozinha na primeira vez que liga;
se errar (ou se o servo foi trocado), corrija com estas funções.

### `consulta_polaridade(tentativas=3)`
Devolve `{'polaridade': ..., 'autodeteccao': ...}` (constantes `POLARIDADE_*` e
`AUTODETECCAO_*`), ou `None`.

### `define_polaridade(invertida, tentativas=3)`
Força a polaridade (`True` = invertida) e grava. `True` se confirmou.

### `inverte_polaridade(tentativas=3)`
Lê a polaridade atual e grava a oposta. Devolve a nova (`POLARIDADE_NORMAL`/`_INVERTIDA`) ou `None`.

* **Quando usar:** o servo foge do alvo em vez de ir até ele.

### `autodetecta_polaridade(tentativas=3)`
Manda a placa refazer o teste (o servo dá dois pulsos curtos; leva até ~1,5 s, e a lib espera 2 s).
Devolve a polaridade detectada, ou `None` se o teste falhou (aí a placa mantém a que tinha).

* **Cuidado:** o servo se mexe um pouco. Faça com o mecanismo livre (nada encostado, braço apoiado).

### `autodetecta_polaridade_todos()`
O mesmo para todas as placas (broadcast); depois confira cada uma com `consulta_polaridade()`.

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
| Servo treme parado | modo liga-desliga com zona morta pequena ou potência alta demais (o proporcional resolve) |
| Servo vai para o lado contrário e fica forçando no fim de curso | polaridade errada: `inverte_polaridade()` |
| Servo para um pouco antes do alvo | `pwm_minimo` baixo para aquele servo, ou um peso constante: suba o `pwm_minimo` ou ligue um `ki` pequeno |
| Funções de controle/polaridade devolvem `None` | firmware da placa anterior a 21/10/2026 |
| `None` em tudo | ID errado, porta errada ou firmware/baud diferente |

## No simulador

O simulador da Line emula o firmware de 21/10/2026 (`resgate` no `robo_4x4.json`: IDs 70 a 73,
posições, velocidade do MG90S, tempo de trava 3000): os dois modos de controle (proporcional por
padrão), a configuração do controle e a polaridade (o motor simulado está ligado do jeito normal,
então a autodetecção sempre acerta). O braço cai sem força a não ser todo levantado, e os dedos só
seguram enquanto empurram.

* No simulador o servo não tem inércia: no liga-desliga ele não vibra em volta do alvo como o de
  verdade, e chega mais rápido que no proporcional (dedo de 380 a 650: ~0,15 s contra ~0,36 s).
* O atrito do servo simulado (`servo.pwm_minimo` no `robo_4x4.json`, 45) é uma estimativa: tem de
  ficar abaixo do `pwm_minimo` do firmware (60), senão o proporcional para antes do alvo.
