# Configurações
$IP          = "192.168.2.129"
$USUARIO     = "banana"
$MANIFEST    = ".manifest"
$TEMP_TAR    = "upload_temp.tar.gz"

# Detecta o nome do projeto pelo nome da pasta atual
$PROJETO = Split-Path -Leaf (Get-Location)

# Arquivos locais que não devem ser enviados ao dispositivo remoto
$EXCLUIR = @($MANIFEST, $TEMP_TAR, "envia.ps1")

# ---------------------------------------------------------------
# 1. Lê o manifesto atual (nome|timestamp)
# ---------------------------------------------------------------
$manifesto      = @{}
$forcarTudo     = $false

if (Test-Path $MANIFEST) {
    $idadeManifesto = (Get-Date).ToUniversalTime() - (Get-Item $MANIFEST).LastWriteTimeUtc
    if ($idadeManifesto.TotalHours -gt 3) {
        Write-Host "Manifesto com mais de 3 horas. Forcando envio completo para garantir integridade..."
        $forcarTudo = $true
    } else {
        Get-Content $MANIFEST -Encoding UTF8 | ForEach-Object {
            if ($_ -match "^(.+)\|(.+)$") {
                $manifesto[$Matches[1]] = $Matches[2]
            }
        }
    }
}

# ---------------------------------------------------------------
# 2. Descobre quais arquivos foram modificados
# ---------------------------------------------------------------
$todosArquivos  = Get-ChildItem -File | Where-Object { $_.Name -notin $EXCLUIR }
$modificados    = @()

foreach ($arq in $todosArquivos) {
    $ts = $arq.LastWriteTimeUtc.ToString("o")   # formato ISO 8601 UTC
    if ($forcarTudo -or $manifesto[$arq.Name] -ne $ts) {
        $modificados += $arq.Name
    }
}

# ---------------------------------------------------------------
# 3. Nada a fazer?
# ---------------------------------------------------------------
if ($modificados.Count -eq 0) {
    Write-Host "Nenhum arquivo modificado desde o ultimo envio. Nada a fazer."
    Write-Host ""
    Write-Host "Encerrando processo remoto..."
    ssh "${USUARIO}@${IP}" "killall python3 2>/dev/null; true"
    exit 0
}

Write-Host "Arquivos modificados ($($modificados.Count)): $($modificados -join ', ')"
Write-Host ""

# ---------------------------------------------------------------
# 4. Garante que a pasta remota existe (funciona no primeiro envio)
# ---------------------------------------------------------------
# Write-Host "Verificando pasta remota ~/$PROJETO ..."
# ssh "${USUARIO}@${IP}" "mkdir -p ~/$PROJETO"
# if ($LASTEXITCODE -ne 0) {
#     Write-Error "Falha ao criar pasta remota. Verifique a conexão SSH."
#     exit 1
# }

# ---------------------------------------------------------------
# 5/6/7. Envia os arquivos (direto se for 1, empacotado se forem vários)
# ---------------------------------------------------------------
if ($modificados.Count -eq 1) {
    # --- envio direto, sem compactação ---
    Write-Host "Enviando $($modificados[0]) diretamente para ${USUARIO}@${IP}:~/${PROJETO}/ ..."
    scp $modificados[0] "${USUARIO}@${IP}:~/${PROJETO}/"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Falha no envio SCP."
        exit 1
    }
} else {
    # --- empacota e envia em uma única transferência ---
    Write-Host "Empacotando $($modificados.Count) arquivos..."
    & tar -czf $TEMP_TAR $modificados
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Falha ao criar o arquivo tar."
        Remove-Item -Force $TEMP_TAR -ErrorAction SilentlyContinue
        exit 1
    }

    Write-Host "Enviando pacote para ${USUARIO}@${IP}:~/${PROJETO}/ ..."
    scp $TEMP_TAR "${USUARIO}@${IP}:~/${PROJETO}/"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Falha no envio SCP."
        Remove-Item -Force $TEMP_TAR -ErrorAction SilentlyContinue
        exit 1
    }

    Write-Host "Extraindo arquivos no dispositivo remoto..."
    ssh "${USUARIO}@${IP}" "cd ~/$PROJETO && tar -xzf $TEMP_TAR && rm $TEMP_TAR"
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Falha ao extrair os arquivos no dispositivo remoto."
        Remove-Item -Force $TEMP_TAR -ErrorAction SilentlyContinue
        exit 1
    }

    Remove-Item -Force $TEMP_TAR
}

# ---------------------------------------------------------------
# 9. Atualiza o manifesto com os timestamps atuais de TODOS os arquivos
# ---------------------------------------------------------------
$novoManifesto = foreach ($arq in $todosArquivos) {
    "$($arq.Name)|$($arq.LastWriteTimeUtc.ToString('o'))"
}
$novoManifesto | Set-Content $MANIFEST -Encoding UTF8

Write-Host ""
Write-Host "Envio concluido com sucesso!"
Write-Host ""

# ---------------------------------------------------------------
# 10. Encerra o processo remoto (igual ao comportamento original)
# ---------------------------------------------------------------
Write-Host "Encerrando processo remoto..."
ssh "${USUARIO}@${IP}" "killall python3 2>/dev/null; true"
