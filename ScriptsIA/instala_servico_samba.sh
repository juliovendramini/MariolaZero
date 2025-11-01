#!/bin/bash
#
# Instala serviço que garante Samba funcional após cada boot
#
# Uso: sudo bash instala_servico_samba.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}INSTALANDO SERVIÇO DE INICIALIZAÇÃO${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Execute como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/5] Criando script de inicialização...${NC}"
cat > /usr/local/bin/samba-fix.sh << 'EOFSCRIPT'
#!/bin/bash
# Script executado no boot para garantir Samba funcional

sleep 5  # Aguardar rede estar pronta

# Corrigir permissões
mkdir -p /var/lib/samba/private
chmod 755 /var/lib/samba/private
chown -R root:root /var/lib/samba

# Corrigir diretório compartilhado
chown -R banana:banana /home/banana
chmod 755 /home/banana

# Garantir que usuário Samba existe
if ! pdbedit -L | grep -q "^banana:"; then
    (echo ""; echo "") | smbpasswd -a -s banana 2>/dev/null
    smbpasswd -e banana 2>/dev/null
fi

# Reiniciar serviços
systemctl restart smbd nmbd

# Log
echo "$(date): Samba fix executado com sucesso" >> /var/log/samba-fix.log

exit 0
EOFSCRIPT

chmod +x /usr/local/bin/samba-fix.sh
echo -e "${GREEN}✓ Script criado em /usr/local/bin/samba-fix.sh${NC}"
echo ""

echo -e "${YELLOW}[2/5] Criando serviço systemd...${NC}"
cat > /etc/systemd/system/samba-fix.service << 'EOFSERVICE'
[Unit]
Description=Samba Fix Service - Garante funcionamento após boot
After=network-online.target smbd.service nmbd.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/samba-fix.sh
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOFSERVICE

echo -e "${GREEN}✓ Serviço criado em /etc/systemd/system/samba-fix.service${NC}"
echo ""

echo -e "${YELLOW}[3/5] Recarregando systemd...${NC}"
systemctl daemon-reload
echo -e "${GREEN}✓ Systemd recarregado${NC}"
echo ""

echo -e "${YELLOW}[4/5] Habilitando serviço...${NC}"
systemctl enable samba-fix.service
echo -e "${GREEN}✓ Serviço habilitado${NC}"
echo ""

echo -e "${YELLOW}[5/5] Testando serviço...${NC}"
systemctl start samba-fix.service
sleep 3

if systemctl is-active --quiet samba-fix.service; then
    echo -e "${GREEN}✓ Serviço rodou com sucesso${NC}"
else
    echo -e "${RED}✗ Erro ao executar serviço${NC}"
    systemctl status samba-fix.service --no-pager
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}INSTALAÇÃO CONCLUÍDA!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "O serviço 'samba-fix' será executado automaticamente"
echo "após cada reinicialização para garantir que o Samba"
echo "funcione corretamente."
echo ""
echo "Comandos úteis:"
echo "  sudo systemctl status samba-fix   # Ver status"
echo "  sudo systemctl start samba-fix    # Executar manualmente"
echo "  sudo journalctl -u samba-fix      # Ver logs"
echo "  cat /var/log/samba-fix.log        # Ver histórico"
echo ""
echo -e "${YELLOW}Agora teste reiniciar o Banana Pi!${NC}"
