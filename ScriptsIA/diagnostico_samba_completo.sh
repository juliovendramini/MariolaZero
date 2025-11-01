#!/bin/bash
#
# Diagnóstico COMPLETO do Samba
# Identifica exatamente o que está impedindo o acesso
#
# Uso: sudo bash diagnostico_samba_completo.sh
#

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}DIAGNÓSTICO COMPLETO DO SAMBA${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

echo -e "${YELLOW}[1] Verificando se os serviços estão rodando...${NC}"
echo ""
systemctl status smbd --no-pager | head -5
echo ""
systemctl status nmbd --no-pager | head -5
echo ""

echo -e "${YELLOW}[2] Verificando portas abertas...${NC}"
echo ""
netstat -tlnp | grep -E ":(139|445)" || echo "PROBLEMA: Portas 139/445 não estão abertas!"
echo ""

echo -e "${YELLOW}[3] Verificando configuração atual do Samba...${NC}"
echo ""
cat /etc/samba/smb.conf
echo ""

echo -e "${YELLOW}[4] Testando sintaxe da configuração...${NC}"
echo ""
testparm -s 2>&1 | head -30
echo ""

echo -e "${YELLOW}[5] Verificando usuários Samba...${NC}"
echo ""
pdbedit -L -v 2>&1
echo ""

echo -e "${YELLOW}[6] Verificando permissões de /home/banana...${NC}"
echo ""
ls -la /home/banana | head -15
echo ""

echo -e "${YELLOW}[7] Verificando ownership recursivo...${NC}"
echo ""
find /home/banana -maxdepth 2 ! -user banana -o ! -group banana 2>/dev/null | head -10
if [ $? -eq 0 ]; then
    echo -e "${RED}PROBLEMA: Arquivos com ownership incorreto encontrados acima!${NC}"
else
    echo -e "${GREEN}✓ Ownership está correto${NC}"
fi
echo ""

echo -e "${YELLOW}[8] Verificando compartilhamentos disponíveis...${NC}"
echo ""
smbclient -L localhost -N 2>&1
echo ""

echo -e "${YELLOW}[9] Verificando logs de erro...${NC}"
echo ""
echo "Últimos erros do smbd:"
tail -30 /var/log/samba/log.smbd 2>/dev/null || echo "Log não encontrado"
echo ""

echo -e "${YELLOW}[10] Verificando firewall...${NC}"
echo ""
if command -v ufw &> /dev/null; then
    ufw status verbose
else
    echo "ufw não instalado"
fi
echo ""
if command -v iptables &> /dev/null; then
    iptables -L -n | grep -E "(139|445)"
fi
echo ""

echo -e "${YELLOW}[11] Verificando SELinux/AppArmor...${NC}"
echo ""
if command -v getenforce &> /dev/null; then
    getenforce
else
    echo "SELinux não instalado"
fi
if command -v aa-status &> /dev/null; then
    aa-status 2>&1 | grep -i samba || echo "AppArmor: sem restrições para Samba"
else
    echo "AppArmor não instalado"
fi
echo ""

echo -e "${YELLOW}[12] Testando acesso local...${NC}"
echo ""
smbclient //localhost/home -N -c "ls" 2>&1 | head -15
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}FIM DO DIAGNÓSTICO${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Copie TODA a saída acima e envie para análise."
