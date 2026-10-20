#!/bin/bash
#
# Configuração FUNCIONAL do Samba (sem wide links)
#
# Uso: sudo bash samba_funcional_final.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CONFIGURAÇÃO FUNCIONAL FINAL${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo "Execute como root: sudo bash $0"
    exit 1
fi

echo -e "${YELLOW}[1/4] Parando serviços...${NC}"
systemctl stop smbd nmbd
sleep 2
echo ""

echo -e "${YELLOW}[2/4] Criando configuração SEM wide links...${NC}"
cat > /etc/samba/smb.conf << 'EOF'
[global]
   workgroup = WORKGROUP
   server string = Banana Pi M4 Zero
   netbios name = BANANAPI
   
   # Autenticação guest
   security = user
   map to guest = Bad User
   guest account = banana
   
   # Permitir protocolos antigos
   client min protocol = CORE
   server min protocol = NT1
   
   # SEM wide links (módulo não existe)
   unix extensions = no
   follow symlinks = yes
   
   # Logs
   log level = 2
   log file = /var/log/samba/log.%m
   max log size = 1000

[home]
   comment = Home Banana
   path = /home/banana
   browseable = yes
   
   # Acesso público
   public = yes
   guest ok = yes
   guest only = yes
   
   # Escrita permitida
   read only = no
   writable = yes
   
   # Permissões abertas
   create mask = 0777
   directory mask = 0777
   force create mode = 0777
   force directory mode = 0777
   
   # Forçar usuário
   force user = banana
   force group = banana

EOF
echo -e "${GREEN}✓ Configuração criada${NC}"
echo ""

echo -e "${YELLOW}[3/4] Testando sintaxe...${NC}"
testparm -s /etc/samba/smb.conf
echo ""

echo -e "${YELLOW}[4/4] Iniciando serviços...${NC}"
systemctl start smbd nmbd
sleep 3
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VERIFICAÇÃO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

systemctl status smbd --no-pager | head -5
echo ""

echo "Listando compartilhamentos:"
smbclient -L localhost -N 2>&1
echo ""

echo "Testando acesso ao home:"
smbclient //localhost/home -N -c "ls" 2>&1 | head -15
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}ACESSE NO WINDOWS:${NC}"
echo "  \\\\192.168.2.167\\home"
echo -e "${GREEN}========================================${NC}"
