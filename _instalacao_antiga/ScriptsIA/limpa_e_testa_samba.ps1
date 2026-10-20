# Script PowerShell para LIMPAR credenciais antigas e testar acesso
# Uso: .\limpa_e_testa_samba.ps1

$IP = "192.168.2.167"
$SHARE = "home"

Write-Host "========================================" -ForegroundColor Green
Write-Host "LIMPEZA DE CREDENCIAIS E TESTE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

Write-Host "[1/4] Removendo credenciais antigas do Windows..." -ForegroundColor Yellow
Write-Host ""

# Remover credenciais específicas do IP
Write-Host "Tentando remover: \\$IP\$SHARE" -ForegroundColor Cyan
net use "\\$IP\$SHARE" /delete 2>$null
cmdkey /delete:"$IP" 2>$null
cmdkey /delete:"TERMSRV/$IP" 2>$null

# Remover TODAS as credenciais relacionadas
Get-ChildItem "HKCU:\Network" -ErrorAction SilentlyContinue | ForEach-Object {
    if ($_.GetValue("RemotePath") -like "*$IP*") {
        Write-Host "Removendo mapeamento antigo: $($_.GetValue('RemotePath'))" -ForegroundColor Yellow
        Remove-Item $_.PSPath -Force -ErrorAction SilentlyContinue
    }
}

Write-Host ""
Write-Host "[2/4] Limpando cache de sessões SMB..." -ForegroundColor Yellow
Get-SmbConnection | Where-Object { $_.ServerName -eq $IP } | Remove-SmbConnection -Force -ErrorAction SilentlyContinue
Get-SmbMapping | Where-Object { $_.RemotePath -like "*$IP*" } | Remove-SmbMapping -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "[3/4] Aguardando cache expirar..." -ForegroundColor Yellow
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "[4/4] Testando acesso SEM credenciais..." -ForegroundColor Yellow
Write-Host ""

# Tentar conectar como guest (sem credenciais)
Write-Host "Comando 1: Listar compartilhamentos disponíveis" -ForegroundColor Cyan
net view \\$IP

Write-Host ""
Write-Host "Comando 2: Conectar no share como GUEST" -ForegroundColor Cyan
net use "\\$IP\$SHARE" /user:"" "" 

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "COMO ACESSAR NO EXPLORADOR" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "1. Abra o Explorador de Arquivos (Win + E)" -ForegroundColor White
Write-Host ""
Write-Host "2. Digite na barra de endereço:" -ForegroundColor White
Write-Host "   \\$IP\$SHARE" -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Se pedir usuário/senha:" -ForegroundColor White
Write-Host "   - Deixe USUÁRIO em BRANCO (vazio)" -ForegroundColor Yellow
Write-Host "   - Deixe SENHA em BRANCO (vazio)" -ForegroundColor Yellow
Write-Host "   - Pressione OK" -ForegroundColor Yellow
Write-Host ""
Write-Host "4. Ou tente:" -ForegroundColor White
Write-Host "   - Usuário: banana" -ForegroundColor Yellow
Write-Host "   - Senha: (deixe vazio, apenas Enter)" -ForegroundColor Yellow
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host ""

# Tentar abrir automaticamente
Write-Host "Abrindo no Explorador de Arquivos..." -ForegroundColor Cyan
Start-Process "explorer.exe" "\\$IP\$SHARE"
