# Script para enviar todos os scripts de migração para Banana Pi
# Autor: GitHub Copilot

param(
    [string]$BananaPiIP = "192.168.2.151",
    [string]$BananaPiUser = "root"
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Envio de Scripts de Migração" -ForegroundColor Cyan
Write-Host "Kernel Vendor 5.4.125 + U-Boot + DTB" -ForegroundColor Cyan
Write-Host "========================================`n" -ForegroundColor Cyan

# Verificar conectividade
Write-Host "Verificando conectividade com $BananaPiIP..." -ForegroundColor Yellow
$pingResult = Test-Connection -ComputerName $BananaPiIP -Count 2 -Quiet
if (-not $pingResult) {
    Write-Host "ERRO: Não foi possível conectar à Banana Pi" -ForegroundColor Red
    exit 1
}
Write-Host "Conectividade OK!`n" -ForegroundColor Green

# Lista de scripts para enviar
$scripts = @(
    "diagnostico_uboot.sh",
    "copia_uboot_sd_emmc.sh",
    "corrige_dtb.sh",
    "migracao_completa_vendor.sh"
)

Write-Host "Enviando scripts para Banana Pi...`n" -ForegroundColor Yellow

foreach ($script in $scripts) {
    Write-Host "  Enviando $script..." -ForegroundColor Cyan
    scp $script ${BananaPiUser}@${BananaPiIP}:/root/
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERRO ao enviar $script" -ForegroundColor Red
        exit 1
    }
    
    # Dar permissão de execução
    ssh ${BananaPiUser}@${BananaPiIP} "chmod +x /root/$script"
    Write-Host "  ✓ $script enviado e permissão concedida" -ForegroundColor Green
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Scripts Enviados com Sucesso!" -ForegroundColor Green
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "Scripts disponíveis na Banana Pi:" -ForegroundColor Yellow
Write-Host ""
Write-Host "1. diagnostico_uboot.sh" -ForegroundColor White
Write-Host "   Diagnóstico completo de U-Boot, kernel e DTB"
Write-Host "   Uso: ssh $BananaPiUser@$BananaPiIP 'bash /root/diagnostico_uboot.sh'"
Write-Host ""
Write-Host "2. copia_uboot_sd_emmc.sh" -ForegroundColor White
Write-Host "   Copia U-Boot do cartão SD para eMMC (use com CUIDADO!)"
Write-Host "   Uso: ssh $BananaPiUser@$BananaPiIP 'bash /root/copia_uboot_sd_emmc.sh'"
Write-Host ""
Write-Host "3. corrige_dtb.sh" -ForegroundColor White
Write-Host "   Corrige DTB e armbianEnv.txt para kernel 5.4.125"
Write-Host "   Uso: ssh $BananaPiUser@$BananaPiIP 'bash /root/corrige_dtb.sh'"
Write-Host ""
Write-Host "4. migracao_completa_vendor.sh" -ForegroundColor White -ForegroundColor Cyan
Write-Host "   ⭐ SCRIPT PRINCIPAL - Executa tudo na ordem correta" -ForegroundColor Yellow
Write-Host "   Uso: ssh $BananaPiUser@$BananaPiIP 'bash /root/migracao_completa_vendor.sh'"
Write-Host ""

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Próximos Passos" -ForegroundColor Yellow
Write-Host "========================================`n" -ForegroundColor Cyan

Write-Host "OPÇÃO A - Migração Completa (Recomendado):" -ForegroundColor Green
Write-Host "  1. Insira o cartão SD com kernel vendor funcionando"
Write-Host "  2. Execute: ssh $BananaPiUser@$BananaPiIP"
Write-Host "  3. Execute: bash /root/migracao_completa_vendor.sh"
Write-Host "  4. Siga as instruções interativas"
Write-Host ""

Write-Host "OPÇÃO B - Passo a Passo Manual:" -ForegroundColor Yellow
Write-Host "  1. Diagnóstico:"
Write-Host "     ssh $BananaPiUser@$BananaPiIP 'bash /root/diagnostico_uboot.sh'"
Write-Host ""
Write-Host "  2. Copiar U-Boot (se necessário):"
Write-Host "     ssh $BananaPiUser@$BananaPiIP 'bash /root/copia_uboot_sd_emmc.sh'"
Write-Host ""
Write-Host "  3. Instalar Kernel (se ainda não instalou):"
Write-Host "     .\install_vendor_kernel_simple.ps1"
Write-Host ""
Write-Host "  4. Corrigir DTB:"
Write-Host "     ssh $BananaPiUser@$BananaPiIP 'bash /root/corrige_dtb.sh'"
Write-Host ""
Write-Host "  5. Reiniciar:"
Write-Host "     ssh $BananaPiUser@$BananaPiIP 'reboot'"
Write-Host ""

Write-Host ""
Write-Host "IMPORTANTE:" -ForegroundColor Red
Write-Host "  Tenha um backup ou forma de recuperacao disponivel" -ForegroundColor White
Write-Host "  O script de U-Boot faz backup automatico antes de copiar" -ForegroundColor White
Write-Host "  Remova o cartao SD antes de reiniciar" -ForegroundColor White
Write-Host ""
