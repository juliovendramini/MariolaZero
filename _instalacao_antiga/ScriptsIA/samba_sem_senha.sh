#!/bin/bash
#
# Remove COMPLETAMENTE autenticação do Samba
# Deixa totalmente público sem pedir usuário/senha
#
# Uso: sudo bash samba_sem_senha.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SAMBA TOTALMENTE PÚBLICO (SEM SENHA)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERRO: Execute como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/6] Parando serviços...${NC}"
systemctl stop smbd nmbd
sleep 2
echo -e "${GREEN}✓ Serviços parados${NC}"
echo ""

echo -e "${YELLOW}[2/6] Criando configuração TOTALMENTE PÚBLICA...${NC}"
cat > /etc/samba/smb.conf << 'EOF'
[global]
   workgroup = WORKGROUP
   server string = Banana Pi
   netbios name = BANANAPI
   
   # SEM AUTENTICAÇÃO
   security = user
   map to guest = Bad User
   guest account = banana
   
   # SEM RESTRIÇÕES
   unix extensions = no
   follow symlinks = yes
   wide links = yes
   unix charset = UTF-8
   
   # Logs para debug
   log level = 2
   log file = /var/log/samba/log.%m
   max log size = 50

[home]
   comment = Pasta Home Banana - ACESSO LIVRE
   path = /home/banana
   browseable = yes
   
   # TOTALMENTE PÚBLICO
   public = yes
   guest ok = yes
   guest only = yes
   
   # SEM RESTRIÇÕES DE ESCRITA
   read only = no
   writable = yes
   
   # PERMISSÕES TOTALMENTE ABERTAS
   create mask = 0777
   directory mask = 0777
   force create mode = 0777
   force directory mode = 0777
   
   # FORÇA USAR USUÁRIO BANANA
   force user = banana
   force group = banana
   
   # SEM VALIDAÇÃO
   valid users = 
   invalid users = 
   write list = 

EOF
echo -e "${GREEN}✓ Configuração criada${NC}"
echo ""

echo -e "${YELLOW}[3/6] Liberando permissões de /home/banana...${NC}"
chown -R banana:banana /home/banana
chmod -R 777 /home/banana
echo -e "${GREEN}✓ Permissões 777 aplicadas${NC}"
echo ""

echo -e "${YELLOW}[4/6] Configurando usuário guest...${NC}"
# Garantir que banana existe no sistema
if ! id "banana" &>/dev/null; then
    echo -e "${RED}Usuário banana não existe no sistema!${NC}"
    exit 1
fi

# Remover TODOS os usuários Samba
pdbedit -L 2>/dev/null | cut -d: -f1 | while read user; do
    smbpasswd -x "$user" 2>/dev/null || true
done

# Adicionar banana com senha VAZIA
echo -e "\n" | smbpasswd -a -s banana
smbpasswd -e banana

echo -e "${GREEN}✓ Usuário guest configurado${NC}"
echo ""

echo -e "${YELLOW}[5/6] Testando configuração...${NC}"
testparm -s 2>&1 | head -20
echo ""

echo -e "${YELLOW}[6/6] Reiniciando serviços...${NC}"
systemctl restart smbd nmbd
sleep 3
echo -e "${GREEN}✓ Serviços reiniciados${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VERIFICAÇÃO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

systemctl status smbd --no-pager | head -5
echo ""
systemctl status nmbd --no-pager | head -5
echo ""

echo "Compartilhamentos disponíveis:"
smbclient -L localhost -N 2>&1 | grep -A 15 "Sharename"
echo ""

echo "Testando acesso como guest:"
smbclient //localhost/home -N -c "ls" 2>&1 | head -10
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}COMO ACESSAR DO WINDOWS${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "1. No Explorador de Arquivos, digite:"
echo "   \\\\192.168.2.167\\home"
echo ""
echo "2. Se pedir usuário/senha, deixe AMBOS EM BRANCO"
echo "   ou use:"
echo "   Usuário: (vazio)"
echo "   Senha: (vazio)"
echo ""
echo "3. Se continuar pedindo, tente:"
echo "   Usuário: banana"
echo "   Senha: (vazio - apenas pressione Enter)"
echo ""
echo -e "${GREEN}Configuração concluída!${NC}"
