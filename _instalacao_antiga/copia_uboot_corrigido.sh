#!/bin/bash
#
# Copia U-Boot do SD card para eMMC PRESERVANDO tabela de partições
# ESPECÍFICO para Banana Pi M4 Zero
#
# Estrutura:
# - Setor 0 (MBR): PRESERVAR do eMMC (tabela de partições)
# - Setores 1-63: Copiar do SD (U-Boot SPL/bootloader)
# - Setores 64+: Copiar do SD (U-Boot principal)
#
# Uso: sudo bash copia_uboot_corrigido.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CÓPIA CORRIGIDA DO U-BOOT${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERRO: Execute como root${NC}"
    echo "Uso: sudo bash $0"
    exit 1
fi

# Detectar dispositivos automaticamente
EMMC_DEVICE=""
SD_DEVICE=""

# Verificar se mmcblk0 é eMMC (tem boot partitions)
if [ -e /dev/mmcblk0boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk0"
    SD_DEVICE="/dev/mmcblk1"
    echo -e "${GREEN}✓ Detectado: mmcblk0 = eMMC, mmcblk1 = SD${NC}"
# Verificar se mmcblk2 é eMMC
elif [ -e /dev/mmcblk2boot0 ]; then
    EMMC_DEVICE="/dev/mmcblk2"
    SD_DEVICE="/dev/mmcblk1"
    echo -e "${GREEN}✓ Detectado: mmcblk2 = eMMC, mmcblk1 = SD${NC}"
else
    echo -e "${RED}✗ Não foi possível detectar eMMC!${NC}"
    exit 1
fi

# Verificar se SD card está inserido
if [ ! -b "$SD_DEVICE" ]; then
    echo -e "${RED}✗ SD card não encontrado em $SD_DEVICE${NC}"
    echo "Insira o SD card bootável e tente novamente"
    exit 1
fi

echo ""
echo -e "${BLUE}Dispositivos detectados:${NC}"
echo "  eMMC: $EMMC_DEVICE"
echo "  SD card: $SD_DEVICE"
echo ""

echo -e "${YELLOW}[1/6] Verificando partições...${NC}"
echo ""
echo "Partições do eMMC:"
lsblk $EMMC_DEVICE -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
echo ""
echo "Partições do SD card:"
lsblk $SD_DEVICE -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINT
echo ""

# Verificar se SD está montado como root
if mount | grep -q "^${SD_DEVICE}p1 on / "; then
    echo -e "${GREEN}✓ Sistema está rodando do SD card${NC}"
elif mount | grep -q "^${EMMC_DEVICE}p1 on / "; then
    echo -e "${RED}✗ Sistema está rodando do eMMC!${NC}"
    echo "Para copiar U-Boot com segurança, você precisa:"
    echo "  1. Bootar do SD card"
    echo "  2. Executar este script"
    echo "  3. Reiniciar e bootar do eMMC"
    read -p "Deseja continuar mesmo assim? (sim/não): " resposta
    if [ "$resposta" != "sim" ]; then
        echo "Operação cancelada"
        exit 1
    fi
fi
echo ""

echo -e "${YELLOW}[2/6] Criando backup da tabela de partições do eMMC...${NC}"
BACKUP_DIR="/home/banana"
BACKUP_MBR="${BACKUP_DIR}/emmc_mbr_backup_$(date +%Y%m%d_%H%M%S).bin"

# Backup do MBR (primeiro setor - 512 bytes)
dd if=$EMMC_DEVICE of=$BACKUP_MBR bs=512 count=1 status=none
echo -e "${GREEN}✓ MBR salvo em: $BACKUP_MBR${NC}"

# Backup dos primeiros 32MB (segurança)
BACKUP_FULL="${BACKUP_DIR}/emmc_uboot_backup_$(date +%Y%m%d_%H%M%S).img"
dd if=$EMMC_DEVICE of=$BACKUP_FULL bs=1M count=32 status=none
echo -e "${GREEN}✓ Backup completo salvo em: $BACKUP_FULL${NC}"
echo ""

echo -e "${YELLOW}[3/6] Verificando U-Boot no SD card...${NC}"
# Verificar assinatura do U-Boot Allwinner (eGON.BT0)
UBOOT_SIGNATURE=$(dd if=$SD_DEVICE bs=512 skip=16 count=1 2>/dev/null | strings | head -1)
if echo "$UBOOT_SIGNATURE" | grep -q "eGON"; then
    echo -e "${GREEN}✓ U-Boot encontrado no SD: $UBOOT_SIGNATURE${NC}"
else
    echo -e "${RED}✗ Assinatura do U-Boot não encontrada no SD!${NC}"
    echo "O SD card pode não ter U-Boot válido"
    read -p "Deseja continuar mesmo assim? (sim/não): " resposta
    if [ "$resposta" != "sim" ]; then
        exit 1
    fi
fi
echo ""

echo -e "${YELLOW}[4/6] Copiando U-Boot...${NC}"
echo ""
echo -e "${BLUE}Estratégia de cópia:${NC}"
echo "  1. Preservar MBR do eMMC (setor 0)"
echo "  2. Copiar U-Boot do SD (setores 1+)"
echo ""

# Passo 1: Copiar do setor 1 em diante (pular MBR)
# Copiar 8KB-16MB (ignorando primeiros 512 bytes)
echo -e "${CYAN}Copiando U-Boot SPL e principal (8KB até 16MB)...${NC}"
dd if=$SD_DEVICE \
   of=$EMMC_DEVICE \
   bs=512 \
   skip=16 \
   seek=16 \
   count=32752 \
   conv=fsync \
   status=progress

echo ""
echo -e "${GREEN}✓ U-Boot copiado com sucesso!${NC}"
echo ""

echo -e "${YELLOW}[5/6] Verificando cópia...${NC}"

# Comparar assinatura
SD_SIG=$(dd if=$SD_DEVICE bs=512 skip=16 count=1 2>/dev/null | strings | head -1)
EMMC_SIG=$(dd if=$EMMC_DEVICE bs=512 skip=16 count=1 2>/dev/null | strings | head -1)

echo "  SD card: $SD_SIG"
echo "  eMMC: $EMMC_SIG"

if [ "$SD_SIG" = "$EMMC_SIG" ]; then
    echo -e "${GREEN}✓ Assinaturas coincidem!${NC}"
else
    echo -e "${RED}✗ AVISO: Assinaturas diferentes!${NC}"
fi
echo ""

echo -e "${YELLOW}[6/6] Verificando tabela de partições...${NC}"
parted $EMMC_DEVICE print || true
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CÓPIA CONCLUÍDA!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Backups salvos:"
echo "  MBR: $BACKUP_MBR"
echo "  Full: $BACKUP_FULL"
echo ""
echo -e "${YELLOW}PRÓXIMOS PASSOS:${NC}"
echo "  1. Remova o SD card"
echo "  2. Reinicie o sistema: sudo reboot"
echo "  3. O sistema deve bootar do eMMC com novo U-Boot"
echo ""
echo "Se algo der errado, você pode:"
echo "  - Bootar do SD card novamente"
echo "  - Restaurar o MBR: sudo dd if=$BACKUP_MBR of=$EMMC_DEVICE bs=512 count=1"
echo ""
echo -e "${GREEN}Pronto!${NC}"
