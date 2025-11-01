#!/bin/bash
# Script mestre para migrar para kernel vendor 5.4.125
# Inclui U-Boot, kernel, módulos e DTB

set -e

echo "=========================================="
echo "MIGRAÇÃO COMPLETA PARA KERNEL VENDOR 5.4"
echo "=========================================="
echo ""
echo "Este script irá:"
echo "  1. Diagnosticar o sistema atual"
echo "  2. Copiar U-Boot do cartão SD para eMMC (OPCIONAL)"
echo "  3. Instalar kernel vendor 5.4.125"
echo "  4. Corrigir configuração de DTB"
echo ""
read -p "Pressione ENTER para continuar ou Ctrl+C para cancelar..."
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then 
    echo "❌ ERRO: Execute como root (sudo bash $0)"
    exit 1
fi

# ETAPA 1: Diagnóstico
echo "=========================================="
echo "ETAPA 1/4: DIAGNÓSTICO"
echo "=========================================="
bash diagnostico_uboot.sh
echo ""
read -p "Pressione ENTER para continuar..."
echo ""

# ETAPA 2: Copiar U-Boot (OPCIONAL)
echo "=========================================="
echo "ETAPA 2/4: U-BOOT (OPCIONAL)"
echo "=========================================="
echo ""
echo "Deseja copiar o U-Boot do cartão SD para o eMMC?"
echo "⚠️  Isso é recomendado se o U-Boot atual não consegue"
echo "   carregar o kernel vendor 5.4.125"
echo ""
read -p "Copiar U-Boot? (s/N): " resposta

if [[ "$resposta" =~ ^[Ss]$ ]]; then
    bash copia_uboot_sd_emmc.sh
else
    echo "⏭️  Pulando cópia de U-Boot"
fi
echo ""
read -p "Pressione ENTER para continuar..."
echo ""

# ETAPA 3: Verificar se kernel já foi instalado
echo "=========================================="
echo "ETAPA 3/4: KERNEL VENDOR 5.4.125"
echo "=========================================="
echo ""

if [ -f "/boot/vmlinuz-5.4.125-legacy-sunxi64" ]; then
    echo "✅ Kernel vendor 5.4.125 já está instalado"
    ls -lh /boot/vmlinuz-5.4.125-legacy-sunxi64
    ls -lh /boot/uInitrd-5.4.125-legacy-sunxi64
else
    echo "⚠️  Kernel vendor 5.4.125 NÃO está instalado"
    echo ""
    echo "Por favor, execute o script de instalação do kernel primeiro:"
    echo "  PowerShell: .\\install_vendor_kernel_simple.ps1"
    echo "Ou transfira a imagem manualmente."
    echo ""
    read -p "Kernel já foi instalado manualmente? (s/N): " kernel_ok
    
    if [[ ! "$kernel_ok" =~ ^[Ss]$ ]]; then
        echo "❌ Instale o kernel primeiro e execute este script novamente"
        exit 1
    fi
fi
echo ""
read -p "Pressione ENTER para continuar..."
echo ""

# ETAPA 4: Corrigir DTB
echo "=========================================="
echo "ETAPA 4/4: CONFIGURAÇÃO DTB"
echo "=========================================="
bash corrige_dtb.sh
echo ""

# Resumo Final
echo "=========================================="
echo "✅ MIGRAÇÃO CONCLUÍDA!"
echo "=========================================="
echo ""
echo "Configuração final:"
echo ""
echo "Kernel instalado:"
ls -lh /boot/vmlinuz-5.4.125-legacy-sunxi64
echo ""
echo "InitRD instalado:"
ls -lh /boot/uInitrd-5.4.125-legacy-sunxi64
echo ""
echo "DTB configurado:"
grep "fdtfile=" /boot/armbianEnv.txt
echo ""
echo "Módulos instalados:"
ls -d /lib/modules/5.4.125-legacy-sunxi64
echo ""

if [ -b /dev/mmcblk1 ]; then
    echo "⚠️  IMPORTANTE: Remova o cartão SD antes de reiniciar!"
    echo "   (O cartão SD está em /dev/mmcblk1)"
    echo ""
    read -p "Cartão SD removido? Pressione ENTER após remover..."
fi

echo ""
echo "Pronto para reiniciar!"
echo ""
read -p "Reiniciar agora? (s/N): " reboot_now

if [[ "$reboot_now" =~ ^[Ss]$ ]]; then
    echo ""
    echo "Reiniciando em 3 segundos..."
    sleep 1
    echo "2..."
    sleep 1
    echo "1..."
    sleep 1
    reboot
else
    echo ""
    echo "Para reiniciar manualmente: reboot"
    echo ""
    echo "Após reiniciar, verifique:"
    echo "  uname -r  (deve mostrar: 5.4.125-legacy-sunxi64)"
    echo "  dmesg | grep -i emac  (verificar ethernet interno)"
fi
