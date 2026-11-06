# simuladorMaze — guia para o Claude Code

Simulador 2D da **RoboCupJunior Rescue Maze** (regra 2026) para a equipe desenvolver posicionamento,
roteamento e descoberta do mapa com o **mesmo código do robô real** (robô da CBR 2026, base Mariola).
As libs reais do Mariola rodam sem alteração; o simulador emula serial/I2C/GPIO/relógio e o firmware
das placas byte a byte.

Leia antes de mexer: `README.md` (física, firmware emulado, juiz, `robo.json`, limitações, estrutura).
As regras gerais do repositório estão no `CLAUDE.md` da pasta de cima. O `simuladorLine` nasceu deste
e os dois compartilham ideias e boa parte do código (`fake_hw/`, `avalia.py`, relógio sincronizado,
painel da tela/teclado): ao corrigir algo comum aqui, veja se vale lá também, e vice-versa.

## Teste de referência

```bash
# apague exemplo_aluno/checkpoint_maze.json antes de cada rodada sem janela
# (senão o programa retoma do checkpoint da rodada anterior)
python simulador.py --sem-janela --programa exemplo_aluno/main.py --mapa mapas/exemplo1.json --velocidade 5 --tempo 480 --semente 1
#   → TOTAL 415, rodada de 320,6 s
python avalia.py --desafio M01 --programa exemplo_aluno/main.py
#   o exemplo cumpre 3/3 em M01-M04 e M06; M05 2/3 (31/10, ver "VL53 em leque" abaixo)
```

Com o relógio sincronizado a velocidade não muda o resultado: em 19/10, `--velocidade 5` e `20` deram o
mesmo 415 (mesmo tempo de rodada, 320,5 s); em 31/10, `2` e `8` deram o mesmo log, linha a linha
(320,6 s). A velocidade 20 só fica limitada pela CPU (~70 s reais).
Cada rodada do `avalia.py` roda numa pasta de trabalho própria (ver "Pasta de trabalho por rodada"),
mas dois `avalia.py` ao mesmo tempo ainda gravam os mesmos `resultados/logs/` (o nome é
desafio + semente): o log de um sobrescreve o do outro.
A nota antiga "com 20 o exemplo fica instável" era do relógio real e não vale mais.
Na janela, "Nova rodada" apaga os arquivos de `arquivos_rodada` (`checkpoint_maze.json`); sem janela,
apague à mão.

## Arquitetura

O programa do aluno roda em processo separado (`rodar.py`) com módulos falsos de `serial`, `smbus2` e
`gpiod` (`fake_hw/`), relógio virtual e `Portas.porta_serial_real` trocado para devolver `sim://SERIALn`.
As libs reais (pasta do programa, depois `libs_mariola/`) não sabem que estão no simulador. O hardware
falso conversa com o simulador por TCP local (JSON com prefixo de tamanho; `sim/protocolo.py`,
`sim/servidor.py`: `mariola_quadro`, `placa_quadro`, `cor`, `vl53`, `gpio_*`, `vitimas`, `kit`, `debug`).
Física 2D em pymunk a 240 Hz, unidades em mm, tração skid-steer com atrito longitudinal e lateral por
roda (motor trava ou a roda patina). VL53 em leque de 25° (21 raios), ver "VL53 em leque" abaixo.
`deteccaoVitimas`, `dispensadorKits` e `simdebug` são módulos do simulador (`fake_hw/sim_modulos.py`);
os de `robo_real/` são os modelos para pôr no robô.

## Relógio sincronizado (desde 18/10, não quebrar)

Igual ao da Line (veja o `CLAUDE.md` de lá): o tempo do programa só anda quando todas as threads dele
estão esperando; mesma semente = mesma rodada, em qualquer velocidade e em paralelo. `--tempo-real`
volta ao modo antigo. Detalhes desta pasta:

* Cada sensor tem o próprio gerador aleatório em `sim/fisica.py` (`rng` = terreno, `rng_vl53`,
  `rng_giro`, `rng_cor`, `rng_cam`), todos derivados da semente. Assim, ler um sensor a mais não muda
  o ruído dos outros. Sensor novo com ruído = gerador novo, não use os existentes.
* Detecção de vítimas (`fake_hw/sim_modulos.py`): a "foto" é tirada na hora da chamada e o resultado
  chega `deteccao.tempo_processamento_s` depois (0,1 s no `robo.json`), com o robô andando nesse meio
  tempo, como no Mariola.
* Por causa do relógio, os desafios M01–M06 exigem 3 de 3 (antes, com relógio real, 2 de 3).
* Travas (desde 31/10): o `RelogioSinc.instala()` troca `threading.Lock`/`RLock` do programa por
  `_TravaVigiada`/`_TravaVigiadaR` (`fake_hw/cliente.py`). Esperar uma trava conta como espera, e o
  `release()` passa a trava direto para a primeira da fila, já tirando ela da lista de espera, com o
  `cond` do relógio na mão. Sem isso, uma thread parada no lock enquanto a dona dormia segurava o
  relógio e, depois de `LIVRE_APOS`, ele ia pelo tempo real (a partida da equipe Challenger mudava
  com a velocidade). A primeira versão (do Challenge, que só embrulhava o lock real com
  `espera_externa()`) deixava o relógio andar entre o `release()` e a thread da fila voltar a rodar:
  aqui ela deu 320,6 s a 8x e 321,9 s a 2x. Uma thread interrompida (`KeyboardInterrupt` do fim da
  rodada) enquanto espera na fila sai dela e, se já tinha recebido a trava, passa adiante.
  Desde 03/11 o `threading.Lock`/`RLock` trocado é um `_FabricaTrava` (objeto com `__call__`), não um
  `lambda`: biblioteca que guarda `threading.Lock` num atributo de classe (o werkzeug do Flask) e
  chama `self.atributo()` passava o `self` para o lambda (`TypeError`). Detalhes no
  `simuladorChallenge/CLAUDE.md`.

## `input()` do programa (29/10/2026)

A equipe usa `input('pare')` como pausa quando roda o programa pelo ssh. O `fake_hw` troca o
`builtins.input` por `cliente.entrada()`, que funciona assim:
* imprime o texto;
* faz a operação `entrada` (o simulador guarda o texto em `Simulacao.entrada`);
* consulta `entrada_estado` a cada 50 ms reais até chegar a resposta.

Na janela, a tecla Enter ou o botão da faixa amarela no alto do console chamam
`responde_entrada()`. No relógio sincronizado, a thread parada no `input()` conta como esperando para
sempre (`espera_externa()`, acorda em `math.inf`). Se todas as threads estão assim, o `_coordena` usa
`avanca livre`: o tempo anda pelo relógio real, na velocidade escolhida, e o timeout de 5 s dos
motores acontece como no robô. Sem janela, `enter_automatico` responde na hora (o teste de referência
continua 415). Levado para a Line no mesmo dia; o `fake_hw/cliente.py` é o mesmo arquivo nos três
simuladores (Line, Maze e Challenge): mudou um, copie para os outros e rode os testes dos três.

## Desafios e `avalia.py`

* `avalia.py` é o mesmo da Line (detecta a Maze por não ter `sim/resgate.py`); o da Line ganhou o
  `.ino` do Paçoca depois. Corrigiu algo comum? Leve para lá também.
* Nomes que as metas em `desafios/desafios.json` usam: `total`, `lop`, `tempo`, `erro_programa`,
  `svi`, `srd`, `sbv`, `ssn`, `srn` (rampas, desde 06/11), `vitimas` (= `svi`), `saida`, `erros`.
* `ferramentas/labirinto_surpresa.py` gera os labirintos de M04–M06 (fácil/médio/difícil, semente).

## Robô (`robo.json`)

* Dimensões 190 × 170 mm, 1,6 kg: **estimadas**, falta o Julio medir.
* Motores: traseira esquerda = Mariola canal 1; traseira direita = Mariola canal 2 (invertido);
  dianteira esquerda = placa id 8; dianteira direita = placa id 51 (invertida). As duas placas no
  `SERIAL1` a 250000 bps. Portas: `SERIAL0` Mariola, `SERIAL1` placas de motor (e servos),
  `SERIAL5` giroscópio, `SERIAL6` Pro1616 (V2).
* Roda: Xiaomi Mijia E10/B112/E12 (robô aspirador), 70 mm × 15 mm. `reducao` 34 e `rpm_livre` 130 são
  **chutes**: quando o Julio medir, os campos `contagens_por_volta_mariola/placa` e
  `calibracao_mariola/placa` do `motor_padrao` têm prioridade (o `_medidas_reais` explica como medir).
  No PID, comando 100 = 80% de `rpm_livre`.
* Para-choque P1 (esq) / P2 (dir), botão de início P3.
* `cores_piso` na escala do firmware (branco 127 / IR 100; prata TCS ~200, IR ~80): estimados,
  trocar pelos lidos no robô.

### `robo_maze2026.json` (05/11/2026): o robô do código da equipe

O código real da equipe fica fora deste repositório, em `Documents\Arduino\maze2026` (GitHub
IzadoraVB/maze2026, privado). Desde 04/11 a versão em uso é a **branch `adaptacao-claude`** (o
`maze2026_simplificado` do professor, ajustado no robô real); a `main` parou em 03/11, com marcadores
de conflito. O `main.py` da branch cai sem câmera (o `except` do import faz `tem_branco = True` e
depois chama `tem_branco()`; com OpenCV, procura os `.png` em `/home/banana/maze2026`): para rodar,
`professor/maze2026/simulador/main_sem_camera.py` troca só a detecção de vítimas. A ligação veio do
`robo.py`/`sensores.py`/`constantes.py` da branch, que a equipe acertou no robô real em 04-05/11:
* motores: Mariola canal 1 invertido; placas no `SERIAL2`: id **72** na dianteira esquerda, id **5**
  invertida na direita (até 05/11 era o contrário, como os nomes do `defs.py` antigo; o Julio tinha
  confirmado em 29/10, mas a equipe trocou no robô);
* giroscópio no `SERIAL4`, **diminuindo para a direita** (`z_horario_positivo: false`; "o giroscópio
  diminui ao girar à direita", medido pela equipe);
* 5 VL53: borda esq `I2C1` (13 mm para dentro), meio esq `I2C3`, borda dir `I2C6`, meio dir `I2C7`
  (37 mm para dentro: o código desconta do meio agora) e frente `I2C8` (posição estimada). Até 05/11
  eram 4, com o I2C6 no meio e o I2C7 (−37) na borda direita;
* para-choque P1/P8.

Contagens: 440 por volta no Mariola e 880 na placa desde 05/11/2026 (`CONTAGENS_POR_MM = 2` da
equipe, ajustado no robô; ainda falta a volta da roda à mão). De 03/11 a 05/11 foram 940/1880 (medida
do Boberto, que não valeu para este robô); antes, 481/962 (1 cm = 1000/45,7 do código antigo). A
calibração (16 no Mariola, 32 nas placas, do `calibracao_manual(32, -32)`) não mudou: ~109 rpm livres.
O `maze2026_simplificado` do professor ainda usa `CONTAGENS_POR_VOLTA = 940`: com este json ele anda
o dobro do que pede.

Conferido com os `movimentos.py` da equipe (com os 481 antigos; com 940 o robô anda metade):
* andar 30 cm → 302 mm;
* `girar(+90)` → 92,6° horário (giroscópio +93);
* 4 rodas juntas.

As libs da equipe (`maze2026/libs/`) são mais antigas, entram pelo pacote `libs` (o `fake_hw` põe
`pasta/libs` no `__path__`) e ainda usam o `botoes.py`, que abre o `gpiochip0`: o `gpiod` falso
aceita qualquer chip, então o simulador não pega o problema do kernel 6.18.

### 6 VL53L0X atrás do mux I2C (TCA9548A)

| nome | mux | x | y | ângulo |
|---|---|---|---|---|
| esq_frente | I2C1 | 70 | 85 | 90 |
| esq_tras | I2C2 | -70 | 85 | 90 |
| dir_frente | I2C3 | 70 | -85 | -90 |
| dir_tras | I2C4 | -70 | -85 | -90 |
| frente | I2C5 | 95 | 0 | 0 |
| tras | I2C6 | -95 | 0 | 180 |

`exemplo_aluno/robo.py` cria `VL53L0X(Portas.I2C6)`. Se o `tras` sumir do `robo.json`, o programa para
com "OSError: [VL53L0X] Sensor não encontrado". Isso já aconteceu uma vez (18/10), quando o arquivo foi
regravado a partir de uma cópia antiga. O `robo.json` certo tem os 6 sensores e
`deteccao.tempo_processamento_s = 0.1`. Ao editar, mude só a chave necessária.

## Fatos do robô real

* Tração 4x4: 2 motores no Mariola + 2 nas placas de controle de motor do Julio, todos com encoder;
  motores/rodas de robô aspirador. Encoder: 17 pulsos por volta no eixo do motor (antes da redução).
  O Mariola conta um canal nas duas bordas (x2); a placa de motor conta em quadratura (x4) = o dobro.
* Giroscópio: Z em graus, acumulando, positivo no sentido horário; trocar GYRO↔GYRO2 zera o Z.
* Para-choque com 2 botões (P1 esquerdo, P2 direito; apertado = nível baixo).
* Sensor de cor/reflexão no chão: Pro1616 (V2). Branco dos TCS calibrado em ~127 de propósito, para o
  piso prata/reflexivo passar de 127. No IR o prata fica abaixo do branco (~80).
* LEDs RGB do Mariola: 0-3 iluminam a câmera esquerda, 4-7 a direita, 8-9 são a indicação de vítima
  (só estes contam para o juiz).
* Kits de resgate: 1 ou 2 por lado (esquerdo/direito). Kit em desenvolvimento: esfera de 1,4 cm
  parcialmente cheia de areia; sai pela lateral rolando, bate na parede e para. No simulador o kit vale
  pela posição em que caiu.
* Detecção de vítimas por câmera: só stub (`deteccaoVitimas`), com os modelos para o robô em `robo_real/`.
  O stub exige os LEDs de iluminação acesos (`deteccao.exige_iluminacao`); o exemplo acende depois do
  botão de início, e o timeout de 5 s do Mariola apaga tudo (por isso o `espera()` do exemplo manda
  comando a cada 0,5 s).

## Kit de resgate (regra 2026, seção 3.7 e pontuação)

* A regra **não** exige cubo: mínimo de 1 cm em cada dimensão e 1 cm³ depois de liberado, no máximo 8,
  não pode rolar nem quicar para longe, liberação clara para o juiz. A esfera de 1,4 cm (~1,44 cm³)
  passa; o limite seria 1,24 cm de diâmetro.
* Vale a posição do kit quando o robô sai inteiro do raio de 15 cm da vítima. Risco levantado: o robô
  girando no lugar chutar o kit encostado na parede. Com as medidas estimadas, o canto do robô varre
  ~127 mm do centro e a bolinha começa a ~136 mm (folga de ~9 mm; some se o robô estiver 10 mm
  deslocado para a parede). Refazer a conta com as medidas reais.
* Ideia oferecida e ainda não feita: simular o kit saindo pela lateral, rolando até a parede, e o robô
  podendo chutá-lo. Hoje o kit cai a `kits.distancia_lateral_mm` (15 mm) da lateral e fica parado.

## Exemplo do aluno (`exemplo_aluno/`)

* `robo.py`: `CONTAGENS_POR_VOLTA = 17 × 34 × 2` (Mariola) e `× 4` (placa); `z()` troca o sinal do
  giroscópio (positivo = esquerda); `anda_mm()` centraliza no corredor pelos VL53 laterais;
  `alinha_parede_lateral()` faz média de 4 leituras; cor do piso pela lib V2 com `cores_piso.json`
  (gerado por `calibra_cores.py`). `corPiso.py` é só um aviso: pode apagar.
* `main.py`, truques que já resolveram bugs: preto lido ao chegar no centro do ladrilho é ignorado
  (o robô passou um pouco do centro e o sensor já vê o ladrilho seguinte); com parede à frente a menos
  de 700 mm, `avanca()` para pela distância da parede e aceita andar até `LADRILHO + 25` pelo encoder.

## Cuidados com o firmware emulado (é o que mais pega)

* Mariola: PID a 40 Hz; o alvo é o `map()` do Arduino (com truncamento inteiro) em pulsos por 25 ms.
  Respostas de motor com cabeçalho 0xFC (0xFB no ATUALIZA); bytes que sobram no buffer depois de um
  quadro são descartados. `CALIBRA_MOTORES` deixa o Mariola ~26 s sem responder.
* Mariola: timeout de 5 s sem pacote solta os motores e apaga **todos** os LEDs. Giro por ângulo em
  int16; ângulo 0 mantém o alvo; um novo `atualiza_motores()` depois de chegar no alvo volta a girar.
* Mariola (firmware de 19/10): 0xF1/0xF0 = LEDs da porta 4 (segunda fita, 10 LEDs; o primeiro desliga
  o servo 4), servo 4 com ângulo ≤ 180 (e o Timer2 dos servos) volta a porta para servo. Emulado nos
  dois simuladores (`FirmwareMariola.leds_porta4`, só o estado: não é desenhado), e `fake_hw` aceita
  de 0xEC a 0xFD.
* Mariola, Timer2 (firmware de 26/10/2026; especificação em `documentação/Motores.md`): servos,
  ventoinha (0xF2) e buzzer (0xEC-0xEF) dividem o timer e **o primeiro uso fica com ele até
  reiniciar** (`FirmwareMariola.modo_timer2`: 0 livre, 1 servos, 2 ventoinha, 3 buzzer; reinicia na
  rodada nova). Conta como uso: `ENVIA_SERVOS` com algum ângulo ≤ 180, o primeiro 0xF2, o primeiro
  som/tom (parar e 0xEC não contam). Ventoinha ou buzzer primeiro desligam os servos. O dono errado é
  ignorado: 0xF2 responde 0xF2 igual, 0xFD responde 0xFD igual, o buzzer responde status 0. O timeout
  de 5 s solta os servos e para o buzzer, não a ventoinha.
* Mariola, buzzer: respostas de 3 bytes `[comando, status, modo do Timer2]`. O som não toca no PC: o
  simulador só guarda até quando ele toca (`buzzer_fim`, tempo simulado), com a duração calculada como
  o `buzzerGeraSegmento` do firmware (velocidade, varreduras em passos de 10 ms, 250 ms entre as
  repetições das melodias, 255 = para sempre) pela tabela `sim/buzzer_mariola.py`, cópia da
  `sonsBuzzer` do `placaBrickVendra/buzzer.h` (conferida nota a nota em 26/10; o mesmo arquivo está na
  Line). O nível (0xEC) fica em `FirmwareMariola.nivel_buzzer_eeprom` (vale até fechar o simulador).
  Na lib: `toca_som`, `toca_tom`, `para_buzzer`, `buzzer_tocando`, `espera_buzzer`,
  `set_nivel_buzzer`/`nivel_buzzer`; `exemplos/13-buzzer/main.py` roda inteiro no simulador.
* Placa de motor: giro em uint16; giro 0 **cancela** o alvo (diferente do Mariola); 5 s sem pacote
  para os motores; ~12 s sem pacote (10 s + watchdog de 2 s) a placa reinicia e a contagem volta a 0.
  Comandos de ajuste (KP etc.) devolvem o valor ajustado, não a contagem. Calibração ~14 s, zera a
  contagem.
* Pro1616: lê a ~50 Hz; 30 s sem pedido para de ler e o primeiro pedido devolve valor velho.
  Calibração do branco ~7 s, do preto ~2,2 s.
* Tudo isso foi tirado de `placaBrickVendra.ino`, `placaControleMotor.ino` e `sensorLinhaPro1616.ino`.
  Não "conserte" um comportamento estranho do firmware emulado sem conferir no `.ino`: ele imita o robô.

## Pendências

* O Julio ainda vai passar: confirmação de ligação/portas/pinos, dimensões reais do robô e posição de
  sensores e câmeras, contagens por volta e calibração medidas, leituras reais das cores do piso e o
  firmware do giroscópio (hoje o giroscópio é emulado só pelo comportamento descrito acima).
* Geometria do Pro1616 no `robo.json` atualizada em 19/10 para a real (a mesma da Line): TCS em
  x = 71, y = ±20 e 0; IR em x = 80, y = ±26,6 e ±8,9 (centro de cada grupo de 3 ITR). Antes era
  TCS ±40/0 e IR ±45/±15. O exemplo continuou com 415 e M01–M06 3/3. O modelo da Maze continua mais
  simples que o da Line (um ponto por canal com um disco de 5 mm, 19 amostras desde 31/10; antes
  era uma cruz de ±5 mm; sem altura nem curva do ITR8307); as
  posições x são estimadas, falta o Julio medir.
* "Sugestão 2" (motor com carga, leitura "velha" do VL53) adiada, a pedido do Julio; está nas limitações.
* `threading.Event.wait(timeout)` e `Queue.get(timeout=...)` usam o relógio real e não contam como espera
  no relógio sincronizado (documentado no README).
* Mudou API, robô, mapas ou placar? Atualize o `README.md` e confira `curso/12-simulador-maze.md`,
  `curso/16-projeto-rescue-maze.md`, `curso/codigos/09_maze/` e `professor/gabarito/`.
* `professor/gabarito/codigos/m16/ex4_zona_main.py` e `ex4_zona_navegacao.py` são cópias do
  `exemplo_aluno/main.py` e do `navegacao.py` com uma mudança (entrar na zona de perigo); o
  `ex1_mao_esquerda.py` é o `curso/codigos/09_maze/mao_direita.py` espelhado. Mudou o exemplo ou o
  tutorial? Refaça as cópias e confira os números no `professor/gabarito/16-projeto-rescue-maze.md`.

## Trazido do simuladorChallenge (31/10/2026; nada commitado ainda)

* **Travas no relógio:** feito (ver "Relógio sincronizado"). O `cliente.py` é o mesmo nos três.
* **VL53 em leque** (`sim/fisica.py` `vl53()`, desenho no `sim/gui.py` com `_leque()`, numa
  superfície só do tamanho do leque: ver o porquê no `simuladorChallenge/CLAUDE.md`), igual ao Challenge: 21 raios
  (`RAIOS_VL53`), peso exp(-1,2 k²), sinal = fração do feixe na forma × (alcance/d)² ≥ 1, vale a
  forma mais perto com sinal. Aqui a forma é o segmento de parede (`segmentos_parede()` já junta as
  colineares). Antes eram 5 raios, os da borda com alcance fixo (35%/70%). O teste de referência
  continuou 415 (320,6 s), mas o exemplo ficou mais frágil: o leque pega a ponta de uma parede
  vizinha com mais frequência (com o robô torto 11° os dois modelos leem 138 mm; com 6°, só o
  antigo lia 194). Resultados comparados com o simulador antigo:
  * M05: 3/3 → 2/3. No `labirinto_medio_2`, semente 2, o `le_paredes()` do exemplo (que usa
    `min()` dos dois VL53 do lado) marca parede à direita no 3º ladrilho (robô torto ~11°, um sensor
    lê 151 mm e o outro 626), acha que explorou tudo e volta aos 34 s: 0 pontos;
  * `M01_exemplo.json`, sementes 1-6: o exemplo se perde na volta nas sementes 4 e 6 (340);
  * `maze2026_simplificado`: 2 das 5 rodadas do `LEIAME` não acham o caminho de volta.
  Com o `fisica.py` antigo e o `cliente.py` novo, todas essas voltam ao início: a causa é o leque.
  O Julio decidiu (31/10) **manter o leque por enquanto**, sem mexer no exemplo. Se for reforçar o
  exemplo depois: parede lateral só com os dois sensores do lado perto (hoje é o `min()`).
* **Mancha do sensor de cor/reflexão:** trazida. `_amostra_piso` usa o disco de 19 pontos
  (`PONTOS_MANCHA`) no lugar da cruz de 5 (±5 mm). M01-M06, teste de referência e 16.3/16.4 do
  gabarito deram os mesmos números; mudaram só os tempos do `maze2026_simplificado` (ver o `LEIAME`
  de lá). Um primeiro teste mostrou o M01 e o M02 piores, mas era a trombada de dois `avalia.py` na
  mesma pasta (ver "Pasta de trabalho por rodada").

## Espessura das paredes (02/11/2026)

Antes era fixa em 20 mm (`MEIA_PAREDE = 10` no `sim/mapa.py`). Agora é `Mapa.espessura_parede`
(campo `espessura_parede` do `.json`, de 1 a 50 mm, uma só para o mapa todo), com
`Mapa.meia_parede` usado pela física (raio do `pymunk.Segment`, que o VL53 e o para-choque
enxergam), pelo desenho e por `ponto_vitima()` (a vítima fica na face da parede). Mapa sem o campo
= 20 mm, então nenhum mapa antigo nem número de teste mudou (referência: 415, 320,6 s). No editor:
"Parede −/+" (1 mm, Shift 0,5 mm). O exemplo, semente 1, no `exemplo1` com parede de 6 mm: 415
(322,3 s); com 15 mm: 415 (321,9 s). Mudar a espessura não mexe na grade: os ladrilhos continuam
com 300 mm de eixo a eixo.

## Rampa e escada que mudam o nível (06/11/2026)

Pedido do Julio: rampa e escada de um ladrilho, até 25°, com o ângulo escolhido no mapa, e **sem
passagem por baixo das áreas altas** (o mapa do programa da equipe continua uma matriz 2D).

* Mapa (`sim/mapa.py`): ladrilho com `terreno` `rampa`, ou `escada` com `sobe`, mais `graus` (padrão
  15) e, na escada, `degrau_mm` (máximo 20, regra 3.4.6). A escada sem `sobe` é a antiga (efeito,
  sobe e desce no ladrilho) e não mudou. `inclinacao()`, `desnivel()`, `degraus()` (espelho k em
  (k − 1/2)·300/n, então a quina fica no ângulo), `laterais()`, `subida()`, `gradiente()`,
  `altura_piso(x, y, niveis, plano=)`. `niveis()` dá a altura de cada ladrilho (busca a partir do
  início em 0, atravessando as bordas sem parede; num inclinado, a da borda de baixo) e os conflitos;
  fica em cache por uma chave com ladrilhos e paredes. `pode_passar()` não passa pelos lados da
  rampa/escada; `validar()` avisa graus fora da regra, lado sem parede e alturas que não fecham.
* Física (`sim/fisica.py`): tudo atrás de `Mundo.com_niveis` (o mapa tem rampa/escada). Sem isso a
  conta é a de antes: referência 415, 320,6 s, conferida depois da mudança. Com isso:
  `_atualiza_plano()` a cada passo (mínimos quadrados das alturas embaixo das 4 rodas;
  `_altura_roda()` faz a roda encostar na quina do degrau), pitch/roll do giroscópio pelo plano, e
  em `_rodas()` a mesma conta do simuladorLine de 04/11 (gravidade, peso nas rodas de baixo com
  `geometria.altura_cg_mm` 45, deriva lateral com `terreno.rigidez_lateral` 3, velocidade da roda ×
  cos), mais a redução segurando a roda solta (`motor_padrao.atrito_reducao_N`, 3 N; sem isso o
  robô parado descia a rampa). VL53: `_raio_3d()`/`_raio_piso()` (altura do sensor `altura_mm`,
  padrão 50; parede de min(pisos) a max(pisos) + 150 mm; o feixe que passa por cima ainda pega a
  parede com a parte de baixo do cone, com o peso proporcional; piso da escada = plano das quinas).
* Juiz: `rampas` (10 cada, `SRN` × 5 no bônus de saída, regra 2026 5.6.9/12), a escada nova conta como
  escada (10, `SSN`). O `SRN` só aparece no `info` dos mapas com rampa (a linha do placar dos outros
  não mudou); o `avalia.py` aceita `srn` nas metas.
* Editor (`sim/gui.py`): ferramenta "Rampa/escada" (`_clique_nivel`, `_roda_nivel`): clique troca o
  tipo e o lado que sobe, põe as paredes dos lados e abre as pontas; roda = graus, Shift+roda =
  degrau. Desenho: `_desenha_nivel` (faixas e seta), área alta azulada com "+N mm".
* `mapas/rampa_escada.json` (4 × 6): térreo, área alta a 109 mm, rampa de 20° em (1,1) e escada de 20°
  em (1,4) (6 degraus de 18,2 mm). Exemplo, semente 1: sobe a rampa, desce a escada e volta: 160
  (SVI 2, rampa 10, escada 10, 0 LoP, 164,8 s).
* Testes sem programa (scripts do scratchpad, potência 40): na rampa a velocidade cai para ~cos 20° e
  o pitch vai a 20°; parado no meio da rampa escorrega 1,7 mm em 5 s; girar 90° no meio dela desce
  ~100 mm; descendo a escada o robô desvia ~3° (solavancos dos degraus).

## Pasta de trabalho por rodada e o "erro no programa" falso (01/11/2026)

Dois defeitos antigos faziam o `avalia.py` marcar "erro no programa" (ou dar resultado errado) numa
rodada que estava boa. Os dois foram corrigidos nos três simuladores.

* **Checkpoint dividido:** as rodadas de um `avalia.py` correm em paralelo e o exemplo grava o
  `checkpoint_maze.json` com caminho relativo, na pasta em que roda. Com uma pasta só, no mesmo mapa
  (`--mapa ... --sementes 1-6`) as rodadas chegavam ao prata quase juntas e às vezes uma morria na
  gravação (no Windows o `os.replace` falha se outro processo mexe no arquivo: 16.4, semente 1 da
  zona, 210 em vez de 495); e uma rodada podia ler o checkpoint de outra depois de um LoP.
  Agora o `simulador.py` tem `--pasta-trabalho` (`Simulacao.pasta_trabalho`; o `app.py` passa
  `SIM_PASTA_TRABALHO` e o `rodar.py` faz `chdir` para ela; os `arquivos_rodada` são apagados nela).
  O `avalia.py` (`pasta_rodada()`) copia a pasta do programa para uma pasta temporária por rodada
  (sem `__pycache__`, `.git`, `resultados`...; pasta acima de 50 MB não é copiada) e apaga no fim. O
  programa continua rodando do lugar original: imports e caminhos a partir de `__file__` não mudam
  (o adaptador das equipes, que importa `../codigo`, continua funcionando); só os caminhos relativos
  caem na cópia. O `.ino` do Paçoca não é copiado. Na janela nada muda.
  Cuidado que já pegou: o `rodar.py` fazia `chdir` para a pasta do programa e desfazia a pasta de
  trabalho (o exemplo leu um checkpoint velho da pasta original e o M04 deu 0 em 4 s).
* **Fim da rodada no meio de uma conversa:** ver `_Interrupcao` no `fake_hw/cliente.py`. O
  `KeyboardInterrupt` do fim da rodada fica guardado enquanto a thread principal está num
  `Conexao.chamar()` e é levantado logo depois da resposta (antes, a resposta ficava no socket e
  outra thread a lia: `KeyError: 'v'` no log).
* Conferido: M01-M06 com os mesmos números (M05 2/3), 16.4 com 390 (exemplo) e 495 (zona) sem
  nenhum "erro no programa", nenhum checkpoint na pasta do exemplo depois do `avalia.py`.
