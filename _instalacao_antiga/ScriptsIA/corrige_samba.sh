#!/bin/bash
# Script para diagnosticar e corrigir permissões do Samba

echo "=========================================="
echo "DIAGNÓSTICO E CORREÇÃO - SAMBA"
echo "=========================================="
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then 
    echo "Execute como root: sudo bash $0"
    exit 1
fi

SHARE_PATH="/home/banana"

echo "[1] Verificando estrutura de diretórios..."
ls -laR "$SHARE_PATH" | head -50
echo ""

echo "[2] Verificando propriedade e permissões..."
echo "Propriedade de $SHARE_PATH:"
ls -ld "$SHARE_PATH"
echo ""
echo "Primeiras subpastas:"
find "$SHARE_PATH" -maxdepth 2 -type d -exec ls -ld {} \; | head -20
echo ""

echo "[3] Verificando configuração do Samba..."
cat /etc/samba/smb.conf | grep -A 10 "\[home\]"
echo ""

echo "[4] Verificando usuário Samba..."
pdbedit -L | grep banana
echo ""

echo "[5] Aplicando correções..."
echo ""

# Correção 1: Ajustar propriedade recursivamente
echo "  [5.1] Ajustando propriedade para banana:banana..."
chown -R banana:banana "$SHARE_PATH"
echo "  OK"

# Correção 2: Ajustar permissões recursivamente
echo "  [5.2] Ajustando permissões (755 para pastas, 644 para arquivos)..."
find "$SHARE_PATH" -type d -exec chmod 755 {} \;
find "$SHARE_PATH" -type f -exec chmod 644 {} \;
echo "  OK"

# Correção 3: Dar permissão de execução em scripts
echo "  [5.3] Dando permissão de execução para scripts .sh e .py..."
find "$SHARE_PATH" -type f \( -name "*.sh" -o -name "*.py" \) -exec chmod 755 {} \;
echo "  OK"

echo ""
echo "[6] Verificando após correções..."
ls -la "$SHARE_PATH" | head -20
echo ""

echo "[7] Reiniciando serviço Samba..."
systemctl restart smbd
systemctl restart nmbd
echo "  Status do Samba:"
systemctl status smbd --no-pager | head -10
echo ""

echo "=========================================="
echo "CORREÇÃO CONCLUÍDA!"
echo "=========================================="
echo ""
echo "Teste o acesso agora pelo Windows:"
echo "  \\\\192.168.2.181\\home"
echo ""
echo "Se ainda houver problemas, verifique:"
echo "  1. Firewall: sudo ufw status"
echo "  2. Logs do Samba: sudo tail -50 /var/log/samba/log.smbd"
echo ""
