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
#   → TOTAL 415
python avalia.py --desafio M01 --programa exemplo_aluno/main.py
#   o exemplo cumpre 3/3 em cada desafio, de M01 a M06
```

Com o relógio sincronizado a velocidade não muda o resultado: em 19/10, `--velocidade 5` e `20` deram o
mesmo 415 (mesmo tempo de rodada, 320,5 s). A velocidade 20 só fica limitada pela CPU (~70 s reais).
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
roda (motor trava ou a roda patina). O ruído do VL53 é por raio num cone de 25°; os raios da borda só
enxergam perto e ignoram retorno rasante (senão pegavam o pilar da parede).
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

## Desafios e `avalia.py`

* `avalia.py` é o mesmo da Line (detecta a Maze por não ter `sim/resgate.py`); o da Line ganhou o
  `.ino` do Paçoca depois. Corrigiu algo comum? Leve para lá também.
* Nomes que as metas em `desafios/desafios.json` usam: `total`, `lop`, `tempo`, `erro_programa`,
  `svi`, `srd`, `sbv`, `ssn`, `vitimas` (= `svi`), `saida`, `erros`.
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
  simples que o da Line (um ponto por canal com cruz de ±5 mm, sem altura nem curva do ITR8307); as
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
