#!/bin/bash
#
# Ajusta boot do eMMC para U-Boot Allwinner
# Corrige problema "error:bad magic" e "Loading boot-pkg fail"
#
# O U-Boot Allwinner procura por arquivos de boot em locais específicos
# Precisa criar estrutura compatível
#
# Uso: sudo bash ajusta_boot_allwinner.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AJUSTE BOOT ALLWINNER${NC}"
echo -e "${GREEN}Corrige 'bad magic' e 'boot-pkg fail'${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Execute como root: sudo bash $0${NC}"
    exit 1
fi

# Detectar dispositivos
EMMC_DEVICE=""
if [ -e /dev/mmcblk0boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk0"
elif [ -e /dev/mmcblk2boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk2"
else
    echo -e "${RED}✗ eMMC não encontrado!${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/5] Montando eMMC...${NC}"
EMMC_MOUNT="/tmp/emmc_root"
mkdir -p $EMMC_MOUNT
mount ${EMMC_DEVICE}p1 $EMMC_MOUNT

echo -e "${GREEN}✓ eMMC montado${NC}"
echo ""

echo -e "${YELLOW}[2/5] Criando boot.cmd otimizado para Allwinner...${NC}"
echo ""

# Criar script de boot que o U-Boot Allwinner entende
cat > $EMMC_MOUNT/boot/boot.cmd << 'EOFBOOT'
# U-Boot boot script para Banana Pi M4 Zero (Allwinner H618)
# Compatível com U-Boot vendor BSP

# Detectar UUID da partição root
part uuid ${devtype} ${devnum}:${bootpart} uuid

# Configurar argumentos de boot
setenv bootargs "console=ttyS0,115200 console=tty1 root=UUID=${uuid} rootwait rootfstype=ext4 cma=128M"

# Carregar kernel
echo "Carregando kernel..."
load ${devtype} ${devnum}:${bootpart} ${kernel_addr_r} /boot/vmlinuz-5.4.125-legacy-sunxi64

# Carregar DTB
echo "Carregando DTB..."
load ${devtype} ${devnum}:${bootpart} ${fdt_addr_r} /boot/dtb-5.4.125-legacy-sunxi64/allwinner/sun50i-h618-bananapi-m4zero.dtb

# Carregar initramfs (se existir)
if load ${devtype} ${devnum}:${bootpart} ${ramdisk_addr_r} /boot/initrd.img-5.4.125-legacy-sunxi64; then
    echo "Carregando initramfs..."
    setenv ramdisk_size ${filesize}
    booti ${kernel_addr_r} ${ramdisk_addr_r}:${ramdisk_size} ${fdt_addr_r}
else
    echo "Boot sem initramfs..."
    booti ${kernel_addr_r} - ${fdt_addr_r}
fi
EOFBOOT

echo "Script de boot criado:"
cat $EMMC_MOUNT/boot/boot.cmd
echo ""

echo -e "${YELLOW}[3/5] Compilando boot.scr...${NC}"

# Compilar para formato U-Boot
mkimage -C none -A arm64 -T script -d $EMMC_MOUNT/boot/boot.cmd $EMMC_MOUNT/boot/boot.scr

echo -e "${GREEN}✓ boot.scr criado${NC}"
echo ""

echo -e "${YELLOW}[4/5] Criando links e arquivos alternativos...${NC}"

# Criar links simbólicos para o U-Boot encontrar
cd $EMMC_MOUNT/boot

# Link do kernel
ln -sf vmlinuz-5.4.125-legacy-sunxi64 vmlinuz 2>/dev/null || true
ln -sf vmlinuz-5.4.125-legacy-sunxi64 Image 2>/dev/null || true

# Link do initrd
ln -sf initrd.img-5.4.125-legacy-sunxi64 initrd.img 2>/dev/null || true
ln -sf initrd.img-5.4.125-legacy-sunxi64 uInitrd 2>/dev/null || true

# Link do DTB
ln -sf dtb-5.4.125-legacy-sunxi64/allwinner/sun50i-h618-bananapi-m4zero.dtb sun50i-h618-bananapi-m4zero.dtb 2>/dev/null || true

# Copiar boot.scr para raiz do /boot (alguns U-Boot procuram aqui)
cp -v boot.scr /boot.scr 2>/dev/null || true

cd - > /dev/null

echo -e "${GREEN}✓ Links criados${NC}"
echo ""

echo -e "${YELLOW}[5/5] Verificando estrutura final...${NC}"
echo ""
echo "Arquivos em /boot:"
ls -lh $EMMC_MOUNT/boot/ | grep -E "(vmlinuz|initrd|boot\.|dtb|Image)"
echo ""

echo "Conteúdo do armbianEnv.txt:"
cat $EMMC_MOUNT/boot/armbianEnv.txt
echo ""

sync
umount $EMMC_MOUNT

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}AJUSTE CONCLUÍDO!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Modificações realizadas:"
echo "  ✓ boot.cmd otimizado para Allwinner"
echo "  ✓ boot.scr recompilado"
echo "  ✓ Links simbólicos criados (vmlinuz, Image, initrd.img)"
echo "  ✓ DTB linkado na raiz do /boot"
echo ""
echo -e "${YELLOW}TESTE AGORA:${NC}"
echo "  1. Remova o SD card"
echo "  2. sudo reboot"
echo "  3. O U-Boot deve encontrar o boot.scr e carregar o kernel"
echo ""
echo -e "${BLUE}Se ainda falhar, o problema pode ser:${NC}"
echo "  - U-Boot procurando em partição errada"
echo "  - Necessário atualizar U-Boot para versão mais recente"
echo "  - Configuração de boot do U-Boot incompatível"
echo ""
echo "Nesse caso, podemos:"
echo "  A) Atualizar o U-Boot para versão mainline"
echo "  B) Ajustar variáveis de ambiente do U-Boot"
echo "  C) Usar o SD como /boot externo"
