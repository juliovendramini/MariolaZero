#!/bin/bash
# Grava na eMMC a imagem guardada na p3 do cartao de reserva (backupMariolaZero*.img).
# O brick tem de ter dado boot PELO CARTAO. Fica na raiz do cartao: /instalacao_emmc.sh
#
# Uso:  sudo bash /instalacao_emmc.sh              (pergunta antes de apagar a eMMC)
#       sudo bash /instalacao_emmc.sh -y           (sem perguntar)
#       sudo bash /instalacao_emmc.sh --verifica   (depois compara a eMMC com a imagem; dobra o tempo)
set -u

EMMC=/dev/mmcblk2
SD=/dev/mmcblk0
P3=${SD}p3
PASTA=/mnt

msg()  { echo -e "\n\033[1;36m==>\033[0m $*"; }
erro() { echo -e "\033[1;31mERRO:\033[0m $*" >&2; exit 1; }

SIM=0; VERIFICA=0
for a in "$@"; do
    case $a in
        -y) SIM=1 ;;
        --verifica) VERIFICA=1 ;;
        *) erro "opcao desconhecida: $a" ;;
    esac
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
        umount "$m" || erro "nao consegui desmontar $m (veja: fuser -vm $m). Nada foi gravado."
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

msg "Concluido. Desligue, tire o cartao e ligue: o brick vai subir pela eMMC."
echo "  (para desligar: sudo shutdown -h now)"
