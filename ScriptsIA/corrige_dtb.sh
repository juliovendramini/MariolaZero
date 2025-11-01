#!/bin/bash
# Script para copiar DTBs do kernel vendor 5.4.125 para /boot

set -e

echo "=========================================="
echo "CORREÇÃO DE DTB - Kernel Vendor 5.4.125"
echo "=========================================="
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ ERRO: Execute como root (sudo bash $0)"
    exit 1
fi

echo "[1] Verificando se a imagem vendor está montada..."

MOUNT_DIR="/tmp/vendor_mount"
IMG_FILE="/tmp/vendor_kernel.img"

# Se a imagem ainda existe, vamos usá-la
if [ -f "$IMG_FILE" ]; then
    echo "✅ Imagem vendor encontrada: $IMG_FILE"
else
    echo "❌ Imagem vendor não encontrada."
    echo "   Por favor, transfira novamente a imagem:"
    echo "   scp <imagem.img> root@192.168.2.151:/tmp/vendor_kernel.img"
    exit 1
fi

# Montar se ainda não estiver montado
if ! mountpoint -q "$MOUNT_DIR" 2>/dev/null; then
    echo "[2] Montando imagem vendor..."
    mkdir -p "$MOUNT_DIR"
    
    # Detectar offset da partição root
    OFFSET=$(fdisk -l "$IMG_FILE" | grep "Linux" | grep -v "swap" | awk '{print $2}')
    OFFSET_BYTES=$((OFFSET * 512))
    
    echo "   Offset da partição: $OFFSET setores ($OFFSET_BYTES bytes)"
    mount -o loop,offset=$OFFSET_BYTES "$IMG_FILE" "$MOUNT_DIR"
    echo "✅ Imagem montada em $MOUNT_DIR"
else
    echo "✅ Imagem já está montada em $MOUNT_DIR"
fi
echo ""

echo "[3] Verificando DTBs disponíveis na imagem vendor..."
if [ -d "$MOUNT_DIR/boot/dtb" ]; then
    echo "✅ Diretório dtb/ encontrado"
    ls -lh "$MOUNT_DIR/boot/dtb/allwinner/" | grep "\.dtb$"
elif [ -d "$MOUNT_DIR/boot/dtb-5.4.125-legacy-sunxi64" ]; then
    echo "✅ Diretório dtb-5.4.125-legacy-sunxi64 encontrado"
    ls -lh "$MOUNT_DIR/boot/dtb-5.4.125-legacy-sunxi64/allwinner/" | grep "\.dtb$"
else
    echo "❌ Diretório de DTBs não encontrado!"
    echo "   Estrutura de /boot na imagem:"
    ls -la "$MOUNT_DIR/boot/"
    umount "$MOUNT_DIR" 2>/dev/null
    exit 1
fi
echo ""

echo "[4] Copiando DTBs para /boot..."

# Criar diretório de DTB se não existir
mkdir -p /boot/dtb/allwinner
mkdir -p /boot/dtb-5.4.125-legacy-sunxi64/allwinner

# Copiar DTBs
if [ -d "$MOUNT_DIR/boot/dtb/allwinner" ]; then
    echo "   Copiando de $MOUNT_DIR/boot/dtb/allwinner/..."
    cp -v "$MOUNT_DIR/boot/dtb/allwinner"/*.dtb /boot/dtb/allwinner/
    
    # Copiar também para o diretório versionado
    cp -v "$MOUNT_DIR/boot/dtb/allwinner"/*.dtb /boot/dtb-5.4.125-legacy-sunxi64/allwinner/
fi

if [ -d "$MOUNT_DIR/boot/dtb-5.4.125-legacy-sunxi64/allwinner" ]; then
    echo "   Copiando de $MOUNT_DIR/boot/dtb-5.4.125-legacy-sunxi64/allwinner/..."
    cp -v "$MOUNT_DIR/boot/dtb-5.4.125-legacy-sunxi64/allwinner"/*.dtb /boot/dtb-5.4.125-legacy-sunxi64/allwinner/
    
    # Copiar também para o diretório padrão
    cp -v "$MOUNT_DIR/boot/dtb-5.4.125-legacy-sunxi64/allwinner"/*.dtb /boot/dtb/allwinner/
fi

echo "✅ DTBs copiados com sucesso!"
echo ""

echo "[5] Procurando DTB específico para Banana Pi M4 Zero..."
DTB_CANDIDATES=(
    "sun50i-h618-orangepi-zero3.dtb"
    "sun50i-h618-bananapi-m4-zero.dtb"
    "sun50i-h616-orangepi-zero2.dtb"
)

DTB_FOUND=""
for dtb in "${DTB_CANDIDATES[@]}"; do
    if [ -f "/boot/dtb/allwinner/$dtb" ]; then
        echo "✅ DTB encontrado: $dtb"
        DTB_FOUND="$dtb"
        break
    fi
done

if [ -z "$DTB_FOUND" ]; then
    echo "⚠️  DTB específico não encontrado. DTBs disponíveis:"
    ls -1 /boot/dtb/allwinner/*.dtb
    echo ""
    echo "Escolha manualmente o DTB correto editando /boot/armbianEnv.txt"
else
    echo ""
    echo "[6] Atualizando armbianEnv.txt..."
    
    # Backup do armbianEnv.txt
    cp /boot/armbianEnv.txt /boot/armbianEnv.txt.backup_$(date +%Y%m%d_%H%M%S)
    
    # Atualizar fdtfile
    if grep -q "^fdtfile=" /boot/armbianEnv.txt; then
        sed -i "s|^fdtfile=.*|fdtfile=allwinner/$DTB_FOUND|" /boot/armbianEnv.txt
        echo "✅ fdtfile atualizado para: allwinner/$DTB_FOUND"
    else
        echo "fdtfile=allwinner/$DTB_FOUND" >> /boot/armbianEnv.txt
        echo "✅ fdtfile adicionado: allwinner/$DTB_FOUND"
    fi
fi
echo ""

echo "[7] Verificando configuração final..."
echo ""
echo "Conteúdo de /boot/armbianEnv.txt:"
cat /boot/armbianEnv.txt
echo ""

echo "[8] DTBs instalados em /boot/dtb/allwinner/:"
ls -lh /boot/dtb/allwinner/*.dtb
echo ""

echo "[9] Desmontando imagem vendor..."
umount "$MOUNT_DIR"
rmdir "$MOUNT_DIR"
echo "✅ Imagem desmontada"
echo ""

echo "=========================================="
echo "✅ CORREÇÃO DE DTB CONCLUÍDA!"
echo "=========================================="
echo ""
echo "Próximos passos:"
echo "1. Verifique /boot/armbianEnv.txt se necessário"
echo "2. Reinicie o sistema: reboot"
echo "3. Verifique se o boot funciona: dmesg | grep -i dtb"
echo ""
