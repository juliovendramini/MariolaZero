#!/bin/bash
# Atualiza a imagem da eMMC guardada na p3 do cartao de reserva.
# Uso: sudo bash ~/atualiza_imagem.sh
set -u

msg()  { echo -e "\n\033[1;36m==>\033[0m $*"; }
erro() { echo -e "\033[1;31mERRO:\033[0m $*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || erro "rode com sudo: sudo bash $0"

EMMC=/dev/mmcblk2
P3=/dev/mmcblk0p3
DESTINO=/mnt
NOVA="$DESTINO/backupMariolaZero$(date +%F).img"

# sempre, mesmo com erro: p3 desmontada, /home gravavel e servicos de volta
volta_ao_normal() {
    msg "Voltando ao normal (p3 desmontada, /home gravavel, menu e Samba ligados)"
    sync
    findmnt $DESTINO >/dev/null && umount $DESTINO
    mount -o remount,rw /home
    systemctl start smbd nmbd menuPrincipal
    echo "  /home: $(findmnt -no OPTIONS /home)"
}
trap volta_ao_normal EXIT

# --- conferencias -------------------------------------------------------------
msg "Conferindo os discos"
[[ -e ${EMMC}boot0 ]] || erro "$EMMC nao tem boot0: nao e a eMMC. Confira o lsblk."
[[ -b $P3 ]] || erro "$P3 nao existe: o cartao nao foi detectado."
[[ -e /dev/mmcblk0boot0 ]] && erro "/dev/mmcblk0 tem boot0: os nomes estao trocados. Confira o lsblk."
findmnt -no OPTIONS / | grep -qw ro || erro "a raiz esta gravavel; reinicie antes (ela tem de estar somente leitura)"
TAM=$(blockdev --getsize64 $EMMC)
echo "  eMMC: $EMMC ($TAM bytes); destino: $P3; raiz: $(findmnt -no SOURCE /); /home: $(findmnt -no SOURCE /home)"

# --- /home sem escrita durante a copia ---------------------------------------
msg "Parando menu e Samba e deixando a /home somente leitura"
systemctl stop menuPrincipal smbd nmbd
sync
mount -o remount,ro /home || erro "a /home esta ocupada (veja: fuser -vm /home)"

# --- p3 limpa e montada direito ------------------------------------------------
msg "Verificando a p3 e montando com escrita"
findmnt $DESTINO >/dev/null && { umount $DESTINO || erro "nao consegui desmontar $DESTINO"; }
e2fsck -f -p $P3; RC=$?
(( RC < 4 )) || erro "o e2fsck achou problemas que nao corrigiu sozinho (codigo $RC)"
mount $P3 $DESTINO || erro "nao montei $P3 em $DESTINO"
rm -f $DESTINO/backupMariolaZero*.img
LIVRE=$(stat -f -c %f $DESTINO); BLOCO=$(stat -f -c %S $DESTINO)
LIVRE=$(( LIVRE * BLOCO ))
echo "  livre (root): $LIVRE bytes; precisa: $TAM bytes"
(( LIVRE >= TAM )) || erro "nao cabe a imagem nova"

# --- grava ------------------------------------------------------------------------
msg "Gravando $NOVA (alguns minutos)"
dd if=$EMMC of="$NOVA" bs=4M conv=fsync status=progress || erro "o dd falhou"
sync

msg "Conferindo"
GRAVADO=$(stat -c %s "$NOVA")
echo "  imagem: $GRAVADO bytes; eMMC: $TAM bytes"
(( GRAVADO == TAM )) || erro "TAMANHOS DIFERENTES"
echo "  tamanhos iguais: ok"
ls -la $DESTINO
msg "Pronto. Para voltar a usar a eMMC: tire o cartao e reinicie (sudo reboot)."
