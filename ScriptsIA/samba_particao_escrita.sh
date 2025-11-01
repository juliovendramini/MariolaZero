#!/bin/bash
#
# Configura Samba para usar APENAS partição com escrita (/home/samba-data)
# Resolve problema de partição raiz somente leitura
#
# Uso: sudo bash samba_particao_escrita.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SAMBA EM PARTIÇÃO COM ESCRITA${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Execute como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/8] Parando serviços...${NC}"
systemctl stop smbd nmbd 2>/dev/null || true
sleep 2
echo -e "${GREEN}✓ Serviços parados${NC}"
echo ""

echo -e "${YELLOW}[2/8] Criando estrutura em /home/samba-data...${NC}"
mkdir -p /home/samba-data/lib
mkdir -p /home/samba-data/private
mkdir -p /home/samba-data/cache
mkdir -p /home/samba-data/lock
mkdir -p /home/samba-data/log

# Corrigir permissões
chown -R root:root /home/samba-data
chmod -R 755 /home/samba-data
chmod 700 /home/samba-data/private

echo -e "${GREEN}✓ Estrutura criada${NC}"
echo ""

echo -e "${YELLOW}[3/8] Criando links simbólicos de /var para /home/samba-data...${NC}"

# Remover arquivos antigos em /var/lib/samba (partição RO pode falhar, ignorar)
rm -f /var/lib/samba/*.tdb 2>/dev/null || true

# Criar/atualizar link do private
if [ -L /var/lib/samba/private ]; then
    rm -f /var/lib/samba/private
elif [ -d /var/lib/samba/private ]; then
    mv /var/lib/samba/private /var/lib/samba/private.old 2>/dev/null || true
fi
ln -sf /home/samba-data/private /var/lib/samba/private

# Criar/atualizar link do cache
if [ -L /var/cache/samba ]; then
    rm -f /var/cache/samba
elif [ -d /var/cache/samba ]; then
    mv /var/cache/samba /var/cache/samba.old 2>/dev/null || true
fi
ln -sf /home/samba-data/cache /var/cache/samba

# Criar/atualizar link do lock
if [ -L /var/lib/samba/lock ]; then
    rm -f /var/lib/samba/lock
elif [ -d /var/lib/samba/lock ]; then
    mv /var/lib/samba/lock /var/lib/samba/lock.old 2>/dev/null || true
fi
ln -sf /home/samba-data/lock /var/lib/samba/lock

echo -e "${GREEN}✓ Links criados${NC}"
echo ""

echo -e "${YELLOW}[4/8] Configurando smb.conf para usar /home/samba-data...${NC}"
cat > /etc/samba/smb.conf << 'EOF'
[global]
   workgroup = WORKGROUP
   server string = Banana Pi M4 Zero
   netbios name = BANANAPI
   
   # Autenticação guest
   security = user
   map to guest = Bad User
   guest account = banana
   
   # Permitir protocolos antigos (compatibilidade)
   client min protocol = CORE
   server min protocol = NT1
   
   # Configurações de caminho (apontar para partição com escrita)
   private dir = /home/samba-data/private
   lock directory = /home/samba-data/lock
   state directory = /home/samba-data/lib
   cache directory = /home/samba-data/cache
   
   # Sem restrições Unix
   unix extensions = no
   follow symlinks = yes
   
   # Logs em /var/log (zram - RAM comprimida)
   log level = 2
   log file = /var/log/samba/log.%m
   max log size = 1000

[dados]
   comment = Dados do Samba (Partição com Escrita)
   path = /home/samba-data
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
   
   # Forçar usuário banana
   force user = banana
   force group = banana

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
   
   # Forçar usuário banana
   force user = banana
   force group = banana

EOF
echo -e "${GREEN}✓ smb.conf configurado${NC}"
echo ""

echo -e "${YELLOW}[5/8] Testando sintaxe da configuração...${NC}"
if testparm -s /etc/samba/smb.conf > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Sintaxe OK${NC}"
else
    echo -e "${RED}✗ Erro na configuração!${NC}"
    testparm -s /etc/samba/smb.conf
    exit 1
fi
echo ""

echo -e "${YELLOW}[6/8] Recriando usuário Samba em /home/samba-data/private...${NC}"
# Garantir que diretório existe e tem permissões corretas
chmod 700 /home/samba-data/private

# Remover usuário antigo
smbpasswd -x banana 2>/dev/null || true

# Adicionar usuário com senha vazia
(echo ""; echo "") | smbpasswd -a -s banana 2>/dev/null
smbpasswd -e banana 2>/dev/null

echo -e "${GREEN}✓ Usuário Samba criado${NC}"
echo ""

echo -e "${YELLOW}[7/8] Ajustando permissões de /home/samba-data...${NC}"
# Permitir que banana acesse /home/samba-data
chown -R banana:banana /home/samba-data
chmod -R 755 /home/samba-data
chmod 700 /home/samba-data/private  # Mais restrito para senhas

echo -e "${GREEN}✓ Permissões ajustadas${NC}"
echo ""

echo -e "${YELLOW}[8/8] Iniciando serviços...${NC}"
systemctl start smbd nmbd
sleep 3

if systemctl is-active --quiet smbd && systemctl is-active --quiet nmbd; then
    echo -e "${GREEN}✓ Serviços iniciados${NC}"
else
    echo -e "${RED}✗ Erro ao iniciar serviços!${NC}"
    systemctl status smbd nmbd --no-pager
    exit 1
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VERIFICAÇÃO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo "Partições:"
df -h | grep -E "(mmcblk|Sist)"
echo ""

echo "Links simbólicos:"
ls -la /var/lib/samba/ | grep -E "(private|lock|cache)"
echo ""

echo "Compartilhamentos disponíveis:"
smbclient -L localhost -N 2>&1 | grep -A 15 "Sharename"
echo ""

echo "Teste de acesso ao compartilhamento 'dados':"
smbclient //localhost/dados -U banana%"" -c "ls" 2>&1 | head -10
echo ""

echo "Teste de acesso ao compartilhamento 'home':"
smbclient //localhost/home -U banana%"" -c "ls" 2>&1 | head -10
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}PRONTO!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Compartilhamentos disponíveis no Windows:"
echo ""
echo "  \\\\192.168.2.167\\dados    (Partição com escrita)"
echo "  \\\\192.168.2.167\\home     (Home do banana)"
echo ""
echo "Usuário: banana"
echo "Senha: (vazio)"
echo ""
echo -e "${YELLOW}IMPORTANTE: Agora tudo está em /home/samba-data${NC}"
echo -e "${YELLOW}que está na partição com escrita!${NC}"
