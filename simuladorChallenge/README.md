# Simulador RCB Challenge — robô com brick Mariola

Simulador 2D da categoria **RoboCup Brasil Challenge** (CBR 2026, regra V1.0: coleta de resíduos
recicláveis) para desenvolver o programa do robô com o **mesmo código** que vai para o robô real.

Como nos simuladores da Line e da Maze, o programa do aluno importa as bibliotecas reais do Mariola
(`motores.py`, `placaControleMotor.py`, `giroscopio.py`, `vl53.py`, `sensorCorReflexao.py`,
`tcs34725.py`, `pinosDigitais.py`, ...) e elas rodam **sem nenhuma alteração**. O simulador troca só a
camada de baixo (porta serial, I2C, GPIO e relógio) e emula o firmware de cada placa byte a byte.

**Estado (31/10/2026).** Já tem a arena, os cubos e as plataformas soltos na pista, o juiz (entregas,
cubo branco, penalidades) e três robôs: o **Bombertinho** (`robo_bombertinho.json`, o robô real,
medido no desenho: duas garras de paralelogramo, na frente e na esquerda, e dois sensores de linha) e
os dois provisórios do começo (garra simples na frente; só mecanum). Ainda não tem o robô adversário:
veja "O que falta".

## Instalação

```bash
pip install pygame pymunk numpy
```

No Windows, `Simulador.bat` abre o simulador (usa o Python portátil da pasta `portatil\python`
quando ela existe; senão, o Python do PC).

## Uso rápido

```bash
# abre a janela com o programa de exemplo e o cenário de exemplo
python simulador.py

# com o programa da equipe e outro cenário
python simulador.py --programa CAMINHO/DO/main.py --cenario cenarios/vazio.json

# cenário sorteado dentro da regra (a mesma semente dá o mesmo cenário)
python simulador.py --sortear 7

# sem janela: uma partida 8x mais rápida, imprime o placar
python simulador.py --sem-janela --velocidade 8

# o robô real (Bombertinho) com o exemplo dele
python simulador.py --robo robo_bombertinho.json --programa exemplo_bombertinho/main.py
```

Outras opções: `--robo outro.json`, `--semente N` (repete a mesma partida), `--tempo 720`,
`--resultado arq.json` (sem janela: grava o placar e a pose final), `--tempo-real` (modo antigo do
relógio).

Na janela: **▶ Iniciar partida** (F5) começa a partida e o programa (o botão de início do robô é
apertado sozinho 1,5 s depois, se "Auto-botão" estiver ligado); **Reinício (−15)** é a equipe pegando
o robô: volta para o início e o programa reinicia; **Sortear cenário**, **Abrir** e **Salvar** mexem no
cenário. Com o programa parado, arraste o robô com o mouse (Q/E giram 90°, a roda do mouse 5°) e
clique nos quadrados para editar o cenário (veja abaixo). Teclas: espaço pausa, B botão, R raios dos
VL53, T trilha, N nomes das posições, 1–5 velocidade, O tela/teclado do brick (F1–F4), Enter responde
o `input()` do programa.

## A arena

Medidas da regra (seção 4) e, onde ela não diz, da figura 1 (2,1 mm por pixel): lona de 2840 × 1500 mm,
simétrica por **rotação de 180°** (os nomes do lado direito aparecem de cabeça para baixo na figura).

| faixa (lado esquerdo, em x) | mm |
|---|---|
| linha vermelha (limite) | 0–20, e nas 4 bordas |
| Ecoponto (amarelo), com 5 locais de descarte brancos de 160 × 50 a 50 mm da linha vermelha | 20–240 |
| área livre (verde) | 240–520 |
| linha azul | 520–540 |
| cidade (branca) | 540–2300 |

Na cidade, linhas pretas de 20 mm numa grade de **300 mm**: em pé em x = 670, 970, 1270, 1570, 1870,
2170 (de uma linha vermelha à outra) e deitadas em y = 150, 450, 750, 1050, 1350 (de uma linha azul à
outra). Quadrados de 50 mm:

* **cinza** (só o contorno, bem claro): onde vão os cubos a coletar, no meio de cada trecho de linha.
  A1–A5 (x = 820), B1–B5 (x = 1120) e C1–C3 (x = 1420, o C3 é o centro da pista) sobre as linhas
  deitadas, de baixo para cima; D (y = 1200), E (900), F (600), G (300), 1 a 3 da área livre para o
  centro, sobre as linhas em pé.
* **marrom** (cheio): onde vão os cubos-obstáculo, no centro das quadras: X1–X4 (x = 820), Y1–Y4
  (x = 1120), Z1–Z2 (x = 1420), de baixo para cima.
* Locais de descarte P1 (embaixo) a P5 (em cima).

Do lado direito, os mesmos nomes com apóstrofo: A1' é o A1 girado.

**Atenção para o tamanho do robô:** com obstáculos nas duas quadras vizinhas, sobram só 250 mm entre
eles. A regra deixa até 300 × 300 mm, mas para seguir a linha entre dois obstáculos o robô (com as
garras fechadas) precisa ter menos de ~240 mm de largura.

## Cenário (`cenarios/*.json`)

O que o árbitro põe na pista: plataformas (nos P1–P5 de cada lado), cubos (nos quadrados) e onde cada
robô começa (na área verde).

```json
{"plataformas": {"P1": "azul", "P1'": "azul"},
 "cubos": {"A2": "vermelho", "A2'": "vermelho", "X1": "preto", "X1'": "preto"},
 "inicio": {"esq": [380, 750, 0], "dir": [2460, 750, 180]}}
```

`inicio` = x, y (mm) e ângulo (graus, anti-horário, 0 = olhando para a direita). Cores dos cubos:
azul, vermelho, verde, amarelo, preto, marrom, branco. Das plataformas: as mesmas menos o branco.

**Editor:** com o programa parado, clique num quadrado cinza ou marrom para trocar a cor do cubo
(azul → vermelho → … → branco → nenhum) ou num local de descarte para trocar a plataforma. O outro
lado muda junto (simetria); com Shift muda só aquele. Botão direito tira. **Salvar** grava o JSON.

**Sorteio** (`--sortear N` ou o botão): 5 plataformas de cores diferentes (as mesmas nos dois lados),
4 pares de cubos de cor com plataforma e 1 par de brancos nos quadrados cinza, 2 pares de obstáculos
nos marrons, respeitando o estoque da pista (5 cubos de cada cor e 6 brancos, 2 plataformas de cada
cor). O simulador avisa (sem impedir) quando um cenário sai da regra.

## O Bombertinho (`robo_bombertinho.json`, o robô real)

Medido no desenho "Bombertinho 2026 - Nacional CBR" (DXF de 31/10/2026), com as rodas reais de 58 mm
(no desenho elas têm 50: o robô de verdade fica 4 mm mais alto, e os sensores de linha ficam a 12 mm do
chão, como a equipe usa). Referencial: x para frente (o lado do TCS e do VL53 baixos), y para a
esquerda, origem no centro entre as rodas.

Ligações (portas, canais do mux, servos, sentido dos motores, encoder) e cores: do **código da equipe**
(CBR-2026, 30/10/2026). O que foi deduzido do código está em `_deducoes` no robo.json: confira no robô.

* Corpo de 180 × 145 mm (rodas por fora), rodas mecanum de 58 mm a ±68,5 (frente/trás) e ±59,3
  (lados). Massa, motores e roletes: **A DEFINIR** (iguais aos provisórios). Mariola canal 1 =
  traseira **direita**, canal 2 = traseira esquerda (invertido no programa); placas 8 (dianteira
  esquerda) e 51 (dianteira direita, invertida) no `SERIAL2`; 75 contagens do Mariola por cm.
* 4 VL53L0X, um para cada lado, em alturas diferentes (frente 24 mm, trás 34, esquerda 19, direita
  44): frente `I2C4`, trás `I2C7`, esquerda `I2C2`, direita `I2C5`. **Leem 60 mm a mais** que a
  distância real (`vl53_params.offset_mm`, deduzido do código da equipe: A MEDIR).
* TCS34725: um baixo na frente (`I2C3`, 31 mm à direita do centro: vê a plataforma, não um cubo
  centrado) e um na parede de trás de cada cabeça de garra, olhando para dentro (frente `I2C8`,
  esquerda `I2C6`). `ganho` por sensor e `refletancia` no robo.json: calibrados para os TCS lerem as
  cores que a equipe mediu (faixas HSV deles), na distância em que o código deles lê.
* Dois Pro1616: um embaixo da frente, atravessado, no `SERIAL1`, e um embaixo da esquerda, virado
  para a esquerda (para andar de lado), no `SERIAL3`. Nos dois os IR estão na **ordem trocada**
  (canal 0 da frente à direita, do lateral para a frente); os TCS, na ordem normal. No robo.json, `cor_reflexao` pode ser uma lista, cada sensor
  com a sua `porta`. `cores_piso` = cores da lona que a equipe mediu (o azul e o verde são bem menos
  saturados que as estimativas antigas).
* Giroscópio no `SERIAL5`, Z crescendo para a **esquerda** (deduzido).
* Servos do Mariola: garra da frente sobe = 3, abre = 4; garra da esquerda sobe = 2, abre = 1.

### As garras de paralelogramo (`garras` no `robo_bombertinho.json`)

Duas garras iguais (`tipo: paralelogramo`, classe `GarraParalela`), uma na frente e uma na esquerda.
A da frente tem as barras mais curtas (66,5 mm contra 79), porque a base é retangular.

* **Braço**: duas barras paralelas vão do suporte (preso ao robô) até a cabeça. O servo de subir gira
  a de baixo; a cabeça sobe e desce sem inclinar, num arco. Com as barras na horizontal, a base do cubo
  preso fica a 54 mm do chão (acima da plataforma, que tem 50). **Descendo, a cabeça também chega
  para perto do robô**: até o chão são 28 mm na garra da frente e 21 na da esquerda.
* **Cabeça**: aberta embaixo, com a parede de trás, o teto e a peça que abre (comporta na ponta e dois
  braços em "V" dos lados do cubo, que o centralizam). O servo de abrir gira uma engrenagem de 24
  dentes (módulo 1, raio 12 mm) numa cremalheira: a comporta corre 0,21 mm por grau, para fora.
  Fechada, sobram 50 mm (o cubo) entre ela e a parede de trás.
* **Pegar**: a cabeça desce por cima do cubo com a comporta aberta, e a comporta fecha, apertando o
  cubo contra a parede de trás. O cubo fica preso se a comporta fechar com a base do cubo a até 17 mm
  do chão (`altura_max_pegar_mm`). Se o robô estiver mal posicionado, a parede de trás, a comporta ou
  os braços do "V" batem **em cima do cubo** e a cabeça para ali (o servo trava). O mesmo vale descendo
  em cima de uma plataforma ou com o cubo preso.
* **Soltar**: abrindo a comporta o cubo cai: em cima da plataforma se a base dele está a 45 mm ou mais
  e o centro dele fica sobre ela; senão, no chão.
* Servo de subir solto: a cabeça desce sozinha com o peso. O pé curvo da barra de baixo, que apoia o
  cubo com a garra levantada, não entra no simulador.

| no robo.json | o que é |
|---|---|
| `x`, `y`, `angulo` | eixo do servo de subir no robô e para onde a garra aponta |
| `barra_mm`, `altura_eixo_mm`, `base_cubo_mm` | geometria do paralelogramo (do desenho) |
| `angulo_horizontal`, `sentido_sobe` | ângulo do servo com as barras na horizontal (90, **A DEFINIR**) e se aumentar levanta (sim: a equipe usa 20 embaixo e 170-180 em cima, barras de pé) |
| `angulo_fechada`, `sentido_abre`, `curso_max_mm` | servo de abrir: 0 = fechada, 180 = aberta (código da equipe) = 37,7 mm (conferir se a cremalheira anda isso) |
| `mm_por_grau` | 0,2094 (engrenagem de 24 dentes, módulo 1) |

## Os robôs provisórios (`robo_garra.json`, o padrão, e `robo_mecanum.json`)

Do começo do simulador, antes do desenho do robô real. Os dois têm a mesma base: brick Mariola,
200 × 200 mm, 1,6 kg, 4 rodas mecanum de 60 mm ligadas como no 4x4 da Maze (traseiras no Mariola,
canais 1 e 2; dianteiras nas placas de motor 8 e 51 no `SERIAL1`), giroscópio no `SERIAL5`, Pro1616
no `SERIAL6` (na frente), 4 VL53L0X (frente, trás, esquerda, direita; `I2C1`–`I2C4`, a 35 mm do chão),
botão de início no P3. Os motores são os de aspirador da Maze. Troque tudo pelo robô real quando ele
existir.

* `robo_garra.json`: com a garra na frente (abaixo) e um TCS34725 entre os dedos, olhando para frente
  (`I2C5`, 25 mm do chão).
* `robo_mecanum.json`: sem garra, com 2 TCS34725 olhando para os lados (`I2C5`, `I2C6`). Para testar
  só a locomoção (`exemplo_aluno/anda_mecanum.py`).

### A garra simples (`garra` no `robo_garra.json`)

Dois dedos na frente do robô (65 mm de comprimento), num braço que sobe e desce. Dois servos do
Mariola (lib `motores.py`: `move_servo(n, ângulo)` e `atualiza_servos()`):

| servo | 0° | 90° |
|---|---|---|
| 1 (dedos) | fechada (30 mm entre os dedos) | aberta (100 mm) |
| 2 (braço) | embaixo (dedos no chão) | em cima (80 mm) |

O servo anda a 300°/s (0,3 s de ponta a ponta). Como o simulador trata:

* Com o braço embaixo, os dedos empurram cubos e batem nas plataformas; acima de 50 mm passam por
  cima de tudo.
* Fechando com um cubo entre os dedos e o braço embaixo (menos de 15 mm), o cubo fica preso: os dedos
  param na largura dele e ele acompanha a garra. Fechar empurra o cubo para o meio.
* Abrindo, o cubo é solto. Com o braço a 45 mm ou mais e o centro do cubo em cima de uma plataforma,
  ele fica em cima dela (e acompanha a plataforma se ela for empurrada); senão, cai no chão.
* Servo solto (o timeout de 5 s do Mariola sem pacote solta os servos): os dedos ficam onde estão e o
  braço desce sozinho com o peso.
* Os sensores enxergam o cubo preso e os cubos nas plataformas na altura em que eles estão: com o
  braço em cima, o cubo passa por cima do feixe do VL53 e do TCS da frente, que então veem a
  plataforma.

**Atenção (firmware de 26/10):** com os servos ligados, o Timer2 do Mariola fica com eles e o buzzer
não toca. Para avisar o cubo branco, use os LEDs.

### Rodas mecanum

Cada motor tem `rolete`: o ângulo do eixo dos roletes que **tocam o chão**, visto de cima (graus,
anti-horário a partir da frente). A roda só empurra o chão na direção perpendicular aos roletes; ao
longo deles ela rola solta (com o atrito de rolamento `atrito_rolete`). Na montagem padrão
(dianteira esquerda e traseira direita +45°, as outras −45°):

| movimento | dianteira esq. | dianteira dir. | traseira esq. | traseira dir. |
|---|---|---|---|---|
| frente | + | + | + | + |
| de lado para a esquerda | − | + | + | − |
| girar para a esquerda | − | + | − | + |

Montou as rodas trocadas? O simulador anda errado igual ao robô de verdade. `eficiencia_lateral`
(0,9) é quanto do caminho ideal o robô faz andando de lado: as rodas mecanum escorregam mais assim, e
o encoder mostra mais do que o robô andou. **Meça no robô** (mande andar 1 m de lado pelo encoder e
meça com a trena).

`exemplo_aluno/robo.py` tem o `move(vx, vy, w)` que mistura as 3 partes nas 4 rodas e o
`deslocamento()` que estima (frente, lado) pelos 4 encoders.

### Sensores

* **Sensor de linha Pro1616**: o mesmo modelo da Maze (4 IR + 3 TCS, cada ponto é a média de um
  disco de 5 mm de raio, 19 amostras). As cores da lona em `cores_piso` são **estimadas**: troque pelas lidas no robô.
* **VL53L0X**: raios num cone de 25° (os da borda só enxergam perto). Enxergam cubos, plataformas e
  robôs. Cada sensor tem `altura` (mm do chão): os objetos têm 50 mm de altura, e um sensor mais alto
  que isso só vê o objeto quando ele está longe o bastante para entrar no cone.
* **TCS34725** (`tcs_i2c`, lib `tcs34725.py`): leem a cor da face do que estiver à frente deles (cubo,
  plataforma), com a luz caindo com a distância, como na Line. As refletâncias de cada cor
  (`REFLETANCIA` em `sim/fisica.py`) são estimadas. O `classifica_cor()` do `exemplo_aluno/robo.py`
  separa as cores pela proporção entre os canais; no robô, ajuste os limites com os cubos de verdade.
* **Giroscópio**: Z em graus, acumulando, positivo no sentido horário, com deriva e ruído.

## O juiz

"Cubo branco" vale também para cubo de uma cor que não tem plataforma na pista (seção 7).

| situação | pontos | o que acontece |
|---|---|---|
| cubo de cor solto em cima da plataforma da mesma cor | +100 | entregue |
| cubo branco identificado: um LED do Mariola acende (ou o buzzer começa a tocar) com o cubo à frente do robô, a até 20 cm da frente dele, ainda no lugar | +50 | uma vez por cubo; cada aviso vale para o cubo branco mais perto |
| cubo solto na plataforma de outra cor | −10 | cubo perdido: o árbitro tira e põe no lugar dele |
| cubo novo caindo em cima de um já entregue (centros a menos de 40 mm) | −45 | o de antes é derrubado e volta para o lugar dele |
| centro do robô passa da linha vermelha, ou da linha azul do lado do adversário | −5 | o robô volta para o início dele; o programa continua |
| Reinício (botão) | −15 | robô no início, programa reiniciado |
| cubo de cor tirado do quadrado (mais de 25 mm) e largado fora da plataforma e fora da área verde da equipe | −10 | cubo perdido: volta para o lugar |
| cubo branco pego pela garra ou tirado do lugar (mais de 25 mm, metade da área) | −15 | volta para o lugar quando for solto |
| cubo-obstáculo (quadrado marrom) pego ou deslocado mais de 10 mm | −15 | obstáculo não identificado: volta para o lugar |
| plataforma deslocada mais de 10 mm | −20 | volta para o lugar (com os cubos que estão em cima) |

O árbitro só decide sobre um objeto empurrado quando ele está parado e o robô não encosta nele há
0,5 s, e só devolve o objeto ao lugar com o robô a mais de 22 cm de lá. O placar nunca fica negativo
(seção 7): o painel mostra os pontos positivos e os negativos separados (critério de desempate).
Partida de 12 minutos; acaba antes se todos os cubos de cor (com plataforma) forem entregues.

**Simplificações:** "robô perdido por deixar de seguir a linha" e "robô inativo" dependem do árbitro e
não são julgados. O limite de 2 cubos por viagem não é conferido (a garra simples leva 1).

## O exemplo (`exemplo_aluno/main.py`, com o `robo_garra.json`)

Sai da área verde, segue a rua do meio até o VL53 da frente ver o cubo do A3, encosta nele com a garra
aberta e lê a cor com o TCS entre os dedos. Cubo branco: acende os LEDs (+50) e deixa no lugar. Outra
cor: fecha a garra, sobe o braço, volta de ré até a linha azul, dá meia-volta, encosta quase na
plataforma da frente e anda de lado pelos locais de descarte lendo a cor de cada plataforma; na da cor
do cubo, centraliza e abre a garra. No `cenarios/exemplo.json` o cubo do A3 é azul e a plataforma azul é
a P1: entrega em 25 s (+100).

## O exemplo do Bombertinho (`exemplo_bombertinho/main.py`, com o `robo_bombertinho.json`)

O mesmo caminho do exemplo acima, com a garra da frente: sai com ela alta (base do cubo a 54 mm, a
parede de trás passa 9 mm acima dos cubos) e aberta, segue a rua até o VL53 da frente marcar 34 mm do
cubo, desce até 10 mm e lê a cor com o TCS da cabeça. Branco: acende os LEDs (+50) e sobe. Outra cor:
fecha (a comporta puxa o cubo ~18 mm até a parede), sobe, volta, dá meia-volta, para a 20 mm da
plataforma (o cubo passa por cima dela) e procura a cor com o TCS baixo da frente. Entrega o azul em
30 s (+100); com o A3 amarelo, procura para um lado, volta e entrega na P4; com o A3 branco, +50.

A distância de 34 mm tem pouca folga: de ~29 a ~38 mm a garra desce certo; mais perto a parede de trás
bate em cima do cubo, mais longe a comporta. O `exemplo_bombertinho/robo.py` converte a altura (mm) e
a abertura (mm) em ângulo dos servos com as constantes do robo.json, desconta os 60 mm a mais dos VL53,
inverte a ordem dos IR do sensor de linha e carrega as cores da lona de `cores_lona.json`
(o papel do `aprende_cor()` no campo).

## O que falta

1. **Bombertinho**: conferir as deduções do `_deducoes` (VL53 lendo 60 mm a mais, giroscópio, sensores
   de linha virados, cores) e o ângulo do servo com as barras na horizontal; massa, motores e roletes. A pose de início do cenário (x = 380)
   é a do robô provisório: com a garra da frente na horizontal a cabeça passa da linha azul. O juiz
   ainda não confere o limite de 2 cubos por viagem.
2. **Robô adversário** do outro lado: a física e o juiz já tratam uma lista de robôs (classe `Robo`
   separada do `Mundo`); falta a segunda conexão (um servidor por robô) e o relógio esperar os dois
   programas.
3. Medidas reais: robô, motores, rodas, servos, `eficiencia_lateral`, cores da lona e dos cubos.

## Estrutura

| arquivo | papel |
|---|---|
| `simulador.py`, `rodar.py`, `Simulador.bat` | entrada; o programa do aluno roda em outro processo |
| `sim/arena.py` | geometria da arena, cor do piso em cada ponto, posições nomeadas, cenário e sorteio |
| `sim/fisica.py` | `Motor`, `Objeto` (cubo, plataforma; solto, preso ou em cima da plataforma), `Robo` (rodas mecanum/comuns, sensores), `Mundo` (prende, solta) |
| `sim/garra.py` | as garras: a simples (`Garra`) e a de paralelogramo do Bombertinho (`GarraParalela`) |
| `sim/juiz.py` | tempo, entregas, cubo branco, saídas da área, penalidades |
| `sim/app.py` | relógio sincronizado, processo do programa, partida, reinício (igual ao da Maze) |
| `sim/servidor.py` | operações pedidas pelo hardware virtual |
| `sim/firmware.py`, `sim/buzzer_mariola.py`, `sim/painel_brick.py` | cópias da Line |
| `sim/gui.py` | janela, painel, editor do cenário |
| `fake_hw/` | serial, I2C (VL53, TCS34725, mux), GPIO, tela/teclado, relógio (cópia da Line sem a câmera; o `CorReflexaoV2` de `dispositivos.py` passa a porta, para ter dois sensores de linha) |
| `libs_mariola/` | cópia das libs do Mariola (a mesma da Line) |
| `exemplo_aluno/` | `robo.py` (mecanum, garra, cor), `main.py` (pega o cubo e entrega), `anda_mecanum.py` (só locomoção) |
| `exemplo_bombertinho/` | o mesmo para o robô real: `robo.py` (duas garras, dois sensores de linha), `main.py` e `cores_lona.json` |
| `robo_real/simdebug.py` | o `simdebug` que não faz nada, para o mesmo código rodar no robô |
