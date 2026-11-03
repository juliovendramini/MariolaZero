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
lá, traga para cá. `fake_hw/cliente.py` é o mesmo arquivo nos três simuladores (com as travas
vigiadas desde 31/10, ver "Relógio e travas" abaixo): mudou um, copie para os outros dois e rode os
testes dos três.

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
#   pose final x=345 y=201 ângulo=178.9°, TOTAL 100
python simulador.py --sem-janela --velocidade 8 --tempo 120 --robo robo_mecanum.json --programa exemplo_aluno/anda_mecanum.py --cenario cenarios/vazio.json
#   só locomoção: 3 cruzamentos, anda de lado, gira 180°, volta; pose final x=449 y=1050 ângulo=179.8°, 0 pontos
python simulador.py --sem-janela --velocidade 8 --tempo 200 --robo robo_bombertinho.json --programa exemplo_bombertinho/main.py
#   Bombertinho, garra da frente: "+100 cubo entregue: azul (A3)" em 0:30.25,
#   pose final x=341 y=214 ângulo=179.5° (igual a 2x); A3 amarelo: +100 em 0:44.01; A3 branco: +50 em 0:06.45
```

Números de 31/10/2026, depois da ligação do código da equipe no Bombertinho, da mancha de 19 pontos do
sensor de linha (`PONTOS_MANCHA` em `sim/fisica.py`; antes era uma cruz de 5 pontos e os números eram
0:25.60 e x=446 y=1048) e do VL53 em leque (antes da troca, x=344 na garra simples).

* **VL53 em leque** (31/10, pedido do Julio depois do comentário de um aluno: "no simulador é uma linha
  reta"): 21 raios no cone de 25° (`RAIOS_VL53`), peso do feixe exp(-1,2 k²) (borda ~30%), sinal =
  fração do feixe no objeto × (alcance/d)² ≥ 1. Antes eram 5 raios, os da borda com alcance fixo
  (35%/70%), e a janela desenhava só o do meio; a geometria perto já batia com o cone (conferido com
  um cubo deslocado de lado). A janela agora desenha o leque. Cubo de frente some a ~600 mm.
  O desenho do leque (`_leque()` no `sim/gui.py`, igual na Line e na Maze) usa uma superfície só do
  tamanho do leque. A primeira versão criava uma do tamanho da janela por sensor e por quadro: o
  quadro ia de 3,4 para 9,8 ms e, como a janela e a física dividem o processo, o código da Challenger
  com a janela a 8x caía de 1,40x para 0,75x (um aluno reclamou de lentidão). Agora: 3,7 ms e 1,38x.
* **Relógio e travas** (31/10): o código da equipe Challenger mudava com a velocidade (entrega aos
  3:00.07 a 2x e 3:00.41 a 8x). Causa: a thread principal parada no `I2C_LOCK` enquanto a thread dos
  sensores o segurava dormindo (VL53 medindo) não contava como "esperando", o relógio não andava e,
  depois de `LIVRE_APOS`, ia pelo tempo real. `fake_hw/cliente.py` (`RelogioSinc.instala`) troca
  `threading.Lock`/`RLock` do programa por travas vigiadas (`_TravaVigiada`/`_TravaVigiadaR`):
  esperar uma trava conta como espera (sem hora, ou até o timeout em tempo simulado). Depois disso,
  2x e 8x deram a mesma partida. Ao levar para a Maze, a primeira versão (que só embrulhava o lock
  real com `espera_externa()`) ainda mudava com a velocidade (320,6 s a 8x, 321,9 s a 2x): entre a
  dona soltar e a thread da fila voltar a rodar, esta ainda constava como esperando e o relógio podia
  andar. Agora o estado da trava fica no `cond` do relógio, e o `release()` passa a trava direto para
  a primeira da fila e a tira da lista de espera; uma thread interrompida na fila sai dela e passa a
  trava adiante. Testes daqui, da Line e da Maze iguais a 2x e 8x.
* **Flask e a fábrica das travas** (03/11, achado pelo Luiz, da equipe Challenger, rodando o
  `main.py` deles direto, sem o adaptador): o `threading.Lock` trocado era um `lambda`, e o werkzeug
  guarda `Map.lock_class = threading.Lock` na classe e chama `self.lock_class()`: o lambda virava
  método e recebia o `self` (`TypeError` no `Flask(__name__)`). Agora é um `_FabricaTrava` (objeto
  com `__call__`, que não vira método), nos três `cliente.py`. E o Flask é falso no `fake_hw`
  (`fake_flask.py`, só aqui no Challenge): o servidor de verdade fica parado num `select` do socket,
  que o relógio não vê como espera, e a partida inteira iria pelo tempo real. Antes o Flask falso
  estava só no adaptador da equipe.

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
  125 pontos, iguais a 2x e 8x (ver a `ANALISE.md`; números depois do VL53 em leque e da segunda
  versão das travas; com a primeira eram 165 e mudavam com a velocidade). Gerado por `professor/challenger2026/simulador/gera_robo.py` sobre o
  `robo_bombertinho_antes.json` de lá. O `exemplo_bombertinho` foi ajustado junto (`cores_lona.json` =
  aprende_cor).
* **Código novo da equipe (02/11/2026**, `CBR-challenger-2026.zip`, commit `9b1c3f2`): está em
  `professor/challenger2026/codigo/` (o de 30/10 ficou em `codigo_20261030/`). Como está: 200 pontos
  (`cenario_challenger.json`, semente 1). As garras não pegavam depois da primeira entrega: **defeito
  do código deles**, não do simulador (o `estado_servo_garra` do `movimentos.py` não é atualizado
  com `suave=False`, e o `fecha_garra()` seguinte não manda nada; detalhes no topo da `ANALISE.md`).
  Com as duas linhas da correção: 280 (4 entregues). Para investigar coisas assim, registrar o
  `robo.servos` a cada passo da `GarraParalela` mostra o que o programa mandou de verdade.
* Vista de lado das garras no painel (02/11/2026, pedido do Julio): `GarraParalela.info()['lado']`
  traz a geometria e `Interface._desenha_garra_lado` desenha (cabeça verde/laranja/cinza pela
  altura). Garra sem `'lado'` (a simples) continua com a linha de texto.
* `tcs_i2c[].ganho` e `refletancia` (no robo.json) existem para isso: calibrar os TCS do mux para as
  leituras de um robô real. Sem eles, vale o `REFLETANCIA` de `sim/fisica.py`.

## Lote de partidas (`lote.py`, 31/10/2026)

Pedido para a equipe Challenger ver só as partidas com problema. Roda o `simulador.py --sem-janela` em
subprocessos (`ThreadPoolExecutor`, `--paralelo` = metade dos núcleos), uma semente por partida;
`--sortear` sorteia o cenário pela mesma semente (`arena.sorteia`) e `--inicio X,Y,ÂNG` fixa o início
(o código da equipe só funciona começando na rua de baixo: 380,150,0). Grava em `resultados/lote_DATA/`
(no `.gitignore`) o cenário, o log e o `--resultado` de cada semente, `resumo.txt` e `resumo.csv`.
"Problema" = evento negativo, `Traceback` no log, programa que parou antes do tempo, ou 0 pontos.
O comando "rever" usa `--enter-automatico` (novo no `simulador.py`: com janela, o `input()` segue
na hora como sem janela), senão a espera do Enter muda a partida. Diferente do `avalia.py` da Line:
não tem desafios nem meta.
Desde 01/11 cada partida roda numa cópia da pasta do programa (`pasta_rodada()`, `--pasta-trabalho`
do `simulador.py`), como no `avalia.py` da Line e da Maze: em paralelo, as partidas dividiam os
arquivos que o programa grava com caminho relativo. Conferido com o `exemplo_bombertinho` e com o
código da Challenger (o adaptador importa `../codigo` e continua funcionando). O fim da partida
também deixou de gerar `Traceback` falso (`_Interrupcao` no `cliente.py`; ver o `CLAUDE.md` da Maze).

## Pendências

* **Bombertinho**: ângulos dos servos, canais do mux, porta do 2º sensor de linha, massa, motores,
  roletes. A pose de início dos cenários (x = 380) é a do robô provisório: a cabeça da garra da frente
  na horizontal passa da linha azul. Juiz: limite de 2 cubos por viagem.
* **Adversário**: um `Servidor` por robô (o construtor já aceita `robo=`), `SIM_PORTA` próprio para
  cada programa e o relógio sincronizado esperando os dois.
* `avalia.py` e desafios, pacote portátil (`monta_portatil.py` da Line), curso.
