#!/bin/bash
#
# Instala o servico de controle do cooler PWM no BPI-M4-Zero (H618).
#
# Uso:   sudo ./instalar-fancontrol.sh
#
# Requisitos:
#   - overlay 'pwm1-pi11' ativo no /boot/armbianEnv.txt
#   - fancontrol.py no mesmo diretorio deste script
#
set -euo pipefail

ORIGEM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_ORIGEM="$ORIGEM/fancontrol.py"
SCRIPT_DESTINO="/usr/local/bin/fancontrol.py"
UNIT_DESTINO="/etc/systemd/system/fancontrol.service"
ARMBIAN_ENV="/boot/armbianEnv.txt"

msg()  { echo -e "\n\033[1;36m==>\033[0m $*"; }
erro() { echo -e "\033[1;31mERRO:\033[0m $*" >&2; exit 1; }
aviso(){ echo -e "\033[1;33maviso:\033[0m $*"; }

# --- Verificacoes ---------------------------------------------------------

[[ $EUID -eq 0 ]] || erro "rode como root (sudo)."
[[ -f "$SCRIPT_ORIGEM" ]] || erro "fancontrol.py nao encontrado em $ORIGEM"

msg "Verificando o overlay do PWM1"
if [[ -e /sys/class/pwm/pwmchip0 ]]; then
    echo "  pwmchip0 presente."
else
    erro "pwmchip0 nao existe. Acrescente 'pwm1-pi11' na linha overlays= de $ARMBIAN_ENV e reinicie."
fi

if [[ -f "$ARMBIAN_ENV" ]] && ! grep -q "pwm1-pi11" "$ARMBIAN_ENV"; then
    aviso "'pwm1-pi11' nao aparece em $ARMBIAN_ENV. O PWM pode sumir no proximo boot."
fi

msg "Verificando a zona termica da CPU"
ZONA=""
for z in /sys/class/thermal/thermal_zone*; do
    if [[ "$(cat "$z/type" 2>/dev/null)" == "cpu-thermal" ]]; then
        ZONA="$z"
        break
    fi
done
[[ -n "$ZONA" ]] || erro "zona 'cpu-thermal' nao encontrada."
echo "  encontrada em $ZONA ($(($(cat "$ZONA/temp") / 1000)) graus agora)."

# --- Raiz gravavel --------------------------------------------------------

REMONTADO=0
if ! touch /usr/local/bin/.escrita-teste 2>/dev/null; then
    msg "Raiz esta somente leitura, remontando como gravavel"
    mount -o remount,rw / || erro "nao foi possivel remontar a raiz."
    REMONTADO=1
else
    rm -f /usr/local/bin/.escrita-teste
fi

# --- Instalacao -----------------------------------------------------------

msg "Instalando o script em $SCRIPT_DESTINO"
install -m 0755 "$SCRIPT_ORIGEM" "$SCRIPT_DESTINO"

msg "Criando a unit do systemd"
cat > "$UNIT_DESTINO" << 'UNIT'
[Unit]
Description=Controle de cooler PWM por temperatura do SoC
After=multi-user.target

[Service]
Type=simple
ExecStart=/usr/local/bin/fancontrol.py
Restart=always
RestartSec=5
Nice=-5

[Install]
WantedBy=multi-user.target
UNIT

msg "Habilitando e iniciando o servico"
systemctl daemon-reload
systemctl enable fancontrol.service >/dev/null
systemctl restart fancontrol.service

sleep 4

# --- Verificacao final ----------------------------------------------------

msg "Resultado"

if systemctl is-active --quiet fancontrol.service; then
    echo "  servico:     ativo"
else
    aviso "servico nao esta ativo. Veja: journalctl -u fancontrol -n 30"
fi

if [[ -e /sys/class/pwm/pwmchip0/pwm1/duty_cycle ]]; then
    DUTY=$(cat /sys/class/pwm/pwmchip0/pwm1/duty_cycle)
    PERIODO=$(cat /sys/class/pwm/pwmchip0/pwm1/period)
    echo "  temperatura: $(($(cat "$ZONA/temp") / 1000)) graus"
    echo "  duty:        $DUTY / $PERIODO ns"
else
    aviso "canal pwm1 nao foi exportado."
fi

echo "  trip 0:      $(($(cat "$ZONA/trip_point_0_temp") / 1000)) graus"
echo "  trip 1:      $(($(cat "$ZONA/trip_point_1_temp") / 1000)) graus"

# --- Restaura o modo somente leitura --------------------------------------

if [[ $REMONTADO -eq 1 ]]; then
    msg "Reinicie para a raiz voltar a somente leitura"
    echo "  (a raiz esta gravavel neste momento)"
fi

msg "Pronto"
echo "  acompanhar:  watch -n1 'cat $ZONA/temp; cat /sys/class/pwm/pwmchip0/pwm1/duty_cycle'"
echo "  logs:        journalctl -u fancontrol -f"
