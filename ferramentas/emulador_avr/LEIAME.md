# emulador_avr: os firmwares dos motores rodando no PC

Os simuladores do repositório imitam o protocolo das placas em Python: não rodam o firmware. Para
testar o firmware de verdade (trancos dos motores, freio travado, timeout, calibração) sem gravar
numa placa, este emulador roda o `.hex` compilado, instrução por instrução:

* **ATmega328PB** (`placaBrickVendra`, o brick) e **ATtiny1616** (`placaControleMotor`, a placa
  de motor externa);
* periféricos: só os que os dois firmwares usam, seguindo o datasheet. No 328PB: Timer0/1/2 com
  PWM e o OCR com buffer, serial, EEPROM, INT0/INT1. No 1616: TCA0 dividido, TCD0 (o `millis()`
  do megaTinyCore), serial de um fio com eco, interrupção de pino, watchdog e causa do reset;
* nos pinos: ponte H + motor DC com redução + encoder em quadratura, com os números do
  `simuladorLine/robo_4x4.json` (130 rpm, 17 pulsos, redução 34, tau 0,06 s).

É um modelo: prova a lógica do firmware e a diferença entre duas versões. A parte elétrica (por
exemplo, a ponte L9110 frear igual com os dois pinos em HIGH ou em LOW) só o robô mostra.

## Uso

```bash
python compila.py            # compila antigo e novo dos dois firmwares em builds/
python testa_brick.py        # trancos no brick: antigo x novo
python testa_placa.py        # reinícios e freio na placa externa: antigo x novo
python testa_polaridade.py   # motor/encoder trocados e falhas na calibração (firmware novo)
python grafico.py            # builds/motores_antes_depois.png
```

* "novo" é o que está agora nas pastas `Documents/Arduino/placaBrickVendra` e `placaControleMotor`;
  "antigo" é um commit do git de cada uma (padrão: o estado de antes das correções de 10/11/2026;
  `--antigo-brick`, `--antigo-placa` trocam). Mexeu num `.ino`? `python compila.py --so-novo` e
  rode os testes de novo.
* `python testa_brick.py parada hold_programa_novo` roda só esses cenários.
* `python testa_polaridade.py antigo` mostra o firmware antigo disparando com a polaridade trocada.
* Precisa de: Python com numpy (matplotlib só para o gráfico), `arduino-cli` (`C:\Arduino` ou a
  variável `ARDUINO_CLI`) com os cores `arduino:avr` e `megaTinyCore`, e um g++ para compilar o
  emulador na primeira vez (procura em `EMU_GXX`, no pacote portátil `simuladorLine/portatil/gcc`
  e no PATH; o TDM-GCC 4.9 do Dev-C++ gera uma DLL que o Python não carrega).
* Tudo o que é gerado fica em `builds/` (fora do git).

## Arquivos

| arquivo | o que é |
|---|---|
| `avremu.cpp` | o emulador: núcleo AVR (AVRe+ e AVRxt), periféricos, física do motor |
| `emu.py` | liga o Python ao emulador; `Emu` (tempo, serial, traço, EEPROM, mão no eixo, ligação trocada) e `Mariola` (manda os comandos como a `libs/motores.py`) |
| `placa.py` | `Placa`: a placa de motor externa e o protocolo de 6 bytes |
| `compila.py` | compila os firmwares com o `arduino-cli` |
| `testa_*.py`, `grafico.py` | os cenários |

## Como escrever um cenário

```python
from emu import *
e = Mariola(*firmware('brick', 'novo'), eeprom=open('builds/eeprom_brick.bin', 'rb').read())
e.roda(0.4)                              # setup() do firmware
e.anda(1.0, 40, 40, freio=HOLD)          # um programa mandando velocidade 40 a cada 20 ms
e.mao(0, 578); e.roda(0.5); e.mao(0, None)   # gira o eixo do motor 1 com a mão
tr = e.traco()                           # t, tensão nas 4 pontes, posição e velocidade dos 2 eixos
```

* O traço sai a cada 256 µs; `e.passos_traco(1)` grava a cada 16 µs (para ver pulsos do PWM).
* `e.ligacao(0, encoder_trocado=True)` troca a polaridade; `falha=1/2/4` solta o canal A, o canal B
  ou o motor.
* `e.le('contadorHold1')` lê uma variável global do firmware (pelo `.elf`).

## O que foi difícil de acertar

* **OCR com buffer:** em Fast PWM o `OCRnx` novo só vale no começo do ciclo seguinte, e o pino de
  direção muda na hora. É a origem dos trancos de partida e parada do firmware antigo.
* **Flip-flop do OCnx:** guarda o último estado mesmo com o timer parado; ao religar o PWM o pino
  sai nesse estado até a primeira comparação (o tranco do primeiro comando depois do timeout).
* **`micros()` do megaTinyCore:** o TCD0 guarda a contagem no comando `SCAPTUREA`, não na leitura.
  Lendo na hora, o `micros()` anda para trás perto do estouro e o `delay()` encurta.
* **AVRxt:** as flags de interrupção não se limpam sozinhas e o `RETI` não mexe no bit I.
* O timer de 16 bits do 328PB é tratado como de 8 (o firmware usa Fast PWM de 8 bits) e o PWM de
  fase correta como rápido (só aparece antes do `setup()`).
