#!/bin/bash
#
# Diagnóstico RÁPIDO do Samba
# Identifica problema de autenticação
#

echo "=========================================="
echo "DIAGNÓSTICO RÁPIDO DO SAMBA"
echo "=========================================="
echo ""

echo "[1] Status dos serviços:"
systemctl status smbd --no-pager | head -3
systemctl status nmbd --no-pager | head -3
echo ""

echo "[2] Portas abertas:"
ss -tlnp | grep -E ":(139|445)" || netstat -tlnp | grep -E ":(139|445)"
echo ""

echo "[3] Compartilhamentos:"
smbclient -L localhost -N 2>&1
echo ""

echo "[4] Teste de acesso local como guest:"
smbclient //localhost/home -N -c "ls" 2>&1
echo ""

echo "[5] Usuários Samba:"
pdbedit -L -v 2>&1
echo ""

echo "[6] Configuração atual [global]:"
grep -A 20 "^\[global\]" /etc/samba/smb.conf
echo ""

echo "[7] Configuração atual [home]:"
grep -A 30 "^\[home\]" /etc/samba/smb.conf
echo ""

echo "[8] Últimos erros do log:"
tail -20 /var/log/samba/log.smbd 2>/dev/null || echo "Sem log"
echo ""

echo "[9] Permissões de /home/banana:"
ls -ld /home/banana
ls -la /home/banana | head -5
echo ""

echo "=========================================="
echo "FIM DO DIAGNÓSTICO"
echo "=========================================="
