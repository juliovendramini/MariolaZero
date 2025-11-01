#!/bin/bash
# Script para copiar U-Boot do cartão SD para eMMC
# CUIDADO: Este script sobrescreve o bootloader do eMMC!

set -e

echo "=========================================="
echo "CÓPIA DE U-BOOT: SD → eMMC"
echo "=========================================="
echo ""
echo "⚠️  ATENÇÃO: Este script irá sobrescrever o U-Boot no eMMC!"
echo "⚠️  Certifique-se de ter um backup ou outra forma de recuperação!"
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ ERRO: Execute como root (sudo bash $0)"
    exit 1
fi

# Detectar dispositivos
SD_DEVICE="/dev/mmcblk1"
EMMC_DEVICE="/dev/mmcblk2"

echo "[1] Verificando dispositivos..."
if [ ! -b "$SD_DEVICE" ]; then
    echo "❌ ERRO: Cartão SD não encontrado em $SD_DEVICE"
    echo "   Insira o cartão SD com o sistema funcionando e tente novamente."
    exit 1
fi

if [ ! -b "$EMMC_DEVICE" ]; then
    echo "❌ ERRO: eMMC não encontrado em $EMMC_DEVICE"
    exit 1
fi

echo "✅ Cartão SD: $SD_DEVICE"
echo "✅ eMMC: $EMMC_DEVICE"
echo ""

# Mostrar versões
echo "[2] Versões de U-Boot detectadas:"
echo ""
echo "U-Boot no CARTÃO SD ($SD_DEVICE):"
dd if=$SD_DEVICE bs=1 skip=8 count=64 2>/dev/null | strings | head -3 | sed 's/^/   /'
echo ""
echo "U-Boot no eMMC ($EMMC_DEVICE):"
dd if=$EMMC_DEVICE bs=1 skip=8 count=64 2>/dev/null | strings | head -3 | sed 's/^/   /'
echo ""

# Confirmação
echo "=========================================="
echo "⚠️  ÚLTIMA CONFIRMAÇÃO"
echo "=========================================="
echo ""
echo "Você está prestes a:"
echo "  - Copiar U-Boot de: $SD_DEVICE (cartão SD)"
echo "  - Para: $EMMC_DEVICE (eMMC)"
echo ""
echo "Isso irá substituir o bootloader atual do eMMC."
echo ""
read -p "Digite 'SIM' (maiúsculas) para continuar: " confirmacao

if [ "$confirmacao" != "SIM" ]; then
    echo ""
    echo "❌ Operação cancelada pelo usuário."
    exit 0
fi

echo ""
echo "[3] Fazendo backup do U-Boot atual do eMMC..."
BACKUP_DIR="/root/uboot_backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

# Backup dos primeiros 1MB do eMMC (contém U-Boot + env)
dd if=$EMMC_DEVICE of="$BACKUP_DIR/emmc_uboot_backup.img" bs=1M count=1 status=progress
echo "✅ Backup salvo em: $BACKUP_DIR/emmc_uboot_backup.img"
echo ""

echo "[4] Copiando U-Boot do cartão SD para eMMC..."
echo "   Isso pode levar alguns segundos..."
echo ""

# Copiar U-Boot (offset 8KB até ~1MB)
# Offset 8KB (16 setores de 512 bytes) é onde o U-Boot começa
# Copiamos 1016KB para não sobrescrever a tabela de partições (primeiros 8KB)
dd if=$SD_DEVICE of=$EMMC_DEVICE bs=1024 seek=8 skip=8 count=1016 conv=fsync status=progress

echo ""
echo "✅ U-Boot copiado com sucesso!"
echo ""

echo "[5] Verificando U-Boot instalado no eMMC..."
dd if=$EMMC_DEVICE bs=1 skip=8 count=64 2>/dev/null | strings | head -3 | sed 's/^/   /'
echo ""

echo "=========================================="
echo "✅ CÓPIA CONCLUÍDA COM SUCESSO!"
echo "=========================================="
echo ""
echo "Backup salvo em: $BACKUP_DIR"
echo ""
echo "Próximos passos:"
echo "1. Remova o cartão SD"
echo "2. Reinicie o sistema: reboot"
echo "3. Verifique se o boot funciona corretamente"
echo ""
echo "Se houver problemas, você pode restaurar o backup:"
echo "   dd if=$BACKUP_DIR/emmc_uboot_backup.img of=$EMMC_DEVICE bs=1M conv=fsync"
echo ""
