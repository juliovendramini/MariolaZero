#!/bin/bash
#
# Configuração FINAL do Samba
# - Usa configuração padrão (funciona após boot)
# - Adiciona compartilhamento 'dados' apontando para /home/samba-data
# - Mantém compartilhamento 'home' para /home/banana
#
# Uso: sudo bash samba_configuracao_final.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}CONFIGURAÇÃO FINAL DO SAMBA${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo "Execute como root: sudo bash $0"
    exit 1
fi

echo -e "${YELLOW}[1/6] Parando serviços...${NC}"
systemctl stop smbd nmbd 2>/dev/null || true
sleep 2
echo ""

echo -e "${YELLOW}[2/6] Preparando /home/samba-data...${NC}"
mkdir -p /home/samba-data
chown -R banana:banana /home/samba-data
chmod -R 777 /home/samba-data
echo -e "${GREEN}✓ Diretório preparado${NC}"
echo ""

echo -e "${YELLOW}[3/6] Criando smb.conf final...${NC}"
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
   
   # Sem restrições Unix
   unix extensions = no
   follow symlinks = yes
   
   # Logs
   log level = 2
   log file = /var/log/samba/log.%m
   max log size = 1000

[dados]
   comment = Dados (Partição com Escrita)
   path = /home/samba-data
   browseable = yes
   public = yes
   guest ok = yes
   guest only = yes
   read only = no
   writable = yes
   create mask = 0777
   directory mask = 0777
   force create mode = 0777
   force directory mode = 0777
   force user = banana
   force group = banana

[home]
   comment = Home Banana
   path = /home/banana
   browseable = yes
   public = yes
   guest ok = yes
   guest only = yes
   read only = no
   writable = yes
   create mask = 0777
   directory mask = 0777
   force create mode = 0777
   force directory mode = 0777
   force user = banana
   force group = banana

EOF
echo -e "${GREEN}✓ smb.conf criado${NC}"
echo ""

echo -e "${YELLOW}[4/6] Testando sintaxe...${NC}"
testparm -s /etc/samba/smb.conf | grep -E "(^\[|path =)"
echo ""

echo -e "${YELLOW}[5/6] Recriando usuário...${NC}"
smbpasswd -x banana 2>/dev/null || true
(echo ""; echo "") | smbpasswd -a -s banana 2>/dev/null
smbpasswd -e banana 2>/dev/null
echo -e "${GREEN}✓ Usuário OK${NC}"
echo ""

echo -e "${YELLOW}[6/6] Iniciando serviços...${NC}"
systemctl start smbd nmbd
sleep 3

if systemctl is-active --quiet smbd && systemctl is-active --quiet nmbd; then
    echo -e "${GREEN}✓ Serviços rodando${NC}"
else
    echo -e "${RED}✗ Erro!${NC}"
    systemctl status smbd nmbd --no-pager
    exit 1
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VERIFICAÇÃO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

smbclient -L localhost -N 2>&1 | grep -A 15 "Sharename"
echo ""

echo "Teste 'dados':"
smbclient //localhost/dados -U banana%"" -c "ls" 2>&1 | head -5
echo ""

echo "Teste 'home':"
smbclient //localhost/home -U banana%"" -c "ls" 2>&1 | head -5
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SUCESSO!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Compartilhamentos disponíveis:"
echo ""
echo "  \\\\192.168.2.167\\dados     <- USE ESTE para seus arquivos!"
echo "                                (Partição com escrita)"
echo ""
echo "  \\\\192.168.2.167\\home      <- Home do usuário banana"
echo ""
echo "Usuário: banana"
echo "Senha: (vazio - apenas pressione Enter)"
echo ""
echo -e "${YELLOW}IMPORTANTE: Salve seus arquivos em \\\\192.168.2.167\\dados${NC}"
echo -e "${YELLOW}pois /home/samba-data está na partição com escrita!${NC}"
