#!/bin/bash
#
# Script de EMERGÊNCIA para restaurar acesso do Samba
# Reverte todas as mudanças e volta para configuração funcional
#
# Uso: sudo bash restaura_samba_emergencia.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}========================================${NC}"
echo -e "${RED}RESTAURAÇÃO DE EMERGÊNCIA DO SAMBA${NC}"
echo -e "${RED}========================================${NC}"
echo ""

# Verificar se está rodando como root
if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}ERRO: Execute como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/7] Parando serviços do Samba...${NC}"
systemctl stop smbd 2>/dev/null || true
systemctl stop nmbd 2>/dev/null || true
sleep 2
echo -e "${GREEN}✓ Serviços parados${NC}"
echo ""

echo -e "${YELLOW}[2/7] Restaurando backup do smb.conf (se existir)...${NC}"
if [ -f /etc/samba/smb.conf.backup.* ]; then
    ULTIMO_BACKUP=$(ls -t /etc/samba/smb.conf.backup.* | head -1)
    echo "Backup encontrado: $ULTIMO_BACKUP"
    cp "$ULTIMO_BACKUP" /etc/samba/smb.conf
    echo -e "${GREEN}✓ Backup restaurado${NC}"
else
    echo -e "${YELLOW}Nenhum backup encontrado, criando configuração básica...${NC}"
fi
echo ""

echo -e "${YELLOW}[3/7] Criando configuração SIMPLES e FUNCIONAL...${NC}"
cat > /etc/samba/smb.conf << 'EOF'
[global]
   workgroup = WORKGROUP
   server string = Banana Pi Samba Server
   netbios name = BANANAPI
   security = user
   map to guest = Bad User
   dns proxy = no
   
   # Permitir acesso sem restrições
   unix extensions = no
   follow symlinks = yes
   wide links = yes
   
[home]
   comment = Home do Banana
   path = /home/banana
   browseable = yes
   read only = no
   writable = yes
   guest ok = yes
   public = yes
   
   # PERMISSÕES TOTALMENTE ABERTAS
   create mask = 0777
   directory mask = 0777
   force create mode = 0777
   force directory mode = 0777
   
   # Sem restrições de usuário
   valid users = 
   force user = 
   force group = 

EOF
echo -e "${GREEN}✓ Configuração simples criada${NC}"
echo ""

echo -e "${YELLOW}[4/7] Liberando TOTALMENTE as permissões de /home/banana...${NC}"
# Ownership correto
chown -R banana:banana /home/banana

# Permissões TOTALMENTE abertas
chmod -R 777 /home/banana

echo -e "${GREEN}✓ Permissões liberadas (777 recursivo)${NC}"
echo ""

echo -e "${YELLOW}[5/7] Verificando usuário Samba...${NC}"
# Remover usuário Samba se existir
smbpasswd -x banana 2>/dev/null || true

# Criar usuário Samba com senha vazia
(echo ""; echo "") | smbpasswd -a -s banana 2>/dev/null || true
smbpasswd -e banana 2>/dev/null || true
echo -e "${GREEN}✓ Usuário Samba configurado (sem senha)${NC}"
echo ""

echo -e "${YELLOW}[6/7] Verificando firewall...${NC}"
# Liberar portas do Samba no firewall (se ufw estiver ativo)
if command -v ufw &> /dev/null; then
    ufw allow 137/udp 2>/dev/null || true
    ufw allow 138/udp 2>/dev/null || true
    ufw allow 139/tcp 2>/dev/null || true
    ufw allow 445/tcp 2>/dev/null || true
    echo -e "${GREEN}✓ Portas do Samba liberadas no firewall${NC}"
else
    echo -e "${YELLOW}ufw não encontrado, pulando...${NC}"
fi
echo ""

echo -e "${YELLOW}[7/7] Reiniciando serviços do Samba...${NC}"
systemctl restart smbd
systemctl restart nmbd
sleep 3
echo -e "${GREEN}✓ Serviços reiniciados${NC}"
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}VERIFICAÇÃO DO STATUS${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

echo "Status do smbd:"
systemctl status smbd --no-pager -l | head -8
echo ""

echo "Status do nmbd:"
systemctl status nmbd --no-pager -l | head -8
echo ""

echo "Permissões de /home/banana:"
ls -la /home/banana | head -10
echo ""

echo "Compartilhamentos disponíveis:"
smbclient -L localhost -N 2>/dev/null | grep -A 10 "Sharename" || true
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}TESTE AGORA!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "No Windows, tente acessar:"
echo "  \\\\192.168.2.167\\home"
echo ""
echo "Se AINDA NÃO FUNCIONAR, execute este diagnóstico:"
echo "  sudo bash diagnostico_samba_completo.sh"
echo ""
echo -e "${GREEN}Restauração concluída!${NC}"
