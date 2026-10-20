#!/bin/bash
# Script para compilar e instalar DTB com WiFi interno habilitado

set -e

echo "========================================="
echo "COMPILAÇÃO E INSTALAÇÃO DO DTB COM WiFi"
echo "========================================="
echo ""

# Verificar se o arquivo DTS existe
if [ ! -f ~/sun50i-h618-bananapi-m4-zero.dts_6.1 ]; then
    echo "ERRO: Arquivo DTS não encontrado!"
    exit 1
fi

# Compilar DTS para DTB
echo "[1/4] Compilando DTS para DTB..."
dtc -I dts -O dtb -o ~/sun50i-h618-bananapi-m4-zero-wifi.dtb ~/sun50i-h618-bananapi-m4-zero.dts_6.1

if [ $? -eq 0 ]; then
    echo "    ✓ DTB compilado com sucesso"
    ls -lh ~/sun50i-h618-bananapi-m4-zero-wifi.dtb
else
    echo "    ✗ ERRO na compilação!"
    exit 1
fi

# Backup do DTB atual
echo ""
echo "[2/4] Fazendo backup do DTB atual..."
mkdir -p /root/backup_dtb_$(date +%Y%m%d_%H%M%S)

if [ -f /boot/dtb/allwinner/sun50i-h618-bananapi-m4-zero.dtb ]; then
    cp /boot/dtb/allwinner/sun50i-h618-bananapi-m4-zero.dtb \
       /root/backup_dtb_$(date +%Y%m%d_%H%M%S)/
    echo "    ✓ Backup salvo em /root/backup_dtb_*"
else
    echo "    ! DTB original não encontrado (primeira instalação?)"
fi

# Instalar novo DTB
echo ""
echo "[3/4] Instalando novo DTB..."
mount -o remount,rw /boot 2>/dev/null || true

if [ ! -d /boot/dtb/allwinner ]; then
    mkdir -p /boot/dtb/allwinner
fi

cp ~/sun50i-h618-bananapi-m4-zero-wifi.dtb \
   /boot/dtb/allwinner/sun50i-h618-bananapi-m4-zero.dtb

echo "    ✓ DTB instalado em /boot/dtb/allwinner/"

# Verificar instalação
echo ""
echo "[4/4] Verificando instalação..."
if [ -f /boot/dtb/allwinner/sun50i-h618-bananapi-m4-zero.dtb ]; then
    ls -lh /boot/dtb/allwinner/sun50i-h618-bananapi-m4-zero.dtb
    echo ""
    echo "✓ DTB instalado com sucesso!"
else
    echo "✗ ERRO: DTB não foi instalado corretamente!"
    exit 1
fi

echo ""
echo "========================================="
echo "RECURSOS HABILITADOS NO NOVO DTB"
echo "========================================="
echo ""
echo "✓ WiFi Interno (Broadcom BCM4329)"
echo "  - Interface: mmc1 (SDIO)"
echo "  - Power Sequence: GPIO PG18"
echo "  - Clock: 32kHz RTC"
echo ""
echo "✓ Reguladores:"
echo "  - vcc-5v: 5V principal"
echo "  - vcc-1v8: 1.8V para WiFi"
echo ""
echo "========================================="
echo "PRÓXIMOS PASSOS"
echo "========================================="
echo ""
echo "1. Reinicie o sistema:"
echo "   reboot"
echo ""
echo "2. Após reiniciar, verifique se o WiFi foi detectado:"
echo "   dmesg | grep -i brcm"
echo "   dmesg | grep -i mmc1"
echo "   ip link show"
echo ""
echo "3. Caso o WiFi não apareça, verifique o firmware:"
echo "   ls /lib/firmware/brcm/"
echo ""
echo "4. Se necessário, instale o firmware manualmente:"
echo "   apt-get update"
echo "   apt-get install firmware-brcm80211"
echo ""

# Perguntar se quer reiniciar
read -p "Deseja reiniciar agora? (s/N): " resposta
if [ "$resposta" = "s" ] || [ "$resposta" = "S" ]; then
    echo "Reiniciando em 5 segundos..."
    sleep 5
    reboot
else
    echo "Sistema não reiniciado. Execute 'reboot' quando estiver pronto."
fi
