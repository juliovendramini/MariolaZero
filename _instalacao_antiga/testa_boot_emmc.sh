#!/bin/bash
#
# Testa se eMMC consegue bootar
# Executa enquanto está no SD card
#

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TESTE DE BOOT DO eMMC${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Detectar eMMC
EMMC_DEVICE=""
if [ -e /dev/mmcblk0boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk0"
elif [ -e /dev/mmcblk2boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk2"
else
    echo -e "${RED}✗ eMMC não encontrado!${NC}"
    exit 1
fi

echo -e "${YELLOW}[1] Verificando U-Boot no eMMC...${NC}"
echo ""

# Verificar assinatura
SIGNATURE=$(sudo dd if=$EMMC_DEVICE bs=512 skip=16 count=1 2>/dev/null | strings | head -2)
echo "Assinatura encontrada:"
echo "$SIGNATURE"
echo ""

if echo "$SIGNATURE" | grep -q "eGON"; then
    echo -e "${GREEN}✓ U-Boot encontrado!${NC}"
else
    echo -e "${RED}✗ U-Boot não encontrado ou corrompido!${NC}"
    exit 1
fi

echo ""
echo -e "${YELLOW}[2] Verificando partições do eMMC...${NC}"
sudo parted $EMMC_DEVICE print
echo ""

echo -e "${YELLOW}[3] Verificando se partições têm sistema de arquivos...${NC}"
sudo blkid ${EMMC_DEVICE}p1
sudo blkid ${EMMC_DEVICE}p2 2>/dev/null || echo "Partição 2 sem filesystem"
echo ""

echo -e "${YELLOW}[4] Montando partição 1 do eMMC para verificar conteúdo...${NC}"
MOUNT_POINT="/tmp/emmc_test"
sudo mkdir -p $MOUNT_POINT
sudo mount ${EMMC_DEVICE}p1 $MOUNT_POINT 2>/dev/null

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Partição montada com sucesso${NC}"
    echo ""
    echo "Conteúdo da partição:"
    ls -lah $MOUNT_POINT | head -20
    echo ""
    
    echo "Verificando arquivos críticos:"
    if [ -d "$MOUNT_POINT/boot" ]; then
        echo -e "${GREEN}✓ Diretório /boot existe${NC}"
        echo ""
        echo "DTBs disponíveis:"
        find $MOUNT_POINT/boot -name "*h618*" -o -name "*m4*" 2>/dev/null | head -5
        echo ""
        echo "Kernels disponíveis:"
        ls -lh $MOUNT_POINT/boot/vmlinuz* 2>/dev/null
    else
        echo -e "${RED}✗ Diretório /boot não encontrado!${NC}"
    fi
    
    echo ""
    if [ -f "$MOUNT_POINT/boot/armbianEnv.txt" ]; then
        echo -e "${GREEN}✓ armbianEnv.txt encontrado${NC}"
        echo ""
        cat $MOUNT_POINT/boot/armbianEnv.txt
    else
        echo -e "${RED}✗ armbianEnv.txt não encontrado!${NC}"
    fi
    
    sudo umount $MOUNT_POINT
else
    echo -e "${RED}✗ Não foi possível montar a partição${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CONCLUSÃO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Para testar o boot do eMMC:"
echo "  1. Remova o SD card fisicamente"
echo "  2. Reinicie: sudo poweroff"
echo "  3. Remova SD"
echo "  4. Ligue o sistema"
echo ""
echo "Se não bootar, você pode:"
echo "  - Inserir o SD card novamente"
echo "  - Bootar do SD"
echo "  - Investigar o problema"
