# pacoca/: brick Paçoca no simulador (por dentro)

O uso está no README do simulador (seção "Brick Paçoca"). Aqui fica como funciona, para quem for
mexer no simulador.

## Peças

| arquivo | o que faz |
|---|---|
| `compila.py` | monta o build em `<pasta do programa>/.sim_build/` e chama o g++ |
| `nucleo/Arduino.h` e companhia | Arduino simulado: tipos, macros, registradores (memória comum), `millis()`, pinos, `Serial`, `String`, `EEPROM`, `avr/*.h`, `util/*.h` |
| `nucleo/sim_core.cpp` | relógio virtual, pinos, `Serial`, EEPROM em arquivo, `random()` igual ao da avr-libc, `main()` |
| `nucleo/sim_rede.cpp` | socket com a ponte (sem `Arduino.h`, por causa dos cabeçalhos do Windows) |
| `nucleo/sim_softserial.cpp`, `nucleo/sim_softwire.cpp` | implementação da `SoftwareSerial` e da `SoftWire` simuladas |
| `troca/*.h` | substituem os da brickSimples: `SoftwareSerial`, `SoftWire`, `Servo`, `ultrassonico`, `voz`, `musica`, `motorAudio`, `Bluetooth`, `interrupcoes` |
| `libs_pacoca/` | cópia da brickSimples (reserva para quem só tem o `.ino`) |
| `ponte.py` | processo Python entre o programa e o simulador; emula Pro1616, BMI160, VL53/TCS (os modelos de `fake_hw/dispositivos.py`), ultrassom e a ponte H |
| `../rodar_pacoca.py` | o que o simulador executa para um `.ino`: compila, sobe a ponte, reinicia no `jmp 0` |

## Build

1. Arquivos: `libs_pacoca/` < pasta do programa < `troca/` (o último ganha; `SoftWire.cpp`,
   `SoftwareSerial.cpp` e `Servo.cpp` da lib saem).
2. Cada arquivo passa por `tira_asm()` (o `asm(...)` vira `((void)0)`, o `jmp 0` vira
   `sim_reset()`, as linhas continuam no mesmo lugar) e o `led.h` ganha o gancho que manda as
   cores para o simulador.
3. Os `.ino` viram `_programa.ino.cpp`: `#include <Arduino.h>`, protótipos das funções antes da
   primeira função e `#line` para os erros apontarem para o `.ino`.
4. `g++ -std=gnu++17 -O1 -fsigned-char`, um `.o` por arquivo com hash no nome (só recompila o que
   mudou); o núcleo fica em cache em `pacoca/.cache/`. No Windows liga com `-static -lws2_32`.

## Relógio

O programa tem o relógio dele (`sim_t_ns`). Cada função do Arduino soma o custo dela no ATmega.
Toda conversa com a ponte leva o tempo atual; a ponte só leva a física até esse tempo
(`avanca` no simulador) quando precisa do mundo (sensor, motor, botão) ou a cada 10 ms de programa.
Registradores que só dependem do relógio (VL53 "medida pronta", BMI160 PMU/STATUS) respondem sem
mexer na física: é isso que deixa rápidos os laços de espera do VL53.

`millis()`/`micros()` imitam o Timer0: com as interrupções desligadas por mais de 1,024 ms os
estouros a mais se perdem (`perdido_ns`) e o `millis()` atrasa.

Se o programa fica 1 s real sem falar com a ponte (laço infinito sem chamar o Arduino), a ponte
deixa a física andar pelo relógio real, como o `RelogioSinc` do Python.

## Protocolo programa ↔ ponte

Pedido: `u32 tamanho | u8 op | i64 t_ns | dados`. Resposta: `u32 tamanho | u8 flags | dados`
(flags bit 0 = o simulador mandou parar). Uma segunda conexão ("vida") só serve para o programa
morrer quando a ponte morre. Operações em `nucleo/sim_ponte.h` (`OP_*`) e `ponte.py` (`trata`).

| op | dados | resposta |
|---|---|---|
| OLA | — | pinos de entrada, analógicos, de saída (motores), ECHO dos ultrassons, bateria (mV) |
| SYNC | — | — (leva a física até t) |
| SERIAL_TX | rx, tx, baud, t do start bit, byte | bytes que voltam: `(t_ns, byte)` cada um |
| I2C_ESCREVE | sda, scl, endereço, n, bytes | 0 = ok, 2 = NACK |
| I2C_LE | sda, scl, endereço, n | status, n, bytes |
| PINO_SAIDA | pino, 0..255 | — (pinos dos motores viram `motor_dc` no simulador) |
| PINO_ENTRADA / ANALOGICO | pino | nível / 0..1023 |
| ULTRASSOM | trig, echo | distância em mm (-1 = sem eco) |
| LEDS | pino, n, rgb… | — |

A `SoftwareSerial` simulada guarda os bytes que voltam como forma de onda da linha RX e lê como o
código do brick: `available()` = linha em LOW agora; `read()` espera a próxima borda de descida e
amostra 2 µs + 1 bit depois de cada bit. Byte que chega com ninguém lendo se perde.

## Para pôr um dispositivo novo

1. Classe em `ponte.py` com `addr`, `escreve(lista)` e `le(n)` (I2C) ou `BAUD` e
   `recebe(byte, t) -> [(t_inicio, bytes)]` (serial).
2. Um `tipo` novo em `Ponte._monta_portas`.
3. Se precisar de uma grandeza do mundo, uma operação nova em `sim/servidor.py`.
