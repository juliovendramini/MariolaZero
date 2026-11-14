# Problemas e pegadinhas conhecidos da Maze

Cada item: sintoma → causa → o que fazer (e onde ler mais). Confira no código se ainda vale. Os do brick, das
libs e do envio estão em `.claude/skills/especialista-mariola/referencias/problemas.md`.

## Movimento: andar e girar

* **`Exception: Erro ao ler o estado dos motores` no meio da rodada** (aconteceu com a equipe em
  12/11/2026, no `zerar_distancia()` do `andar_mm_corrigindo`, com `usb 1-1: reset high-speed USB device`
  no `dmesg`) → o hub USB do brick reiniciou e a lib antiga da equipe desistiu em 10 ms. Causa elétrica e
  o que fazer: o item do hub USB nos problemas da skill especialista-mariola. A correção da lib (12/11) está
  em `libs/motores.py`, `placaControleMotor.py` e `portas.py` do repositório do Mariola; na pasta `libs/` da
  equipe, trocar o `from portas import Portas` por `from libs.portas import Portas` nas duas primeiras
  (o professor tem os três prontos). Não diga que a causa está confirmada sem o `dmesg` do momento do erro.
* **Motores soltam e os LEDs apagam sozinhos (esperando o botão, num `time.sleep` longo, procurando
  vítima)** → timeout de 5 s do firmware do Mariola: 5 s sem nenhum pacote solta os motores e apaga
  **todos** os LEDs, inclusive a iluminação das câmeras. Espere num laço que manda comando (como o
  `espera()` do exemplo, a cada 0,5 s) e acenda a iluminação **depois** do botão de início.
* **Depois de girar por ângulo, o robô volta a girar sozinho** → no Mariola, ao chegar no alvo o setpoint
  zera mas a velocidade fica guardada: um novo `atualiza_motores()` volta a girar. Ângulo 0 **mantém** o
  alvo anterior; velocidade 0 cancela. Na placa de motor é diferente: giro 0 **cancela**. Acompanhe com
  `estado()` (README do simulador, "Firmware emulado").
* **Contagem da placa de motor volta a 0 no meio da rodada** → ~12 s sem pacote para ela: o watchdog
  reinicia a placa (a contagem zera e o `angulo_delta` guardado na lib fica errado). Mande comando para as
  placas também enquanto espera.
* **Um lado anda o dobro (ou metade) do outro** → a placa de motor conta em quadratura (x4) e o Mariola só
  um canal nas duas bordas (x2): o mesmo motor dá o dobro de contagens na placa. Use uma constante para
  cada (`CONTAGENS_POR_VOLTA` e `CONTAGENS_POR_VOLTA_PLACA` no exemplo).
* **O robô anda o dobro do que pede no simulador com `robo_maze2026.json`** → o programa usa outra
  contagem por volta. O robô da equipe está com 440 contagens por volta no Mariola (880 na placa), o
  `CONTAGENS_POR_MM = 2` da equipe, que **ela acertou no robô real em 05/11/2026** (os comentários antigos
  do código, com 1000/45,7 ≈ 2,19 ou 940 por volta, são de antes e não valem). Confira a constante do
  programa. Não sugira trocar o 2,0 sem medida nova: no robô real, mande andar 300 mm com trena (ou gire a
  roda 1 volta à mão e leia a contagem).
* **Giro sai para o lado errado ou não para** → sinal do giroscópio. Na lib, Z positivo = horário; no robô
  da equipe o Z **diminui** girando para a direita (`z_horario_positivo: false` no `robo_maze2026.json`).
  Troque o sinal **num lugar só** (como o `z()` do exemplo) e use **alvo acumulado** (alvo += 90; não
  "girar 90 a partir de onde estou"), senão o erro de cada giro soma.
* **Depois de alguns minutos o robô anda torto e erra os giros** → deriva do giroscópio e patinação.
  Corrija pelas paredes: com parede na frente, encoste no para-choque (os dois botões apertados = reto) e
  redefina a direção; com parede do lado, meça o ângulo com dois VL53 do mesmo lado (curso 16.5 e 7.6).
* **Para antes ou passa do centro do ladrilho** → o encoder patina. Com parede à frente ao alcance, pare
  pela distância da parede (`FOLGA_FRENTE`) e use o encoder só como limite (o exemplo aceita até
  `LADRILHO + 25`).
* **Encostando na parede, o robô gira para um lado** → só um botão do para-choque apertou: ele gira para o
  lado do botão apertado (curso 8.2).

## Paredes e VL53

* **`OSError: [VL53L0X] Sensor não encontrado`** → o canal do mux (`Portas.I2C1` ... `I2C8`) não tem
  sensor: no robô, fio ou porta trocada; no simulador, o `robo.json` usado não tem um VL53 nesse canal
  (`robo.json` tem 6; `robo_maze2026.json`, 5 em `I2C1/3/6/7/8`). Confira o `--robo`.
* **No robô, um VL53 para de responder depois de um Ctrl+C e só volta desligando** → `vl53.py` antigo
  (antes de 09/11/2026; as libs da equipe em `maze2026/libs/` são antigas). O Ctrl+C no meio de uma
  sequência deixava o sensor no banco de registradores errado e a inicialização seguinte o travava. A
  lib nova reinicia o sensor por software (registrador 0xBF) ao criar o objeto e no `recover()`: não
  precisa de XSHUT. Copiar o `libs/vl53.py` atual.
* **Vê parede onde não tem (ou não vê) num ladrilho de canto** → o VL53 tem um leque de 25°: a ponta de
  uma parede de lado só aparece mais perto. Use limiar de lado (~150 mm) e de frente (~200 mm), leia com o
  robô parado no centro e faça média de algumas leituras.
* **Primeira leitura depois de girar está errada no robô e certa no simulador** → no robô a medida é da
  hora em que foi pedida (leitura "velha"); no simulador, da hora em que é lida. Depois de girar, descarte
  uma leitura ou espere uma medida nova.
* **Leitura travando ou com lixo usando thread** → o I2C só pode ser usado por uma thread (curso 7.3).
* **Sensor deslocado da borda do robô** → desconte a distância do sensor até a lateral (no robô da equipe,
  13 mm e 37 mm para dentro).

## Pisos

* **Cai no preto mesmo detectando** → o sensor de cor fica na frente: ao ver preto, volte a distância
  andada e marque o ladrilho como proibido no mapa (o preto não é parede para o VL53: na volta seguinte a
  "direita livre" leva ao preto de novo; curso 16.3).
* **Marca preto no ladrilho errado** → ao chegar no centro, o robô passou um pouco e o sensor já vê o
  ladrilho seguinte. O exemplo ignora preto lido ao chegar no centro.
* **Azul dá LoP** → precisa ficar parado 5 s no azul (o exemplo espera 5,5 s mandando comando).
* **Prata vira branco (ou branco vira prata)** → no TCS o prata passa de 127 (branco ≈ 127); no IR o prata
  fica ~80, abaixo do branco (~100). Aprenda as cores no campo com a V2 (`calibra_cores.py` do exemplo).

## Vítimas e kits

* **Juiz não conta a identificação** → piscar 500 ms / 500 ms por 5 s **parado** a até 15 cm. No simulador
  só os LEDs 8-9 contam (`set_led_rgb_one`); `set_led_rgb_all` pisca também a iluminação das câmeras.
* **Câmera não vê vítima no simulador** → com `deteccao.exige_iluminacao`, câmera com os LEDs apagados não
  enxerga (e o timeout de 5 s apaga). A vítima precisa estar de frente, no campo de visão, sem parede no
  meio.
* **Sinalizou a mesma vítima duas vezes / identificação errada (−5)** → guarde `(ladrilho, parede)` das
  vítimas já sinalizadas; não sinalize letra ou soma de anéis que não é vítima (falsa).
* **Kit não conta** → só depois da identificação; vale a posição do kit quando o robô sai inteiro do raio
  de 15 cm da vítima. Girar no lugar perto da parede pode chutar o kit.

## Checkpoint e LoP

* **Depois do LoP o robô "esquece" o mapa** → no LoP o programa pode ser reiniciado: salve mapa e posição
  **em arquivo** ao chegar no prata (escrita atômica: grava num temporário e renomeia), e ao começar leia
  o arquivo (`salva_checkpoint`/`carrega_checkpoint` do `navegacao.py`). No simulador, "LoP: reinicia
  prog." testa isso.
* **No robô o checkpoint não é achado (ou é gravado em outro lugar)** → o menu roda com a pasta atual em
  `/home/banana`: monte o caminho a partir de `__file__`.
* **Rodada nova começa com o mapa da rodada anterior** → o arquivo de checkpoint ficou. "Nova rodada"
  apaga os `arquivos_rodada` do `robo.json` (`checkpoint_maze.json`); com outro nome de arquivo, ponha o
  nome lá ou apague à mão. No robô, apague ao começar uma rodada nova de verdade (ou guarde a hora no
  arquivo e ignore se for velho, como o `carrega_checkpoint(validade_s)`).

## Rampa e escada (mudam o nível)

* **O robô escorrega ao girar no meio da rampa** → é real: girar no lugar a 20° faz descer uns 10 cm num
  giro de 90°. Gire no ladrilho plano, antes ou depois da rampa.
* **Na rampa o encoder conta mais do que andou no mapa** → na horizontal o robô anda cos(ângulo) do que o
  encoder conta. O feixe do VL53 inclina com o robô: do pé da rampa ele vê a própria rampa (~14 cm
  depois do começo dela, a 20°) e lá de cima pode passar por cima de uma parede baixa. Use o giroscópio
  (X/Y mostram a inclinação) para saber que está na rampa e conte o ladrilho da rampa como um.

## Simulador

* **Mesma semente, resultado diferente** → não deveria (relógio sincronizado): mudou o programa, o robô
  (`--robo`) ou o mapa. Sem `--semente`, cada rodada sorteia uma.
* **Simulador fica lento ou o tempo anda estranho** → laço sem `time.sleep` (trava o relógio sincronizado;
  depois de 1 s real ele passa a usar o relógio real) ou `threading.Event.wait(timeout)` /
  `Queue.get(timeout=...)`, que usam o relógio real: prefira `time.sleep` em laço.
* **Lib se comporta diferente do robô** → as libs de reserva (`simuladorMaze/libs_mariola/`) podem estar
  mais velhas: copie as libs atuais para a pasta do programa (curso 12.7).
* **Funciona no simulador e não no robô** → motor ideal, VL53 sem leitura velha, I2C sem tempo, medidas do
  `robo.json` estimadas (curso 17, README "Limitações conhecidas"). Ajuste ganhos, velocidades e tempos
  no robô.
* **O `main.py` da equipe cai no simulador procurando vítima** → a câmera USB (OpenCV) não existe no
  simulador: troque a detecção de vítimas por `DeteccaoVitimas` (ou um falso) para testar a navegação.
