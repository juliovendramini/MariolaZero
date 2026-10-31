# bananaPiM4Zero (MariolaZero) — guia para o Claude Code

Repositório do **brick Mariola** (Banana Pi M4 Zero + Armbian) do Julio (professor do Ifes Colatina,
equipes Titãs da Robótica). Tudo em português: código, comentários, commits e respostas.

## O que tem aqui

| pasta / arquivo | o que é |
|---|---|
| `README.md` | apresentação do repositório (reescrito em 20/10/2026; o antigo era o guia de instalação) |
| `INSTALACAO.md` + `instalacao/` | instalação do Linux do brick num arquivo só (Armbian Bookworm + kernel 6.18 com overlays, Python, permissões, menu, rede, câmeras, áudio, cooler, raiz somente leitura, Samba, boot rápido, recuperação, build) e os arquivos de apoio. **Duas imagens:** Line/Maze = Bookworm Minimal no BPI-M4 Zero de 8 GB (sem cooler); @Work = Armbian Noble/Ubuntu 24.04 + ROS2 no de 32 GB (com cooler `fancontrol`, NetworkManager). O apêndice C é a conferência de um brick em 20/10/2026. Gravar a eMMC: Line/Maze = `instalacao_emmc.sh` (imagem na p3 do cartão de reserva, gerada pelo `atualiza_imagem.sh`; desde 28/10 sorteia os 4 grupos do meio do MAC da `wlan0` no `/etc/netplan/armbian.yaml` da eMMC depois de gravar, `--mac`/`--mesmo-mac`; imagem atual: `backupMariolaZero2026-10-28.img`; o clone do cartão de reserva inteiro está no Google Drive como `backup-mariola20261029.dd.zst`, link e passo a passo no fim da "Cartão de reserva" da seção 17); @Work = `clona_sd_emmc.sh` (rsync do cartão para partições novas com UUIDs novos; apêndice D; ainda não rodado numa eMMC de 32 GB) |
| `_instalacao_antiga/` | os `.md`, scripts, `.dts`/`.dtb` e o `ScriptsIA/` antigos, movidos em 20/10/2026. O Julio vai apagar depois de revisar o `INSTALACAO.md`; não use como fonte (o apêndice B do `INSTALACAO.md` diz o que ficou só lá) |
| `firmware/mariola/` | o `.hex` do `placaBrickVendra` (firmware de 26/10/2026, md5 `eb34acab`), `grava_mariola.sh` (roda no brick: acha a porta pela regra do `portas.py`, avisa se a porta está em uso, pede ENTER com o **RESET na mão**, `avrdude -F -patmega328pb -carduino -b 115200 -D`; `-n` só confere), `grava_mariola.bat` (copia para `~/firmware_mariola` e roda por `ssh -t`) e `LEIAME.md`. `.gitattributes` da pasta força LF no `.sh`. Firmware novo? Troque o `.hex` e a versão/md5 no LEIAME. O script antigo `~/gravaMicrocontrolador.sh` do brick usava `/dev/ttyUSB0` fixo |
| `libs/` | bibliotecas **reais** do Mariola (Python, rodam no robô): motores, placaControleMotor, placaControleServo, giroscopio, vl53, sensorCorReflexao, teclado, tela, botoes... |
| `exemplos/`, `menuPrincipal/`, `telemetria/` | programas do robô real |
| `simuladorLine/` | simulador da RoboCupJunior Rescue Line (tem `CLAUDE.md` próprio) |
| `simuladorMaze/` | simulador da RoboCupJunior Rescue Maze (tem `CLAUDE.md` próprio) |
| `simuladorChallenge/` | simulador da RCB Challenge (CBR 2026), começado em 30/10/2026: arena, cubos e plataformas, mecanum, juiz e o robô real **Bombertinho** (`robo_bombertinho.json`, 31/10: duas garras de paralelogramo, medido no DXF do Julio); os robôs provisórios continuam; **falta o adversário** (tem `CLAUDE.md` próprio) |
| `curso/` | curso para os alunos (público): 18 módulos em Markdown, `referencia/`, `codigos/`, `curso-mariola.html` (tem `CLAUDE.md` próprio) |
| `professor/` | material do professor: **NUNCA vai para o GitHub** (`.gitignore` = `*`; tem `CLAUDE.md` próprio) |
| `simuladorLine.zip` | zip antigo do simulador; o zip atual para os laboratórios sai de `simuladorLine/ferramentas/monta_portatil.py` |

## Regras

* **Commits e push: só quando o Julio pedir.** Ele costuma fazer os commits.
* **`professor/` é privada.** Nunca copie gabarito, quizzes com resposta ou rubricas para `curso/`,
  que é pública. Não tire o `.gitignore` de dentro dela.
* **`libs/` roda no robô de verdade.** Não mude sem ele pedir. Os simuladores usam as libs reais sem
  alteração (a pasta do programa primeiro, depois `libs_mariola/` de cada simulador, que é uma cópia).
  Se mudar algo em `libs/`, avise que as cópias em `simuladorLine/libs_mariola/` e
  `simuladorMaze/libs_mariola/` ficaram diferentes.
* O Julio trabalha no **Windows**. Os simuladores também precisam rodar em PCs de laboratório com
  Windows travado (sem instalar nada, sem mexer no PATH). `.bat` com quebra de linha CRLF.
* Repositório no GitHub: `https://github.com/juliovendramini/MariolaZero` (branch `main`).
* Até 19/10/2026 este trabalho era feito por conversas no app do Claude, com uma cópia na nuvem.
  Se o Julio ainda usar essas conversas em paralelo, uma pode sobrescrever o que a outra fez:
  confira o `git status`/`git diff` antes de começar e não regrave arquivos inteiros sem necessidade.
  As notas `simuladorMaze-estado.md` e `simuladorLine-estado.md` do projeto "Simuladores de Robótica"
  no app eram o "CLAUDE.md" daquela época; o conteúdo delas já está nos `CLAUDE.md` das pastas.

## Firmwares (fora deste repositório, em `Documents\Arduino\`)

Os simuladores emulam estes firmwares byte a byte. Na dúvida sobre um comportamento, o `.ino` manda.

| pasta | placa |
|---|---|
| `placaBrickVendra` | ATmega328PB dentro do Mariola (2 motores com encoder, 10 LEDs RGB, botões) |
| `placaControleMotor` | placa de controle de motor independente do Julio (barramento serial, endereço por placa) |
| `placaControleServo` | placa do servo inteligente (ATtiny, MG90S). Firmware de 21/10/2026: controle proporcional (padrão) ou liga-desliga, polaridade, comandos 65000-65003. A pasta tem também a lib `placaControleServo.py` (a mesma de `libs/`, desde 22/10) |
| `sensorLinhaPro1616` | sensor de linha/cor Pro1616 (ATtiny1616). O `sensorCorReflexao.py` de lá é cópia da V2 atual (atualizado em 20/10). O `sensorLinhaPro1616.py` é a lib do EV3 (pybricks), igual à de `scriptsEv3dev`, com o mesmo classificador de cor da V2 |
| `brickSimples` | libs do brick Paçoca (copiadas em `simuladorLine/pacoca/libs_pacoca/`) |
| `sensorLinhaPro` | versão **antiga** do sensor de linha do Paçoca (ATmega328P, não controla os LEDs dos TCS). Só curiosidade: o Paçoca usa o Pro1616 |

### brickSimples (brick Paçoca)

* Brick Paçoca: ATmega328PB programado na IDE do Arduino, com a lib `brickSimples` (o aluno escreve
  `.ino`). Ponte H L9110S, tudo a 5 V, motores sem encoder (TT amarelo ou EV3 grande), giroscópio
  BMI160 por I2C, demais sensores iguais aos do Mariola. Detalhes de pinos no `simuladorLine/CLAUDE.md`.
* Mudanças feitas em 18/10/2026 (estão no PC; o repositório da brickSimples é outro):
  `sensorLinha.h` reescrito para o protocolo do Pro1616 (a versão do brick era do sensor antigo);
  `brickSimples.h` com o `adiciona(Motor&, Motor&)` dentro de `#ifdef SUPORTE_MOTOR` (sem isso não
  compilava sem motor) e um comentário no `frear()` (no L9110S `parar()` e `frear()` dão no mesmo);
  `docs/DOCUMENTACAO_COMPLETA_ACESSIVEL.md` seção 10.5 com a API nova do sensor.
* 23/10/2026: `SoftWire.h/.cpp` trocadas pela versão acelerada do medidor de vazão do SmartIrriga
  (`smartIrriga/medidorVazaoFerti`: pinos inline, millis só no clock stretching), mas com o buffer de
  recepção de **32** bytes (o do medidor tem 8; BMI160, VL53 e RFID leem mais). +~500 bytes de flash,
  mesma RAM. Não testada em I2C de verdade (o simulador troca a SoftWire pela dele).
  Depois, no mesmo dia: o laço de bits do `llWrite`/`llRead` guarda os ponteiros dos registradores e
  as máscaras em variáveis locais (antes cada operação de pino relia tudo do objeto) e o `llRead` solta
  o SDA uma vez por byte. Contagem de ciclos do código compilado a 16 MHz: bit de escrita 139 → 100
  ciclos (~160 kHz), de leitura ~88 (~180 kHz); +22 bytes de flash.
  `//#define SOFTWIRE_100KHZ` no começo da `SoftWire.h`: sem comentário, `DELAY_TIME_US` vai de 1
  para 4 (pior caso, leitura: 4,9 µs em baixo, dentro do I2C padrão; ~80-90 kHz). O simulador conta
  50 µs por byte nos dois modos (o real ficou em ~55-65 µs no máximo).
* `brickSimples.h` está com quebra de linha CRLF: mantenha.
* Mudou algo na brickSimples? Copie para `simuladorLine/pacoca/libs_pacoca/` e rode o teste do Paçoca.

## Pendências das libs (o Julio pediu para deixar como está por enquanto)

* `libs/sensorCorReflexao.py` ainda é a V1 (protocolo de 32 bytes; documentada em
  `documentação/CorReflexao.md`). A V2 (Pro1616, cores aprendidas no campo, `usar_ir=False`
  por padrão) está em `exemplos/11-sensorCorReflexaoV2/` e é **idêntica** às cópias em
  `simuladorMaze/libs_mariola/` e `simuladorLine/libs_mariola/` (conferido em 19/10) e à da pasta
  `sensorLinhaPro1616` (desde 20/10): mudou uma, copie para as outras. Mudou o classificador de cor?
  Leve também para o `sensorLinhaPro1616.py` do EV3 (nas pastas `sensorLinhaPro1616` e `scriptsEv3dev`). Documentação: `documentação/CorReflexaoV2.md`. O IR desligado na classificação de cor é
  provisório: ele quer analisar melhor (o IR fica 9 mm à frente dos TCS e dava falso vermelho/verde na
  borda da linha).
* A V2 foi reescrita em 15/10 porque o `detecta_cor()` original esperava branco > 230 e, com o
  firmware mandando o TCS pela metade (branco ≈ 127), classificava o branco como vermelho. Agora:
  cada cor é uma referência (média e desvio) de cromaticidade r/g/b, brilho C/127 e (opcional) IR/100;
  a leitura vai para a mais próxima, `'desconhecida'` acima de `limiar` (6); no preto (C < 15) a
  cromaticidade não conta. API: `cor(sensor)` (1 = TCS1, 2 = meio, 3 = TCS2), `cores()`, `cor_piso()`
  (votação dos 3; sem maioria vale o do meio), `distancias(sensor)`, `aprende_cor(nome)`,
  `esquece_cor`, `salva_cores`/`carrega_cores` (JSON), `usa_cores([...])` (Maze: branco, preto, prata,
  azul, vermelho; Line: + verde), `COR_PRATA` (nova), `detecta_cor()`/`nome_cor()` usam o
  classificador. **Quebra de compatibilidade:** `detectar_cor(r, g, b, c, ir=None)` virou método da
  instância (era `staticmethod`). IR de cada TCS: TCS1 → IR0, meio → IR1/IR2, TCS2 → IR3.
* `Teclado` tem padrão `i2c_bus=1` (placa antiga). Na placa atual (tela + teclado numa PCB só, no
  conector TELA) usar `Teclado(i2c_bus=0)`. Não mexer na lib nem no firmware `tecladoMariola.ino` ainda.
* `libs/tela.py` já corrigida (`self.device` → `self.display`).
* Menu principal roda com cwd=/home/banana e stdout em arquivo (bufferizado): nos programas, caminhos a
  partir de `__file__` e `line_buffering`.
* `Portas.abre_porta_serial` com o conversor ausente devolve um Serial fechado (não `None`).

## Hardware que aparece em todo lugar

* Tela + teclado: OLED SSD1306 em 0x3C; teclado = ATtiny1616 imitando um PCF8574A em 0x38.
  Bits 0-3 = botões (da esquerda para a direita: Voltar, Baixo, Cima, Enter; apertado = 0).
  Bits 4-7 = LEDs branco, vermelho, laranja, verde, cada um num NPN: **acende com bit 1**. Ao ligar
  ficam todos acesos; `Teclado()` escreve 0x0F e apaga.
* Sensor de linha/cor **Pro1616**: 12 ITR8307 agrupados de 3 em 3 = 4 canais IR (6,5 cm do centro do
  1º ao 12º), 3 TCS34725 a 2 cm um do outro, fileiras IR e TCS separadas por 9 mm, 3 LEDs brancos.
  IR: 0 = preto, ~100 = branco calibrado, **fita prata ~80 (abaixo do branco)**. TCS calibrado no
  branco e enviado pela metade (branco ≈ 127, prata passa de 127). A equipe usa o sensor a 12 mm do chão.
* Pinos digitais P1-P8 (`PinosDigitais`): linhas 259, 260, 71, 234, 228, 265, 266, 267 do
  PIO principal do H618 (`300b000.pinctrl`). No kernel 6.18 (conferido num brick em 27/10/2026) ele é
  o `gpiochip1`; o `gpiochip0` é o R_PIO, de 32 linhas (no 6.6 era o contrário). Desde 27/10 a lib
  acha o chip pelo rótulo (`acha_chip_gpio()`); antes estava fixa no `gpiochip0` e não funcionava no
  6.18. `libs/pinosDigitais.py` = a versão do `exemplos/06-lidar` (singleton, `SAIDA`/`ENTRADA`, P8
  indisponível se a linha estiver em uso pelo PWM), copiada em `exemplos/04`, `05`, `06` e nos
  `libs_mariola`. **A classe `Botoes` (`botoes.py`) foi juntada ao `PinosDigitais` em 27/10** (as duas
  disputavam os pinos): `botoes.py` apagado de `libs/`, `exemplos/04` e `libs_mariola`, e os
  programas (exemplos dos simuladores, `curso/codigos`, gabarito m08/m16, exemplo 04) trocados para
  `PinosDigitais`, que tem `le_botao`/`botao_pressionado`/`LIBERADO`/`APERTADO`. Programa de aluno
  com `from botoes import Botoes` quebra de propósito (a referência `curso/referencia/botoes.md`
  explica a troca). O `menuPrincipal/botoes.py` (antigo, pinos em outra ordem, `gpiochip0`, não
  usado pelo menu) também saiu, e o `cronometro.py` do menu ficou igual ao de `libs/` (só mudava a
  formatação). O `gpiod` falso dos simuladores responde `get_info()` como o PIO principal.
* Giroscópio do Mariola: Z em graus, acumulando, positivo no sentido horário. O curso usa
  `z()` positivo = esquerda e troca o sinal numa função só.
* Servos inteligentes do Julio (lib `placaControleServo`) no mesmo barramento serial (SERIAL1) das
  placas de motor.
* Conectores: `documentação/Conectores.pdf`/`.odp` (fonte, o Julio edita) e `documentação/Conectores.md`
  (texto). Header amarelo = 6 colunas (SINAL, 5V, GND): SERVOS 1–4 (pinos 14–17; o 4 pode ser a 2ª
  fita de LEDs), LEDs (pino 12, os 10 RGB) e DEBUG/PWM (pino 11: TX do serialDebug do ATmega, PWM
  da ventoinha ou buzzer). Servos comuns, ventoinha e buzzer dividem o Timer2: desde o firmware de
  26/10/2026 o primeiro usado fica com ele até reiniciar (`documentação/Motores.md`). REDE (RXN, RXP, TXN, TXP; virado 180° em relação ao USB) e AUDIO (GND, L_OUT,
  L_IN, 5V) são do Banana Pi. A imagem do mapa no curso (`curso/imagens/conectores.jpg`) sai da
  página 1 do PDF.

## Curso (`curso/`)

* 18 módulos (`01-...md` a `18-desafios.md`), `referencia/` (uma página por lib), `codigos/`
  (18 programas testados nos simuladores, sem janela, 4x), `mapas/` (`curso_pista.json`,
  `curso_area.json`, também em `simuladorLine/mapas/`).
* Convenções: velocidades -100 a 100, distâncias em mm, ângulos em graus, canal 0 do sensor de linha e
  TCS 1 à esquerda.
* `curso-mariola.html` é o site gerado a partir dos `.md` (também publicado como artifact "Curso
  Mariola" no app do Claude). Gerador: `python curso/site/monta.py` (usa `curso/site/modelo.html`).
  Rode depois de mudar qualquer módulo; o artifact do app fica desatualizado até ser republicado
  (como republicar: `curso/CLAUDE.md`).
* Detalhes (estrutura, testes dos códigos, tabela de referência do módulo 18): `curso/CLAUDE.md`.
* Ao mudar a API de um simulador ou de uma lib, confira os módulos e os `codigos/` que usam aquilo.

## Material do professor (`professor/`)

`plano-de-aulas.md` (18 semanas × 2 h, trilha alternativa da Maze nas semanas 9-15), `rubricas.md`,
`quizzes.md` (com resposta) e `quizzes-aluno.md` (gerado por `gera_quiz_aluno.py`), `gabarito/`
(módulos 1-17, códigos em `gabarito/codigos/mNN/`), `mapas_teste/` (mapas e robôs de laboratório),
`professor.html` (gerado por `python professor/monta_professor.py`). `testa.sh` e `testa_maze.sh`
rodam um código do gabarito sem janela (bash/Git Bash). Detalhes em `professor/CLAUDE.md`.
