#!/bin/bash
#
# Garante que o Samba funcione após reinicialização
# Corrige permissões e reinicia serviços
#
# Uso: sudo bash garante_samba_boot.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}GARANTINDO SAMBA APÓS BOOT${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Execute como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/6] Verificando serviços...${NC}"
systemctl status smbd --no-pager | head -3
systemctl status nmbd --no-pager | head -3
echo ""

echo -e "${YELLOW}[2/6] Corrigindo permissões críticas...${NC}"
# Diretórios do Samba
mkdir -p /var/lib/samba/private
chmod 755 /var/lib/samba/private
chown -R root:root /var/lib/samba

# Diretório compartilhado
chown -R banana:banana /home/banana
chmod 755 /home/banana

echo -e "${GREEN}✓ Permissões corrigidas${NC}"
echo ""

echo -e "${YELLOW}[3/6] Recriando usuário Samba...${NC}"
# Remover e recriar usuário
smbpasswd -x banana 2>/dev/null || true
(echo ""; echo "") | smbpasswd -a -s banana
smbpasswd -e banana
echo -e "${GREEN}✓ Usuário Samba OK${NC}"
echo ""

echo -e "${YELLOW}[4/6] Reiniciando serviços...${NC}"
systemctl restart smbd nmbd
sleep 3
echo ""

echo -e "${YELLOW}[5/6] Verificando funcionamento...${NC}"
if systemctl is-active --quiet smbd && systemctl is-active --quiet nmbd; then
    echo -e "${GREEN}✓ Serviços rodando${NC}"
else
    echo -e "${RED}✗ ERRO: Serviços não iniciaram!${NC}"
    systemctl status smbd nmbd --no-pager
    exit 1
fi
echo ""

echo "Testando acesso:"
smbclient //localhost/home -U banana%"" -c "ls" 2>&1 | head -10
echo ""

echo -e "${YELLOW}[6/6] Habilitando início automático...${NC}"
systemctl enable smbd
systemctl enable nmbd
echo -e "${GREEN}✓ Serviços habilitados para iniciar no boot${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SAMBA FUNCIONANDO!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "No Windows, acesse:"
echo "  \\\\192.168.2.167\\home"
echo ""
echo "Usuário: banana"
echo "Senha: (vazio)"
