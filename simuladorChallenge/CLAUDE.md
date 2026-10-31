# simuladorChallenge — guia para o Claude Code

Simulador 2D da **RCB Challenge** (RoboCup Brasil Challenge, CBR 2026, regra V1.0 de jul/2026:
coleta de resíduos recicláveis, cubos coloridos levados até plataformas). Começado em 30/10/2026.
Robô real = **Bombertinho** (`robo_bombertinho.json`, 31/10: brick Mariola, 4 rodas mecanum de 58 mm,
duas garras de paralelogramo, uma na frente e uma na esquerda, dois sensores de linha). Os robôs
provisórios do começo continuam: `robo_garra.json` (garra simples na frente, ainda o padrão do
`simulador.py`) e `robo_mecanum.json` (sem garra).

Leia o `README.md` (arena, cenário, robô, mecanum, juiz, o que falta). As regras gerais do repositório
estão no `CLAUDE.md` da pasta de cima.

## Origem do código

Nasceu da Maze (esqueleto: `app.py` com o relógio sincronizado, `servidor.py`, `gui.py`, `juiz.py`)
com o hardware falso da Line (`fake_hw/` tem o TCS34725 por I2C; a câmera foi tirada porque a regra
proíbe câmera e LiDAR). `sim/firmware.py`, `sim/buzzer_mariola.py`, `sim/painel_brick.py`,
`fake_hw/` (menos `__init__.py` e `sim_modulos.py`) e `libs_mariola/` são **cópias da Line**: corrigiu
lá, traga para cá. `fake_hw/cliente.py` é o mesmo arquivo nos três simuladores.

Diferenças de estrutura em relação à Maze: o robô é a classe `Robo` (corpo, motores, firmwares,
sensores, LEDs, tela, teclado) e o `Mundo` tem o espaço, os objetos e `robos` (hoje só um). O firmware
emulado recebe o `Robo` no lugar do mundo (usa só `por_mariola`, `servos` e `leds`). O "LoP" virou
`reinicio()` (−15, programa reiniciado) e `_reposiciona()` (robô saiu da área: volta para o início,
programa continua); `_reinicio_ate` é o antigo `_lop_ate`.

## Teste de referência

```bash
python simulador.py --sem-janela --velocidade 8 --tempo 200
#   garra (robo_garra.json, cenarios/exemplo.json, semente 1): pega o cubo azul do A3 e entrega na
#   plataforma azul (P1): "+100 cubo entregue" em 0:25.66,
#   pose final x=344 y=201 ângulo=178.9°, TOTAL 100
python simulador.py --sem-janela --velocidade 8 --tempo 120 --robo robo_mecanum.json --programa exemplo_aluno/anda_mecanum.py --cenario cenarios/vazio.json
#   só locomoção: 3 cruzamentos, anda de lado, gira 180°, volta; pose final x=449 y=1050 ângulo=179.8°, 0 pontos
python simulador.py --sem-janela --velocidade 8 --tempo 200 --robo robo_bombertinho.json --programa exemplo_bombertinho/main.py
#   Bombertinho, garra da frente: "+100 cubo entregue: azul (A3)" em 0:30.25,
#   pose final x=341 y=214 ângulo=179.5° (igual a 2x); A3 amarelo: +100 em 0:44.01; A3 branco: +50 em 0:06.45
```

Números de 31/10/2026, depois da ligação do código da equipe no Bombertinho e da mancha de 19 pontos do
sensor de linha (`PONTOS_MANCHA` em `sim/fisica.py`; antes era uma cruz de 5 pontos e os números eram
0:25.60 e x=446 y=1048).

Em 30/10 os dois deram a mesma pose final em `--velocidade 2` e `8` (relógio sincronizado). Trocando o
cubo do A3 (e do A3') no cenário: amarelo → procura para um lado, volta e entrega na P4 (+100);
branco → acende os LEDs e não pega (+50). Rode depois de mexer em `sim/` ou `fake_hw/`.

## Fatos da regra que o simulador segue

* Arena 2840 × 1500, simétrica por rotação de 180° (não espelhamento): `arena.gira()`, nomes do lado
  direito com apóstrofo (`A1'`), C3 único (centro). Grade de 300 mm medida na figura 1 da regra
  (2,1 mm/px), conferida contra as medidas do texto (amarelo 220, verde 280, linhas 20, descarte
  160 × 50 a 50 mm da vermelha e 100 mm entre eles).
* Cubos 50 mm, 25–40 g (massa sorteada pela semente); plataformas 160 × 50 × 50, 400–500 g. Atrito
  com a lona feito à mão em `Mundo._atrito_objetos` (o pymunk é 2D).
* Estoque por pista: 5 cubos de cada cor + 6 brancos; 2 plataformas de cada cor (menos branco).
* Pontuação: o total nunca fica negativo; positivos e negativos guardados para o desempate.
* PDF da regra: `https://cbr.robocup.org.br/wp-content/uploads/2026/07/Regras_Challenge_2026_Portugues-V1.0.pdf`.
  O arquivo vetorial da pista está no Google Drive como `Pista-2025.pdf` (link na página de categorias
  da CBR); não foi baixado: se o Julio puser na pasta, confira as medidas da grade e dos quadrados.

## Decisões e simplificações (30/10/2026)

* Mecanum em `Robo.rodas()`: impulsos sequenciais (4 iterações) com o total de cada roda limitado pelo
  atrito e pela força do motor. A roda só segura a velocidade na direção perpendicular aos roletes;
  ao longo deles, só `atrito_rolete`. A perda andando de lado é empírica: `eficiencia_lateral` (0,9)
  faz a componente lateral (no referencial do robô) da velocidade "pesar" 1/0,9 na condição da roda.
  Conferido: frente/lado/diagonal/giro sem desvio; de lado anda 90% do que anda para frente.
* "Fora da área" = centro do robô passa da borda interna da linha vermelha ou da linha azul do outro
  lado. A regra não diz se é o robô inteiro ou parte; escolhido o centro.
* Objeto deslocado: o juiz espera o objeto parar e o robô não encostar por 0,5 s; devolve com o robô a
  mais de 220 mm. Cubo de cor largado inteiro na área verde **da equipe que encostou por último** não é
  penalizado (seção 7 permite).
* O painel lê os sensores para mostrar e restaura o estado dos geradores de ruído depois: a partida com
  e sem janela é a mesma.
* Robôs provisórios (`robo_garra.json`, padrão, e `robo_mecanum.json`, sem garra): tudo marcado
  A DEFINIR. Motor = o de aspirador da Maze. O `robo_garra.json` foi gerado a partir do
  `robo_mecanum.json` (mesma base): mudou a base de um, leve para o outro.

## Garra simples (`sim/garra.py`, 30/10/2026)

* Servos do Mariola 1 (dedos: 0° fechada 30 mm, 90° aberta 100 mm) e 2 (braço: 0° no chão, 90° a
  80 mm), 300°/s. Servo solto (> 180 ou timeout de 5 s): dedos param, braço cai a 120°/s.
* Dedos = 2 `pymunk.Segment` no corpo do robô, movidos por `unsafe_set_endpoints` a cada passo;
  colidem com cubos e plataformas só com o braço abaixo de 50 mm. Os raios dos sensores ignoram os
  dedos (`dedo = True`).
* `Objeto.estado`: 'livre' (física 2D), 'preso' (na garra) ou 'plataforma' (em cima de uma, segue a
  plataforma pelo `off`). Preso e na plataforma ficam na categoria `CAT_ALTO`: fora das colisões, mas
  os raios enxergam. `base_mm`/`altura_mm` da forma dizem a faixa de altura que o feixe vê.
* Prende: fechando até ~60 mm com o braço abaixo de 15 mm e um cubo livre entre os dedos. Solta:
  abrindo além de ~60 mm; em cima da plataforma se o braço está a 45 mm ou mais e o centro do cubo cai
  dentro dela.
* O `Mundo` registra `eventos_garra` ('preso', 'plataforma', 'chao') e o juiz consome a cada passo.
* Cubo branco: identificação pela borda de subida do sinal (LED aceso ou buzzer começando), um cubo
  por aviso (o mais perto, à frente, até 20 cm da frente do robô). Antes valia para todos os cubos
  perto e um aviso só identificou dois (o E1 fica a 195 mm do A3).
* Com servos, o Timer2 do Mariola é deles: o buzzer não toca (firmware de 26/10). O exemplo avisa com
  os LEDs.

## Bombertinho (`robo_bombertinho.json`, 31/10/2026)

* Medido no DXF que o Julio exportou do AutoCAD ("Bombertinho 2026 - Nacional CBR_claude.dxf", em
  `Downloads`; o .dwg não dá para ler, e o DXF 2013 sai com os sólidos em ACIS binário, que o `ezdxf`
  1.x não interpreta: as coordenadas saíram de um leitor feito à mão dos registros `point`,
  `transform` e `ellipse-curve`). No desenho: camadas `sensor_distancia`, `sensor_cor`,
  `sensores reflexao`, `giroscópio`, `servos`, `mães`; **verde = parte fixa** (presa ao robô), a peça
  que abre em laranja-avermelhado (RGB 242,103,34). Referencial do DXF → robô: x_r = −y_dxf − 113,7,
  y_r = x_dxf + 262,9, altura = z_dxf − 1,7 (chão com as rodas de 58 mm medidas pelo Julio; no
  desenho elas têm 50). Frente = lado do TCS e do VL53 baixos (Julio).
* Garras (`GarraParalela` em `sim/garra.py`): paralelogramo (barras de 66,5 na frente e 79 na
  esquerda, "de propósito, a base é retangular"), cabeça aberta embaixo, comporta numa cremalheira
  (engrenagem `engrenagem_24d_mg90s.stl` e `cremalheira_14d_*.stl` em
  `Documents\modelos3D\robotica\challenge2026`: 24 dentes, módulo 1, raio 12 → 0,2094 mm/grau).
  A cabeça desce por cima do cubo; mal posicionada, bate em cima dele (Julio confirmou). O "pé" da
  barra de baixo apoia o cubo com a garra levantada: não simulado. Ângulos dos servos, curso máximo
  da comporta, portas: o Julio pediu para deixar uma configuração no JSON e ajustar depois.
* `Robo.garras` (lista; `Robo.garra` = a primeira), `Mundo.prende(robo, o, garra)`. TCS com `"garra"`
  anda com a cabeça (`Robo.pose_tcs`). `cor_reflexao` pode ser lista (cada um com `porta`); cada sensor
  de linha tem cache e gerador de ruído próprios (`rng_cor` é lista): a lib lê cada um numa thread e a
  ordem entre elas varia, com um gerador só a partida mudava com a velocidade.
* O `fake_hw/dispositivos.py` (`CorReflexaoV2` manda a porta) e o `sim/servidor.py` ficaram diferentes
  dos da Line nisso.
* **Código da equipe** (zip "Challenger - 2026", repositório CBR-2026, commit 4f613f5 de 30/10): está
  em `professor/challenger2026/` (privado: `codigo/` sem mudança, `ANALISE.md`, `simulador/` com o
  adaptador). O `robo_bombertinho.json` foi refeito em 31/10 com a ligação dele (portas, mux, servos,
  sentido dos motores, encoder) e com o que foi **deduzido** do código (`_deducoes`: VL53 lendo 60 mm a
  mais, giroscópio crescendo para a esquerda, IR dos sensores de linha na ordem trocada com os TCS na
  normal, cores da lona e dos cubos tiradas das faixas HSV deles). Resultado no simulador: o código
  deles roda (com o adaptador), mas não entrega cubo; com o `alinhar_distancia_lixeira()` corrigido,
  110 pontos (ver a `ANALISE.md`). Gerado por `professor/challenger2026/simulador/gera_robo.py` sobre o
  `robo_bombertinho_antes.json` de lá. O `exemplo_bombertinho` foi ajustado junto (`cores_lona.json` =
  aprende_cor).
* `tcs_i2c[].ganho` e `refletancia` (no robo.json) existem para isso: calibrar os TCS do mux para as
  leituras de um robô real. Sem eles, vale o `REFLETANCIA` de `sim/fisica.py`.

## Pendências

* **Bombertinho**: ângulos dos servos, canais do mux, porta do 2º sensor de linha, massa, motores,
  roletes. A pose de início dos cenários (x = 380) é a do robô provisório: a cabeça da garra da frente
  na horizontal passa da linha azul. Juiz: limite de 2 cubos por viagem.
* **Adversário**: um `Servidor` por robô (o construtor já aceita `robo=`), `SIM_PORTA` próprio para
  cada programa e o relógio sincronizado esperando os dois.
* `avalia.py` e desafios, pacote portátil (`monta_portatil.py` da Line), curso.
