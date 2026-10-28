#!/bin/bash
# Grava o firmware do Mariola (ATmega328PB, placaBrickVendra) pelo bootloader, com o avrdude.
# Roda no próprio brick:  bash grava_mariola.sh [arquivo.hex]      (-n = só confere, não grava)
# O RESET do Mariola é apertado À MÃO, na hora do ENTER (a placa não reinicia sozinha pela serial).
# Explicação completa: LEIAME.md (nesta pasta).

cd "$(dirname "$0")" || exit 1
SO_CONFERE=0
if [ "${1:-}" = "-n" ]; then SO_CONFERE=1; shift; fi
HEX="${1:-placaBrickVendra.ino.eightanaloginputs_328pb.hex}"

if [ ! -f "$HEX" ]; then
    echo "Não achei o arquivo $HEX nesta pasta."
    exit 1
fi
if ! command -v avrdude > /dev/null; then
    echo "O avrdude não está instalado (sudo apt install avrdude)."
    exit 1
fi

# Porta do Mariola: o conversor USB-serial na porta 1.1 do hub interno (a mesma regra da lib
# portas.py). O número (/dev/ttyUSB0, 1...) pode mudar de um boot para o outro; o caminho não.
LINK=$(ls /dev/serial/by-path/*usb-0:1.1:1.0-port0 2> /dev/null | head -1)
if [ -z "$LINK" ]; then
    echo "Não achei o Mariola em /dev/serial/by-path/ (porta 1.1 do hub USB)."
    exit 1
fi
PORTA=$(readlink -f "$LINK")
echo "Mariola na porta $PORTA"
echo "Firmware: $HEX (md5 $(md5sum < "$HEX" | cut -c1-8): confira com o LEIAME.md)"

# A porta precisa estar livre: um programa do robô aberto (pelo menu ou pelo terminal) segura a serial.
EM_USO=""
for p in /proc/[0-9]*; do
    if ls -l "$p/fd" 2> /dev/null | grep -q -- "-> $PORTA\$"; then
        EM_USO="$EM_USO  PID ${p#/proc/}: $(tr '\0' ' ' < "$p/cmdline")"$'\n'
    fi
done
if [ -n "$EM_USO" ]; then
    echo
    echo "A porta do Mariola está em uso por:"
    printf '%s' "$EM_USO"
    echo "Pare esse programa (pelo menu ou com kill PID) e rode este script de novo."
    exit 1
fi

if [ "$SO_CONFERE" = 1 ]; then
    echo "Tudo certo para gravar (rodado com -n: não gravou nada)."
    exit 0
fi

while true; do
    echo
    echo "Na hora de apertar ENTER, aperte e solte o botão RESET do Mariola."
    echo "(Jeito mais fácil: segure o RESET apertado, aperte ENTER aqui e solte o RESET.)"
    read -r -p "Pronto? Aperte ENTER... "
    if avrdude -F -patmega328pb -carduino -P "$PORTA" -b 115200 -D -Uflash:w:"$HEX":i; then
        echo
        echo "Firmware gravado. O Mariola já reiniciou com ele."
        echo "A calibração dos motores e o nível do buzzer (EEPROM) continuam os mesmos."
        exit 0
    fi
    echo
    echo "Não gravou. O mais comum é o RESET fora de hora (\"not in sync\"): tente de novo."
    read -r -p "Tentar de novo? [S/n] " R
    case "$R" in
        n|N) exit 1 ;;
    esac
done
