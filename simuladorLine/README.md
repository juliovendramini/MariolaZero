# Simulador RoboCupJunior Rescue Line — robôs com brick Mariola

Simulador 2,5D para desenvolver e testar o robô da **Rescue Line** (regra do mundial 2026): a linha
e a **área de resgate** (vítimas, triângulos, garra e caçamba), com o **mesmo código** que vai para o
robô real.

Como no simulador da Maze, o programa do aluno importa as bibliotecas reais do Mariola
(`motores.py`, `placaControleMotor.py`, `giroscopio.py`, `vl53.py`, `sensorCorReflexao.py`,
`botoes.py`, ...) e elas rodam **sem nenhuma alteração**. O simulador troca só a camada de baixo
(serial, I2C, GPIO e relógio) e emula o firmware de cada placa byte a byte.

---

## Instalação

Python **3.11 ou mais novo**.

```bash
pip install pygame pymunk numpy
```

Funciona no Windows e no Linux. No Linux, para os diálogos de abrir/salvar mapa, instale também
`python3-tk`.

## Uso rápido

```bash
python simulador.py                                        # robô 4x4, mapa de treino, programa de exemplo
python simulador.py --robo robo_esteira.json               # robô de esteira
python simulador.py --mapa mapas/completo.json             # rampas, ponte, gangorra, obstáculo...
python simulador.py --mapa mapas/resgate.json              # linha + área de resgate
python simulador.py --programa CAMINHO/DO/main.py          # programa da equipe
python simulador.py --editor                               # abre direto no editor de mapas

# sem janela: uma rodada inteira 2x mais rápido, imprime o placar (bom para testar várias vezes)
python simulador.py --mapa mapas/completo.json --sem-janela --velocidade 2
```

Opções: `--semente N` (ruído dos sensores; padrão 1, `-1` sorteia a cada rodada), `--lop botao|reiniciar`,
`--tempo 480`, `--tempo-real` (modo antigo do relógio, veja abaixo).

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
| **Robô: 4x4 / esteira** | troca o robô (os `robo_*.json` da pasta) |
| **Caminho (P)** | mostra o número de cada passo do caminho esperado, como no editor oficial |
| **Pausar** (espaço) / **Vel.** (1–5) | pausa ou muda a velocidade (0,25x a 4x). O resultado é o mesmo em qualquer velocidade |
| arrastar o robô / Q, E / roda do mouse | reposiciona o robô (com o programa parado) |
| R, T | raios dos VL53, trilha |

O painel mostra o tempo, a pontuação, os eventos do juiz e as leituras: os **4 canais de reflexão**
(o que a lib recebe), os **12 ITR8307 um a um** (cinza = leitura de cada um), a cor dos **3 TCS**,
giroscópio, encoders, VL53 e para-choque. No mapa, cada ITR8307 e cada TCS aparece no robô com a
leitura dele. Com área de resgate aparecem também os TCS horizontais, o estado do braço, dos dedos,
da porta e da caçamba, cada servo (posição > alvo, ligado/desligado/TRAVA) e o que a câmera viu
(o leque azul na frente do robô fica vermelho quando a garra abaixada tapa a câmera). As vítimas
resgatadas continuam desenhadas dentro do triângulo, com um anel verde.

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

## Os dois robôs

| | `robo_4x4.json` | `robo_esteira.json` |
|---|---|---|
| tração | 4 rodas de aspirador 70 mm: 2 no Mariola + 2 placas de motor (SERIAL1) | 2 esteiras, 2 motores no Mariola |
| sensor de linha | Pro1616 na SERIAL6 | o mesmo, na mesma altura |
| outros | giroscópio (SERIAL5), VL53 esquerda/direita/frente a 5 cm (I2C1, I2C3, I2C5) e na garra (I2C2), TCS horizontais frente/trás (I2C6, I2C7), para-choque P1/P2, botão P3 | giroscópio, 3 VL53 a 5 cm (I2C1, I2C3, I2C5), para-choque, botão |
| resgate | câmera USB na frente (stub) + garra de 2 dedos + caçamba de 2 lados, 4 servos inteligentes na SERIAL1 | não tem: só atravessa a área e sai |

Cada esteira encosta no chão em 5 pontos, todos com a velocidade do mesmo motor: o robô de esteira
gira com mais esforço (as pontas da esteira arrastam de lado). **Medidas, motor e polia da esteira
são estimativas** (ver `_comentario` no json).

### Sensor de linha Pro1616 (como está no `sensor_linha`)

```
            ← esquerda (y +)                        direita (y −) →
 fileira IR   o o o | o o o | o o o | o o o      12 ITR8307, 65 mm entre o 1º e o 12º (passo 5,9 mm)
   x = 80      canal0  canal1  canal2  canal3    cada grupo de 3 = 1 canal (média, como em paralelo)
                       9 mm
 fileira TCS    [TCS1]    [TCS2]    [TCS3]       20 mm entre si
   x = 71        y=+20     y=0      y=−20
```

* **Bytes** iguais aos do firmware: 4 de reflexão (0 = preto, ~100 = branco calibrado, acima de 100 =
  mais refletivo) + 3 x RGBC (TCS calibrado no branco e enviado pela metade, branco ≈ 127), na taxa do
  firmware (`taxa_hz`, 50 Hz). A lib `sensorCorReflexao.py` não muda.
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
**firmware unificado da placa** byte a byte: protocolo de 6 bytes, broadcast (ID 254), troca de ID,
calibração do tempo de trava (comando 65000), controle liga-desliga com zona morta e potência,
**trava** (parado mais que o tempo de trava = motor desliga 2 s), **5 s sem comando = motor desliga**,
10 s = a placa reinicia. A lib `placaControleServo.py` roda sem mudar.

* Cada posição é a **leitura do potenciômetro** (0–1023) que vocês calibram no robô: braço `baixo`
  (garra no chão) e `alto`; dedos `aberto` e `fechado` (encostando no outro); porta `fechada`,
  `solta_esq` e `solta_dir`.
* MG90S a 5 V pela ponte L9110S: ~0,12 s por 60° com potência 255 (`graus_por_s`), parado abaixo de
  `pwm_minimo`. O braço é mais lento (`carga`).
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
* Fita prata x lombada x rampa: em cima da lombada e no pé da rampa o sensor fica mais perto do chão
  e o branco também lê "claro demais". O exemplo só aceita a entrada com 3 canais entre 140 e 235
  (a lombada satura o IR), o robô nivelado e 2 TCS classificando "prata".

É um ponto de partida, não a solução. Nos mapas de exemplo ele completa a rodada às vezes sem LoP e
às vezes com. Na área de resgate ele costuma pegar as três vítimas, mas às vezes perde uma. Use isso
para ver o que melhorar.

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
robo_4x4.json       robô 4x4 (o da Maze) com o sensor de linha, câmera e mecanismo de resgate
robo_esteira.json   robô de esteira
sim/                ladrilhos, mapa, física, área de resgate (resgate.py), juiz, servidor, interface
ladrilhos/          os 82 ladrilhos oficiais (1 mm por pixel) + ladrilhos.json
fake_hw/            serial, smbus2, gpiod, firmware das placas, relógio virtual
libs_mariola/       cópia das libs do Mariola (reserva)
mapas/              treino.json, completo.json e resgate.json
exemplo_aluno/      programa de exemplo
ferramentas/        importa_ladrilhos.py (refaz os ladrilhos a partir do rcj-rescue-cms), gera_mapas.py
```

## Limitações conhecidas

* Mundo 2,5D: o robô não capota nem pula. A altura do piso vem do mapa e o robô se apoia nos
  contatos mais altos.
* Lombada e palito levantam o robô, mas não freiam nem fazem o robô quicar (sem dinâmica vertical).
* A câmera não gera imagem: é um stub que devolve as detecções (a YOLO de vocês não roda aqui).
* As vítimas são bolinhas 2D com altura: não pulam, não saem rolando por cima de nada e não apertam o
  para-choque. O mecanismo é cinemático (posições dos servos, sem forças): a bolinha entra na garra se
  estiver entre os dedos quando eles fecham.
* O barramento dos servos e das placas de motor é ideal (no real a resposta de 8 bytes da placa de
  motor pode desalinhar o próximo pacote de servo).
* A tela OLED e o BNO085 não são emulados.

## Créditos

Desenhos dos ladrilhos e definição dos caminhos:
[rcj-rescue-cms](https://github.com/robocup-junior/rcj-rescue-cms) (licença MIT, ver
`ladrilhos/LICENCA-rcj-rescue-cms.txt`).
