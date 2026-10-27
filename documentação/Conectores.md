# Conectores do MariolaZero

Mapa e pinagem de todos os conectores da placa do Mariola. A versão com as fotos de cada conector
está em [`Conectores.pdf`](Conectores.pdf) (fonte editável: `Conectores.odp`).

![Mapa dos conectores](../curso/imagens/conectores.jpg)

## Tabela

| Conector | Quantos | Pinos | Para quê |
|---|---|---|---|
| **MOTOR 1, MOTOR 2** | 2 | PWM1, PWM2, GND, 5V, ENCODER_DIR, ENCODER_CLK | motores **com encoder** |
| **MOTOR 3, MOTOR 4** | 2 | 2 fios | motores **sem encoder** |
| **SERVOS 1–4** | 4 colunas | SINAL, 5V, GND | servos comuns. A coluna 4 também pode ser uma 2ª fita de LEDs (`set_led_rgb_*_porta4`) |
| **LEDs** | 1 coluna | SINAL, 5V, GND | fita dos 10 LEDs RGB WS2812B do Mariola (`set_led_rgb_all/one`) |
| **DEBUG/PWM** | 1 coluna | SINAL, 5V, GND | pino 11 do ATmega: TX do serial de debug do firmware (115200 bps) **ou** PWM da ventoinha (`set_ventoinha`) **ou** buzzer (`toca_som`) |
| **SERIAIS 1, 2, 3** | 3 | TX, RX, GND, 5V | placas e sensores seriais (conversores USB dentro do brick) |
| **SERIAIS 4, 5, 6** | 3 | TX, RX, GND, 5V | placas e sensores seriais (UART do Banana Pi) |
| **I2C1 … I2C8** | 8 | SDA, SCL, GND, 5V | sensores I2C, um por conector (multiplexador TCA9548A) |
| **PINOS DIGITAIS 1–8** | 8 | GND, PINO | entrada ou saída, aceitam 5 V, com proteção |
| **TELA**, **TECLADO** | 2 | SDA, SCL, GND, 3,3V | só a tela e o teclado: **sem proteção** |
| **USB** | 1 | GND, DP, DM, 5V | câmera, pendrive, adaptador Wi-Fi |
| **REDE** | 1 | RXN, RXP, TXN, TXP | Ethernet cabeada do Banana Pi. O conector está **virado 180°** em relação ao USB |
| **AUDIO** | 1 | GND, L_OUT, L_IN, 5V | saída e entrada de áudio do Banana Pi |
| **VOLTÍMETRO** | 1 | GND, VBAT+ | mede a bateria |
| **RESET**, **BOTÃO 1** | 2 botões | | |

## O header amarelo (servos, LEDs e DEBUG/PWM)

Seis colunas de três pinos. Em cada coluna, de cima para baixo: **SINAL, 5V, GND**. Da esquerda
para a direita:

| Coluna | Pino no firmware (Arduino) | Uso |
|---|---|---|
| SERVO 1 | 14 | servo |
| SERVO 2 | 15 | servo |
| SERVO 3 | 16 | servo |
| SERVO 4 | 17 | servo **ou** 2ª fita de LEDs (o último comando decide) |
| LEDs | 12 | fita de 10 LEDs RGB |
| DEBUG/PWM | 11 (PB3) | TX do debug do ATmega **ou** PWM da ventoinha **ou** buzzer |

* Servos comuns, ventoinha e buzzer usam o mesmo timer do ATmega: o primeiro que for usado fica com
  ele até o brick reiniciar e os outros dois param de funcionar. Depois do primeiro `set_ventoinha`
  ou do primeiro som do buzzer, a coluna DEBUG/PWM deixa de ser o debug. Detalhes em
  [Motores](Motores.md).
* O buzzer padrão liga com o pino em **LOW** (dá para trocar para HIGH; fica salvo na EEPROM).
* Este DEBUG é o do **ATmega**. O terminal serial do **Banana Pi** (Linux) é outra porta, de 3 pinos,
  na lateral do brick ao lado da mini HDMI (GND no pino mais externo, 115200 bps).

## Lateral do brick

| Porta | Para quê |
|---|---|
| **DEBUG** (3 pinos, no canto) | terminal serial do Banana Pi; o pino mais externo é o GND |
| **mini HDMI** | monitor |
| furinho quadrado | LEDs verde e vermelho do Banana Pi M4 Zero |
| **USB-C** (2) | dados e alimentação do Banana Pi |

## Cuidados

* Não use os conectores TELA/TECLADO para outros fins: eles não têm proteção.
