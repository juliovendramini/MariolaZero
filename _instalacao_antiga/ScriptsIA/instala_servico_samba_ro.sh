#!/bin/bash
#
# Instala serviço que garante Samba funcional após boot
# Específico para sistema com partição raiz somente leitura
#
# Uso: sudo bash instala_servico_samba_ro.sh
#

set -e

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}INSTALANDO SERVIÇO SAMBA (SISTEMA RO)${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

if [ "$EUID" -ne 0 ]; then 
    echo -e "${RED}Execute como root: sudo bash $0${NC}"
    exit 1
fi

echo -e "${YELLOW}[1/3] Criando script de inicialização...${NC}"
cat > /usr/local/bin/samba-fix-ro.sh << 'EOFSCRIPT'
#!/bin/bash
# Script executado no boot para garantir Samba funcional
# em sistema com partição raiz somente leitura

# Aguardar rede e sistema de arquivos
sleep 5

# Garantir que /home/samba-data existe e tem estrutura
mkdir -p /home/samba-data/{lib,private,cache,lock,log}
chown -R root:root /home/samba-data
chmod -R 755 /home/samba-data
chmod 700 /home/samba-data/private

# Criar links simbólicos (podem ser perdidos em partição RO)
# Link do private
if [ ! -L /var/lib/samba/private ]; then
    rm -rf /var/lib/samba/private 2>/dev/null || true
    ln -sf /home/samba-data/private /var/lib/samba/private
fi

# Link do cache
if [ ! -L /var/cache/samba ]; then
    rm -rf /var/cache/samba 2>/dev/null || true
    ln -sf /home/samba-data/cache /var/cache/samba
fi

# Link do lock
if [ ! -L /var/lib/samba/lock ]; then
    rm -rf /var/lib/samba/lock 2>/dev/null || true
    ln -sf /home/samba-data/lock /var/lib/samba/lock
fi

# Garantir que usuário Samba existe
if ! pdbedit -L 2>/dev/null | grep -q "^banana:"; then
    (echo ""; echo "") | smbpasswd -a -s banana 2>/dev/null || true
    smbpasswd -e banana 2>/dev/null || true
fi

# Ajustar permissões de /home/samba-data para banana
chown -R banana:banana /home/samba-data
chmod 755 /home/samba-data
chmod 700 /home/samba-data/private

# Reiniciar serviços do Samba
systemctl restart smbd nmbd 2>/dev/null || true

# Log
echo "$(date): Samba fix RO executado" >> /home/samba-data/log/samba-fix.log

exit 0
EOFSCRIPT

chmod +x /usr/local/bin/samba-fix-ro.sh
echo -e "${GREEN}✓ Script criado em /usr/local/bin/samba-fix-ro.sh${NC}"
echo ""

echo -e "${YELLOW}[2/3] Criando serviço systemd...${NC}"
cat > /etc/systemd/system/samba-fix.service << 'EOFSERVICE'
[Unit]
Description=Samba Fix Service - Sistema com Partição RO
After=network-online.target local-fs.target smbd.service nmbd.service
Wants=network-online.target
Before=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/samba-fix-ro.sh
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
EOFSERVICE

echo -e "${GREEN}✓ Serviço criado${NC}"
echo ""

echo -e "${YELLOW}[3/3] Habilitando serviço...${NC}"
systemctl daemon-reload
systemctl enable samba-fix.service
systemctl start samba-fix.service
sleep 3

if systemctl is-active --quiet samba-fix.service; then
    echo -e "${GREEN}✓ Serviço ativo${NC}"
else
    echo -e "${YELLOW}⚠ Serviço executado (normal para oneshot)${NC}"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}INSTALAÇÃO CONCLUÍDA!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Serviço 'samba-fix' será executado automaticamente"
echo "após cada boot para:"
echo "  - Recriar links simbólicos"
echo "  - Garantir que banco de dados está em /home/samba-data"
echo "  - Recriar usuário Samba se necessário"
echo "  - Reiniciar serviços"
echo ""
echo "Comandos úteis:"
echo "  systemctl status samba-fix"
echo "  journalctl -u samba-fix"
echo "  cat /home/samba-data/log/samba-fix.log"
echo ""
echo -e "${YELLOW}TESTE: Reinicie o Banana Pi agora!${NC}"
echo "  sudo reboot"
