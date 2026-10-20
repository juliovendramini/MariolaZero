# Script para enviar scripts de migracao para Banana Pi

param(
    [string]$BananaPiIP = "192.168.2.151",
    [string]$BananaPiUser = "root"
)

Write-Host "Enviando scripts de migracao para Banana Pi..." -ForegroundColor Cyan

$scripts = @(
    "diagnostico_uboot.sh",
    "copia_uboot_sd_emmc.sh",
    "corrige_dtb.sh",
    "migracao_completa_vendor.sh"
)

foreach ($script in $scripts) {
    Write-Host "Enviando $script..." -ForegroundColor Yellow
    scp $script ${BananaPiUser}@${BananaPiIP}:/root/
    ssh ${BananaPiUser}@${BananaPiIP} "chmod +x /root/$script"
    Write-Host "OK: $script" -ForegroundColor Green
}

Write-Host ""
Write-Host "Scripts enviados com sucesso!" -ForegroundColor Green
Write-Host ""
Write-Host "Para executar a migracao completa:" -ForegroundColor Yellow
Write-Host "  ssh $BananaPiUser@$BananaPiIP"
Write-Host "  bash /root/migracao_completa_vendor.sh"
Write-Host ""
