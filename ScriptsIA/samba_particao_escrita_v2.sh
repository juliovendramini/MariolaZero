#!/bin/bash
#
# Configura Samba para usar APENAS partição com escrita (/home/samba-data)
# Versão para sistema com partição raiz somente leitura (modo OVERLAY)
#
# Uso: sudo bash samba_particao_escrita_v2.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}SAMBA EM PARTIÇÃO COM ESCRITA V2${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Execute como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}[INFO] Verificando se partição raiz é RO...${NC}"
if mount | grep -q "on / .*[(,]ro[,$]"; then
    echo -e "${YELLOW}⚠ Partição raiz é somente leitura!${NC}"
    echo -e "${YELLOW}  Habilitando modo de escrita temporário...${NC}"
    mount -o remount,rw / 2>/dev/null || {
        echo -e "${RED}✗ Não foi possível habilitar escrita na raiz${NC}"
        echo -e "${YELLOW}  Continuando mesmo assim (overlay pode funcionar)...${NC}"
    }
else
    echo -e "${GREEN}✓ Partição raiz com escrita habilitada${NC}"
fi
echo ""

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

echo -e "${YELLOW}[3/8] Verificando links simbólicos existentes...${NC}"

# Verificar e criar/atualizar link do private
if [ -L /var/lib/samba/private ]; then
    LINK_TARGET=$(readlink /var/lib/samba/private)
    if [ "$LINK_TARGET" = "/home/samba-data/private" ]; then
        echo "  ✓ Link private já correto"
    else
        echo "  ⚠ Link private incorreto, atualizando..."
        rm -f /var/lib/samba/private 2>/dev/null || true
        ln -sf /home/samba-data/private /var/lib/samba/private
    fi
elif [ -d /var/lib/samba/private ]; then
    echo "  ⚠ private é diretório, tentando remover..."
    rm -rf /var/lib/samba/private 2>/dev/null || mv /var/lib/samba/private /var/lib/samba/private.old
    ln -sf /home/samba-data/private /var/lib/samba/private
elif [ ! -e /var/lib/samba/private ]; then
    echo "  ⚠ private não existe, criando link..."
    ln -sf /home/samba-data/private /var/lib/samba/private
fi

# Verificar lock
if [ ! -L /var/lib/samba/lock ] && [ ! -e /var/lib/samba/lock ]; then
    ln -sf /home/samba-data/lock /var/lib/samba/lock 2>/dev/null || echo "  ⚠ Não foi possível criar link lock"
fi

# Verificar cache
if [ ! -L /var/cache/samba ] && [ ! -e /var/cache/samba ]; then
    ln -sf /home/samba-data/cache /var/cache/samba 2>/dev/null || echo "  ⚠ Não foi possível criar link cache"
fi

echo -e "${GREEN}✓ Links verificados${NC}"
echo ""

echo -e "${YELLOW}[4/8] Configurando smb.conf...${NC}"
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
   
   # CRÍTICO: Apontar TUDO para /home/samba-data (partição RW)
   private dir = /home/samba-data/private
   lock directory = /home/samba-data/lock
   state directory = /home/samba-data/lib
   cache directory = /home/samba-data/cache
   
   # Sem restrições Unix
   unix extensions = no
   follow symlinks = yes
   
   # Logs em /var/log (zram - RAM)
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
echo -e "${GREEN}✓ smb.conf configurado${NC}"
echo ""

echo -e "${YELLOW}[5/8] Testando sintaxe...${NC}"
testparm -s /etc/samba/smb.conf | head -40
echo ""

echo -e "${YELLOW}[6/8] Recriando usuário Samba...${NC}"
chmod 700 /home/samba-data/private
smbpasswd -x banana 2>/dev/null || true
(echo ""; echo "") | smbpasswd -a -s banana 2>/dev/null
smbpasswd -e banana 2>/dev/null
echo -e "${GREEN}✓ Usuário criado${NC}"
echo ""

echo -e "${YELLOW}[7/8] Ajustando permissões...${NC}"
chown -R banana:banana /home/samba-data
chmod -R 755 /home/samba-data
chmod 700 /home/samba-data/private
echo -e "${GREEN}✓ Permissões OK${NC}"
echo ""

echo -e "${YELLOW}[8/8] Iniciando serviços...${NC}"
systemctl start smbd nmbd
sleep 3

if systemctl is-active --quiet smbd && systemctl is-active --quiet nmbd; then
    echo -e "${GREEN}✓ Serviços rodando${NC}"
else
    echo -e "${RED}✗ Erro!${NC}"
    systemctl status smbd --no-pager | head -10
    exit 1
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VERIFICAÇÃO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

df -h | grep -E "(mmcblk|Sist)"
echo ""

ls -la /var/lib/samba/private
echo ""

smbclient -L localhost -N 2>&1 | grep -A 15 "Sharename"
echo ""

echo "Teste 'dados':"
smbclient //localhost/dados -U banana%"" -c "ls" 2>&1 | head -10
echo ""

echo "Teste 'home':"
smbclient //localhost/home -U banana%"" -c "ls" 2>&1 | head -10
echo ""

echo -e "${GREEN}========================================${NC}"
echo "  \\\\192.168.2.167\\dados"
echo "  \\\\192.168.2.167\\home"
echo ""
echo "Usuário: banana | Senha: (vazio)"
echo -e "${GREEN}========================================${NC}"
