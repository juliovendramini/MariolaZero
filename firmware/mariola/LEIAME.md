# Atualizar o firmware do Mariola

O Mariola (a placa com o ATmega328PB dentro do brick: motores, encoders, LEDs, servos, ventoinha,
buzzer) tem um firmware próprio, o `placaBrickVendra`. Quando ele muda (comando novo, correção),
cada brick precisa ser regravado. Esta pasta tem tudo para isso:

| arquivo | o que é |
|---|---|
| `placaBrickVendra.ino.eightanaloginputs_328pb.hex` | o firmware compilado (versão abaixo) |
| `grava_mariola.sh` | grava o firmware; roda **no brick** |
| `grava_mariola.bat` | no Windows: copia esta pasta para o brick e roda o `grava_mariola.sh` lá |

**Versão do `.hex` desta pasta:** firmware de 26/10/2026 (buzzer no pino 11 e a regra nova do
Timer2; veja `documentação/Motores.md`). MD5 começando com `eb34acab` (o script mostra).

A gravação usa o **bootloader** do ATmega pela própria serial USB do Mariola: não precisa de
gravador, nem de abrir o brick. O que fica na EEPROM (calibração dos motores, nível do buzzer)
**não é apagado**.

## O RESET é na mão

A placa não reinicia sozinha pela serial. Para o bootloader receber o firmware, o ATmega precisa
ter acabado de reiniciar quando o `avrdude` começa a falar com ele. Por isso o script para e pede um
ENTER: **na hora do ENTER, aperte e solte o botão RESET** do brick (o botão RESET do painel, veja
`documentação/Conectores.md`).

O jeito mais fácil de acertar o tempo: **segure o RESET apertado, aperte ENTER e solte o RESET**.
O bootloader espera cerca de 1 segundo depois do reset; se passar disso, o `avrdude` dá
`not in sync` e o script pergunta se quer tentar de novo.

## Do Windows (o jeito normal)

1. Brick ligado e na mesma rede do PC.
2. Feche os programas do robô (o menu pode ficar aberto; um programa rodando segura a serial do
   Mariola e o script avisa qual é).
3. Dê dois cliques em **`grava_mariola.bat`** e confirme o IP do brick (ENTER aceita o que aparece).
4. Ele copia esta pasta para `~/firmware_mariola` no brick e abre o script. Quando aparecer
   `Pronto? Aperte ENTER...`: segure o RESET, aperte ENTER, solte o RESET.
5. O `avrdude` mostra o progresso (`Writing`, `Reading`) e termina com `Firmware gravado`. O
   Mariola já reinicia com o firmware novo.

Se pedir senha, é a do usuário `banana` do brick (o mesmo login do SSH).

## Direto no brick (sem o .bat)

Copie esta pasta para o brick (Samba, `scp`, pendrive) e, num terminal do brick:

```bash
cd ~/firmware_mariola
bash grava_mariola.sh            # grava (pede o ENTER + RESET)
bash grava_mariola.sh -n         # só confere: acha a porta e vê se ela está livre, não grava
bash grava_mariola.sh outro.hex  # grava outro arquivo .hex desta pasta
```

O script acha a porta do Mariola sozinho (o conversor USB da porta 1.1 do hub interno, a mesma
regra da lib `portas.py`; costuma ser o `/dev/ttyUSB0`, mas o número pode mudar). O comando que ele
roda é:

```bash
avrdude -F -patmega328pb -carduino -P /dev/ttyUSB0 -b 115200 -D -Uflash:w:placaBrickVendra.ino.eightanaloginputs_328pb.hex:i
```

## Problemas

| mensagem | o que fazer |
|---|---|
| `not in sync`, `programmer is not responding` | o RESET foi fora de hora: tente de novo (segure o RESET, ENTER, solte) |
| `A porta do Mariola está em uso por: PID ...` | feche esse programa (pelo menu ou `kill PID`) e rode de novo |
| `Não achei o Mariola em /dev/serial/by-path/` | o conversor USB do Mariola não apareceu: desligue e ligue o brick |
| `O avrdude não está instalado` | `sudo apt install avrdude` (a raiz do brick é somente leitura: libere a escrita antes, veja o `INSTALACAO.md`) |
| depois de gravar, os programas dão erro de comunicação | firmware e lib `motores.py` fora de sincronia: use a lib do mesmo período do firmware (`libs/motores.py`) |

## Para quem atualiza esta pasta (quando o firmware mudar)

1. Na pasta do firmware (`Documents\Arduino\placaBrickVendra`), gere o `.hex` na IDE do Arduino
   (**Sketch > Exportar binário compilado**). Use o arquivo **sem** `with_bootloader` no nome: o
   bootloader já está na placa e o `-D` do `avrdude` não apaga a flash inteira.
2. Copie o `.hex` para cá com o mesmo nome (ou mude o nome padrão no `grava_mariola.sh` e no
   `grava_mariola.bat`).
3. Atualize a versão e o começo do MD5 aqui em cima (no PowerShell:
   `(Get-FileHash arquivo.hex -Algorithm MD5).Hash`).
4. Se o firmware ganhou comando novo, a `libs/motores.py`, a `documentação/Motores.md` e a emulação
   dos simuladores (`sim/firmware.py`) têm de acompanhar.
