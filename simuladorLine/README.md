# Simulador RoboCupJunior Rescue Line — robôs com brick Mariola

Simulador 2,5D para desenvolver e testar o robô da **Rescue Line** (regra do mundial 2026): a linha
e a **área de resgate** (vítimas, triângulos, garra e caçamba), com o **mesmo código** que vai para o
robô real.

Como no simulador da Maze, o programa do aluno importa as bibliotecas reais do Mariola
(`motores.py`, `placaControleMotor.py`, `giroscopio.py`, `vl53.py`, `sensorCorReflexao.py`,
`pinosDigitais.py`, ...) e elas rodam **sem nenhuma alteração**. O simulador troca só a camada de baixo
(serial, I2C, GPIO e relógio) e emula o firmware de cada placa byte a byte.

Também roda robôs com o **brick Paçoca** (ATmega328PB, programa em Arduino/C++): o `.ino` da equipe
e a biblioteca brickSimples compilam para o PC sem mudar e falam com o mesmo simulador
(ver [Brick Paçoca](#brick-paçoca-programa-em-arduino)).

---

## Instalação

Python **3.11 ou mais novo**.

```bash
pip install pygame pymunk numpy pillow
pip install opencv-python-headless       # só para a câmera de linha (programas com import cv2)
```

Funciona no Windows e no Linux. No Linux, para os diálogos de abrir/salvar mapa, instale também
`python3-tk`.

Para o **brick Paçoca** é preciso também um **g++** (compilador C++ do PC):

* **Windows:** instale o [MSYS2](https://www.msys2.org), abra o terminal "MSYS2 UCRT64" e rode
  `pacman -S mingw-w64-ucrt-x86_64-gcc`. O simulador acha o g++ sozinho em `C:\msys64\ucrt64\bin`
  (ou ponha essa pasta no PATH, ou defina `PACOCA_GXX` com o caminho do `g++.exe`). O
  [w64devkit](https://github.com/skeeto/w64devkit) também serve.
* **Linux:** `sudo apt install g++`.

### Pacote portátil para Windows (laboratório sem administrador)

Para PC onde não dá para instalar nada, o simulador vai junto com o Python, as bibliotecas e o g++,
tudo dentro da pasta `portatil/`. Não instala nada no Windows nem mexe no PATH.

Para montar o pacote, num PC com internet (de preferência Windows, que aí ele é testado no fim):

```bash
python ferramentas/monta_portatil.py
```

* Baixa o Python 3.12 ([python-build-standalone](https://github.com/astral-sh/python-build-standalone)),
  as bibliotecas do `requirements.txt` para Windows e o g++ do [w64devkit](https://github.com/skeeto/w64devkit),
  e deixa só o que o simulador usa (sem gdb, make, Fortran, testes do Python, pip...).
* Testa: abre o Python, roda o exemplo em Python e compila e roda o exemplo do Paçoca, sem janela.
* Gera `dist/SimuladorLine-portatil-AAAAMMDD.zip`: o simulador inteiro + `portatil/` + o núcleo do
  Paçoca já compilado. É esse zip que vai para o laboratório.
* `portatil/` e `dist/` estão no `.gitignore` (são programas, não vão para o git). O que foi baixado
  fica em `portatil/_baixados/`; `--so-zip` refaz só o zip e `--help` mostra como usar arquivos já
  baixados (sem internet).

No laboratório: descompacte o zip e dê dois cliques em **`Simulador.bat`** (`Avaliar.bat` roda o
`avalia.py`; os dois aceitam as mesmas opções, ex.: `Simulador.bat --programa ..\equipe\equipe.ino`).
Os `.bat` usam o Python de `portatil/` e o `.ino` compila com o g++ de `portatil/gcc`, mesmo que
o PC tenha outro Python ou g++ instalado. Sem a pasta `portatil/` eles usam o Python do PC.

Cuidados no laboratório:

* Se o zip veio da internet, antes de descompactar: botão direito > Propriedades > **Desbloquear**.
  Senão o Windows pergunta "deseja executar?" a cada `.bat`.
* O programa do Paçoca vira um `.exe` na pasta `.sim_build/` ao lado do `.ino`: a pasta do aluno
  precisa permitir escrita. O antivírus às vezes segura esse `.exe` novo por alguns segundos na
  primeira vez.
* Se o Windows bloqueia programas fora de `C:\Program Files` (AppLocker), nem o Python portátil roda:
  aí é preciso pedir ao TI para liberar a pasta do simulador.

## Uso rápido

```bash
python simulador.py                                        # robô 4x4, mapa de treino, programa de exemplo
python simulador.py --robo robo_esteira.json               # robô de esteira
python simulador.py --mapa mapas/completo.json             # rampas, ponte, gangorra, obstáculo...
python simulador.py --mapa mapas/resgate.json              # linha + área de resgate
python simulador.py --programa CAMINHO/DO/main.py          # programa da equipe
python simulador.py --editor                               # abre direto no editor de mapas
python simulador.py --programa exemplo_pacoca/exemplo_pacoca.ino   # brick Paçoca (motor amarelo)
python simulador.py --robo robo_pacoca_ev3.json            # Paçoca com os motores grandes do EV3

# sem janela: uma rodada inteira 2x mais rápido, imprime o placar (bom para testar várias vezes)
python simulador.py --mapa mapas/completo.json --sem-janela --velocidade 2
```

Opções: `--semente N` (ruído dos sensores; padrão 1, `-1` sorteia a cada rodada), `--lop botao|reiniciar`,
`--tempo 480`, `--tempo-real` (modo antigo do relógio, veja abaixo), `--resultado arq.json` (sem
janela: grava o placar em JSON).

**`input()` como pausa.** No robô, rodando pelo terminal ssh, um `input('pare')` segura o programa até
alguém apertar Enter. No simulador funciona igual:
* o console mostra o texto;
* aparece uma faixa amarela, "O programa está parado no input(...)";
* o programa segue com a tecla **Enter** ou com o botão **⏎ Enter** da faixa (o `input()` devolve `''`).

Enquanto isso o tempo continua andando, como no robô: as outras threads seguem rodando e os motores
mantêm o último comando até o timeout de 5 s do firmware. Use **Pausar** (espaço) para congelar tudo.
Sem janela (e no `avalia.py`) o Enter é automático, com um aviso no console. Não confunda com o botão
Enter do teclado do brick, que fica no F4.

## Desafios e avaliação automática (`avalia.py`)

Uma rodada só não diz se o programa é bom: o ruído muda com a semente e uma rodada de sorte
engana. O `avalia.py` roda o programa em várias sementes, sem janela, mostra uma tabela com cada
rodada, a média e a pior, e confere a meta do desafio.

```bash
python avalia.py --lista                                        # os desafios (L01 a L13)
python avalia.py --desafio L04 --programa CAMINHO/DO/main.py    # roda o desafio e confere a meta
python avalia.py --programa CAMINHO/DO/main.py --mapa mapas/completo.json --sementes 1-6
python avalia.py --programa CAMINHO/DO/main.py --surpresa medio --mapas 6   # 6 pistas sorteadas
```

* Rodadas em paralelo (`--paralelo N`; padrão: metade dos núcleos do PC). Como o relógio é
  sincronizado, rodar em paralelo não muda o resultado.
* Os desafios ficam em `desafios/desafios.json` (mapa, robô, sementes, tempo e meta) e os mapas
  em `desafios/mapas/`. O professor pode criar outros no mesmo formato.
* Cada avaliação grava um relatório em `resultados/` (placar de cada rodada, se cumpriu a meta e
  uma impressão digital dos `.py` do programa) e o log de cada rodada em `resultados/logs/`.
* `--aluno "Nome"` põe o nome no relatório. `--semente-mapas N` troca as pistas surpresa (o
  professor pode usar uma que os alunos não conhecem).

**Pista surpresa:** `python ferramentas/pista_surpresa.py --nivel facil|medio|dificil --semente N`
grava em `mapas/` uma pista sorteada dentro da regra (caminho, ladrilhos, interseções com verde,
gaps, obstáculo, lombada e detritos, conforme o nível). Abra no simulador para treinar. A mesma
semente gera sempre a mesma pista.

### Relógio sincronizado: o resultado não depende da velocidade nem do PC

O programa do aluno roda num processo separado e é Python: cada volta do laço gasta alguns
milissegundos de PC (ler sensores pelo socket, calcular). Se o relógio simulado andasse junto com o
relógio real, em 4x cada volta do laço "custaria" 4 vezes mais tempo simulado. O controle rodaria
a ~11 Hz em vez de ~46 Hz, o robô andaria 4 vezes mais entre uma leitura e outra e o PID enlouqueceria.
O mesmo aconteceria num PC mais lento.

Por isso o padrão é o **relógio sincronizado**: o tempo do programa só anda quando todas as threads
dele estão esperando (`time.sleep`, espera da serial ou do I2C). Nessa hora o simulador avança a física
exatamente até o primeiro despertar. O tempo que o PC gasta calculando não conta. As esperas contam
como no robô.

* Com a mesma semente, o mesmo mapa e o mesmo programa, a rodada sai **igual, bit a bit**, em 0,25x,
  1x ou 4x, com ou sem janela, inclusive com LoP.
* **Vel.** passa a ser um limite. Se o PC não acompanha, o simulador fica mais lento que o pedido e o
  botão mostra quanto conseguiu, por exemplo `Vel. 4x (PC: 1.7x)`. O resultado não muda.
* O auto-botão e o reposicionamento do LoP acontecem no tempo simulado exato.
* No robô de verdade o laço também gasta tempo calculando. Se o programa só funciona porque o
  simulador "congela" o tempo durante o cálculo, ele pode se comportar diferente no robô. Um
  `time.sleep(0.01)` no laço principal, como no exemplo, deixa os dois parecidos.
* Uma thread que fica calculando sem nunca esperar (laço sem `sleep`, ou presa num `Lock`) trava
  esse esquema. Depois de 1 s real nessa situação, o tempo passa a andar pelo relógio real, como
  no modo antigo.
* `--tempo-real` volta ao modo antigo: o programa usa o relógio real multiplicado pela velocidade.

### Na janela (modo simular)

| Botão / tecla | O que faz |
|---|---|
| **▶ Iniciar rodada** (F5) | zera o placar, põe o robô no início, inicia o programa e o cronômetro de 8 min |
| **■ Parar** | manda `KeyboardInterrupt` para o programa e encerra a rodada |
| **↺ Nova rodada** | para tudo, volta o robô ao início, obstáculos e gangorras voltam ao lugar |
| **LoP** (L) | falta de progresso: o robô volta ao último checkpoint, virado para a chegada |
| **LoP: reinicia prog. / só botão** | num LoP, desliga e liga o programa ou só aperta o botão de início |
| **Botão do robô** (B), **Auto-botão** | aperta o botão de início (P3); o auto-botão aperta 1,5 s depois que o programa sobe |
| **Robô: 4x4 / esteira / Paçoca** | troca o robô (os `robo_*.json` da pasta). Robô do Paçoca roda `.ino`; os do Mariola, `.py`: ao trocar, o programa troca junto (o último usado com aquele brick ou o exemplo) |
| **Programa: pasta/arquivo (trocar)** | escolhe outro programa sem fechar o simulador (`.py` nos robôs do Mariola, `.ino` no Paçoca): para o que está rodando, volta à rodada nova e o próximo ▶ Iniciar já roda o escolhido |
| **Caminho (P)** | mostra o número de cada passo do caminho esperado, como no editor oficial |
| **Pausar** (espaço) / **Vel.** (1–5) | pausa ou muda a velocidade (0,25x a 4x). O resultado é o mesmo em qualquer velocidade |
| arrastar o robô / Q, E / roda do mouse | reposiciona o robô (com o programa parado) |
| R, T | raios dos VL53, trilha |
| O | mostra/esconde a tela e o teclado do brick (botões: clique ou F1–F4) |
| C | mostra/esconde o último quadro que o programa leu da câmera de linha (canto de baixo à esquerda) |

O painel mostra o tempo, a pontuação, os eventos do juiz e as leituras: os **4 canais de reflexão**
(o que a lib recebe), os **12 ITR8307 um a um** (cinza = leitura de cada um), a cor dos **3 TCS**,
giroscópio, encoders, VL53 e para-choque. No mapa, cada ITR8307 e cada TCS aparece no robô com a
leitura dele. Com área de resgate aparecem também os TCS horizontais, o estado do braço, dos dedos,
da porta e da caçamba, cada servo (posição > alvo, ligado/desligado/TRAVA) e o que a câmera viu
(o leque azul na frente do robô fica vermelho quando a garra abaixada tapa a câmera). As vítimas
resgatadas continuam desenhadas dentro do triângulo, com um anel verde.


### Tela OLED e teclado do brick

A placa da tela + teclado (conector TELA, barramento I2C 0) aparece no canto de baixo à direita do
mapa: a tela 128x64, os 4 LEDs (branco, vermelho, laranja, verde) e os 4 botões (Voltar, Baixo,
Cima, Enter). Clique nos botões ou use F1–F4; **O** esconde o painel. A `tela.py` e a `teclado.py`
rodam sem mudar: o simulador troca o `luma.oled` por uma tela virtual (o desenho é feito com o
Pillow, como no robô) e traz a fonte DejaVu em `fake_hw/fontes/` para o caminho do Linux funcionar
no Windows. No robo.json: `"tela"` (barramento e endereço) e `"teclado"` (barramento, endereço e
`leds_acendem_com`: o nível do bit que acende o LED; na placa atual, 1: ao ligar os quatro ficam acesos e `Teclado()` apaga todos). Use `Teclado(i2c_bus=0)`:
`"teclado": true` simula a placa antiga, com o teclado no barramento 1.

---

## Editor de mapas

O editor usa os **82 ladrilhos do sistema oficial** (o `rcj-rescue-cms`, que é o que roda o
editor do rcj.cloud), com os caminhos, gaps e interseções de cada um. Mais três gerados aqui:
`branco`, `gangorra` e `chegada` (fita vermelha 25 x 300 mm).

| Ferramenta | Uso |
|---|---|
| **Ladrilho** | escolha na paleta e clique na célula. Clicar de novo no mesmo ladrilho gira 90°. **R** ou roda do mouse giram o da paleta. Botão direito apaga |
| **Girar** | clique gira 90° horário; botão direito, anti-horário |
| **Início** | marca o ladrilho de início; clique de novo para trocar a direção de saída |
| **Checkpoint** | marca/desmarca (o editor avisa se o ladrilho tem item pontuável) |
| **Rampa** | sem rampa → sobe para N → L → S → O. Botão direito troca a inclinação (10°–25°) |
| **Lombada** | põe uma lombada (1 cm) atravessada no caminho onde clicou; botão direito tira |
| **Obstáculo** | põe em cima da linha mais perto do clique; Shift+clique: solto/fixo; roda do mouse gira |
| **Detritos** | +1/−1 palito solto no ladrilho |
| **Camada ± ** | ladrilhos de ponte ficam na camada 1 (por cima de um ladrilho da camada 0) |
| **Área resgate** | clique põe a área (4 x 3 ladrilhos) com o canto de cima à esquerda na célula. Roda do mouse: 4x3 / 3x4. Shift+clique dentro: obstáculo. Botão direito dentro: tira a área |
| **Entrada/saída** | clique perto de uma parede da área: entrada (fita prata). Botão direito: saída (fita preta) |
| **Triângulos** | clique perto de um canto: triângulo verde. Botão direito: vermelho |

O editor calcula o **caminho esperado** a partir do início (o mesmo algoritmo do sistema oficial)
e mostra o número de cada passo em cada ladrilho. Ele avisa se o caminho não chega na chegada, se tem
menos de 8 ladrilhos, checkpoint em ladrilho com item, rampa acima de 25°, etc.

**Altura:** não precisa mexer em camada para rampa. Depois de uma rampa o caminho segue na altura
nova (o simulador calcula a altura de cada ladrilho seguindo o caminho). Camada só é necessária para
**ponte**: o ladrilho de cima vai na camada 1, na mesma célula de um ladrilho da camada 0. A ponte
tem pilares de 25 x 25 mm nos cantos, que o robô de baixo pode acertar.

**Área de resgate:** a linha tem que chegar na entrada (vinda do ladrilho do lado de fora) e
recomeçar no ladrilho do lado de fora da saída. O caminho conta a área como um passo só. O editor
avisa se os triângulos estão no canto da entrada/saída (regra 3.9.9) ou se a parede é preta,
vermelha ou verde.

**Importar do rcj.cloud:** o "Abrir" também aceita o JSON de mapa exportado pelo sistema oficial
(`tiles`, `tileType`, `levelUp/levelDown`, `checkPoint`, `items`). A zona de resgate dele é
ignorada (desenhe a área com a ferramenta **Área resgate**).

Formato próprio (`mapas/*.json`, fácil de editar na mão):

```json
{"largura": 8, "altura": 7, "inicio": [0, 5, 0], "inicio_dir": "L",
 "ladrilhos": [
   {"x": 0, "y": 5, "z": 0, "tipo": "tile-0", "rot": 0},
   {"x": 1, "y": 5, "z": 0, "tipo": "tile-0", "rot": 0, "lombadas": [{"pos": 0.35, "eixo": "LO"}]},
   {"x": 7, "y": 4, "z": 0, "tipo": "tile-0", "rot": 90, "rampa": {"sobe": "N", "graus": 25}},
   {"x": 3, "y": 5, "z": 0, "tipo": "tile-0", "rot": 0,
    "obstaculos": [{"u": 150, "v": 150, "larg": 60, "comp": 60, "altura": 150, "fixo": false, "massa_kg": 1.5}]},
   {"x": 6, "y": 5, "z": 0, "tipo": "tile-0", "rot": 0, "checkpoint": true, "detritos": 3}
 ]}
```

Grade: `x` = coluna, `y` = linha (0 em cima), `z` = camada. `rot` em graus no sentido horário.
Direções: N (cima), L (direita), S (baixo), O (esquerda). Obstáculo: `u`, `v` em mm a partir do
canto sudoeste do ladrilho.

A área de resgate vai em `zona_resgate` (as células dela não têm ladrilhos no arquivo):

```json
"zona_resgate": {"x": 2, "y": 1, "larg": 4, "alt": 3,
  "entrada": {"lado": "S", "i": 2}, "saida": {"lado": "L", "i": 0},
  "verde": "NO", "vermelho": "SE", "obstaculo": null, "cor_parede": [200, 200, 205],
  "vitimas": null, "falsas": 0}
```

`lado` + `i`: parede e célula (contando da esquerda ou de cima) do vão. `vitimas: null` sorteia
2 vivas e 1 morta a cada rodada pela semente; ou uma lista `[{"tipo": "viva", "u": 300, "v": 450}, ...]`
(mm a partir do canto sudoeste da área). `falsas`: quantas vítimas falsas (regra 3.10.5) pôr no chão.

---

## Os robôs do Mariola

| | `robo_4x4.json` | `robo_esteira.json` |
|---|---|---|
| tração | 4 rodas de aspirador 70 mm: 2 no Mariola + 2 placas de motor (SERIAL1) | 2 esteiras, 2 motores no Mariola |
| sensor de linha | Pro1616 na SERIAL6 | o mesmo, na mesma altura |
| outros | giroscópio (SERIAL5), VL53 esquerda/direita/frente a 5 cm (I2C1, I2C3, I2C5) e na garra (I2C2), TCS horizontais frente/trás (I2C6, I2C7), para-choque P1/P2, botão P3 | giroscópio, 3 VL53 a 5 cm (I2C1, I2C3, I2C5), para-choque, botão |
| resgate | câmera USB na frente (stub) + garra de 2 dedos + caçamba de 2 lados, 4 servos inteligentes na SERIAL1 | não tem: só atravessa a área e sai |

Cada esteira encosta no chão em 5 pontos, todos com a velocidade do mesmo motor: o robô de esteira
gira com mais esforço (as pontas da esteira arrastam de lado). **Medidas, motor e polia da esteira
são estimativas** (ver `_comentario` no json).

`robo_4x4_camera.json` é o mesmo 4x4, mas segue a linha com a **câmera de linha** no lugar do
Pro1616 (não tem `sensor_linha` nem nada na SERIAL6: a `CorReflexao` dá erro ao abrir, como no robô).
Programa de exemplo: `exemplo_aluno/seguidor_camera.py`. Na janela, o botão **Robô** mostra "4x4-câmera".

### Sensor de linha Pro1616 (como está no `sensor_linha`)

```
            ← esquerda (y +)                        direita (y −) →
 fileira IR   o o o | o o o | o o o | o o o      12 ITR8307, 65 mm entre o 1º e o 12º (passo 5,9 mm)
   x = 80      canal0  canal1  canal2  canal3    cada grupo de 3 = 1 canal (média, como em paralelo)
                       9 mm
 fileira TCS    [TCS1]    [TCS2]    [TCS3]       20 mm entre si
   x = 71        y=+20     y=0      y=−20
```

* **Bytes** iguais aos do firmware: 4 de reflexão (0 = preto, ~100 = branco calibrado; a fita prata lê
  menos que o branco, ~80) + 3 x RGBC (TCS calibrado no branco e enviado pela metade, branco ≈ 127;
  com os LEDs brancos de 5 mm a fita prata passa de 127, ~200), na taxa do firmware (`taxa_hz`,
  50 Hz). A lib `sensorCorReflexao.py` não muda.
* Cada ITR8307 enxerga um disquinho de 2 mm de raio; cada TCS, 4 mm. Por isso a borda da linha e
  o verde aparecem "misturados", como no real.
* **Altura:** se o piso fica mais longe que o normal (crista de rampa, robô inclinado de lado, beira
  de ladrilho elevado), a leitura cai, porque o ITR8307 é muito sensível à distância. Em cima do vazio ele lê
  0, que parece preto. A curva é a `curva_ir` (ver abaixo).
* `modo_grupo: "minimo"` troca a média dos 3 pelo menor valor; `ordem_ir` inverte o lado do canal 0.
* `cores_piso`: leitura de cada material (branco, preto, verde, vermelho, prata, madeira dos
  detritos, fora do campo). **Atenção ao verde no IR**: fita verde costuma refletir infravermelho.
  Meça no robô e troque.

**A medir no robô:** `x_ir`/`x_tcs` (distância do sensor à frente do centro do robô), o motor e a polia da esteira, e os valores de `cores_piso`.

### Mecanismo de resgate (`resgate` no `robo_4x4.json`)

Quatro servos inteligentes (MG90S com a `placaControleServo`) no **mesmo barramento das placas de
motor** (SERIAL1): braço, dedo esquerdo, dedo direito e a porta da caçamba. O simulador emula o
**firmware da placa de 21/10/2026** byte a byte: protocolo de 6 bytes, broadcast (ID 254), troca de
ID, calibração do tempo de trava (comando 65000), consulta (65001), polaridade (65002) e
configuração do controle (65003); controle **proporcional com freio** (o padrão: KP, KD, termo I,
PWM mínimo, histerese) ou **liga-desliga**, sempre com zona morta e a potência como teto; **trava**
(parado mais que o tempo de trava = motor desliga 2 s), **5 s sem comando = motor desliga**, 10 s =
a placa reinicia (configuração e polaridade ficam, como na EEPROM). O motor simulado está ligado do
jeito normal: a autodetecção da polaridade sempre acerta. A lib `placaControleServo.py` roda sem
mudar.

* Cada posição é a **leitura do potenciômetro** (0–1023) que vocês calibram no robô: braço `baixo`
  (garra no chão) e `alto`; dedos `aberto` e `fechado` (encostando no outro); porta `fechada`,
  `solta_esq` e `solta_dir`.
* MG90S a 5 V pela ponte L9110S: ~0,12 s por 60° com potência 255 (`graus_por_s`), parado abaixo de
  `pwm_minimo` (45, estimado: tem de ficar abaixo dos 60 de PWM mínimo do firmware, senão o
  controle proporcional para antes do alvo). O braço é mais lento (`carga`). Sem inércia: no
  liga-desliga ele não vibra em volta do alvo como o servo de verdade.
* **O braço cai sem força**, a não ser todo levantado (ali ele se apoia no fim de curso). Trava,
  potência 0, 5 s sem comando e `le_posicao()` desligam o motor. Use `consulta_posicao()` para ler.
* **Os dedos só seguram com força enquanto empurram.** Fechando na bolinha eles param encostados e,
  depois do tempo de trava, o motor desliga; se o braço estiver se mexendo nessa hora, a bolinha cai.
  Por isso o `tempo_trava_ms` (o valor calibrado na EEPROM) está em 3000 no exemplo.
* Com o braço no alto, **abrir um dedo só** joga a bolinha naquele lado da caçamba
  (`capacidade_lado` bolinhas por lado). A porta, girando para um lado, solta o lado oposto: a
  bolinha cai a ~10 cm do chão, `distancia_queda` atrás da traseira, e passa por cima da parede de
  6 cm do triângulo se o robô estiver encostado nele.
* Com a garra **toda abaixada**, a câmera fica tapada.

### Câmera (stub, módulo `visao`)

A câmera ainda não gera imagem: o módulo `visao` devolve o que a IA e o OpenCV veriam, para treinar
a **movimentação e a lógica**. A interface é a mesma do `robo_real/visao.py`, que faz isso com a câmera
USB (falta só colocar a YOLO de vocês):

```python
from visao import Visao
v = Visao()
for d in v.vitimas():       # ~4 quadros/s, como a IA no Mariola
    print(d.tipo, d.angulo, d.distancia, d.x, d.raio_px, d.confianca)
for t in v.triangulos():    # ~30 quadros/s, como o OpenCV
    print(t.cor, t.angulo, t.distancia, t.x_min, t.x_max)
```

* Cada chamada espera o próximo quadro e devolve o que a câmera viu **quando o quadro foi
  capturado**: a resposta chega um quadro atrasada, com o robô já mais à frente, como no robô.
* `acerto` 90%: a vítima visível pode não aparecer. O erro fica **preso ao ponto de vista**: parado no
  mesmo lugar o resultado se repete; andando ou girando ele é sorteado de novo.
* `erro_classe` 3% (viva vira morta e vice-versa), ruído no ângulo e na distância, vítimas falsas
  detectadas como vivas (`falsa_detectada`), campo de visão (`fov_graus`) e alcance.
* A câmera fica a 5 cm do chão: uma vítima esconde a outra, a parede do triângulo (6 cm) esconde o
  que está dentro dele, a parede e o obstáculo escondem o que está atrás.

### Câmera de linha (`camera_linha`, imagem de verdade para o OpenCV)

Só no `robo_4x4_camera.json`: uma segunda câmera USB, **embaixo do robô, olhando reto para o
chão**, um pouco atrás das rodas da frente, no lugar do sensor de linha. Esta gera a imagem: o
programa usa o OpenCV normalmente e só o `cv2.VideoCapture` é do simulador (a câmera das vítimas
continua sendo o stub `visao` de cima).

```python
import cv2
cam = cv2.VideoCapture('/dev/video_usb2')    # câmera da porta USB 2 (regra 99-cameras.rules)
ok, img = cam.read()                         # BGR, 320 x 240, como no robô
cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
```

* Frente do robô no topo da imagem, esquerda do robô à esquerda. 76° na horizontal a 106 mm do
  chão: a imagem cobre 165 x 124 mm (0,52 mm por pixel), de 12 mm atrás a 112 mm à frente do centro
  do robô. As **rodas da frente aparecem nas bordas** da esquerda e da direita (corte uns 40 px de
  cada lado antes de procurar a linha).
* `read()` segue o fps da câmera (30): devolve o quadro mais novo e, se ele já foi lido, espera o
  próximo. `set(cv2.CAP_PROP_FRAME_WIDTH/HEIGHT)` muda a resolução (o campo de visão continua o
  mesmo). Arquivos de vídeo/imagem do PC abrem com o `VideoCapture` de verdade.
* A luz vem só da **fita de LEDs** do robô (`leds`; luz de fora não entra). Cada LED ilumina o chão
  caindo com a distância (o meio fica mais claro que os cantos) e se **reflete** no chão liso onde o
  ângulo do LED e o da câmera batem:
  * `"difusor": false`: imagem bem iluminada, mas a **fita isolante preta** e a **fita prata**
    estouram em pontos brancos (um por LED, onde a fita passa pela faixa dos reflexos);
  * `"difusor": true`: passa só `transmissao_difusor` da luz e cada LED vira uma faixa de
    `largura_difusor_mm`: o reflexo vira uma faixa larga e mais fraca na fita preta;
  * `"exposicao": "auto"` compensa a luz que falta (com o difusor, o ruído aumenta quase 2x); um
    número fixa a exposição (1 = certa para a fita sem difusor; com o difusor a imagem escurece);
  * `"reflexos": false` deixa o chão todo fosco; sem `leds` a luz é igual em tudo (modelo simples).
  Posição da fita (`x`, `y_inicio`, `y_fim`, `altura_mm`) e o brilho de cada material
  (`ESPECULAR` em `sim/camera_linha.py`) são estimativas. Além disso: menos luz nos cantos pela
  lente (`vinheta`), foco um pouco mole (`desfoque`) e ruído em cada pixel (`ruido`). As cores são
  as do piso do simulador (branco, preto, verde, vermelho, prata, madeira dos palitos).
* No `camera_linha` do json: posição (`x` = 50 mm, `y`, `altura_mm`), `fov_horizontal_graus`, `rotacao_graus`
  (câmera montada girada), resolução, `fps`, `dispositivos` (o nome que o programa abre) e `tampas`
  (placas embaixo do robô que aparecem na imagem, como a do sensor de linha).
* Precisa do OpenCV no Python do PC (`pip install opencv-python-headless`; o pacote portátil já traz).
* Gasta uns 12 ms de PC por quadro: com a câmera, o simulador fica mais lento (o resultado não muda).

### TCS34725 horizontais (`tcs_i2c`)

Pela lib `tcs34725.py` (I2C, mux). Leem a cor do que está na frente deles, na altura deles: a
parede do triângulo, a parede da área ou uma vítima. A leitura cai com a distância (o LED do módulo
ilumina). O de trás confirma que o robô encostou no triângulo certo antes de soltar.

---

## Física

* **Rampas** (até 25°): a gravidade puxa o robô na subida e na descida. O giroscópio mostra a
  inclinação. O robô se apoia nos contatos mais altos, então no pé e na crista da rampa ele fica
  inclinado e o sensor muda de altura.
* **Gangorra**: gira no meio do ladrilho quando o centro do robô passa do eixo. Começa inclinada para
  o lado de quem chega. Num LoP, a gangorra à frente é virada a favor do robô, como diz a regra.
* **Ponte**: o robô de baixo passa por baixo do ladrilho da camada 1 e pode bater nos pilares.
  Cair de um ladrilho elevado ou sair do campo dá LoP.
* **Lombadas e detritos são relevo de verdade.** A lombada tem 10 mm de altura e perfil arredondado
  de 30 mm. O palito é um cilindro de 3 mm. O robô se apoia nos pontos mais altos das rodas, das
  esteiras e da **placa do sensor**, e daí saem a inclinação, o giroscópio e a distância de cada
  ITR8307/TCS até o chão.
  * **Roda (4x4):** sobe na lombada antes de chegar nela, pelo raio da roda. Só ela levanta, por
    pouco tempo, e as rodas que ficam no ar perdem tração (contorno laranja na tela).
  * **Esteira:** a parte de baixo é reta. Um ressalto embaixo de qualquer trecho dela levanta aquele
    lado inteiro, e o robô fica inclinado enquanto a esteira toda passa por cima. Na lombada ele vai
    inclinando até o centro passar e então tomba para a frente, como uma gangorra. O sensor fica
    longe do chão por muito mais tempo que no 4x4. A esteira tem tração enquanto algum trecho dela
    encosta em alguma coisa.
  * **Placa do sensor:** se o chão sobe mais que `altura_mm` (com os 12 mm da equipe isso não acontece
    na lombada de 10 mm; acontece se `altura_mm` for menor), ela **raspa**: a frente do robô levanta, as rodas da frente podem sair do
    chão e o sensor encostado lê quase 0, que parece preto.
  * **Leitura x distância:** o sensor fica a `altura_mm` = **12 mm** do chão (altura da equipe) e a
    calibração vale nessa altura. Fora dela, a leitura segue a curva do ITR8307 (`curva_ir`, forma
    aproximada do datasheet: pico perto de 1 mm e queda de ~1/d² depois):
    * 5 mm mais longe: cai mais ou menos pela metade.
    * Sensor a 2 mm do topo da lombada: o branco satura em 255 e o preto da linha fica cinza.
    * Encostado: vai a 0.
    O painel mostra a distância sensor–piso. Se medirem a curva no robô (leitura no branco a
    várias alturas), troquem a `curva_ir`.
  * Ainda há uma vibração extra no giroscópio e um pequeno desvio de direção quando a roda bate. Os
    palitos rolam um pouco quando a roda passa e o sensor os vê como madeira.
* **Obstáculos**: caixas (60 x 60 mm por padrão) que o robô empurra (com atrito no chão) ou fixas.
  Os VL53 e o para-choque enxergam obstáculos e pilares.
* Motores, encoders, PID, timeouts e watchdog: os mesmos do simulador da Maze (firmware do
  Mariola e da placa de motor). **5 s sem pacote para o Mariola: motores soltos.** Numa rampa, o robô
  desce de ré.
* **Área de resgate** (regra 3.9 e 3.10): 120 x 90 cm medidos por fora; as paredes (10 cm de altura,
  25 mm de espessura) ficam para dentro. Vão de 25 cm na entrada e na saída, com a fita (prata na
  entrada, preta na saída, 25 x 250 mm) faceada com a parede, no vão. Triângulos de 30 x 30 cm com
  paredes de 6 cm, encostados nas faces de dentro das paredes; obstáculo opcional. Vítimas: esferas de 45 mm e 70 g, que rolam com
  resistência ao rolamento e com o centro de massa deslocado (fazem curva), batem nas paredes e são
  empurradas pelo robô. Uma vítima não sobe a parede de 6 cm do triângulo: só entra caindo de cima.
  Os VL53 têm `altura`: o feixe só vê o que é mais alto que ele (um VL53 a 5 cm vê a parede e o
  triângulo, mas não as vítimas).

## Juiz (regra 2026)

* Cada perigo vale **uma vez por sentido** em que o caminho passa por ele, quando o robô sai do
  ladrilho para o próximo do caminho: interseção/beco sem saída 10, gap 10, obstáculo 20, lombada 10
  (por ladrilho), rampa 10 (por ladrilho), gangorra 20.
* **Checkpoint**: ladrilhos desde o anterior x 5 / 3 / 1 / 0 (1ª, 2ª, 3ª, 4ª tentativa).
* **Chegada**: parado mais de 5 s no ladrilho da fita vermelha. Ganha os ladrilhos desde o último
  checkpoint e o bônus de saída, 60 − 5 x LoP (no mínimo 0). A rodada termina.
* **LoP automático**: robô sai do campo ou cai, chega numa linha que não é a próxima do caminho, ou
  fica 10 s fora do caminho sem linha. Contornar obstáculo por um ladrilho vizinho é permitido. Depois
  de 3 tentativas, o robô vai para o próximo checkpoint.
* Ajustes em `juiz` no `robo_*.json`: `tempo_fora_do_caminho_s`, `lop_sem_progresso_s` (LoP
  se ficar N s sem avançar; 0 = desligado), `pula_checkpoint_apos_3_tentativas`.
* **Área de resgate** (5.6.6 a 5.6.12): vítima inteira dentro do triângulo certo e sem o robô
  encostar nela = resgatada (o juiz tira do campo). Viva no verde x1,4; a morta no vermelho x1,4
  **só se as duas vivas já foram resgatadas** (antes disso ela fica lá e não vale). Cada termo perde
  0,05 por LoP no trecho entre os checkpoints que contêm a área, sem ficar abaixo de 1,25.
  Pontuação final = (linha + bônus de saída) x multiplicador. A área não conta como ladrilho nos
  checkpoints (a regra não diz; aqui não conta).
* **LoP na área** (5.5.6): vítimas que estavam com o robô (garra e caçamba) ficam no chão onde ele
  estava; se o LoP foi depois de sair da área, elas são espalhadas pela área. As do chão não mudam.

O LoP volta o robô ao último checkpoint. O modo **reinicia prog.** desliga e liga o programa, como
desligar o robô. Arquivos listados em `arquivos_rodada` são apagados a cada "Nova rodada".

---

## Programa de exemplo (`exemplo_aluno/`)

* `robo.py`: hardware. Funciona nos dois robôs: `TRACAO = 'auto'` vê se há placas de motor na
  SERIAL1.
  Também acha a garra (servos), os VL53 extras e os TCS horizontais, se existirem.
* `main.py`: seguidor com PID nos 4 canais, verde pelos TCS da esquerda e da direita (os dois =
  meia-volta), curva de 90°, gap pelo giroscópio, obstáculo contornando pela direita e parada na fita
  vermelha. Na fita prata chama o `resgate.py`.
* `resgate.py`: com câmera e garra, gira procurando vítimas, chega perto, confirma o tipo em mais dois
  quadros, abaixa a garra aberta, avança até o VL53 da garra ver a bolinha, fecha, levanta e joga no
  lado certo da caçamba. Depois leva as vivas ao verde e, se as duas foram entregues, a morta ao
  vermelho: chega de frente, vira e encosta de ré (o TCS de trás confere a cor). Sem câmera (robô
  de esteira) vai direto para a saída: segue a parede pela direita até um vão com fita preta (a
  prata é a entrada: passa reto). As paredes da área são paralelas à direção em que o robô entrou, e
  o giroscópio guarda essa direção para o robô se alinhar.
* Fita prata x lombada x rampa: quem vê o prata é o TCS (C ~200, acima do branco); o IR lê menos no
  prata (~80). Em cima da lombada e no pé da rampa o sensor fica mais perto do chão e tudo clareia.
  No alto da lombada o branco também chega a ~200 no TCS, mas a linha preta continua embaixo do meio
  do sensor. O exemplo só aceita a fita prata com os 3 TCS classificando "prata" e C acima de 165,
  os 4 canais de IR entre 50 e 120 (sem linha preta, sem estourar) e, na entrada da área, o robô
  nivelado.
* `robo.py` aceita robô sem o sensor de linha (`self.cor = None`; `reflexao()` e `cores()` dão erro).
* `seguidor_camera.py` (robô `robo_4x4_camera.json`): seguidor só com a **câmera de linha** (OpenCV):
  PD na posição da linha na metade de cima da imagem, gap reto, verde (só o que aparece antes da
  interseção, chegando pela frente da imagem; depois de girar, o verde da mesma interseção não conta
  de novo) e parada no vermelho. Não trata obstáculo, rampa nem área de resgate.

É um ponto de partida, não a solução. Nos mapas de exemplo ele completa a rodada às vezes sem LoP e
às vezes com. Na área de resgate ele costuma pegar as três vítimas, mas às vezes perde uma. Use isso
para ver o que melhorar.

## Brick Paçoca (programa em Arduino)

O robô do Paçoca é programado em Arduino (C++) com a biblioteca **brickSimples**. O simulador
compila o `.ino` da equipe **com o g++ do PC**, junto com as bibliotecas reais do brick
(`brickSimples.h`, `BMI160.cpp`, `VL53L0X.cpp`, `TCS34725.cpp`, ...), e troca só a camada de baixo:

```
  programa da equipe (.ino)
        │  #include "brickSimples.h"   (SensorLinha, BMI160, VL53L0X, Motor...)
        ▼
  bibliotecas REAIS do brick  (pasta do programa, ou pacoca/libs_pacoca/ como reserva)
        │  Arduino.h, SoftwareSerial, SoftWire, pinos, millis()
        ▼
  pacoca/nucleo + pacoca/troca  ── Arduino simulado: relógio virtual, pinos, serial e I2C
        │  socket local
        ▼
  pacoca/ponte.py  ── Pro1616, VL53L0X, TCS34725, BMI160, ultrassom, ponte H dos motores
        │  socket TCP local
        ▼
  simulador.py  ── física, juiz, janela (os mesmos dos robôs do Mariola)
```

* **Para rodar:** `python simulador.py --programa CAMINHO/DO/programa.ino` (com um `.ino`, o
  simulador já escolhe o `robo_pacoca_amarelo.json`). Ou troque o robô na janela.
* A **primeira** rodada compila tudo (alguns segundos); depois só o que mudou. Os erros de
  compilação aparecem no terminal do simulador, com o nome do arquivo e a linha. Para só compilar:
  `python pacoca/compila.py CAMINHO/DO/programa.ino`.
* A pasta do programa pode ter só o `.ino` (as bibliotecas vêm de `pacoca/libs_pacoca/`) ou a cópia
  da brickSimples da equipe, mesmo modificada: os arquivos da pasta do programa ganham. Vários `.ino`
  na pasta são juntados como na IDE do Arduino (o do nome passado primeiro), com os protótipos
  das funções gerados sozinhos.
* O build fica em `.sim_build/` dentro da pasta do programa (pode apagar). A EEPROM do brick fica
  em `eeprom_pacoca.bin`, na mesma pasta: a calibragem gravada (`giro.calibrar()`) continua lá na
  próxima rodada, como no robô. Apague o arquivo para começar com a EEPROM limpa.
* O **sensor de linha** é o Pro1616 com o protocolo novo (`0x61` → 16 bytes; `0x62`/`0x63`
  calibram). Use o `sensorLinha.h` atual da brickSimples; o antigo (modos 0 a 7, 32 bytes) não
  recebe resposta e o simulador avisa.
* `avalia.py` também aceita `.ino` (usa o robô do Paçoca; compila uma vez antes das rodadas).

### Robôs do Paçoca (`robo_pacoca_amarelo.json`, `robo_pacoca_ev3.json`)

Dois motores sem encoder nas portas **M1** (esquerdo: pinos 9 PWM e 7 direção) e **M2** (direito:
10 e 4) e uma roda boba na frente (`apoios`). O motor da direita é montado espelhado
(`"sentido": -1`): como no robô, o programa usa `MOTOR_INVERTIDO` nele. O botão do brick (A6) é o
**Botão do robô** / tecla **B** (`brick.botaoApertado()`).

O que está ligado em cada porta do brick fica em `"pacoca" → "portas"`. As portas 1 a 5 são
genéricas: cada uma é I2C, serial ou ultrassom, conforme o que a equipe pôs nela.

```json
"pacoca": {
  "portas": {
    "1": {"tipo": "vl53", "sensor": "frente"},
    "3": {"tipo": "pro1616"},
    "5": {"tipo": "bmi160"},
    "2": [{"tipo": "vl53", "sensor": "esquerda"}, {"tipo": "tcs34725", "sensor": "lado_esq"}]
  }
}
```

| tipo | o que é | detalhes |
|---|---|---|
| `pro1616` | sensor de linha/cor (serial 115200) | a geometria e as cores são as do `sensor_linha`/`cores_piso` |
| `vl53` | VL53L0X (I2C 0x29; a lib muda para 0x30) | `sensor` = nome em `"vl53"` (posição, ângulo, altura no robô) |
| `tcs34725` | TCS34725 olhando para o lado (I2C 0x29) | `sensor` = nome em `"tcs_i2c"`; VL53 + TCS na mesma porta funciona como no robô (o VL53 tem de ser iniciado primeiro) |
| `bmi160` | BMI160 (I2C 0x68) | `"bmi160"`: eixos do chip no robô, viés de cada eixo, resíduo depois do `calibrar()` |
| `ultrassonico` | HC-SR04 (`PORTA_ULTRASSONICO_n`) | `sensor` = um item de `"vl53"` com `"params"` de ultrassom (cone, alcance) |

Para-choque e outros botões: `"para_choque"` com `"pino"` = número do pino do Arduino (ex.: 13 =
porta S1) e `"pacoca" → "botoes"`; `digitalRead` desses pinos lê o simulador (0 = apertado).

**Motores.** Cada motor é um motor DC numa ponte H, sem PID: força no chão = Fs·(u − c·v/v0), onde
u é a fração do tempo com tensão (o sinal dá o sentido) e c a fração do tempo com o circuito fechado
(tensão ou freio). Rotação sem carga (`rpm_livre`), força com o motor travado (`forca_max_N`),
atrito interno da redução (`pwm_minimo`: abaixo disso o motor parado não sai do lugar) e a
diferença entre dois motores do mesmo modelo (`variacao`, sorteada pela semente: um lado puxa mais)
ficam em `motor_padrao`. **São estimativas (A MEDIR):** amarelo 1:48 a 5 V ~200 rpm, roda 65 mm;
EV3 grande a 5 V ~90 rpm, roda 56 mm, bem mais força.

`"ponte_h"` diz o que a ponte H do brick (**L9110S**) faz com os dois pinos iguais: `LL`
(`parar()` e a parte desligada do PWM para a frente) e `HH` (`frear()` e a parte desligada do PWM
na ré, porque o brick faz `analogWrite(255 - pwm)` com a direção em HIGH). No L9110S os dois são
**freio** (saídas em curto): `parar()` e `frear()` fazem a mesma coisa, e entre os pulsos do PWM o
motor freia nos dois sentidos, então frente e ré respondem igual. Há clones do L9110S em que `LL`
deixa as saídas soltas (alta impedância); para simular um deles, use `"LL": "solto"`: aí a frente
fica bem mais rápida que a ré com a mesma potência e a resposta deixa de ser linear.

**BMI160.** A lib lê a FIFO do giro (25 Hz) a cada 40 ms e integra; `getEixoZ()` é em **décimos de
grau** (+ = anti-horário com o chip na orientação padrão). Sem calibrar, o viés (`bias_dps`) faz o
ângulo andar sozinho (0,5 °/s = 30° por minuto); o `calibrar()` usa o FOC do chip e grava os offsets
na EEPROM.

**Tempo.** Cada função do Arduino gasta mais ou menos o tempo que gasta no ATmega a 16 MHz
(`analogRead` ~112 µs, I2C ~50 µs por byte, um byte da SoftwareSerial ~87 µs). O cálculo do
programa não gasta tempo. O `brick.atualiza()` tem esperas fixas de ~15 ms e, com um VL53
adicionado, espera a medida dele (~33 ms): o laço do programa roda a ~30 Hz, como no robô. O
`millis()` atrasa um pouco quando a lib desliga as interrupções por mais de 1 ms (leitura do
Pro1616), como no ATmega.

**O que é diferente do robô** (o programa pode funcionar aqui e não no robô):

* `int` tem 32 bits no PC (16 no AVR) e `double` tem 64 (32 no AVR): conta que estoura no robô
  (`int x = 300 * 200;`) dá certo aqui. A RAM não tem o limite de 2 KB.
* O código em assembly do AVR é retirado. O reset (`jmp 0`) reinicia o programa.
* Servo, buzzer, voz, música e bluetooth não aparecem no robô simulado (voz e música só escrevem
  no terminal). A fita de LED aparece nos LEDs do robô. Interrupções externas e de pino não são
  simuladas (o ultrassom do brick foi trocado por uma versão sem interrupção, com a mesma interface).
* A SoftwareSerial do brick não tem buffer, e a simulada também não: o byte que chega enquanto o
  programa não está lendo é perdido, como no robô.

### Programa de exemplo do Paçoca (`exemplo_pacoca/`)

`exemplo_pacoca.ino`: o mesmo seguidor do exemplo em Python (PID nos 4 canais, verde, curva de 90°,
gap pelo giroscópio, lombada/rampa, obstáculo pela direita, parada na fita vermelha), sem área de
resgate. Sem encoder, as distâncias das manobras são por tempo (`MM_POR_S` e `PARTIDA_MS`, medidos
no simulador com o motor amarelo: meçam no robô de vocês) e os giros são pelo BMI160.

## Como o código continua compatível com o robô

```
  programa do aluno (main.py)
        │  from motores import Motores, from sensorCorReflexao import CorReflexao ...
        ▼
  bibliotecas REAIS do Mariola  (pasta do programa, ou libs_mariola/ como reserva)
        │  serial.Serial / smbus2.SMBus / gpiod / time
        ▼
  fake_hw/  ── firmware do Mariola, das placas de motor, do giroscópio, do Pro1616, VL53L0X/TCA9548A
        │  socket TCP local
        ▼
  simulador.py  ── física (pymunk + altura do piso), sensores, juiz, janela
```

Igual ao simulador da Maze: o programa roda num processo separado e a pasta do programa vem
primeiro no import. `simdebug` (`pose`, `texto`, `marca`) desenha na tela o que o programa acha. No
robô, use `robo_real/simdebug.py`, que não faz nada. O `visao` também só existe no simulador; no robô,
use `robo_real/visao.py` (câmera USB + a sua YOLO/OpenCV, mesma interface).

## Estrutura

```
simulador.py        janela / modo sem janela
rodar.py            executa o programa do aluno com o hardware virtual
rodar_pacoca.py     compila e executa o programa do brick Paçoca (.ino) com o hardware virtual
robo_4x4.json       robô 4x4 (o da Maze) com o sensor de linha, câmera e mecanismo de resgate
robo_4x4_camera.json  o mesmo 4x4 com a câmera de linha no lugar do sensor de linha
robo_esteira.json   robô de esteira
robo_pacoca_*.json  robôs do brick Paçoca (motor amarelo, motor EV3)
pacoca/             brick Paçoca: compila.py (g++), ponte.py (dispositivos), nucleo/ (Arduino.h
                    simulado), troca/ (SoftwareSerial, SoftWire, ultrassom... simulados),
                    libs_pacoca/ (cópia da brickSimples, reserva). Detalhes em pacoca/LEIAME.md
exemplo_pacoca/     programa de exemplo do Paçoca (.ino)
sim/                ladrilhos, mapa, física, área de resgate (resgate.py), juiz, servidor, interface,
                    camera_linha.py (geometria e imagem da câmera de linha)
ladrilhos/          os 82 ladrilhos oficiais (1 mm por pixel) + ladrilhos.json
fake_hw/            serial, smbus2, gpiod, firmware das placas, relógio virtual, camera.py (cv2.VideoCapture)
libs_mariola/       cópia das libs do Mariola (reserva)
mapas/              treino.json, completo.json e resgate.json
exemplo_aluno/      programa de exemplo
avalia.py           roda o programa em várias sementes e confere a meta dos desafios
desafios/           desafios.json (a trilha L01-L13) e os mapas dos desafios
resultados/         (criada pelo avalia.py) relatórios, logs e pistas surpresa
ferramentas/        importa_ladrilhos.py (refaz os ladrilhos a partir do rcj-rescue-cms), gera_mapas.py,
                    gera_desafios.py, pista_surpresa.py (gerador de pistas sorteadas),
                    monta_portatil.py (pacote portátil para Windows)
Simulador.bat       abre o simulador no Windows (com o Python de portatil/, se existir)
Avaliar.bat         roda o avalia.py no Windows (idem)
portatil/           (criada pelo monta_portatil.py, fora do git) python/ e gcc/ para Windows
dist/               (criada pelo monta_portatil.py, fora do git) o zip para o laboratório
```

## Limitações conhecidas

* Mundo 2,5D: o robô não capota nem pula. A altura do piso vem do mapa e o robô se apoia nos
  contatos mais altos.
* Lombada e palito levantam o robô, mas não freiam nem fazem o robô quicar (sem dinâmica vertical).
* A câmera das vítimas não gera imagem: é um stub que devolve as detecções (a YOLO de vocês não roda
  aqui).
* Câmera de linha: lente sem distorção (pinhole), piso sempre plano embaixo dela (na lombada e no pé
  da rampa a imagem não muda), rodas não fazem sombra, exposição automática fixa (calculada uma vez,
  não muda com a cena), sem borrão de movimento e sem o
  buffer do V4L2 (no robô, um laço lento pode receber quadros atrasados). O tempo que o OpenCV gasta
  no PC não conta: no Banana Pi, processar cada quadro leva alguns milissegundos.
* As vítimas são bolinhas 2D com altura: não pulam, não saem rolando por cima de nada e não apertam o
  para-choque. O mecanismo é cinemático (posições dos servos, sem forças): a bolinha entra na garra se
  estiver entre os dedos quando eles fecham.
* O barramento dos servos e das placas de motor é ideal (no real a resposta de 8 bytes da placa de
  motor pode desalinhar o próximo pacote de servo).
* O VL53 mede na hora em que o resultado é lido; no robô a medida é da hora em que foi pedida (a
  primeira leitura depois de um giro é "velha" no robô, e não no simulador).
* Uma conversa I2C não gasta tempo simulado (no robô, cada uma leva uma fração de milissegundo):
  ler o TCS no meio da espera dos VL53 só economiza tempo no robô.
* O motor é ideal: em potência (`potencia_motores`) a rotação não cai com a carga (rampa, empurrar
  obstáculo), e em velocidade o PID nunca satura. No robô, potência fixa fica mais lenta na subida.
* O BNO085 não é emulado.
* Paçoca: ver "O que é diferente do robô" na seção do brick Paçoca. O motor DC é o modelo médio
  (o PWM de ~30 Hz do Timer1 não faz o robô tremer).

## Créditos

Desenhos dos ladrilhos e definição dos caminhos:
[rcj-rescue-cms](https://github.com/robocup-junior/rcj-rescue-cms) (licença MIT, ver
`ladrilhos/LICENCA-rcj-rescue-cms.txt`).
