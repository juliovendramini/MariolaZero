# Autoteste do Bombertinho (Challenge)

Programa que testa as peças do robô, uma por uma, para **achar problemas**. Ele mostra na tela o que
está testando e os valores, usa os botões do teclado para andar no menu e responder, e grava tudo num
relatório.

Cada robô tem um projeto próprio (`autoteste_boberto/`, `autoteste_challenge/` e `autoteste_maze/`) com o mesmo código:
o que muda é o `robo.json`, que diz o que o robô tem e onde está ligado, e por isso quais testes
aparecem.

## O que este robô tem (`robo.json`)

Tirado do código da equipe (`defs.py` e `movimentos.py` da equipe, commit `9b1c3f2`):

* brick: motores 1 e 2 com encoder (traseiros), 10 LEDs RGB, **servos comuns** 1 (mão lateral), 2 (tronco lateral), 3 (tronco frontal), 4 (mão frontal). Com os servos no Timer2, o buzzer não funciona neste robô e não é testado;
* barramento no **SERIAL2**: placas de motor 8 (frente esq) e 51 (frente dir);
* giroscópio no **SERIAL5**;
* sensores de linha frontal no **SERIAL1** e lateral no **SERIAL3**;
* 4 VL53: frente I2C4, lateral esq I2C2, lateral dir I2C5, trás I2C7;
* 3 TCS: frente I2C3, garra lateral I2C6, garra frontal I2C8;
* sem câmera, sem para-choques e sem servos inteligentes.

Sem câmera, para-choques, servos inteligentes nem buzzer, os testes `cameras`, `pinos`, `servos` e `buzzer` não aparecem. Se a equipe trocar um sensor de porta, mude o `robo.json`, senão o autoteste vai acusar a
troca.

## Como usar

1. Mande a pasta para o robô com o `envia.bat` ou o `envia.sh` (o IP fica no começo do arquivo). Ela
   fica em `~/autoteste_challenge` e aparece no menu principal do robô.
2. No menu do robô, escolha **autoteste_challenge** e depois **Teste completo** ou um teste só.
3. No fim aparece o resumo. **BAIXO/CIMA** passam pelas falhas e avisos, **ENTER** mostra a dica de
   cada um e **VOLTAR** volta ao menu.

Botões: **CIMA/BAIXO** andam no menu, **ENTER** escolhe ou responde "sim", **VOLTAR** volta, responde
"não" ou pula. LEDs do teclado: branco = testando, verde = tudo certo, laranja = aviso,
vermelho = falha.

**Antes de girar motores** ele pergunta, uma vez por execução, se as **rodas estão no ar**.

Para os testes guiados, tenha à mão:
* um suporte para as rodas;
* uma folha branca com uma faixa preta (sensor de linha);
* uma parede ou caixa a uns 20 cm (VL53).

## Pelo terminal (SSH): um teste só

Com um ou mais nomes, ele roda só esses testes, mostra o resultado e sai, sem o menu. Com **`?`**
ele mostra a lista dos testes deste robô:

```bash
cd ~/autoteste_challenge
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

Cada rodada grava `~/autoteste_challenge/relatorios/AAAA-MM-DD_HHMMSS.txt`, linha a linha: se o programa travar
no meio, o que já foi testado fica lá. As fotos das câmeras vão para `fotos/`. Para trazer para o PC:

```bash
scp -r banana@192.168.2.167:~/autoteste_challenge/relatorios .
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

Um teste só aparece se o `robo.json` tiver o que ele testa. Por exemplo, `linha` só aparece com
`sensores_linha`.

## Como foi testado (14/11/2026)

No simulador da Challenge, com o `robo_bombertinho.json` (pasta `simuladorChallenge`):

```powershell
$env:AUTOTESTE_AUTOMATICO='1'; $env:AUTOTESTE_MOTORES='1'
python simulador.py --robo robo_bombertinho.json --cenario cenarios/exemplo.json --programa ../autoteste_challenge/main.py --sem-janela --tempo 400
```

Resultado em 14/11/2026: 23 ok, 5 avisos, 0 falhas. Os avisos são do simulador: VL53 sem nada na frente e TCS sem luz ambiente.

Também foi testado num Bombertinho com defeitos de propósito. O autoteste achou os 5 e deu a dica certa:
* VL53 trocado de porta: "tem um VL53 sobrando no I2C1: cabo trocado de porta?";
* TCS faltando;
* giroscópio em outra porta: "achei algo que responde como giroscópio em: SERIAL4";
* sensor de linha faltando;
* placa de motor com ID trocado: "responde uma placa de motor com ID 52: ID trocado?".

A interface (menu, perguntas, botão preso, os 4 botões, lista de problemas) foi testada com um teclado
falso.

**Não testado num robô de verdade:**
* o Linux do brick (temperatura, USB, `dmesg`);
* a tela e o teclado reais;
* as câmeras e os servos inteligentes de verdade;
* o `--terminal` e o "ao vivo" pelo SSH (o Enter sem travar só funciona no Linux).

O simulador não passa parâmetros ao programa. Por isso as variáveis `AUTOTESTE_AUTOMATICO`,
`AUTOTESTE_MOTORES` e `AUTOTESTE_TESTES` (nomes separados por espaço ou vírgula) fazem o mesmo, e
valem também no robô.

## Para quem mexer

* **O código é o mesmo nos três projetos** (`autoteste_boberto/`, `autoteste_challenge/` e `autoteste_maze/`): só o
  `robo.json` e este LEIAME mudam. Mudou um `.py`? Copie para os outros dois.
* `libs/` é uma cópia das `libs/` do repositório, sem mudança, para a pasta funcionar sozinha no robô.
  Mudou uma lib lá? Copie para cá.
* `main.py` tem a lista `TODOS` (chave, nome no menu, função, se entra no completo, quando o robô
  tem, descrição do `?`). A interface fica em `interface.py`, o relatório em `relatorio.py` e o que os
  testes dividem em `contexto.py`. Os testes estão em `testes/`.
* Cada teste recebe o contexto e escreve com `ctx.rel.ok/aviso/falha/info/pulou(texto, dica)`. A dica
  é o que conferir: é o que aparece com ENTER na tela de resumo.
