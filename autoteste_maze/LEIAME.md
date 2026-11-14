# Autoteste do robô da Maze

Programa que testa as peças do robô, uma por uma, para **achar problemas**. Ele mostra na tela o que
está testando e os valores, usa os botões do teclado para andar no menu e responder, e grava tudo num
relatório.

Cada robô tem um projeto próprio (`autoteste_boberto/`, `autoteste_maze/` e `autoteste_maze/`) com o mesmo código:
o que muda é o `robo.json`, que diz o que o robô tem e onde está ligado, e por isso quais testes
aparecem.

## O que este robô tem (`robo.json`)

Tirado do código da equipe (`robo.py`, `sensores.py` e `constantes.py`, repositório `IzadoraVB/maze2026`,
ramo `adaptacao-claude`, commit `75a33d1` de 14/11/2026):

* brick: motores 1 (invertido, esquerdo) e 2 (direito) com encoder, nos traseiros, e 10 LEDs RGB. A
  equipe não usa buzzer nem servo comum. Por isso o teste do buzzer fica de fora (`"timer2": "livre"`):
  ele prenderia o Timer2 até reiniciar o brick, e o dispenser de kits ainda pode ser um servo comum;
* barramento no **SERIAL2**: placas de motor 72 (frente esq) e 5 (frente dir, invertida);
* giroscópio no **SERIAL4** (o Z diminui girando para a direita);
* sensor de linha/cor (Pro1616) no **SERIAL6**: o TCS do meio lê a cor do chão;
* 5 VL53: frente I2C8, meio esq I2C3, borda esq I2C1, meio dir I2C7, borda dir I2C6;
* para-choques no P1 (esquerdo) e P8 (direito);
* câmera `/dev/video_usb3`.

A chave `maze` traz os números da equipe para os 3 testes próprios da Maze: inversões dos motores,
velocidades, `CONTAGENS_POR_MM`, `DISTANCIA_SEM_PAREDE`, descontos dos VL53 e as faixas de cor do
`SensorChao.cor()`. Se a equipe mudar a ligação ou um desses números, mude o `robo.json`, senão o
autoteste vai acusar a diferença.

## Como usar

1. Mande a pasta para o robô com o `envia.bat` ou o `envia.sh` (o IP fica no começo do arquivo). Ela
   fica em `~/autoteste_maze` e aparece no menu principal do robô.
2. No menu do robô, escolha **autoteste_maze** e depois **Teste completo** ou um teste só.
3. No fim aparece o resumo. **BAIXO/CIMA** passam pelas falhas e avisos, **ENTER** mostra a dica de
   cada um e **VOLTAR** volta ao menu.

Botões: **CIMA/BAIXO** andam no menu, **ENTER** escolhe ou responde "sim", **VOLTAR** volta, responde
"não" ou pula. LEDs do teclado: branco = testando, verde = tudo certo, laranja = aviso,
vermelho = falha.

**Antes de girar motores** ele pergunta, uma vez por execução, se as **rodas estão no ar**.

Para os testes guiados, tenha à mão:
* um suporte para as rodas;
* uma folha branca com uma faixa preta (sensor de linha);
* uma parede ou caixa a uns 20 cm (VL53);
* um ladrilho com paredes dos dois lados (`paredes`);
* pedaços dos pisos: branco, preto, azul, prata e vermelho (`cores_piso`);
* para o `andar`, o robô no chão, de frente para uma parede a 40-90 cm, com espaço para girar.

## Pelo terminal (SSH): um teste só

Com um ou mais nomes, ele roda só esses testes, mostra o resultado e sai, sem o menu. Com **`?`**
ele mostra a lista dos testes deste robô:

```bash
cd ~/autoteste_maze
python3 main.py ?                      # lista os testes (ou: python3 main.py lista)
python3 main.py giroscopio             # só o giroscópio
python3 main.py i2c motores            # vários, na ordem
python3 main.py vl53_vivo              # valores ao vivo (Enter ou Ctrl+C para sair)
python3 main.py giroscopio --terminal  # as perguntas são respondidas aqui, não no teclado do robô
python3 main.py completo               # o teste completo, sem o menu
python3 main.py --automatico           # tudo sem perguntar (motores parados)
python3 main.py --automatico --motores # ...e gira os motores (rodas no ar!)
```

O `~/meu_venv` já vem ativado quando se entra no robô pelo SSH, então é só chamar o `python3`. O
`executa.sh` faz o mesmo ativando o ambiente antes (`bash executa.sh ?`), para quando ele não estiver
ativo. Um nome errado mostra a lista e sai com código 2.

No bash, o `?` sozinho vira o nome de um arquivo de uma letra, se a pasta tiver um. Se isso
acontecer, use `'?'` ou `lista`.

Sem `--terminal`, as perguntas ("ouviu o bipe?", "ponha no branco") são respondidas no teclado do
robô. Com ele, são respondidas no terminal: Enter = ENTER, `v` = VOLTAR. Se o teclado do robô não
responder, o terminal é usado sozinho.

No `--automatico`, o que precisa de alguém (apertar botão, olhar LED, ouvir o buzzer, pôr no branco)
fica como **PULOU**. Os motores só giram com `--motores`. O programa sai com código 1 se houver falha.

## Relatório

Cada rodada grava `~/autoteste_maze/relatorios/AAAA-MM-DD_HHMMSS.txt`, linha a linha: se o programa travar
no meio, o que já foi testado fica lá. As fotos das câmeras vão para `fotos/`. Para trazer para o PC:

```bash
scp -r banana@192.168.1.202:~/autoteste_maze/relatorios .
```

## O que cada teste confere

| teste | o que confere |
|---|---|
| `sistema` | Temperatura da CPU, memória, disco da `/home`, IP. Se os conversores USB do robô estão no hub interno (`/dev/serial/by-path`, 1.1 a 1.4), `ttyS2/4/5` e `i2c-0/1`. No `dmesg`: resets e desconexões do hub USB (o problema da Maze de 12/11/2026) e erros de I2C. |
| `painel` | Tela e teclado respondem? Botão preso. Pede cada um dos 4 botões, acende os 4 LEDs um por vez, mostra um padrão na tela. |
| `brick` | 200 trocas com o ATmega: tempo médio e máximo, repetidas e perdidas. Calibração dos motores 1 e 2: calibrado, encoder invertido, resultado da última calibração (firmware de 10/11). |
| `leds` | Os 10 LEDs RGB nas 4 cores e um por um. |
| `buzzer` | Nível LOW/HIGH gravado contra o do robô, 2 bipes e um tom. |
| `servos_comuns` | Cada servo comum do brick vai do repouso ao ângulo de teste e volta. |
| `i2c` | Mux 0x70. Acha VL53 e TCS nos 8 canais e compara com o robô: se falta um e sobra outro do mesmo tipo, diz "cabo trocado de porta?". VL53: 30 leituras (média, variação, falhas, nada à frente, algo encostado). TCS: RGBC (zerado, saturado, parado). |
| `giroscopio` | Procura na porta do robô e, se não está lá, nas outras. Leituras por segundo e perdidas. Inclinação parada. Deriva do Z em 20 s parado. Gire 90° à mão e confira o quanto mediu e para que lado o Z vai. |
| `linha` | Pro1616 (comando 0x61; nunca manda os comandos de calibração): 100 leituras. Ponha no branco e no preto e veja se os 4 IR e os 3 TCS mudam. |
| `pinos` | Só leitura. Chave apertada sem ninguém tocar; depois pede para apertar cada uma. |
| `cameras` | Cada câmera: resolução, quadros/s, brilho (lente tampada), contraste (desfocada). Salva uma foto. |
| `placas` | Cada placa de motor do barramento: responde? calibração? Gira com potência ±40 e com velocidade ±50 (PID). O encoder conta nos dois sentidos e para o lado certo? A velocidade é igual nos dois sentidos? |
| `servos` | Cada servo inteligente: responde? posição, polaridade calibrada, potenciômetro no fim da escala. Mexe 60 unidades e volta para onde estava. |
| `motores` | Motores 1 e 2 do brick: potência ±40, velocidade ±50 (PID), `move_motor(360)` com freio HOLD, os dois na mesma velocidade. |
| `estresse` | 20 s com os motores invertendo a 80% sem parar de conversar com o brick e as placas. Conta comunicação perdida e resets do hub USB: acha queda dos 5 V e ruído dos motores. |
| `vl53_vivo`, `tcs_vivo`, `pinos_vivo` | Valores na hora (CIMA/BAIXO trocam de página). Fora do teste completo. |
| `calibra` | Calibração dos motores 1 e 2 (30 s, rodas no ar). Fora do completo. |
| `procura` | Placas de motor e servos (IDs 0 a 255) nos SERIAL1 a 3: acha ID trocado. Fora do completo. |
| `paredes` | **Maze.** Robô no centro de um ladrilho com parede dos dois lados. Cada VL53 lateral, já com o desconto da equipe, tem de ficar abaixo da `distancia_sem_parede` (acima dela, o programa acha que não tem parede). O meio e a borda do mesmo lado têm de bater (±10 mm): é com essa diferença que a equipe anda reto. |
| `cores_piso` | **Maze.** O TCS do chão em cada cor das faixas da equipe (preto, vermelho, azul, prata e branco, na ordem do `SensorChao.cor()`). Mostra o RGBC medido e a cor que as faixas da equipe dariam, e grava média e faixa para ajustar o `sensores.py`. |
| `andar` | **Maze, fora do completo.** No chão, de frente para uma parede a 25-120 cm: anda até 300 mm pelo encoder (para 100 mm antes da parede) e confere pelo VL53 da frente quanto andou de verdade. Isso dá o `CONTAGENS_POR_MM` certo (aviso acima de 5% de diferença). Depois faz 4 giros de 90° à direita com o mesmo controle do `girar_ate_angulo()` e mostra o erro de cada um. |

## Chaves do `robo.json`

| chave | o que é |
|---|---|
| `nome` | aparece na tela e no relatório |
| `brick.motores_encoder` / `motores_sem_encoder` | motores do brick |
| `brick.timer2` | `"buzzer"` ou `"servos"`: o que o robô usa (o Timer2 fica com o primeiro até reiniciar o brick) |
| `brick.buzzer_nivel` | `"LOW"` ou `"HIGH"` (fica na EEPROM) |
| `brick.servos_comuns` | `servo`, `nome`, `repouso`, `teste` (ângulos seguros para a garra) |
| `brick.fita_porta4` | `true` se a porta 4 é uma fita de LEDs |
| `brick.freio` | `"HOLD"` (padrão) ou `"BREAK"`, para o teste do `move_motor` |
| `barramento.porta` | porta das placas de motor e dos servos inteligentes |
| `barramento.placas_motor` / `servos` | `id`, `nome`; servo com `passo` (quanto mexe no teste) |
| `giroscopio` | porta do giroscópio |
| `giroscopio_direita` | `"aumenta"` ou `"diminui"`: o que o programa da equipe espera do Z girando para a direita |
| `sensores_linha` | `porta`, `nome` |
| `vl53`, `tcs` | `porta` (`I2C1` a `I2C8`), `nome` |
| `pinos` | `pino` (`P1` a `P8`), `nome` |
| `pinos_nao_mexer` | pinos que o robô usa como saída: o autoteste não mexe neles |
| `cameras` | caminhos (`/dev/video_usb1`...) |
| `maze` | só no robô da Maze (testes `paredes`, `cores_piso` e `andar`): `brick_invertidos`, `placa_esq`/`placa_dir`, `placas_invertidas`, `velocidade`, `velocidade_giro_min`/`max`, `kp_giro`, `contagens_por_mm`, `distancia_sem_parede`, `vl53_frente`, `paredes` (lado, VL53 do meio e da borda), `descontos` (mm tirados de cada VL53), `tcs_chao` (1 a 3) e `faixas_cor` (`cor`, `r`, `g`, `b` = [mín, máx], na ordem do `SensorChao.cor()`) |

Um teste só aparece se o `robo.json` tiver o que ele testa. Por exemplo, `linha` só aparece com
`sensores_linha`.

## Como foi testado (14/11/2026)

No simulador da Maze, com o `robo_maze2026.json` (pasta `simuladorMaze`):

```powershell
$env:AUTOTESTE_AUTOMATICO='1'; $env:AUTOTESTE_MOTORES='1'
python simulador.py --robo robo_maze2026.json --mapa mapas/treino.json --programa ../autoteste_maze/main.py --sem-janela --semente 1
```

* **Teste completo:** tudo ok menos a câmera, que o simulador não tem. A parte do Linux e o que precisa
  de alguém (botões, LEDs, giro à mão, cores do piso) ficam como PULOU.
* **`andar` (`$env:AUTOTESTE_TESTES='andar'`):** mediu `CONTAGENS_POR_MM` 2,00 contra os 1,82 do
  `constantes.py`. O simulador usa 2 (440 contagens por volta), então a medida bateu. Os 4 giros
  terminaram com 0° de erro.
* **`cores_piso` e `paredes` com uma pessoa respondendo:** testados com sensores e teclado falsos. Um
  vermelho fora da faixa da equipe dá FALHA, com a dica de ajustar o `sensores.py`; meio e borda
  diferentes dão AVISO.

O resto do código é o mesmo do Boberto e do Bombertinho, testado lá.

**Não testado num robô de verdade:**
* nada desta pasta rodou ainda num robô da Maze;
* o Linux do brick (temperatura, USB, `dmesg`);
* a tela e o teclado reais;
* a câmera de verdade;
* o `--terminal` e o "ao vivo" pelo SSH.

O simulador não passa parâmetros ao programa. Por isso as variáveis `AUTOTESTE_AUTOMATICO`,
`AUTOTESTE_MOTORES` e `AUTOTESTE_TESTES` (nomes separados por espaço ou vírgula) fazem o mesmo, e
valem também no robô.

## Para quem mexer

* **O código é o mesmo nos três projetos** (`autoteste_boberto/`, `autoteste_maze/` e `autoteste_maze/`): só o
  `robo.json` e este LEIAME mudam. Mudou um `.py`? Copie para os outros dois.
* `libs/` é uma cópia das `libs/` do repositório, sem mudança, para a pasta funcionar sozinha no robô.
  Mudou uma lib lá? Copie para cá.
* `main.py` tem a lista `TODOS` (chave, nome no menu, função, se entra no completo, quando o robô
  tem, descrição do `?`). A interface fica em `interface.py`, o relatório em `relatorio.py` e o que os
  testes dividem em `contexto.py`. Os testes estão em `testes/`.
* Cada teste recebe o contexto e escreve com `ctx.rel.ok/aviso/falha/info/pulou(texto, dica)`. A dica
  é o que conferir: é o que aparece com ENTER na tela de resumo.
