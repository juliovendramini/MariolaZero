# Script PowerShell para executar a restauração do Samba remotamente
# Uso: .\executa_restauracao_samba.ps1

$IP = "192.168.2.167"
$USER = "banana"

Write-Host "========================================" -ForegroundColor Green
Write-Host "RESTAURAÇÃO DE EMERGÊNCIA DO SAMBA" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Este script vai se conectar ao Banana Pi e executar a restauração." -ForegroundColor Yellow
Write-Host "Você precisará digitar a senha do usuário 'banana' quando solicitado." -ForegroundColor Yellow
Write-Host ""

# Executar script remotamente com sessão interativa
ssh -t ${USER}@${IP} "sudo bash ~/restaura_samba_emergencia.sh"

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "Agora teste o acesso:" -ForegroundColor Green
Write-Host "  \\$IP\home" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Green
