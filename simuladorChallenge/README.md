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
`--resultado arq.json` (sem janela: grava o placar e a pose final), `--enter-automatico` (com janela, o
`input()` do programa segue na hora, como sem janela), `--tempo-real` (modo antigo do relógio).

### Lote de partidas (`lote.py`)

Roda várias sementes sem janela, em paralelo, e no fim separa as partidas com problema (penalidade,
erro no programa, programa que parou antes da hora, nenhum ponto):

```bash
# 10 partidas no cenário de exemplo, cada uma com uma semente de ruído
python lote.py --programa ../meuRobo/main.py --robo robo_bombertinho.json --sementes 1-10

# cada semente sorteia também o cenário; robô sempre na rua de baixo, olhando para a cidade
python lote.py --programa ../meuRobo/main.py --robo robo_bombertinho.json --sortear --inicio 380,150,0 --sementes 1-20
```

Os resultados ficam em `resultados/lote_DATA/`: `resumo.txt` (as partidas sem problema numa linha e,
para cada uma com problema, os eventos e o comando para rever na janela), `resumo.csv` (para a
planilha) e, de cada semente, o log do programa, o placar (`semente_N.json`) e o cenário
(`cenario_N.json`). O comando de rever usa a mesma semente, o mesmo cenário e `--enter-automatico`:
a partida na janela é a mesma do lote. Opções: `--tempo` (padrão 720), `--velocidade` (8),
`--paralelo` (metade dos núcleos do PC), `--saida`. Cada partida roda numa cópia da pasta do
programa (apagada no fim), para uma não ler os arquivos que a outra grava; o programa é o original,
então imports e arquivos abertos a partir de `__file__` não mudam.

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
* **Soltar**: abrindo a comporta o cubo cai no que estiver embaixo: em cima da plataforma, ou dos
  cubos que já estão nela (ver "Empilhar", abaixo), se o centro dele fica sobre o apoio; senão, no
  chão.
* **Depois de soltar, levante a garra antes de recuar**: a comporta aberta fica do outro lado do cubo
  e, na altura dele (23 mm acima da base), puxa o cubo da plataforma. Subindo, a cabeça chega para
  perto do robô, mas a comporta passa por cima do cubo antes de encostar nele.

### Empilhar (até 5 cubos por plataforma)

A regra (seção 6) deixa a plataforma com até cinco cubos "de qualquer forma, desde que fiquem em cima
da plataforma"; em fila cabem 3. O simulador empilha:

* O cubo solto cai no apoio mais alto que fica embaixo de algum ponto da base dele: a plataforma
  (topo a 50 mm) ou um cubo que já está nela (topo a 100, 150...). Fica em pé se o centro dele cai
  sobre um apoio, ou entre apoios (um cubo em cima de dois, na emenda); senão escorrega e cai no chão,
  para fora da plataforma ("não ficou em pé e caiu", julgado como cubo no chão).
* Lá no alto os cubos ficam fora da física 2D. O robô, as peças da cabeça e o cubo preso que entram
  num deles (na altura dele) o empurram por cima do apoio; se o centro sai do apoio, ele cai
  (−45 se já estava entregue), e o que estava em cima dele, sem apoio, cai junto.
* Plataforma empurrada leva a pilha junto.
* Não simulado: cubo que pula ou tomba ao cair de muito alto, cubo de baixo que escorrega quando o de
  cima cai na beirada.

O que isso pede do Bombertinho (`exemplo_bombertinho/empilha.py` faz tudo):

* A **2ª camada só com a garra da esquerda**: subindo, a cabeça do paralelogramo chega para perto do
  robô. Com a base do cubo a 108 mm (o topo da 1ª camada fica a 100) a da frente pediria a
  plataforma a 96 mm do centro do robô, e as rodas da frente vão até 97,5. A da esquerda (barra de
  79) alcança com a lateral do robô a uns 23 mm da plataforma.
* Os braços do "V" vão até 40 mm do centro do cubo e começam 38 mm acima da base dele: soltando ao
  lado de outro cubo da mesma camada, solte mais alto (o do meio da 1ª camada, com a base a 65 mm) ou
  deixe 30 mm entre eles (os da 2ª camada).
* Nunca passe com a cabeça (ou o cubo preso) do lado da pilha e na altura dela: ajuste a posição ao
  longo da plataforma longe dela e só depois chegue perto.
* Servo de subir solto: a cabeça desce sozinha com o peso. O pé curvo da barra de baixo, que apoia o
  cubo com a garra levantada, não entra no simulador.
* **Na janela**, o painel mostra cada garra vista de lado (robô à esquerda, chão embaixo): as duas
  barras, a cabeça e a comporta, e o cubo preso na cor dele. Cabeça **verde** = embaixo, baixa o
  bastante para pegar (a linha verde fina é essa altura); **laranja** = no meio, abaixo do topo dos
  cubos (bate neles); **cinza claro** = no alto. O título diz também se a comporta está aberta
  (quantos mm) ou fechada. Assim dá para ver se a garra fechou embaixo ou só depois de subir.

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
* **VL53L0X**: campo de visão em leque de 25° (datasheet), com 21 raios; a janela desenha o leque
  (tecla R). O feixe é mais forte no meio (~30% na borda) e o sinal que volta de um objeto é a
  fração do feixe que bate nele vezes (alcance/d)²: uma parede aparece até o `alcance_mm`; um cubo,
  que enche só um pedaço do leque, aparece até uns 600 mm de frente e menos se estiver de lado.
  Perto, vale a geometria do cone: a 150 mm um cubo com o centro até ~60 mm fora do eixo do sensor
  ainda aparece; a 30 mm, só até ~30 mm. Vale o objeto mais perto com sinal suficiente (um cubo fraco
  demais deixa ver a parede atrás). Enxergam cubos, plataformas e robôs. Cada sensor tem `altura` (mm
  do chão): os objetos têm 50 mm de altura, e um sensor mais alto que isso só vê o objeto quando ele
  está longe o bastante para entrar no cone.
* **TCS34725** (`tcs_i2c`, lib `tcs34725.py`): leem a cor da face do que estiver à frente deles (cubo,
  plataforma), com a luz caindo com a distância, como na Line. As refletâncias de cada cor
  (`REFLETANCIA` em `sim/fisica.py`) são estimadas. O `classifica_cor()` do `exemplo_aluno/robo.py`
  separa as cores pela proporção entre os canais; no robô, ajuste os limites com os cubos de verdade.
* **Giroscópio**: Z em graus, acumulando, positivo no sentido horário, com deriva e ruído.

## O juiz

"Cubo branco" vale também para cubo de uma cor que não tem plataforma na pista (seção 7).

| situação | pontos | o que acontece |
|---|---|---|
| cubo de cor solto em cima da plataforma da mesma cor (direto ou em cima de outros cubos) | +100 | entregue |
| cubo branco identificado: um LED do Mariola acende (ou o buzzer começa a tocar) com o cubo à frente do robô, a até 20 cm da frente dele, ainda no lugar | +50 | uma vez por cubo; cada aviso vale para o cubo branco mais perto |
| cubo solto na plataforma de outra cor | −10 | cubo perdido: o árbitro tira e põe no lugar dele |
| cubo que não fica em pé ao ser solto (centro fora do apoio) | — | cai no chão: julgado como cubo no chão (−10, cubo perdido) |
| cubo já entregue derrubado (empurrado pelo robô, pela garra ou pelo cubo preso até sair do apoio, ou o de baixo saiu) | −45 | volta para o lugar dele |
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
bate em cima do cubo, mais longe a comporta. Soltou o cubo, sobe a garra (base a 105 mm) e só então
recua. O `exemplo_bombertinho/robo.py` converte a altura (mm) e
a abertura (mm) em ângulo dos servos com as constantes do robo.json, desconta os 60 mm a mais dos VL53,
inverte a ordem dos IR do sensor de linha e carrega as cores da lona de `cores_lona.json`
(o papel do `aprende_cor()` no campo).

## Empilhando (`exemplo_bombertinho/empilha.py`, com o `cenarios/empilha.json`)

    python simulador.py --robo robo_bombertinho.json --programa exemplo_bombertinho/empilha.py --cenario cenarios/empilha.json

ou dois cliques no `rodar_empilha.bat` (e "Iniciar partida", F5). Cinco cubos azuis na rua do meio (A3, B3, C3, B3', A3': fora da regra de propósito, todos do mesmo
lado) e a plataforma azul na P3, em frente à rua. Um cubo por viagem; o robô volta de ré pela rua,
andando de lado para o sensor de linha ficar em cima dela, e chega na frente do meio da plataforma.

* **Embaixo, garra da frente**: cubos em −55, +55 e 0 mm ao longo da plataforma (+ = para o P5), nessa
  ordem; o do meio é solto com a base a 65 mm (os braços do "V" passam por cima dos vizinhos). O VL53
  da frente a 29 mm da plataforma deixa o centro do cubo no meio da largura dela.
* **Em cima, garra da esquerda**: o robô traz o cubo na garra da frente, larga no chão da área verde
  (a regra deixa ajustar o cubo lá por até 30 s), gira 90° para a direita, acerta a distância pelo
  VL53 da esquerda e pega com a garra da esquerda (comporta toda aberta, 37 mm: o "V" fica longe do
  cubo). Gira até a esquerda ficar para as plataformas, anda até −40 ou +40 mm, sobe o cubo até a base
  a 108 mm e chega de lado até o VL53 da esquerda marcar 26 mm. Solta, sobe até 128 mm (a comporta
  passa do topo do cubo, a 150) e sai de lado.
* Os ajustes ao longo da plataforma são feitos longe dela; depois de soltar, sempre sobe a garra antes
  de recuar.

Resultado: 500 pontos, partida completa em 3:16.85. Na competição a plataforma muda de lugar: ache a da
cor (`procura_plataforma` do `main.py`) enquanto ela está vazia e guarde quanto o robô andou de lado.
`EFICIENCIA_LATERAL`, os VL53 e o ângulo das barras na horizontal estão **A DEFINIR** no robô.

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
| `lote.py` | várias sementes sem janela, em paralelo; resumo com as partidas com problema (`resultados/`) |
| `sim/arena.py` | geometria da arena, cor do piso em cada ponto, posições nomeadas, cenário e sorteio |
| `sim/fisica.py` | `Motor`, `Objeto` (cubo, plataforma; solto, preso ou em cima da plataforma), `Robo` (rodas mecanum/comuns, sensores), `Mundo` (prende, solta, pilhas em cima das plataformas) |
| `sim/garra.py` | as garras: a simples (`Garra`) e a de paralelogramo do Bombertinho (`GarraParalela`) |
| `sim/juiz.py` | tempo, entregas, cubo branco, saídas da área, penalidades |
| `sim/app.py` | relógio sincronizado, processo do programa, partida, reinício (igual ao da Maze) |
| `sim/servidor.py` | operações pedidas pelo hardware virtual |
| `sim/firmware.py`, `sim/buzzer_mariola.py`, `sim/painel_brick.py` | cópias da Line |
| `sim/gui.py` | janela, painel, editor do cenário |
| `fake_hw/` | serial, I2C (VL53, TCS34725, mux), GPIO, tela/teclado, relógio (cópia da Line sem a câmera; o `CorReflexaoV2` de `dispositivos.py` passa a porta, para ter dois sensores de linha) e um Flask falso (`fake_flask.py`: o `app.run()` só avisa; um servidor web de verdade esperando conexão tiraria a partida do relógio sincronizado) |
| `libs_mariola/` | cópia das libs do Mariola (a mesma da Line) |
| `exemplo_aluno/` | `robo.py` (mecanum, garra, cor), `main.py` (pega o cubo e entrega), `anda_mecanum.py` (só locomoção) |
| `exemplo_bombertinho/` | o mesmo para o robô real: `robo.py` (duas garras, dois sensores de linha), `main.py`, `empilha.py` (5 cubos numa plataforma, com o `cenarios/empilha.json`) e `cores_lona.json` |
| `robo_real/simdebug.py` | o `simdebug` que não faz nada, para o mesmo código rodar no robô |
