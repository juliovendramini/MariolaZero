#!/bin/bash
# rasp4_somente_leitura.sh — converte a imagem do Raspberry Pi 4 (@Work: Ubuntu 24.04 + ROS2)
# para o jeito do Mariola: raiz somente leitura + /home numa partição própria, gravável.
#
# Roda num Linux qualquer (PC ou VM), como root, sobre o ARQUIVO da imagem (.img/.dd já
# descompactado). Não mexe na imagem original: trabalha numa cópia.
#
#   sudo bash rasp4_somente_leitura.sh ORIGINAL.img NOVA.img
#
# Se NOVA.img não existe, o script copia a original (cópia sequencial, ~32 GB). Se você já copiou
# por fora (no Windows é bem mais rápido que por pasta compartilhada de VM), rode com JA_COPIADA=1.
#
# Variáveis (opcionais): RAIZ_GIB (tamanho da raiz, padrão 16) e TOTAL_MIB (tamanho da imagem
# nova, padrão 29000 = 30,4 GB, para caber em qualquer cartão de "32 GB"; a /home fica com o resto).
#
# Partições da imagem nova:
#   p1  FAT  system-boot  /boot/firmware  (a mesma da original; montada ro)
#   p2  ext4 writable     /               (a mesma da original, encolhida com resize2fs; ro)
#   p3  ext4 rasp_home    /home           (nova; data=journal, nofail)
#
# Como a raiz é encolhida no lugar (e não copiada arquivo por arquivo), o UUID, os donos, as
# permissões, os xattrs e as capabilities ficam exatamente como estavam. Só a /home (26 mil
# arquivos, contra 260 mil da raiz) é copiada com rsync.
#
# Dentro do sistema novo:
#   * /tmp, /var/tmp e /var/log em RAM (tmpfs); as pastas do /var/log são recriadas a cada boot a
#     partir de /var/log.esqueleto (var-log-esqueleto.service); journald só na RAM; rsyslog
#     desligado (use journalctl).
#   * /var/lib/systemd/timesync na /home/.sistema (o Pi não tem relógio: sem isso a hora voltaria
#     sempre para a data da imagem até achar NTP), e /var/lib/vnstat também (o banco do vnstat).
#   * desligados (mask): cloud-init, snapd, atualizações automáticas (apt-daily, unattended-upgrades),
#     apport e timers que só gravam na raiz (logrotate, man-db, motd-news, fstrim, e2scrub,
#     systemd-tmpfiles-clean...).
#   * cmdline.txt com fsck.repair=yes; ~/remonta.sh para destravar até o próximo boot.
set -euo pipefail

ORIG=${1:?uso: sudo bash $0 ORIGINAL.img NOVA.img}
NOVA=${2:?uso: sudo bash $0 ORIGINAL.img NOVA.img}
RAIZ_GIB=${RAIZ_GIB:-16}
TOTAL_MIB=${TOTAL_MIB:-29000}
export PATH=/usr/sbin:/sbin:$PATH
passo() { echo; echo "=== $(date +%H:%M:%S) $*"; }

[ "$(id -u)" = 0 ] || { echo "rode como root (sudo)"; exit 1; }
[ -f "$ORIG" ] || { echo "não achei $ORIG"; exit 1; }

# ---- tabela da original -------------------------------------------------------------------------
read -r P1S P1N P2S P2N < <(sfdisk -d "$ORIG" | awk -F'[=,]' '
  /start=/ {gsub(/ /,""); for(i=1;i<=NF;i++){ if($i ~ /start$/) s=$(i+1); if($i ~ /size$/) n=$(i+1) } a[++k]=s" "n }
  END { print a[1], a[2] }')
DISKID=$(sfdisk -d "$ORIG" | awk '/label-id/ {print $2}')
echo "original: p1 $P1S+$P1N  p2 $P2S+$P2N  id $DISKID"

P2N_NOVO=$((RAIZ_GIB * 1024 * 1024 * 2))
P3S=$((P2S + P2N_NOVO))
TOTAL=$((TOTAL_MIB * 2048))
P3N=$((TOTAL - P3S))
[ $((P2S % 2048)) = 0 ] || { echo "p2 não começa alinhada em 1 MiB"; exit 1; }
[ "$P2N_NOVO" -lt "$P2N" ] || { echo "a raiz nova não é menor que a original"; exit 1; }
[ "$P3N" -gt $((1024 * 2048)) ] || { echo "sobra pouco para a /home: aumente TOTAL_MIB"; exit 1; }
echo "nova:     p2 $P2S+$P2N_NOVO ($RAIZ_GIB GiB)  p3 $P3S+$P3N ($((P3N / 2048)) MiB)  total $TOTAL_MIB MiB"

# ---- cópia da imagem ----------------------------------------------------------------------------
if [ -e "$NOVA" ]; then
  [ "${JA_COPIADA:-0}" = 1 ] || { echo "$NOVA já existe: apague, ou rode com JA_COPIADA=1 se for uma cópia da original"; exit 1; }
  [ "$(stat -c %s "$NOVA")" = "$(stat -c %s "$ORIG")" ] || { echo "$NOVA não tem o tamanho da original"; exit 1; }
  [ "$(sfdisk -d "$NOVA" | grep -c start=)" = 2 ] || { echo "$NOVA não tem a tabela da original (já foi convertida?)"; exit 1; }
  cmp -n $((P2S * 512)) "$ORIG" "$NOVA" || { echo "o começo de $NOVA difere da original"; exit 1; }
else
  passo "copiando $ORIG para $NOVA"
  dd if="$ORIG" of="$NOVA" bs=4M conv=fsync status=progress
fi

MO=/mnt/rasp_orig; MR=/mnt/rasp_raiz; MH=/mnt/rasp_home; MB=/mnt/rasp_boot
LO=""; LN=""
limpa() {
  set +e
  for m in $MB $MH $MR $MO; do mountpoint -q $m && umount $m; done
  [ -n "$LN" ] && losetup -d "$LN"
  [ -n "$LO" ] && losetup -d "$LO"
}
trap limpa EXIT
mkdir -p $MO $MR $MH $MB

LO=$(losetup -f --show -r -P "$ORIG")
LN=$(losetup -f --show -P "$NOVA")
sleep 1
echo "loops: original $LO, nova $LN"
FEAT=$(dumpe2fs -h ${LO}p2 2>/dev/null | sed -n 's/^Filesystem features: *//p' | tr ' ' ',' \
       | sed 's/needs_recovery,\?//')

# ---- raiz: limpa a /home e o /var/log, configura ------------------------------------------------
passo "e2fsck da raiz"
e2fsck -fy ${LN}p2 || [ $? -le 1 ]
mount ${LN}p2 $MR

passo "esqueleto do /var/log e limpeza da /home e do /var/log na raiz"
rsync -aAX --numeric-ids -f'- /journal/' -f'+ */' -f'- *' $MR/var/log/ $MR/var/log.esqueleto/
find $MR/var/log -mindepth 1 -delete
find $MR/home -mindepth 1 -delete

passo "fstab, journald, serviços, cloud-init"
cp -a $MR/etc/fstab $MR/etc/fstab.antes-somente-leitura
cat > $MR/etc/fstab <<'EOF'
# Raiz somente leitura (jeito do Mariola). Para mudar o sistema: ~/remonta.sh (até o próximo boot).
# O original está em /etc/fstab.antes-somente-leitura.
LABEL=writable     /                ext4   ro,noatime,errors=remount-ro              0 1
LABEL=system-boot  /boot/firmware   vfat   ro,defaults                               0 2
LABEL=rasp_home    /home            ext4   defaults,noatime,data=journal,nofail      0 2
tmpfs              /tmp             tmpfs  defaults,nosuid,nodev,mode=1777           0 0
tmpfs              /var/tmp         tmpfs  defaults,nosuid,nodev,mode=1777           0 0
tmpfs              /var/log         tmpfs  defaults,nosuid,nodev,mode=0755,size=128M 0 0
# hora salva entre boots (o Pi não tem relógio) e o banco do vnstat: gravados na /home
/home/.sistema/timesync /var/lib/systemd/timesync none bind,nofail,x-systemd.requires-mounts-for=/home 0 0
/home/.sistema/vnstat   /var/lib/vnstat           none bind,nofail,x-systemd.requires-mounts-for=/home 0 0
EOF

cat > $MR/etc/systemd/system/var-log-esqueleto.service <<'EOF'
[Unit]
Description=Recria as pastas do /var/log no tmpfs (raiz somente leitura)
DefaultDependencies=no
RequiresMountsFor=/var/log
Before=local-fs.target systemd-tmpfiles-setup.service sysinit.target

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/bin/cp -a /var/log.esqueleto/. /var/log/

[Install]
WantedBy=local-fs.target
EOF
mkdir -p $MR/etc/systemd/system/local-fs.target.wants
ln -sfn /etc/systemd/system/var-log-esqueleto.service $MR/etc/systemd/system/local-fs.target.wants/

mkdir -p $MR/etc/systemd/journald.conf.d
cat > $MR/etc/systemd/journald.conf.d/somente-leitura.conf <<'EOF'
# raiz somente leitura: o journal fica só na RAM (some a cada boot)
[Journal]
Storage=volatile
RuntimeMaxUse=64M
EOF

DESLIGA="snapd.service snapd.socket snapd.seeded.service snapd.apparmor.service
 snapd.autoimport.service snapd.core-fixup.service snapd.recovery-chooser-trigger.service
 snapd.snap-repair.timer snapd.snap-repair.service
 unattended-upgrades.service apt-daily.timer apt-daily-upgrade.timer apt-daily.service apt-daily-upgrade.service
 apport.service apport-autoreport.timer apport-autoreport.service
 dpkg-db-backup.timer e2scrub_all.timer e2scrub_reap.service fstrim.timer fwupd-refresh.timer
 logrotate.timer man-db.timer motd-news.timer ua-timer.timer
 update-notifier-download.timer update-notifier-motd.timer
 systemd-tmpfiles-clean.timer rsyslog.service"
for u in $DESLIGA; do
  rm -f $MR/etc/systemd/system/*.wants/$u
  ln -sfn /dev/null $MR/etc/systemd/system/$u
done
rm -f $MR/etc/systemd/system/syslog.service          # apelido do rsyslog
for m in $MR/etc/systemd/system/snap-*.mount; do     # montagens dos snaps: sem o snapd não servem
  [ -e "$m" ] && rm -f $MR/etc/systemd/system/*.wants/$(basename "$m")
done
touch $MR/etc/cloud/cloud-init.disabled
mkdir -p $MR/var/lib/systemd/timesync $MR/var/lib/vnstat
umount $MR

# ---- encolhe a raiz -----------------------------------------------------------------------------
passo "e2fsck + resize2fs da raiz para $RAIZ_GIB GiB"
e2fsck -fy ${LN}p2 || [ $? -le 1 ]
resize2fs ${LN}p2 ${RAIZ_GIB}G
tune2fs -m 2 ${LN}p2 >/dev/null

# ---- tabela nova --------------------------------------------------------------------------------
passo "tabela de partições nova"
losetup -d "$LN"; LN=""
sfdisk --no-reread "$NOVA" <<EOF
label: dos
label-id: $DISKID
unit: sectors

start=$P1S, size=$P1N, type=c, bootable
start=$P2S, size=$P2N_NOVO, type=83
start=$P3S, size=$P3N, type=83
EOF
LN=$(losetup -f --show -P "$NOVA")
sleep 1

# ---- /home --------------------------------------------------------------------------------------
passo "zerando a área da /home (o resto da raiz antiga; deixa a imagem compactada menor)"
dd if=/dev/zero of=${LN}p3 bs=4M conv=fsync status=progress || true
mkfs.ext4 -q -F -L rasp_home -m 1 -O none,$FEAT ${LN}p3
mount ${LN}p3 $MH
mount -o ro,noload ${LO}p2 $MO

passo "copiando a /home"
rsync -aAXH --numeric-ids $MO/home/ $MH/
mkdir -p $MH/.sistema
for d in systemd/timesync vnstat; do
  if [ -d $MO/var/lib/$d ]; then
    cp -a $MO/var/lib/$d $MH/.sistema/
  else
    mkdir -p $MH/.sistema/$(basename $d)
  fi
done
for d in $MH/*/; do
  u=$(basename "$d")
  [ "$u" = lost+found ] && continue
  cat > "$d/remonta.sh" <<'EOF'
#!/bin/bash
# Remonta a raiz e o boot como graváveis (até o próximo boot). Use antes de apt, dpkg,
# systemctl enable, netplan, editar /etc...  Depois: sudo reboot (volta a ficar somente leitura).
sudo mount -o remount,rw / && sudo mount -o remount,rw /boot/firmware && echo "raiz e /boot/firmware graváveis até o próximo boot"
EOF
  chown --reference="$d" "$d/remonta.sh"
  chmod 755 "$d/remonta.sh"
done

passo "conferindo a /home (rsync -n: não deve listar nada)"
rsync -aAXHn --numeric-ids --itemize-changes --exclude='/.sistema' --exclude='/*/remonta.sh' \
  --exclude='/lost+found' $MO/home/ $MH/ | head -20
umount $MH $MO

# ---- zera o espaço livre da raiz (compactação) --------------------------------------------------
passo "zerando o espaço livre da raiz"
mount ${LN}p2 $MR
dd if=/dev/zero of=$MR/zero.tmp bs=4M status=progress 2>&1 | tail -1 || true
rm -f $MR/zero.tmp
sync
df -h $MR
umount $MR

# ---- cmdline.txt --------------------------------------------------------------------------------
passo "cmdline.txt"
mount ${LN}p1 $MB
cp $MB/cmdline.txt $MB/cmdline.txt.antes-somente-leitura
grep -q 'fsck.repair=' $MB/cmdline.txt || sed -i '1 s/$/ fsck.repair=yes/' $MB/cmdline.txt
echo "cmdline.txt: $(cat $MB/cmdline.txt)"
umount $MB

# ---- fim ----------------------------------------------------------------------------------------
passo "e2fsck final"
e2fsck -fn ${LN}p2 && echo "e2fsck raiz ok"
e2fsck -fn ${LN}p3 && echo "e2fsck home ok"
losetup -d "$LN"; LN=""
truncate -s $((TOTAL * 512)) "$NOVA"
sfdisk -l "$NOVA"
passo "pronto: $NOVA"
