#!/bin/bash
# Grava na eMMC a imagem guardada na p3 do cartao de reserva (backupMariolaZero*.img).
# O brick tem de ter dado boot PELO CARTAO. Fica na raiz do cartao: /instalacao_emmc.sh
# (na raiz, e nao na /home, porque a /home costuma vir da eMMC e precisa ser desmontada; pelo mesmo
# motivo o terminal que chama o script tem de estar fora da /home: rode "cd /" antes)
#
# Uso:  cd /
#       sudo bash /instalacao_emmc.sh              (pergunta antes de apagar a eMMC)
#       sudo bash /instalacao_emmc.sh -y           (sem perguntar)
#       sudo bash /instalacao_emmc.sh --verifica   (depois compara a eMMC com a imagem; dobra o tempo)
#       sudo bash /instalacao_emmc.sh --mac ac:12:34:56:78:bd   (MAC do Wi-Fi escolhido, em vez de sorteado)
#       sudo bash /instalacao_emmc.sh --mesmo-mac  (mantem o MAC do Wi-Fi da imagem)
#
# Depois de gravar, troca o MAC do Wi-Fi (wlan0) no netplan da eMMC: a imagem fixa um MAC
# ("macaddress:" no /etc/netplan/armbian.yaml), e bricks com o mesmo MAC brigam pelo mesmo IP na rede.
# O novo mantem o primeiro e o ultimo grupo e sorteia os 4 do meio.
set -u

EMMC=/dev/mmcblk2
SD=/dev/mmcblk0
P3=${SD}p3
PASTA=/mnt
NETPLAN=etc/netplan/armbian.yaml     # dentro da raiz da eMMC

msg()  { echo -e "\n\033[1;36m==>\033[0m $*"; }
erro() { echo -e "\033[1;31mERRO:\033[0m $*" >&2; exit 1; }
FORMATO_MAC='^([0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}$'

SIM=0; VERIFICA=0; MAC=sorteia
while (( $# )); do
    case $1 in
        -y) SIM=1 ;;
        --verifica) VERIFICA=1 ;;
        --mesmo-mac) MAC=mantem ;;
        --mac) shift; MAC=${1:-}
               [[ $MAC =~ $FORMATO_MAC ]] || erro "--mac precisa de um MAC no formato ac:12:34:56:78:bd" ;;
        *) erro "opcao desconhecida: $1" ;;
    esac
    shift
done

[[ $EUID -eq 0 ]] || erro "rode com sudo: sudo bash $0"

# --- 1. discos certos ----------------------------------------------------------
msg "Conferindo os discos"
[[ -e ${EMMC}boot0 ]] || erro "$EMMC nao tem boot0: nao e a eMMC. Confira o lsblk."
[[ -e ${SD}boot0 ]] && erro "$SD tem boot0: os nomes estao trocados. Confira o lsblk."
[[ -b $P3 ]] || erro "$P3 nao existe: o cartao nao foi detectado."

RAIZ=$(findmnt -no SOURCE /)
case $RAIZ in
    ${SD}p*) echo "  raiz: $RAIZ (cartao) - ok" ;;
    *) erro "a raiz e $RAIZ, nao o cartao. De boot pelo cartao (com ele no slot) e rode de novo." ;;
esac

# --- 2. nada da eMMC montado ----------------------------------------------------
msg "Soltando a eMMC (a /home costuma vir dela no boot pelo cartao)"
if findmnt -rno SOURCE | grep -q "^${EMMC}p"; then
    systemctl stop menuPrincipal smbd nmbd 2>/dev/null
    cd /
    sync
    for m in $(findmnt -rno TARGET,SOURCE | awk -v d="${EMMC}p" 'index($2, d) == 1 {print $1}' | sort -r); do
        echo "  desmontando $m"
        if ! umount "$m"; then
            # quem esta usando: processo com a pasta atual ou arquivo aberto dentro de $m
            echo "  $m esta em uso por:"
            for p in /proc/[0-9]*; do
                pasta=$(readlink "$p/cwd" 2>/dev/null)
                if [[ "$pasta" == "$m" || "$pasta" == "$m"/* ]]; then
                    echo "    PID ${p#/proc/} ($(cat "$p/comm" 2>/dev/null)): pasta atual $pasta"
                elif ls -l "$p/fd" 2>/dev/null | grep -q -- "-> $m/"; then
                    echo "    PID ${p#/proc/} ($(cat "$p/comm" 2>/dev/null)): arquivo aberto em $m"
                fi
            done
            echo "  Se for o seu terminal (bash), saia da pasta: cd /  e rode o script de novo."
            erro "nao consegui desmontar $m. Nada foi gravado."
        fi
    done
fi
findmnt -rno SOURCE | grep -q "^${EMMC}p" && erro "ainda ha particao da eMMC montada. Nada foi gravado."
echo "  nenhuma particao da eMMC montada - ok"

# --- 3. imagem ----------------------------------------------------------------
msg "Procurando a imagem na $P3"
findmnt -no SOURCE $PASTA >/dev/null && umount $PASTA
mount -o ro $P3 $PASTA || erro "nao montei $P3 em $PASTA"
trap 'cd /; umount $PASTA 2>/dev/null' EXIT
IMAGEM=$(ls -1 $PASTA/backupMariolaZero*.img 2>/dev/null | sort | tail -1)
[[ -n $IMAGEM ]] || erro "nenhuma backupMariolaZero*.img em $P3"
TAM_IMG=$(stat -c %s "$IMAGEM")
TAM_EMMC=$(blockdev --getsize64 $EMMC)
echo "  imagem: $IMAGEM ($TAM_IMG bytes)"
echo "  eMMC:   $EMMC ($TAM_EMMC bytes)"
(( TAM_IMG <= TAM_EMMC )) || erro "a imagem e maior que a eMMC"
(( TAM_IMG == TAM_EMMC )) || echo "  aviso: a imagem e menor que a eMMC (o resto fica como esta)"

# --- 4. confirmacao -------------------------------------------------------------
if (( ! SIM )); then
    echo -e "\n\033[1;31mTUDO que esta na eMMC sera APAGADO e trocado pela imagem.\033[0m"
    read -r -p "Digite SIM para continuar: " RESP
    [[ $RESP == SIM ]] || erro "cancelado. Nada foi gravado."
fi

# --- 5. grava -----------------------------------------------------------------
echo "Gravando EMMC, aguarde que demora...."
dd if="$IMAGEM" of=$EMMC bs=4M conv=fsync status=progress || erro "o dd falhou: a eMMC pode estar incompleta. Rode de novo."
sync
blockdev --rereadpt $EMMC 2>/dev/null

# --- 6. conferencia (opcional) ----------------------------------------------------
if (( VERIFICA )); then
    msg "Comparando a eMMC com a imagem (demora quase o mesmo tanto)"
    echo 3 > /proc/sys/vm/drop_caches
    cmp -n "$TAM_IMG" "$IMAGEM" $EMMC && echo "  eMMC igual a imagem - ok" || erro "a eMMC ficou DIFERENTE da imagem"
fi

# --- 7. MAC do Wi-Fi ------------------------------------------------------------------
# (depois da conferencia: a troca muda a eMMC, que deixa de ser igual a imagem)
if [[ $MAC != mantem ]]; then
    msg "Trocando o MAC do Wi-Fi no netplan da eMMC"
    RAIZ_EMMC=/run/raiz_emmc         # a raiz do cartao e somente leitura: monta na /run
    partprobe $EMMC 2>/dev/null; udevadm settle
    mkdir -p $RAIZ_EMMC
    mount ${EMMC}p1 $RAIZ_EMMC || erro "nao montei ${EMMC}p1 (a eMMC foi gravada; so o MAC nao foi trocado)"
    trap 'cd /; umount $RAIZ_EMMC 2>/dev/null; umount $PASTA 2>/dev/null' EXIT
    ARQ=$RAIZ_EMMC/$NETPLAN
    [[ -f $ARQ ]] || erro "$ARQ nao existe (a eMMC foi gravada; so o MAC nao foi trocado)"
    # o primeiro "macaddress:" depois de "wifis:" (o da wlan0; o da end0 fica antes, em "ethernets:")
    ANTIGO=$(awk '/^[[:space:]]*wifis:/ { w = 1 }
                  w && /^[[:space:]]*macaddress:/ { sub(/^[[:space:]]*macaddress:[[:space:]]*/, ""); gsub(/["'\'']/, ""); print; exit }' "$ARQ")
    [[ $ANTIGO =~ $FORMATO_MAC ]] || erro "nao achei o macaddress do Wi-Fi em $ARQ (a eMMC foi gravada; so o MAC nao foi trocado)"
    if [[ $MAC == sorteia ]]; then
        MAC=$(printf '%s:%02x:%02x:%02x:%02x:%s' "${ANTIGO%%:*}" $(( RANDOM % 256 )) $(( RANDOM % 256 )) \
              $(( RANDOM % 256 )) $(( RANDOM % 256 )) "${ANTIGO##*:}")
    fi
    MAC=${MAC,,}
    sed -i "s/$ANTIGO/$MAC/I" "$ARQ"
    grep -qi "macaddress:.*$MAC" "$ARQ" || erro "a troca do MAC nao ficou no $ARQ"
    sync
    umount $RAIZ_EMMC
    echo "  Wi-Fi (wlan0): $ANTIGO -> $MAC"
    echo "  Anote no brick: o roteador vai ver este MAC (e dar outro IP, se o DHCP for por MAC)."
fi

msg "Concluido. Desligue, tire o cartao e ligue: o brick vai subir pela eMMC."
echo "  (para desligar: sudo shutdown -h now)"
