# simuladorLine — guia para o Claude Code

Simulador 2,5D da **RoboCupJunior Rescue Line** (regra do mundial 2026): linha + área de resgate.
O programa do aluno usa as **bibliotecas reais do Mariola sem alteração**; o simulador troca só a camada
de baixo (serial, I2C, GPIO, relógio) e emula o firmware de cada placa byte a byte. Também roda o
**brick Paçoca** (ATmega328PB, `.ino` compilado com g++ para o PC).

Leia antes de mexer: `README.md` (uso, física, juiz, estrutura, limitações) e `pacoca/LEIAME.md`
(por dentro do Paçoca: build, relógio, protocolo programa ↔ ponte, como pôr um dispositivo novo).
As regras gerais do repositório estão no `CLAUDE.md` da pasta de cima.

## Arquitetura em uma linha

`main.py` do aluno → libs reais (pasta do programa, depois `libs_mariola/`) → `fake_hw/` (serial,
smbus2, gpiod, firmware, relógio virtual) → socket TCP → `sim/servidor.py` → física/juiz/janela.
O programa roda em processo separado (`rodar.py`; para `.ino`, `rodar_pacoca.py`).

| arquivo | papel |
|---|---|
| `sim/fisica.py` | robôs, motores (inclusive DC na ponte H do Paçoca), sensores, pymunk + altura do piso |
| `sim/mapa.py`, `sim/ladrilhos.py` | mapa, editor, os 82 ladrilhos oficiais (`ladrilhos/`, 1 mm/px) |
| `sim/resgate.py` | área de resgate: vítimas, triângulos, garra e caçamba (cinemático) |
| `sim/juiz.py` | pontuação e LoP (regra 2026) |
| `sim/servidor.py` | operações pedidas pelo hardware virtual (inclusive `imu`, `motor_dc`, `leds` do Paçoca) |
| `sim/firmware.py`, `fake_hw/dispositivos.py` | firmware emulado (Mariola, placas de motor, Pro1616, VL53L0X/TCA9548A, servos) |
| `sim/app.py`, `sim/gui.py`, `sim/painel_brick.py` | janela, painéis, tela OLED e teclado (tecla O) |
| `avalia.py` | várias sementes sem janela, desafios L01-L13 (`desafios/desafios.json`), relatório em `resultados/` |
| `ferramentas/` | `pista_surpresa.py`, `gera_desafios.py`, `gera_mapas.py`, `importa_ladrilhos.py`, `monta_portatil.py` |
| `robo_4x4.json`, `robo_esteira.json`, `robo_pacoca_amarelo.json`, `robo_pacoca_ev3.json` | os robôs |

## Testes de referência (rode depois de qualquer mudança em `sim/`, `fake_hw/` ou `pacoca/`)

```bash
python simulador.py --sem-janela --velocidade 8 --mapa mapas/completo.json
#   exemplo em Python, robô 4x4 → TOTAL 295
python simulador.py --programa exemplo_pacoca/exemplo_pacoca.ino --sem-janela --velocidade 4 --semente 1
#   Paçoca, mapa de treino → TOTAL 160, 0 LoP
#   com --mapa mapas/completo.json --tempo 300 → ~230, chega na fita vermelha
python avalia.py --desafio L04 --programa exemplo_aluno/main.py
#   exemplo → 6 de 6
```

* A EEPROM simulada do Paçoca fica em `exemplo_pacoca/eeprom_pacoca.bin`: a primeira rodada (sem o
  arquivo) sai um pouco diferente das seguintes.
* O Paçoca precisa de g++ (Windows: pacote portátil, MSYS2 ucrt64 ou w64devkit; `PACOCA_GXX` força um).
* Referência do exemplo nos desafios (depois da correção do cruzamento com verde, 18/10): L04-L06, L08,
  L09, L11 6/6; L07 média ~287; L10 5/6; L12 4/6; **L13 3/6 (em aberto)**.

## Relógio sincronizado (não quebrar)

O tempo do programa só anda quando todas as threads dele estão esperando (`time.sleep`, espera da
serial/I2C); aí a física avança até o primeiro despertar. Mesma semente + mesmo mapa + mesmo programa =
rodada **igual bit a bit** em qualquer velocidade, com ou sem janela, em paralelo ou não. Qualquer
mudança que introduza tempo real, aleatoriedade sem a semente ou ordem dependente de thread quebra isso:
confira rodando o mesmo teste em `--velocidade 1` e `8` e comparando o placar. Thread sem espera por
1 s real cai no relógio real (modo de segurança). `--tempo-real` é o modo antigo.
No Paçoca o relógio é do programa (`sim_t_ns`) e a ponte só leva a física até ele quando precisa do
mundo ou a cada 10 ms (detalhes no `pacoca/LEIAME.md`).

## Brick Paçoca

* Partes do Paçoca espalhadas em arquivos do simulador (não regredir): `sim/fisica.py` (`Motor.dc`,
  `varia()`, `dc_estado()`, `dc_coef()`, ramo `if mot.dc:` em `_rodas()`, `apoios`/roda boba em
  `_monta_apoios()`, `carga_apoios`, `params` por sensor em `vl53()`, `Mundo.imu()`, `por_dc`),
  `sim/servidor.py` (`imu`, `motor_dc`, `leds`), `sim/app.py` (`programa_do_robo()`, `eh_pacoca()`,
  trocar o robô troca o programa), `sim/gui.py` (painel "Motores (tensão média)"; tela/teclado do
  Mariola escondidos no Paçoca; o botão "Programa" só aceita `.ino` no Paçoca e `.py` no Mariola),
  `simulador.py` e `avalia.py` (aceitam `.ino`).
* Botão "Programa" (19/10, nos dois simuladores): `Interface._escolhe_programa()` abre o seletor do
  tkinter e chama `Simulacao.troca_programa()` (para o programa e faz `nova_rodada()`).
* Hardware: ponte H **L9110S** (LL e HH = freio → `"ponte_h": {"LL": "freio", "HH": "freio"}`), tudo em
  5 V, motores **sem encoder** (amarelo: mais rápido, mais impreciso e mais fraco; EV3 grande ligado sem
  o encoder), giroscópio **BMI160** lido direto por I2C, demais sensores iguais aos do Mariola, portas
  de sensor genéricas (o aluno escolhe o que vai em cada uma).
* `pacoca/libs_pacoca/` é cópia da brickSimples (`Documents\Arduino\brickSimples`, fora deste
  repositório). Se a lib mudar lá, copiar de novo. O `sensorLinha.h` foi reescrito para o Pro1616
  (protocolo 0x61/0x62/0x63).
* Fidelidade ao AVR não é objetivo por enquanto (int de 16 bits etc.): é host build com g++.
* Windows: compila com `-D__CRT__NO_INLINE` (o `math.h` do MinGW define `powf` inline e o
  `TCS34725.cpp` define a dele); `nucleo/sim_rede.cpp` usa `CreateThread`/pthread (sem `std::thread`).
  Dá para testar o alvo Windows no Linux com
  `PACOCA_GXX=x86_64-w64-mingw32-g++-posix` + Wine.

### Paçoca por dentro: fatos que custaram para descobrir

* Portas do brick (o aluno escolhe o que liga em cada uma; `pacoca.portas` no JSON do robô diz o que
  está ligado no simulador). Portas de sensor (sda/rx, scl/tx; no ultrassom echo, trig):
  1 = (14, 15), 2 = (16, 17), 3 = (8, 6), 4 = (2, 3), 5 = (18, 19). Servo/LED: S1 = 13, S2 = 12,
  S3 = 11, S4 = 5. Motores: M1 = PWM 9 + sentido 7, M2 = PWM 10 + sentido 4 (na ré o brick faz
  `analogWrite(255 - pwm)`). Botão do brick = A6 (pino 20, apertado < 100). Bateria = A7.
* Robôs: `{"1": vl53 frente, "3": pro1616, "5": bmi160}`; M1 `sentido` 1, M2 -1; um VL53 só
  ("frente"); roda boba (`apoios`) com `carga_apoios` 0.3. Motor amarelo: rpm 200, 2,0 N, `pwm_minimo`
  0.15, `variacao` 0.08. EV3: rpm 90, 7,5 N, 0.06, 0.03. **Tudo estimativa, falta o Julio medir.**
  Com a ponte L9110S o amarelo anda ~154 mm/s a 40%, ~215 mm/s a 50%, ~530 mm/s a 100%. Com
  `"LL": "solto"` (clone de L9110S) o robô puxa muito para um lado: é o esperado, não é bug.
* Custos no relógio do programa (ATmega a 16 MHz): `digitalWrite` 3,6 µs, `analogRead` 112 µs,
  `millis` 1,2 µs, `micros` 3,5 µs (resolução de 4 µs), I2C por software ~50 µs/byte, byte da
  SoftwareSerial ~87 µs. A ponte sincroniza a cada 10 ms de programa. O Paçoca também é determinístico:
  mesma semente dá a mesma rodada em 1x e 4x.
* `sensorLinha.h` (Pro1616): `lerDados()` faz `cli`, manda 0x61 e lê 16 bytes; `calibrarBranco()` /
  `calibrarPreto()` = 0x62 / 0x63. Leitura: `getReflexao(i)` (0 preto, ~100 branco), `getLinha(i)` =
  100 - reflexão, `getPosicaoLinha()` (-150..150, + = direita), `getRGBC(sensor, r, g, b, c)`,
  `getCor(sensor)`, `getCorEsquerda/Meio/Direita()`, limiares públicos `limiarPreto` 20,
  `limiarBranco` 70, `limiarPrata` 160. `SENSOR_COR_ESQUERDA/MEIO/DIREITA` = 1/2/3, `COR_PRATA` = 7.
  Saíram `setModo`, `getModoAtual` e `MODO_*` (eram do sensor antigo).
* BMI160: `getEixoZ()` é em **décimos de grau** (o exemplo usa `z() = getEixoZ() / 10`, + = esquerda).
  A ponte emula FIFO a 25 Hz, FOC, offsets, PMU e acelerômetro (`bmi160` no JSON: eixos, bias, erro_foc).
* A lib do VL53L0X troca o endereço para 0x30 no começo: a ponte procura o dispositivo pelo endereço
  **atual**. VL53/TCS reaproveitam os modelos de `fake_hw/dispositivos.py`.
* A `SoftwareSerial` simulada é forma de onda da linha RX (sem buffer): byte que chega com ninguém
  lendo se perde, como no brick.
* Saída 42 do programa = reset (`jmp 0`): o `rodar_pacoca.py` roda de novo. `PACOCA_ESTAT=1` imprime
  quantas operações de cada tipo o programa pediu à ponte (bom para achar lentidão).
* Variáveis: `PACOCA_GXX` (qual g++), `PACOCA_CACHE` (pasta do cache do núcleo), `PACOCA_ESTAT`;
  `PACOCA_PONTE` e `PACOCA_EEPROM` a ponte define sozinha.
* Exemplo (`exemplo_pacoca.ino`): segue linha com PD (VEL 45, KP 0.22, KD 0.9), gira pelo giroscópio
  com freio no fim, anda distâncias por tempo (`MM_POR_S` 215, `PARTIDA_MS` 90: medir no robô),
  trata verde, gap, obstáculo, lombada/rampa (sem contraste + inclinação) e para na fita vermelha.
  Build com avr-gcc de verdade: ~19 KB de flash, 462 B de RAM (cabe no 328PB).
* Testar o alvo Windows no Linux: `PACOCA_GXX=x86_64-w64-mingw32-g++-posix` gera o `.exe`; para rodar,
  troque o `Popen([self.exe])` da `ponte.py` por `['wine', exe]` numa cópia (não no código). Deu o
  mesmo placar do Linux.

## Pacote portátil para Windows (laboratório travado)

* `ferramentas/monta_portatil.py` (roda no PC do Julio): baixa Python 3.12 (python-build-standalone) +
  rodas do `requirements.txt` (win_amd64) + w64devkit, enxuga, monta `portatil/python` e `portatil/gcc`,
  testa e gera `dist/SimuladorLine-portatil-AAAAMMDD.zip` (com o núcleo do Paçoca pré-compilado).
  `portatil/` e `dist/` ficam fora do git; o zip não vai para o GitHub.
* `Simulador.bat` / `Avaliar.bat` (CRLF): usam `portatil\python\python.exe` se existir
  (`PYTHONNOUSERSITE=1`, sem PYTHONHOME/PYTHONPATH), senão `python`.
* Ordem do g++ em `pacoca/compila.py`: `PACOCA_GXX` > `portatil/gcc/bin/g++.exe` > PATH > MSYS2/w64devkit.
* Montado pela primeira vez no PC do Julio em 19/10/2026 (w64devkit 2.10.1, cpython 3.12.15, numpy
  2.5.4, pygame 2.6.1, pymunk 7.3.1, pillow 13): zip de ~121 MB. O que entrou fica em
  `portatil/VERSOES.txt`. Para testar como no laboratório, rode com `portatil\python\python.exe` (o
  `.ino` compila com `portatil\gcc` sozinho). Ainda não foi testado num PC de laboratório de verdade.
* O script testa no fim (sem janela, no Windows): imports, `g++ --version`, uma rodada do exemplo em
  Python e uma do exemplo do Paçoca; o zip só sai se tudo passar (a menos que use `--sem-teste`).
  `--so-zip` refaz só o zip; `--python`, `--w64devkit`, `--rodas` usam arquivos já baixados.
* O enxugamento do w64devkit é por exclusão (`GCC_BIN`, `GCC_LIBEXEC_FORA`, `GCC_PASTAS_FORA`): se uma
  versão nova do w64devkit mudar de layout e o teste do Paçoca falhar, é ali que se mexe.
* O pacote só tem o que está no `requirements.txt`. Biblioteca nova que o simulador (ou o programa de
  alguma equipe) precisar tem de entrar lá antes de montar o zip.
* Python do Windows no Wine 9: numpy ≥ 2.2 aborta (falta `ucrtbase.crealf` no Wine, não no Windows).
  Para testar pelo Wine use numpy 2.1.x via `--rodas`.

## Fatos do robô real que o simulador segue

* Lib de cor: a V2 de `exemplos/11-sensorCorReflexaoV2/` (cópia idêntica em `libs_mariola/`; API e
  histórico no `CLAUDE.md` de cima). Na Line, `usa_cores([...])` inclui `'verde'`.
* Pro1616: geometria e valores no `CLAUDE.md` de cima. **Prata no IR ~80 (abaixo do branco)**, de
  propósito; quem vê o prata são os TCS (C ≥ 165, com os 4 IR entre 50 e 120 e o robô nivelado).
  Sensor a 12 mm do chão, igual nos dois robôs (4x4 e esteira).
* Resgate: garra com 4 servos MG90S a 5 V (um baixa a garra, dois abrem/fecham, um na porta da
  caçamba de dois lados), no mesmo barramento serial das placas de motor; posições variam por robô e
  ficam no JSON; a garra cai se o servo desliga no meio do curso. Câmera da frente a ~5 cm do chão
  (a garra atrapalha a visão); bolinha despejada a ~10 cm de altura com o robô faceado no triângulo.
* Placa de servo (`FirmwareServo` em `sim/resgate.py`) emula o `placaControleServo.ino` de
  21/10/2026 (`Documents\Arduino\placaControleServo`): controle proporcional (padrão; KP 3, KD 8,
  PWM mín. 60, histerese 4, período 5 ms, KI 0) ou liga-desliga, comandos 65000-65003, polaridade
  (motor simulado normal). A velocidade do termo D é normalizada para "por período" porque a física
  roda a 240 Hz. O atrito do servo físico (`servo.pwm_minimo` no `robo_4x4.json` e nas cópias de
  `professor/mapas_teste/`) foi de 60 para 45 em 22/10: com 60, o PWM mínimo do firmware não movia o
  servo e o proporcional parava antes do alvo. A lib `placaControleServo.py` (22/10) é a mesma em
  `libs/`, nos `libs_mariola/` e nos exemplos 08, 10 e 12.
* Câmera é **stub** (`visao`): devolve detecções (~90% de acerto), sem imagem. No Mariola a IA das
  vítimas roda a ~4 fps e o OpenCV dos triângulos a ~30 fps. A câmera que olha para baixo (para seguir
  linha) não é simulada.
* Sensores do 4x4 no resgate: VL53 na garra, um de cada lado no meio, um na frente na altura do
  triângulo, TCS na frente (talvez um atrás).

## Desafios e `avalia.py`

* `avalia.py` nasceu **igual** nos dois simuladores (descobre qual é pela existência de
  `sim/resgate.py`); o da Line agora também aceita `.ino`. Ao corrigir algo comum, leve para o da Maze.
* Meta de cada desafio em `desafios/desafios.json`: `{"rodada": expr, "minimo": k}` (k rodadas
  cumprindo `expr`) e/ou `{"media": expr}` (sobre as médias). Nomes que as expressões usam (função
  `metricas()`): `total`, `lop`, `tempo`, `erro_programa`, `passo`, `passos`, `progresso`, `chegou`,
  `vivas`, `mortas`, `vitimas`, `linha`. Renomear um deles quebra metas e o `curso/18-desafios.md`.
* Mudou o placar, o juiz ou o exemplo? Rode os desafios do exemplo (`python avalia.py --desafio LXX`)
  e atualize a tabela de referência acima, a do `curso/18-desafios.md` (18.6) e a do `curso/CLAUDE.md`.

## Quem depende do exemplo e dos JSON (fora desta pasta)

* `professor/gabarito/codigos/m14/*_main.py` são cópias do `exemplo_aluno/main.py` com **uma**
  mudança cada (exercícios do módulo 14). Se o `main.py` do exemplo mudar, refaça essas cópias a
  partir do novo e confira os números no `professor/gabarito/14-projeto-rescue-line.md`.
* `professor/mapas_teste/robo_esteira_lab.json`, `robo_4x4_lab.json` e `robo_4x4_trava1000.json` são
  cópias dos robôs com `juiz.tempo_fora_do_caminho_s = 99999` (sem LoP automático). Se a chave mudar
  de nome ou os robôs ganharem campos novos obrigatórios, atualize essas cópias.
* `curso/mapas/curso_pista.json` e `curso_area.json` são cópias dos de `mapas/`: mude os dois.

## Pendências e decisões

* "Sugestão 2" (aproximar do robô real: motor perdendo rotação com carga, leitura "velha" do VL53,
  barramento de servo não ideal) ficou para o futuro, a pedido do Julio. Já está nas limitações do
  README e do curso (11.9, 17.1).
* L13 do exemplo em 3/6: em aberto.
* A geometria nova do Pro1616 foi levada para o `robo.json` da Maze em 19/10 (só as posições; o
  modelo de leitura de lá continua o simples).
* Mudou API, robôs, mapas ou placar? Atualize o `README.md` e confira `curso/11-simulador-line.md`,
  `curso/18-desafios.md`, `curso/codigos/` e `professor/gabarito/`.
