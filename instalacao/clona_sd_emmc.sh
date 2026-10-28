#!/bin/bash
# Clona o cartao SD (o sistema que esta rodando) para a eMMC. Feito para a imagem @Work (Ubuntu
# 24.04 + ROS2, BPI-M4 Zero de 32 GB): cartao e eMMC tem o mesmo tamanho, entao nao sobra lugar no
# cartao para uma particao com o .img, como no cartao de reserva da Line/Maze (instalacao_emmc.sh).
#
# O que faz, com o brick ligado PELO CARTAO:
#   1. cria na eMMC as mesmas particoes do cartao (p1 = raiz, p2 = /home com o resto da eMMC; se a
#      eMMC for menor que o cartao, a raiz encolhe, desde que os arquivos caibam);
#   2. formata com as mesmas opcoes do ext4 do cartao, com UUIDs novos (rotulos armbi_emmc e homeemmc);
#   3. copia os arquivos com rsync (a raiz do cartao ja e somente leitura; a /home fica somente leitura
#      durante a copia);
#   4. troca os UUIDs no /etc/fstab e no /boot/armbianEnv.txt da copia;
#   5. copia o U-Boot do cartao (a area crua de 8 KiB ate o comeco da p1).
# Com UUIDs diferentes, um boot pelo cartao com a eMMC gravada nao mistura as particoes dos dois.
#
# Uso:  sudo bash clona_sd_emmc.sh        (mostra o plano e pede SIM antes de apagar a eMMC)
#       sudo bash clona_sd_emmc.sh -y     (sem perguntar)
#       bash clona_sd_emmc.sh -n          (so confere e mostra o plano; nao grava nada, nem precisa de sudo)
set -u

msg()  { echo -e "\n\033[1;36m==>\033[0m $*"; }
erro() { echo -e "\033[1;31mERRO:\033[0m $*" >&2; exit 1; }
gb()   { awk -v s="$1" 'BEGIN { printf "%.1f GB", s * 512 / 1e9 }'; }   # setores de 512 -> GB

SIM=0; SIMULA=0
for a in "$@"; do
    case $a in
        -y) SIM=1 ;;
        -n) SIMULA=1 ;;
        *) erro "opcao desconhecida: $a" ;;
    esac
done
(( SIMULA )) || [[ $EUID -eq 0 ]] || erro "rode com sudo: sudo bash $0   (ou bash $0 -n para so conferir)"

# --- 1. discos ----------------------------------------------------------------------
msg "Conferindo os discos"
RAIZ=$(findmnt -no SOURCE /)
HOME_SD=$(findmnt -no SOURCE /home)
SD=/dev/$(lsblk -no PKNAME "$RAIZ")
[[ $SD == /dev/mmcblk[0-9] ]] || erro "a raiz e $RAIZ, que nao esta num cartao SD"
[[ -e ${SD}boot0 ]] && erro "a raiz ($RAIZ) esta na eMMC. Ligue o brick com o cartao no slot e rode de novo."
[[ $RAIZ == ${SD}p1 && $HOME_SD == ${SD}p2 ]] || erro "esperava a raiz em ${SD}p1 e a /home em ${SD}p2 (raiz: $RAIZ, /home: $HOME_SD)"
EMMC=
for d in /dev/mmcblk[0-9]; do [[ -e ${d}boot0 ]] && EMMC=$d; done
[[ -n $EMMC ]] || erro "nao achei a eMMC (nenhum /dev/mmcblkN com boot0)"
[[ $EMMC != "$SD" ]] || erro "cartao e eMMC deram o mesmo disco ($SD)"
echo "  cartao: $SD ($(cat /sys/block/${SD#/dev/}/device/name 2>/dev/null)); raiz $RAIZ, /home $HOME_SD"
echo "  eMMC:   $EMMC ($(cat /sys/block/${EMMC#/dev/}/device/name 2>/dev/null))"

# --- 2. tamanhos (em setores de 512 bytes) --------------------------------------------
INICIO=$(cat /sys/block/${SD#/dev/}/${RAIZ#/dev/}/start)       # comeco da p1 (antes dele: MBR e U-Boot)
TAM_RAIZ=$(cat /sys/block/${SD#/dev/}/${RAIZ#/dev/}/size)
TAM_HOME=$(cat /sys/block/${SD#/dev/}/${HOME_SD#/dev/}/size)
TAM_EMMC=$(cat /sys/block/${EMMC#/dev/}/size)
(( INICIO > 16 )) || erro "a p1 do cartao comeca no setor $INICIO: nao ha espaco para o U-Boot"
USADO_RAIZ=$(df -B512 --output=used / | tail -1)
USADO_HOME=$(df -B512 --output=used /home | tail -1)
PRECISA_RAIZ=$(( USADO_RAIZ * 11 / 10 + 1048576 ))             # +10% e +512 MiB de folga
PRECISA_HOME=$(( USADO_HOME * 11 / 10 + 1048576 ))
DISPONIVEL=$(( TAM_EMMC - INICIO ))
NOVA_RAIZ=$TAM_RAIZ
if (( DISPONIVEL - NOVA_RAIZ < PRECISA_HOME )); then
    NOVA_RAIZ=$(( (DISPONIVEL - PRECISA_HOME) / 8192 * 8192 ))   # alinhada em 4 MiB
    (( NOVA_RAIZ > 0 )) || NOVA_RAIZ=0
    echo "  aviso: a eMMC e menor que o cartao; a raiz encolhe para $(gb $NOVA_RAIZ)"
fi
NOVA_HOME=$(( DISPONIVEL - NOVA_RAIZ ))
printf '  %-6s %-22s %-22s %s\n' "" "no cartao" "na eMMC" "usado no cartao" \
    raiz "$(gb $TAM_RAIZ)" "$(gb $NOVA_RAIZ)" "$(gb $USADO_RAIZ)" \
    /home "$(gb $TAM_HOME)" "$(gb $NOVA_HOME)" "$(gb $USADO_HOME)"
echo "  eMMC inteira: $(gb $TAM_EMMC); particoes a partir do setor $INICIO"
(( NOVA_RAIZ >= PRECISA_RAIZ && NOVA_HOME >= PRECISA_HOME )) ||
    erro "nao cabe: a eMMC tem $(gb $TAM_EMMC) e os arquivos do cartao pedem $(gb $(( INICIO + PRECISA_RAIZ + PRECISA_HOME ))) (com folga). E a eMMC certa (a de 32 GB)?"

# opcoes do mkfs.ext4 iguais as do ext4 da particao $1 (recursos, bloco, inode, reserva do root)
opcoes_ext4() {
    dumpe2fs -h "$1" 2>/dev/null | awk -F: '
        /^Filesystem features:/  { n = split($2, f, " "); s = "none"
                                   for (i = 1; i <= n; i++)
                                       if (f[i] != "needs_recovery" && f[i] != "orphan_present") s = s "," f[i]
                                   rec = s }
        /^Block size:/           { gsub(/[ \t]/, "", $2); bl = $2 }
        /^Inode size:/           { gsub(/[ \t]/, "", $2); ino = $2 }
        /^Block count:/          { gsub(/[ \t]/, "", $2); bc = $2 }
        /^Reserved block count:/ { gsub(/[ \t]/, "", $2); rb = $2 }
        END { if (rec == "" || bc == "") exit 1
              printf "-O %s -b %s -I %s -m %.1f", rec, bl, ino, rb * 100 / bc }'
}
# opcoes de montagem padrao gravadas no ext4 (no cartao: journal_data_writeback na raiz, journal_data na /home)
montagem_ext4() {
    dumpe2fs -h "$1" 2>/dev/null | sed -n 's/^Default mount options: *//p' | tr -s ' ' ','
}
OPC_RAIZ=$(opcoes_ext4 "$RAIZ") || erro "nao consegui ler o ext4 de $RAIZ (dumpe2fs)"
OPC_HOME=$(opcoes_ext4 "$HOME_SD") || erro "nao consegui ler o ext4 de $HOME_SD (dumpe2fs)"
MNT_RAIZ=$(montagem_ext4 "$RAIZ")
MNT_HOME=$(montagem_ext4 "$HOME_SD")
echo "  ext4 da raiz:  $OPC_RAIZ${MNT_RAIZ:+ (montagem padrao: $MNT_RAIZ)}"
echo "  ext4 da /home: $OPC_HOME${MNT_HOME:+ (montagem padrao: $MNT_HOME)}"

echo "  eMMC agora:"
lsblk -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT "$EMMC" | sed 's/^/    /'

if (( SIMULA )); then
    msg "Simulacao (-n): tudo conferido, nada foi gravado."
    exit 0
fi

# --- 3. confirmacao --------------------------------------------------------------------
if (( ! SIM )); then
    echo -e "\n\033[1;31mTUDO que esta na eMMC ($EMMC) sera APAGADO e trocado pela copia do cartao.\033[0m"
    read -r -p "Digite SIM para continuar: " RESP
    [[ $RESP == SIM ]] || erro "cancelado. Nada foi gravado."
fi

# --- 4. nada da eMMC montado ----------------------------------------------------------------
msg "Soltando a eMMC"
cd /
for m in $(findmnt -rno TARGET,SOURCE | awk -v d="${EMMC}p" 'index($2, d) == 1 {print $1}' | sort -r); do
    echo "  desmontando $m"
    umount "$m" || erro "nao consegui desmontar $m (veja quem usa: fuser -vm $m). Nada foi gravado."
done
findmnt -rno SOURCE | grep -q "^${EMMC}p" && erro "ainda ha particao da eMMC montada. Nada foi gravado."
echo "  nenhuma particao da eMMC montada - ok"

# --- 5. /home do cartao somente leitura durante a copia ---------------------------------------
TMP=/run/clona_sd_emmc        # a raiz e somente leitura: as pastas de montagem ficam na /run
mkdir -p $TMP/sd_raiz $TMP/sd_home $TMP/emmc_raiz $TMP/emmc_home
volta_ao_normal() {
    msg "Voltando ao normal (desmontando a eMMC, /home do cartao gravavel)"
    cd /
    sync
    for m in $TMP/emmc_home $TMP/emmc_raiz $TMP/sd_home $TMP/sd_raiz; do
        findmnt "$m" >/dev/null && umount "$m"
    done
    mount -o remount,rw /home
    echo "  /home: $(findmnt -no OPTIONS /home)"
}

msg "Deixando a /home somente leitura"
sync
if ! mount -o remount,ro /home; then
    echo "  a /home tem arquivos abertos por:"
    for p in /proc/[0-9]*; do
        ls -l "$p/fd" 2>/dev/null | grep -q -- "-> /home/" &&
            echo "    PID ${p#/proc/} ($(cat "$p/comm" 2>/dev/null))"
    done
    erro "nao consegui deixar a /home somente leitura: feche esses programas e rode de novo. Nada foi gravado."
fi
trap volta_ao_normal EXIT

# --- 6. particoes e ext4 -----------------------------------------------------------------------
msg "Criando as particoes na eMMC"
wipefs -q -a ${EMMC}p[0-9]* 2>/dev/null
wipefs -q -a $EMMC
printf 'label: dos\nstart=%s, size=%s, type=83\nstart=%s, type=83\n' \
    $INICIO $NOVA_RAIZ $(( INICIO + NOVA_RAIZ )) | sfdisk -q --wipe always $EMMC ||
    erro "o sfdisk falhou: a eMMC ficou sem particoes. Rode de novo."
partprobe $EMMC 2>/dev/null || blockdev --rereadpt $EMMC
udevadm settle
[[ -b ${EMMC}p1 && -b ${EMMC}p2 ]] || erro "${EMMC}p1/p2 nao apareceram depois do sfdisk"
sfdisk -d $EMMC | grep "^$EMMC" | sed 's/^/  /'

msg "Formatando (mesmas opcoes do cartao)"
mkfs.ext4 -F -q $OPC_RAIZ -L armbi_emmc ${EMMC}p1 || erro "mkfs da raiz falhou"
mkfs.ext4 -F -q $OPC_HOME -L homeemmc ${EMMC}p2 || erro "mkfs da /home falhou"
[[ -n $MNT_RAIZ && $MNT_RAIZ != "(none)" ]] && { tune2fs -o "$MNT_RAIZ" ${EMMC}p1 >/dev/null || erro "tune2fs da raiz falhou"; }
[[ -n $MNT_HOME && $MNT_HOME != "(none)" ]] && { tune2fs -o "$MNT_HOME" ${EMMC}p2 >/dev/null || erro "tune2fs da /home falhou"; }

# --- 7. copia -----------------------------------------------------------------------------------
# "bind" mostra so o sistema de arquivos da raiz, sem /proc, /sys, /run, /home montados por cima
mount --bind / $TMP/sd_raiz && mount -o remount,bind,ro $TMP/sd_raiz || erro "nao montei a raiz do cartao em $TMP/sd_raiz"
mount --bind /home $TMP/sd_home && mount -o remount,bind,ro $TMP/sd_home || erro "nao montei a /home do cartao em $TMP/sd_home"
mount ${EMMC}p1 $TMP/emmc_raiz || erro "nao montei ${EMMC}p1"
mount ${EMMC}p2 $TMP/emmc_home || erro "nao montei ${EMMC}p2"

copia() {   # copia $1 para $2; o rsync sai com 24 se um arquivo sumiu no meio, o que nao e erro aqui
    rsync -aAXH --numeric-ids --info=progress2 "$1/" "$2/"
    local rc=$?
    (( rc == 0 || rc == 24 )) || erro "o rsync de $1 falhou (codigo $rc): a eMMC ficou incompleta. Rode de novo."
}
msg "Copiando a raiz ($(gb $USADO_RAIZ); alguns minutos)"
copia $TMP/sd_raiz $TMP/emmc_raiz
msg "Copiando a /home ($(gb $USADO_HOME); alguns minutos)"
copia $TMP/sd_home $TMP/emmc_home

# --- 8. UUIDs da copia ------------------------------------------------------------------------------
msg "Trocando os UUIDs no fstab e no armbianEnv.txt da eMMC"
U_SD_RAIZ=$(blkid -p -s UUID -o value $RAIZ)
U_SD_HOME=$(blkid -p -s UUID -o value $HOME_SD)
L_SD_HOME=$(blkid -p -s LABEL -o value $HOME_SD)
U_RAIZ=$(blkid -p -s UUID -o value ${EMMC}p1)
U_HOME=$(blkid -p -s UUID -o value ${EMMC}p2)
[[ -n $U_SD_RAIZ && -n $U_RAIZ && -n $U_HOME ]] || erro "nao consegui ler os UUIDs (blkid)"
FSTAB=$TMP/emmc_raiz/etc/fstab
ENV=$TMP/emmc_raiz/boot/armbianEnv.txt
sed -i -e "s/$U_SD_RAIZ/$U_RAIZ/g" -e "s/$U_SD_HOME/$U_HOME/g" $FSTAB
[[ -n $L_SD_HOME ]] && sed -i -E "s/^LABEL=$L_SD_HOME([[:space:]])/UUID=$U_HOME\1/" $FSTAB
if grep -q '^rootdev=' $ENV; then
    sed -i "s/^rootdev=.*/rootdev=UUID=$U_RAIZ/" $ENV
else
    echo "rootdev=UUID=$U_RAIZ" >> $ENV
fi
echo "  fstab da eMMC:"
grep -v '^#' $FSTAB | grep . | sed 's/^/    /'
echo "  armbianEnv.txt: $(grep '^rootdev=' $ENV)"
SOBRA=$(grep -rIl -e "$U_SD_RAIZ" -e "$U_SD_HOME" $TMP/emmc_raiz/etc $TMP/emmc_raiz/boot 2>/dev/null)
[[ -n $SOBRA ]] && echo -e "  \033[1;33maviso:\033[0m ainda citam o UUID do cartao: $SOBRA"

# --- 9. U-Boot ------------------------------------------------------------------------------------------
msg "Copiando o U-Boot do cartao (de 8 KiB ate o setor $INICIO)"
dd if=$SD of=$EMMC bs=512 skip=16 seek=16 count=$(( INICIO - 16 )) conv=fsync status=none ||
    erro "o dd do U-Boot falhou"
cmp -i $(( 16 * 512 )) -n $(( (INICIO - 16) * 512 )) $SD $EMMC && echo "  U-Boot igual ao do cartao - ok" ||
    erro "o U-Boot da eMMC ficou diferente do cartao"

msg "Concluido. Desligue, tire o cartao e ligue: o brick vai subir pela eMMC."
echo "  (para desligar: sudo shutdown -h now; depois confira com: findmnt / /home)"
