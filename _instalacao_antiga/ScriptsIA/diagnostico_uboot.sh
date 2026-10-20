#!/bin/bash
# Script para diagnosticar U-Boot e DTB

echo "=========================================="
echo "DIAGNÓSTICO U-BOOT E DTB"
echo "=========================================="
echo ""

echo "[1] Verificando versão do U-Boot no eMMC..."
dd if=/dev/mmcblk2 bs=1 skip=8 count=64 2>/dev/null | strings | head -3
echo ""

echo "[2] Verificando arquivos DTB no /boot..."
ls -lh /boot/*.dtb 2>/dev/null || echo "Nenhum DTB encontrado!"
ls -lh /boot/dtb/ 2>/dev/null || echo "Diretório dtb/ não existe!"
ls -lh /boot/dtb/allwinner/*.dtb 2>/dev/null || echo "DTBs Allwinner não encontrados!"
echo ""

echo "[3] Verificando armbianEnv.txt..."
cat /boot/armbianEnv.txt
echo ""

echo "[4] Verificando dispositivos de boot..."
lsblk -o NAME,SIZE,TYPE,MOUNTPOINT | grep -E "mmcblk|boot"
echo ""

echo "[5] Verificando kernel atual..."
uname -r
ls -lh /boot/vmlinuz* 2>/dev/null
ls -lh /boot/uInitrd* 2>/dev/null
echo ""

echo "[6] Verificando se há U-Boot no cartão SD..."
if [ -b /dev/mmcblk1 ]; then
    echo "Cartão SD detectado em /dev/mmcblk1"
    dd if=/dev/mmcblk1 bs=1 skip=8 count=64 2>/dev/null | strings | head -3
else
    echo "Cartão SD NÃO detectado"
fi
echo ""

echo "=========================================="
echo "FIM DO DIAGNÓSTICO"
echo "=========================================="
