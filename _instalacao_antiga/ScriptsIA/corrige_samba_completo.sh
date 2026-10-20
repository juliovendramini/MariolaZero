#!/bin/bash
#
# Script para corrigir COMPLETAMENTE o acesso do Samba aos subdiretórios
# Corrige permissões, ownership, e configuração do Samba
#
# Uso: sudo bash corrige_samba_completo.sh
#

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Script de Correção COMPLETA do Samba${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERRO: Este script precisa ser executado como root${NC}"
    echo "Use: sudo bash $0"
    exit 1
fi

# Verificar se o usuário banana existe
if ! id "banana" &>/dev/null; then
    echo -e "${RED}ERRO: Usuário 'banana' não existe${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/8] Diagnóstico inicial...${NC}"
echo ""
echo "Estrutura atual de /home/banana:"
ls -la /home/banana | head -20
echo ""

echo -e "${YELLOW}[2/8] Corrigindo ownership RECURSIVAMENTE...${NC}"
chown -R banana:banana /home/banana
echo -e "${GREEN}✓ Ownership corrigido${NC}"
echo ""

echo -e "${YELLOW}[3/8] Corrigindo permissões de diretórios...${NC}"
# Diretórios: 755 (rwxr-xr-x)
find /home/banana -type d -exec chmod 755 {} \;
echo -e "${GREEN}✓ Permissões de diretórios: 755${NC}"
echo ""

echo -e "${YELLOW}[4/8] Corrigindo permissões de arquivos...${NC}"
# Arquivos regulares: 644 (rw-r--r--)
find /home/banana -type f -exec chmod 644 {} \;
echo -e "${GREEN}✓ Permissões de arquivos: 644${NC}"
echo ""

echo -e "${YELLOW}[5/8] Corrigindo permissões de scripts...${NC}"
# Scripts Python e Shell: 755 (rwxr-xr-x)
find /home/banana -type f \( -name "*.py" -o -name "*.sh" \) -exec chmod 755 {} \;
echo -e "${GREEN}✓ Permissões de scripts: 755${NC}"
echo ""

echo -e "${YELLOW}[6/8] Verificando configuração do Samba...${NC}"
echo ""
echo "Configuração atual da seção [home]:"
sed -n '/\[home\]/,/^$/p' /etc/samba/smb.conf
echo ""

echo -e "${YELLOW}[7/8] Criando backup e aplicando nova configuração...${NC}"
# Backup da configuração atual
cp /etc/samba/smb.conf /etc/samba/smb.conf.backup.$(date +%Y%m%d_%H%M%S)

# Remover seção [home] antiga se existir
sed -i '/\[home\]/,/^$/d' /etc/samba/smb.conf

# Adicionar nova configuração otimizada
cat >> /etc/samba/smb.conf << 'EOF'

[home]
   comment = Pasta Home do Usuario Banana
   path = /home/banana
   browseable = yes
   writable = yes
   guest ok = yes
   read only = no
   create mask = 0664
   directory mask = 0775
   force user = banana
   force group = banana
   
   # Permitir acesso aos subdiretórios
   follow symlinks = yes
   wide links = yes
   unix extensions = no
   
   # Opções de compatibilidade
   vfs objects = acl_xattr
   map acl inherit = yes
   store dos attributes = yes

EOF

echo -e "${GREEN}✓ Configuração do Samba atualizada${NC}"
echo ""

echo -e "${YELLOW}[8/8] Reiniciando serviços do Samba...${NC}"
systemctl restart smbd
systemctl restart nmbd
sleep 2
echo -e "${GREEN}✓ Serviços reiniciados${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VERIFICAÇÃO FINAL${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo "Status dos serviços:"
systemctl status smbd --no-pager -l | head -10
echo ""
systemctl status nmbd --no-pager -l | head -10
echo ""

echo "Permissões de alguns subdiretórios:"
find /home/banana -maxdepth 2 -type d -exec ls -ld {} \; | head -20
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TESTE DE ACESSO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Para testar o acesso do Samba, no Windows:"
echo "1. Abra o Explorador de Arquivos"
echo "2. Digite na barra de endereço: \\\\192.168.2.181\\home"
echo "3. Tente acessar os subdiretórios"
echo ""
echo "Se ainda tiver problemas, verifique:"
echo "  - Firewall do Banana Pi: sudo ufw status"
echo "  - SELinux/AppArmor: getenforce ou aa-status"
echo "  - Logs do Samba: tail -50 /var/log/samba/log.smbd"
echo ""
echo -e "${GREEN}Correção concluída!${NC}"
