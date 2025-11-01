#!/bin/bash
#
# Corrige banco de dados de senhas e recria compartilhamento
#
# Uso: sudo bash corrige_permissoes_samba.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CORREÇÃO DE PERMISSÕES DO SAMBA${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERRO: Execute como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/7] Parando serviços...${NC}"
systemctl stop smbd nmbd
sleep 2
echo ""

echo -e "${YELLOW}[2/7] Corrigindo permissões do banco de dados Samba...${NC}"
# Criar diretório se não existir
mkdir -p /var/lib/samba/private
chmod 755 /var/lib/samba/private

# Remover arquivos antigos corrompidos
rm -f /var/lib/samba/private/passdb.tdb*
rm -f /var/lib/samba/*.tdb

# Corrigir ownership
chown -R root:root /var/lib/samba
chmod -R 755 /var/lib/samba

echo -e "${GREEN}✓ Permissões corrigidas${NC}"
echo ""

echo -e "${YELLOW}[3/7] Recriando configuração limpa...${NC}"
cat > /etc/samba/smb.conf << 'EOF'
[global]
   workgroup = WORKGROUP
   server string = Banana Pi M4 Zero
   netbios name = BANANAPI
   
   # Autenticação guest
   security = user
   map to guest = Bad User
   guest account = banana
   
   # Permitir protocolos antigos (compatibilidade Windows)
   client min protocol = CORE
   server min protocol = NT1
   
   # Sem restrições Unix
   unix extensions = no
   follow symlinks = yes
   wide links = yes
   
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

echo -e "${YELLOW}[4/7] Testando sintaxe...${NC}"
if testparm -s /etc/samba/smb.conf > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Sintaxe OK${NC}"
else
    echo -e "${RED}✗ Erro na configuração!${NC}"
    testparm -s /etc/samba/smb.conf
    exit 1
fi
echo ""

echo -e "${YELLOW}[5/7] Recriando banco de usuários...${NC}"
# Inicializar banco de dados vazio
pdbedit -L > /dev/null 2>&1 || true

# Adicionar usuário banana
(echo ""; echo "") | smbpasswd -a -s banana 2>/dev/null || true
smbpasswd -e banana 2>/dev/null || true

echo -e "${GREEN}✓ Banco de usuários criado${NC}"
echo ""

echo -e "${YELLOW}[6/7] Corrigindo permissões de /home/banana...${NC}"
chown -R banana:banana /home/banana
chmod 755 /home/banana
find /home/banana -type d -exec chmod 755 {} \;
find /home/banana -type f -exec chmod 644 {} \;
echo -e "${GREEN}✓ Permissões ajustadas${NC}"
echo ""

echo -e "${YELLOW}[7/7] Iniciando serviços...${NC}"
systemctl start smbd nmbd
sleep 3

if systemctl is-active --quiet smbd && systemctl is-active --quiet nmbd; then
    echo -e "${GREEN}✓ Serviços iniciados com sucesso${NC}"
else
    echo -e "${RED}✗ Erro ao iniciar serviços!${NC}"
    systemctl status smbd nmbd --no-pager
    exit 1
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TESTES${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo "Listando compartilhamentos:"
smbclient -L localhost -N 2>&1 | grep -A 10 "Sharename" || echo "Erro ao listar"
echo ""

echo "Testando acesso ao compartilhamento home:"
smbclient //localhost/home -N -c "ls" 2>&1 | head -10
echo ""

echo "Usuários Samba:"
pdbedit -L 2>&1
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}PRONTO PARA TESTAR!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "No Windows, acesse:"
echo "  \\\\192.168.2.167\\home"
echo ""
echo "Deixe usuário e senha em BRANCO"
