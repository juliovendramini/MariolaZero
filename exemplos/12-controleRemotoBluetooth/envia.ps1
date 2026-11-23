# Manda a pasta deste projeto (com as subpastas) para o Mariola. É o envia.sh para o Windows.
# Uso (no terminal, dentro da pasta do projeto ou não):
#   powershell -ExecutionPolicy Bypass -File envia.ps1                  manda só o que mudou
#   powershell -ExecutionPolicy Bypass -File envia.ps1 tudo             manda a pasta inteira
#   powershell -ExecutionPolicy Bypass -File envia.ps1 192.168.2.151    usa outro IP
# Normalmente quem chama é o envia.bat (duplo clique, F5 ou Ctrl+Shift+B), que passa o IP dele.
# A pasta no robô tem o mesmo nome desta: /home/banana/<nome-da-pasta>; é criada se não existir.
# No fim encerra o main.py que estiver rodando no robô.
# Precisa só do ssh e do tar, que já vêm no Windows 10/11. Sem a chave SSH, pede a senha uma vez.

# IP do robô: vale o passado na hora; sem ele, o da linha "set IP=" do envia.bat desta pasta;
# sem envia.bat, este aqui.
$IP_PADRAO = "192.168.2.151"
$USUARIO   = "banana"
# Pasta no robô: vazio = o nome desta pasta.
$PASTA_NO_ROBO = ""

# Pastas que não vão (em qualquer nível) e arquivos que não vão.
$PULA_PASTAS   = @("__pycache__", ".git", ".vscode", ".idea", "venv", ".venv", "node_modules")
$PULA_ARQUIVOS = @(".ultimo_envio_*", ".envio_em_andamento", ".manifest", "*.pyc",
                   "envia.sh", "envia.bat", "envia.ps1", "upload_temp.tar.gz", "upload_lista.txt")
# Passadas estas horas desde o último envio para o robô, manda tudo (ele pode ter sido regravado).
$HORAS_PARA_MANDAR_TUDO = 3

# ---------------------------------------------------------------------------------------------
$ErrorActionPreference = "Stop"
$RAIZ = $PSScriptRoot
Set-Location -LiteralPath $RAIZ

$IP   = $null
$TUDO = $false
foreach ($a in $args) {
    switch -Regex ([string]$a) {
        '^(-{0,2}t|-{0,2}tudo)$'        { $TUDO = $true }
        '^(-{0,2}h|-{0,2}ajuda|-\?|/\?)$' { Get-Content -LiteralPath $PSCommandPath -TotalCount 9 -Encoding UTF8; exit 0 }
        default                          { $IP = [string]$a }
    }
}
if (-not $IP -and (Test-Path -LiteralPath "envia.bat")) {
    foreach ($linha in Get-Content -LiteralPath "envia.bat") {
        if ($linha -match '^\s*set\s+"?IP=([^"\s]+)') { $IP = $Matches[1]; break }
    }
}
if (-not $IP) { $IP = $IP_PADRAO }

$PROJETO = if ($PASTA_NO_ROBO) { $PASTA_NO_ROBO } else { Split-Path -Leaf $RAIZ }
$ROBO    = "$USUARIO@$IP"
$MARCA   = Join-Path $RAIZ ".ultimo_envio_$IP"   # o mesmo arquivo do envia.sh
$LISTA   = Join-Path $RAIZ "upload_lista.txt"
$PACOTE  = Join-Path $RAIZ "upload_temp.tar.gz"

# o ssh e o tar do Windows (o "tar" do Git Bash, se estiver antes no PATH, não entende C:\...)
$SSH = Join-Path $env:SystemRoot "System32\OpenSSH\ssh.exe"
if (-not (Test-Path -LiteralPath $SSH)) { $SSH = (Get-Command ssh -ErrorAction SilentlyContinue).Source }
$TAR = Join-Path $env:SystemRoot "System32\tar.exe"
if (-not (Test-Path -LiteralPath $TAR)) { $TAR = (Get-Command tar -ErrorAction SilentlyContinue).Source }
if (-not $SSH -or -not $TAR) {
    Write-Host "Nao achei o ssh ou o tar do Windows (vem no Windows 10 de 2018 para frente)."
    Write-Host "Use o jeito antigo: no envia.bat, troque para set MODO=scp"
    exit 1
}

# só o python rodando um main.py (o do menu ou o do executa.sh), não um "nano main.py" aberto
$ENCERRA = "pkill -f '^([^ ]*/)?python[0-9.]* .*main\.py' && echo 'Programa que estava rodando no robo: encerrado.'; true"

# roda um programa com a linha de comando exatamente como está (o PowerShell 5 mexe nas aspas)
function Roda([string]$exe, [string]$argumentos) {
    $p = New-Object System.Diagnostics.ProcessStartInfo
    $p.FileName = $exe
    $p.Arguments = $argumentos
    $p.WorkingDirectory = $RAIZ
    $p.UseShellExecute = $false
    [System.Diagnostics.Process]::Start($p)
}

function Falhou {
    Write-Host ""
    Write-Host "O envio falhou. Confira:"
    Write-Host "  - o IP na tela do robo ($IP aqui; troque na linha set IP= do envia.bat ou passe o IP: envia.bat 192.168.2.XXX);"
    Write-Host "  - se o PC esta na mesma rede do robo: ssh $ROBO"
    exit 2
}

# 1. O que mandar. A marca guarda caminho|data|tamanho de cada arquivo do último envio;
#    vai o que é novo ou mudou (até um arquivo com data antiga, vindo de um zip).
$enviados = @{}
if (-not $TUDO -and (Test-Path -LiteralPath $MARCA)) {
    $idade = (Get-Date).ToUniversalTime() - (Get-Item -LiteralPath $MARCA).LastWriteTimeUtc
    if ($idade.TotalHours -gt $HORAS_PARA_MANDAR_TUDO) {
        $TUDO = $true
    } else {
        foreach ($linha in [System.IO.File]::ReadAllLines($MARCA)) {
            $i = $linha.IndexOf('|')
            if ($i -gt 0) { $enviados[$linha.Substring(0, $i)] = $linha.Substring($i + 1) }
        }
    }
} else {
    $TUDO = $true
}
if ($enviados.Count -eq 0) { $TUDO = $true }   # marca vazia (a do envia.sh só tem a data)

$inicio  = (Get-Date).ToUniversalTime()   # o que for salvo durante o envio vai de novo no próximo
$todos   = New-Object System.Collections.Generic.List[object]
$pastas  = New-Object System.Collections.Generic.Stack[string]
$pastas.Push($RAIZ)
while ($pastas.Count -gt 0) {
    foreach ($item in Get-ChildItem -LiteralPath $pastas.Pop() -Force) {
        if ($item.PSIsContainer) {
            if ($PULA_PASTAS -notcontains $item.Name) { $pastas.Push($item.FullName) }
            continue
        }
        $pula = $false
        foreach ($padrao in $PULA_ARQUIVOS) { if ($item.Name -like $padrao) { $pula = $true; break } }
        if ($pula) { continue }
        $rel = $item.FullName.Substring($RAIZ.Length).TrimStart('\', '/').Replace('\', '/')
        $todos.Add([PSCustomObject]@{
            Rel   = $rel
            Marca = "$($item.LastWriteTimeUtc.Ticks)|$($item.Length)"
        })
    }
}
$mandar = @($todos | Where-Object { $TUDO -or $enviados[$_.Rel] -ne $_.Marca } | ForEach-Object { $_.Rel })

function Grava-Marca {
    $linhas = [string[]]@($todos | ForEach-Object { "$($_.Rel)|$($_.Marca)" })
    [System.IO.File]::WriteAllLines($MARCA, $linhas)
    (Get-Item -LiteralPath $MARCA).LastWriteTimeUtc = $inicio
}

# 2. Nada mudou: só encerra o programa no robô.
if ($mandar.Count -eq 0) {
    Write-Host "Nada mudou desde o ultimo envio para $IP (para mandar tudo: envia.bat tudo)."
    $ssh = Roda $SSH "-o ConnectTimeout=5 $ROBO `"$ENCERRA`""
    $ssh.WaitForExit()
    if ($ssh.ExitCode -ne 0) { Falhou }
    exit 0
}

if ($TUDO) {
    Write-Host "Mandando a pasta inteira ($($mandar.Count) arquivos) para ${ROBO}:~/$PROJETO ..."
} else {
    Write-Host "Mandando $($mandar.Count) arquivo(s) que mudaram para ${ROBO}:~/$PROJETO :"
    $mandar | ForEach-Object { Write-Host "  $_" }
}

# 3. Um pacote só, pela mesma conexão: cria a pasta no robô, desempacota e encerra o programa.
#    O pacote entra no ssh pelo "<" do cmd (o PowerShell 5 estraga dados binários num "|").
#    O -m do tar dá a data de agora aos arquivos (o relógio do robô pode estar diferente do PC).
#    A lista vai com LF (com CRLF o tar procura "main.py\r") e na codificação ANSI do Windows,
#    que é a que o tar do Windows usa para ler nomes com acento.
[System.IO.File]::WriteAllText($LISTA, (($mandar -join "`n") + "`n"), [System.Text.Encoding]::Default)
$remoto = "mkdir -p ~/'$PROJETO' && tar -xzmf - -C ~/'$PROJETO' && { $ENCERRA; }"
try {
    $tar = Roda $TAR "-czf `"$PACOTE`" -T `"$LISTA`""
    $tar.WaitForExit()
    if ($tar.ExitCode -ne 0) {
        Write-Host ""
        Write-Host "O tar nao conseguiu empacotar os arquivos acima (nada foi mandado)."
        exit 2
    }
    $cmd = Roda $env:ComSpec "/d /s /c `"`"$SSH`" -o ConnectTimeout=5 $ROBO `"$remoto`" < `"$PACOTE`"`""
    $cmd.WaitForExit()
    $ok = ($cmd.ExitCode -eq 0)
} finally {
    Remove-Item -LiteralPath $LISTA, $PACOTE -Force -ErrorAction SilentlyContinue
}
if (-not $ok) { Falhou }

Grava-Marca
Write-Host "Envio concluido."
