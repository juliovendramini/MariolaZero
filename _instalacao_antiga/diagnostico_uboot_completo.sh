#!/bin/bash
#
# Diagnóstico completo de U-Boot e partições
# Para entender o que aconteceu
#

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}DIAGNÓSTICO U-BOOT E PARTIÇÕES${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Detectar dispositivos
EMMC_DEVICE=""
SD_DEVICE=""

if [ -e /dev/mmcblk0boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk0"
    SD_DEVICE="/dev/mmcblk1"
elif [ -e /dev/mmcblk2boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk2"
    SD_DEVICE="/dev/mmcblk1"
fi

echo -e "${BLUE}[1] Dispositivos de armazenamento:${NC}"
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
echo ""

echo -e "${BLUE}[2] De onde o sistema bootou:${NC}"
if mount | grep "^${SD_DEVICE}p1 on / "; then
    echo -e "${GREEN}✓ Bootou do SD CARD${NC}"
elif mount | grep "^${EMMC_DEVICE}p1 on / "; then
    echo -e "${GREEN}✓ Bootou do eMMC${NC}"
else
    echo -e "${YELLOW}⚠ Não foi possível determinar${NC}"
fi
mount | grep " on / "
echo ""

if [ -n "$EMMC_DEVICE" ]; then
    echo -e "${BLUE}[3] Tabela de partições do eMMC ($EMMC_DEVICE):${NC}"
    sudo parted $EMMC_DEVICE unit s print 2>/dev/null || echo "Erro ao ler"
    echo ""
    
    echo -e "${BLUE}[4] Assinatura U-Boot no eMMC (setor 16 = 8KB):${NC}"
    sudo dd if=$EMMC_DEVICE bs=512 skip=16 count=1 2>/dev/null | strings | head -3
    echo ""
    
    echo -e "${BLUE}[5] MBR do eMMC (primeiros 512 bytes):${NC}"
    sudo dd if=$EMMC_DEVICE bs=512 count=1 2>/dev/null | hexdump -C | grep -E "(000001b0|000001c0|000001d0)" | head -4
    echo ""
fi

if [ -b "$SD_DEVICE" ]; then
    echo -e "${BLUE}[6] Tabela de partições do SD ($SD_DEVICE):${NC}"
    sudo parted $SD_DEVICE unit s print 2>/dev/null || echo "SD não inserido"
    echo ""
    
    echo -e "${BLUE}[7] Assinatura U-Boot no SD (setor 16 = 8KB):${NC}"
    sudo dd if=$SD_DEVICE bs=512 skip=16 count=1 2>/dev/null | strings | head -3 || echo "SD não inserido"
    echo ""
else
    echo -e "${YELLOW}[6-7] SD card não inserido${NC}"
    echo ""
fi

echo -e "${BLUE}[8] Versão do kernel:${NC}"
uname -r
echo ""

echo -e "${BLUE}[9] Arquivos DTB disponíveis:${NC}"
ls -lh /boot/dtb*/allwinner/sun50i-h618-* 2>/dev/null | head -10 || echo "Nenhum DTB encontrado"
echo ""

echo -e "${BLUE}[10] Configuração do boot (armbianEnv.txt):${NC}"
cat /boot/armbianEnv.txt 2>/dev/null || echo "Arquivo não encontrado"
echo ""

echo -e "${BLUE}[11] Logs do boot (dmesg - primeiras 50 linhas):${NC}"
dmesg | head -50
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}FIM DO DIAGNÓSTICO${NC}"
echo -e "${GREEN}========================================${NC}"
