#!/bin/bash
#
# Corrige problema "bad magic" no boot do eMMC
# Copia kernel, DTB e configuração do SD para o eMMC
#
# Uso: sudo bash corrige_boot_emmc.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CORREÇÃO DO BOOT DO eMMC${NC}"
echo -e "${GREEN}Corrige erro 'bad magic'${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Execute como root: sudo bash $0${NC}"
    exit 1
fi

# Detectar dispositivos
EMMC_DEVICE=""
SD_DEVICE=""

if [ -e /dev/mmcblk0boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk0"
    SD_DEVICE="/dev/mmcblk1"
elif [ -e /dev/mmcblk2boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk2"
    SD_DEVICE="/dev/mmcblk1"
else
    echo -e "${RED}✗ eMMC não encontrado!${NC}"
    exit 1
fi

# Verificar se está bootado do SD
if ! mount | grep -q "^${SD_DEVICE}p1 on / "; then
    echo -e "${RED}✗ Este script precisa ser executado bootando do SD card!${NC}"
    echo "Boot atual:"
    mount | grep " on / "
    exit 1
fi

echo -e "${GREEN}✓ Sistema bootado do SD card${NC}"
echo ""

echo -e "${YELLOW}[1/7] Montando partições...${NC}"
EMMC_MOUNT="/tmp/emmc_root"
SD_MOUNT="/"

mkdir -p $EMMC_MOUNT
mount ${EMMC_DEVICE}p1 $EMMC_MOUNT 2>/dev/null || {
    echo -e "${RED}✗ Erro ao montar eMMC${NC}"
    exit 1
}

echo -e "${GREEN}✓ eMMC montado em $EMMC_MOUNT${NC}"
echo ""

echo -e "${YELLOW}[2/7] Verificando estrutura do eMMC...${NC}"
ls -la $EMMC_MOUNT | head -10
echo ""

if [ ! -d "$EMMC_MOUNT/boot" ]; then
    echo -e "${RED}✗ Diretório /boot não existe no eMMC!${NC}"
    mkdir -p $EMMC_MOUNT/boot
    echo -e "${YELLOW}⚠ Criado diretório /boot${NC}"
fi
echo ""

echo -e "${YELLOW}[3/7] Copiando kernel do SD para eMMC...${NC}"
echo ""
echo "Kernels disponíveis no SD:"
ls -lh /boot/vmlinuz* 2>/dev/null

KERNEL_SD=$(ls /boot/vmlinuz-* 2>/dev/null | head -1)
if [ -z "$KERNEL_SD" ]; then
    echo -e "${RED}✗ Kernel não encontrado no SD!${NC}"
    exit 1
fi

KERNEL_VERSION=$(basename $KERNEL_SD | sed 's/vmlinuz-//')
echo ""
echo "Versão do kernel: $KERNEL_VERSION"
echo "Copiando $KERNEL_SD..."

cp -v $KERNEL_SD $EMMC_MOUNT/boot/
cp -v /boot/config-* $EMMC_MOUNT/boot/ 2>/dev/null || true
cp -v /boot/System.map-* $EMMC_MOUNT/boot/ 2>/dev/null || true

echo -e "${GREEN}✓ Kernel copiado${NC}"
echo ""

echo -e "${YELLOW}[4/7] Copiando DTBs do SD para eMMC...${NC}"
echo ""

# Copiar diretórios de DTB
if [ -d "/boot/dtb" ]; then
    echo "Copiando /boot/dtb..."
    cp -rfv /boot/dtb $EMMC_MOUNT/boot/
fi

if [ -d "/boot/dtb-${KERNEL_VERSION}" ]; then
    echo "Copiando /boot/dtb-${KERNEL_VERSION}..."
    cp -rfv /boot/dtb-${KERNEL_VERSION} $EMMC_MOUNT/boot/
fi

echo -e "${GREEN}✓ DTBs copiados${NC}"
echo ""

echo -e "${YELLOW}[5/7] Criando/atualizando armbianEnv.txt...${NC}"
echo ""

# Copiar do SD
if [ -f "/boot/armbianEnv.txt" ]; then
    echo "Arquivo armbianEnv.txt do SD:"
    cat /boot/armbianEnv.txt
    echo ""
    
    cp -v /boot/armbianEnv.txt $EMMC_MOUNT/boot/
    
    # Atualizar UUID para o eMMC
    EMMC_UUID=$(blkid -s UUID -o value ${EMMC_DEVICE}p1)
    echo "UUID do eMMC: $EMMC_UUID"
    
    sed -i "s/rootdev=UUID=.*/rootdev=UUID=${EMMC_UUID}/" $EMMC_MOUNT/boot/armbianEnv.txt
    
    echo ""
    echo "Arquivo armbianEnv.txt atualizado no eMMC:"
    cat $EMMC_MOUNT/boot/armbianEnv.txt
else
    echo -e "${RED}✗ armbianEnv.txt não encontrado no SD!${NC}"
    echo "Criando arquivo básico..."
    
    EMMC_UUID=$(blkid -s UUID -o value ${EMMC_DEVICE}p1)
    
    cat > $EMMC_MOUNT/boot/armbianEnv.txt << EOF
verbosity=1
bootlogo=false
console=both
disp_mode=1080p60
overlay_prefix=sun50i-h616
rootdev=UUID=${EMMC_UUID}
rootfstype=ext4
EOF
fi

echo -e "${GREEN}✓ armbianEnv.txt configurado${NC}"
echo ""

echo -e "${YELLOW}[6/7] Copiando initramfs...${NC}"
if [ -f "/boot/initrd.img-${KERNEL_VERSION}" ]; then
    cp -v /boot/initrd.img-${KERNEL_VERSION} $EMMC_MOUNT/boot/
    echo -e "${GREEN}✓ initramfs copiado${NC}"
elif [ -f "/boot/uInitrd" ]; then
    cp -v /boot/uInitrd $EMMC_MOUNT/boot/
    echo -e "${GREEN}✓ uInitrd copiado${NC}"
else
    echo -e "${YELLOW}⚠ initramfs não encontrado (opcional)${NC}"
fi
echo ""

echo -e "${YELLOW}[7/7] Criando boot.cmd e boot.scr...${NC}"
echo ""

# Criar script de boot compatível
cat > $EMMC_MOUNT/boot/boot.cmd << 'EOFBOOT'
# U-Boot boot script for Banana Pi M4 Zero

setenv bootargs "console=ttyS0,115200 console=tty1 root=UUID=${uuid} rootwait rootfstype=ext4 splash=verbose"

# Detectar versão do kernel
ext4ls mmc 0:1 /boot
ext4load mmc 0:1 ${kernel_addr_r} /boot/vmlinuz-5.4.125-legacy-sunxi64
ext4load mmc 0:1 ${fdt_addr_r} /boot/dtb-5.4.125-legacy-sunxi64/allwinner/sun50i-h618-bananapi-m4zero.dtb

# Boot
booti ${kernel_addr_r} - ${fdt_addr_r}
EOFBOOT

# Converter para formato U-Boot (se mkimage disponível)
if command -v mkimage &> /dev/null; then
    mkimage -C none -A arm64 -T script -d $EMMC_MOUNT/boot/boot.cmd $EMMC_MOUNT/boot/boot.scr
    echo -e "${GREEN}✓ boot.scr criado${NC}"
else
    echo -e "${YELLOW}⚠ mkimage não disponível, boot.scr não criado${NC}"
fi
echo ""

echo -e "${YELLOW}Sincronizando...${NC}"
sync
echo ""

echo -e "${YELLOW}Desmontando eMMC...${NC}"
umount $EMMC_MOUNT
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CORREÇÃO CONCLUÍDA!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "O que foi feito:"
echo "  ✓ Kernel copiado do SD para eMMC"
echo "  ✓ DTBs copiados"
echo "  ✓ armbianEnv.txt configurado com UUID correto"
echo "  ✓ Initramfs copiado (se disponível)"
echo "  ✓ boot.cmd criado"
echo ""
echo -e "${YELLOW}PRÓXIMOS PASSOS:${NC}"
echo "  1. Remova o SD card"
echo "  2. Reinicie o sistema"
echo "  3. O sistema deve bootar do eMMC"
echo ""
echo "Arquivos no eMMC /boot:"
ls -lh ${EMMC_DEVICE}p1 2>/dev/null || echo "(já desmontado)"
echo ""
echo -e "${GREEN}Pronto para testar!${NC}"
