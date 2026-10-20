#!/bin/bash
#
# Move TODOS os arquivos .tdb do Samba para /home/samba-data
# e cria links simbólicos
#
# Uso: sudo bash samba_move_tdb.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}MOVENDO TDBs PARA PARTIÇÃO RW${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Execute como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/5] Parando serviços...${NC}"
systemctl stop smbd nmbd 2>/dev/null || true
sleep 2
echo ""

echo -e "${YELLOW}[2/5] Criando estrutura completa em /home/samba-data...${NC}"
mkdir -p /home/samba-data/lib
mkdir -p /home/samba-data/private
mkdir -p /home/samba-data/cache
mkdir -p /home/samba-data/lock
mkdir -p /home/samba-data/log
chown -R banana:banana /home/samba-data
chmod -R 755 /home/samba-data
chmod 700 /home/samba-data/private
echo -e "${GREEN}✓ Estrutura criada${NC}"
echo ""

echo -e "${YELLOW}[3/5] Movendo arquivos .tdb existentes...${NC}"
# Copiar arquivos .tdb de /var/lib/samba para /home/samba-data/lib
if ls /var/lib/samba/*.tdb 1> /dev/null 2>&1; then
    echo "  Copiando arquivos .tdb..."
    cp -p /var/lib/samba/*.tdb /home/samba-data/lib/ 2>/dev/null || true
    echo "  ✓ Arquivos copiados"
fi
echo ""

echo -e "${YELLOW}[4/5] Criando smb.conf com state directory correto...${NC}"
cat > /etc/samba/smb.conf << 'EOF'
[global]
   workgroup = WORKGROUP
   server string = Banana Pi M4 Zero
   netbios name = BANANAPI
   
   # Autenticação guest
   security = user
   map to guest = Bad User
   guest account = banana
   
   # Protocolos
   client min protocol = CORE
   server min protocol = NT1
   
   # CRÍTICO: state directory aponta para partição RW
   # Todos os .tdb serão criados aqui
   state directory = /home/samba-data/lib
   private dir = /home/samba-data/private
   lock directory = /home/samba-data/lock
   cache directory = /home/samba-data/cache
   
   # Sem restrições
   unix extensions = no
   follow symlinks = yes
   
   # Logs em RAM (zram)
   log level = 2
   log file = /var/log/samba/log.%m
   max log size = 1000

[dados]
   comment = Dados Samba (Partição RW)
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

echo -e "${YELLOW}[5/5] Testando e iniciando...${NC}"
echo "Teste de sintaxe:"
testparm -s /etc/samba/smb.conf 2>&1 | grep -E "(state directory|private dir|lock directory)"
echo ""

# Recriar usuário
(echo ""; echo "") | smbpasswd -a -s banana 2>/dev/null || true
smbpasswd -e banana 2>/dev/null || true

# Iniciar serviços
systemctl start smbd nmbd
sleep 3

if systemctl is-active --quiet smbd; then
    echo -e "${GREEN}✓ SMBD RODANDO!${NC}"
else
    echo -e "${RED}✗ SMBD FALHOU!${NC}"
    systemctl status smbd --no-pager | head -10
    exit 1
fi

if systemctl is-active --quiet nmbd; then
    echo -e "${GREEN}✓ NMBD RODANDO!${NC}"
else
    echo -e "${YELLOW}⚠ NMBD com problema${NC}"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VERIFICAÇÃO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo "Arquivos .tdb em /home/samba-data/lib:"
ls -lh /home/samba-data/lib/*.tdb 2>/dev/null | head -10 || echo "Nenhum ainda"
echo ""

echo "Compartilhamentos:"
smbclient -L localhost -N 2>&1 | grep -A 10 "Sharename"
echo ""

echo "Teste de acesso:"
smbclient //localhost/dados -U banana%"" -c "ls" 2>&1 | head -5
echo ""

echo -e "${GREEN}SUCESSO!${NC}"
echo "  \\\\192.168.2.167\\dados"
echo "  \\\\192.168.2.167\\home"
