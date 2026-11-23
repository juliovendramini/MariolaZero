# Le um cartao SD inteiro no Windows (precisa de administrador; o le_cartao.bat pede).
#
#   le_cartao.bat                        le o cartao DUAS vezes, grava a primeira leitura em
#                                        D:\cartaoReserva-AAAA-MM-DD.img e compara as duas
#   le_cartao.bat confere ARQUIVO.img    le o cartao e compara com o arquivo (ex.: depois de
#                                        gravar o cartao novo no USBImager). Caminho completo,
#                                        sem espacos (a janela de administrador abre em System32)
#   le_cartao.bat rele 386+387           le esses pedacos de 16 MB 7 vezes e grava cada leitura
#                                        em D:\cartaoReserva-relido-...\ (cartao instavel; separe com +:
#                                        o cmd come virgula e aspas)
#
# As duas leituras sao comparadas em pedacos de 16 MB, para dizer ONDE o cartao le diferente.
# Feito em 18/11/2026 para o cartao de reserva do Mariola (secao 17 do INSTALACAO.md).
# Sem acentos de proposito: o PowerShell 5.1 le .ps1 sem BOM como ANSI.

param(
    [string]$Modo = 'le',
    [string]$Arquivo = '',
    [string]$Destino = 'D:\',
    [string]$Teste = ''      # so para testar o script: um arquivo faz o papel do cartao
)
$ErrorActionPreference = 'Stop'
$PEDACO = 16MB

function Sai($msg) { Write-Host "`nERRO: $msg" -ForegroundColor Red; exit 1 }

$admin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()
         ).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $admin -and -not $Teste) { Sai 'rode pelo le_cartao.bat (ele pede administrador)' }
if ($Modo -notin 'le', 'confere', 'rele') { Sai "modo desconhecido: $Modo (use 'confere ARQUIVO.img', 'rele PEDACO[,PEDACO...]' ou nada)" }
if ($Modo -eq 'confere') {
    if (-not $Arquivo -or -not (Test-Path -LiteralPath $Arquivo -PathType Leaf)) { Sai "nao achei o arquivo '$Arquivo'" }
    $Arquivo = (Resolve-Path -LiteralPath $Arquivo).Path
}

Add-Type @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class DiscoCru {
    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    public static extern SafeFileHandle CreateFile(string nome, uint acesso, uint compartilha,
        IntPtr seguranca, uint criacao, uint flags, IntPtr modelo);
}
'@

# ---------- escolhe o cartao ----------
# so discos removiveis/USB/SD de 1 a 128 GB, que nao sejam o de boot nem o do sistema
if ($Teste) {
    $TAM = [int64](Get-Item -LiteralPath $Teste).Length
    $dispositivo = (Resolve-Path -LiteralPath $Teste).Path
} else {
    $discos = @(Get-Disk | Where-Object {
        -not $_.IsBoot -and -not $_.IsSystem -and $_.Size -ge 1GB -and $_.Size -le 128GB -and
        ("$($_.BusType)" -in 'USB', 'SD', 'MMC')
    } | Sort-Object Number)
    if ($discos.Count -eq 0) { Sai 'nenhum cartao encontrado (o leitor esta ligado? o cartao esta nele?)' }
    Write-Host "`nCartoes encontrados:"
    foreach ($d in $discos) {
        $np = @(Get-Partition -DiskNumber $d.Number -ErrorAction SilentlyContinue).Count
        '  disco {0}: {1}  ({2}, {3:N2} GB = {4:N0} bytes, {5} particoes)' -f $d.Number, $d.FriendlyName,
            $d.BusType, ($d.Size / 1GB), $d.Size, $np | Write-Host
    }
    Write-Host ''
    Write-Host 'Se o Windows oferecer "formatar o disco", clique em CANCELAR.' -ForegroundColor Yellow
    $n = Read-Host 'Numero do disco do cartao'
    $disco = $discos | Where-Object { "$($_.Number)" -eq $n.Trim() }
    if (-not $disco) { Sai "o disco '$n' nao esta na lista" }
    $TAM = [int64]$disco.Size
    $dispositivo = "\\.\PhysicalDrive$($disco.Number)"
}

# ---------- uma leitura do cartao inteiro ----------
# devolve @{ total = md5 do cartao; pedacos = lista de md5 por pedaco }
# $saida: grava o que leu nesse arquivo; $compara: le o arquivo junto e compara pedaco por pedaco
function LeCartao([string]$titulo, [string]$saida, [string]$compara, [int64]$limite) {
    $h = [DiscoCru]::CreateFile($dispositivo, [uint32]2147483648, 3, [IntPtr]::Zero, 3, 0, [IntPtr]::Zero)
    if ($h.IsInvalid) { Sai "nao consegui abrir $dispositivo (erro $([Runtime.InteropServices.Marshal]::GetLastWin32Error()))" }
    $fs = New-Object IO.FileStream($h, [IO.FileAccess]::Read, 4096)
    $out = $null; $ref = $null
    if ($saida)   { $out = New-Object IO.FileStream($saida, [IO.FileMode]::Create, [IO.FileAccess]::Write, [IO.FileShare]::None, 4MB) }
    if ($compara) { $ref = New-Object IO.FileStream($compara, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read, 4MB) }
    $buf = New-Object byte[] $PEDACO
    $bufRef = if ($ref) { New-Object byte[] $PEDACO } else { $null }
    $md5Total = [Security.Cryptography.MD5]::Create()
    $md5 = [Security.Cryptography.MD5]::Create()
    $pedacos = New-Object Collections.Generic.List[string]
    $difs = New-Object Collections.Generic.List[int]
    $pos = [int64]0; $i = 0
    $relogio = [Diagnostics.Stopwatch]::StartNew()
    try {
        while ($pos -lt $limite) {
            $quer = [int][Math]::Min([int64]$PEDACO, $limite - $pos)
            $tem = 0
            while ($tem -lt $quer) {
                try { $r = $fs.Read($buf, $tem, $quer - $tem) }
                catch { Sai ("erro de leitura do cartao em {0:N0} bytes ({1:N0} MB): {2}" -f ($pos + $tem), (($pos + $tem) / 1MB), $_.Exception.Message) }
                if ($r -le 0) { Sai ("o cartao acabou antes da hora, em {0:N0} bytes" -f ($pos + $tem)) }
                $tem += $r
            }
            [void]$md5Total.TransformBlock($buf, 0, $quer, $null, 0)
            $pedacos.Add([BitConverter]::ToString($md5.ComputeHash($buf, 0, $quer)).Replace('-', '').ToLower())
            if ($out) { $out.Write($buf, 0, $quer) }
            if ($ref) {
                $t = 0
                while ($t -lt $quer) { $r = $ref.Read($bufRef, $t, $quer - $t); if ($r -le 0) { break }; $t += $r }
                if ($t -ne $quer -or $pedacos[$i] -ne [BitConverter]::ToString($md5.ComputeHash($bufRef, 0, $quer)).Replace('-', '').ToLower()) { $difs.Add($i) }
            }
            $pos += $quer; $i++
            $s = [Math]::Max($relogio.Elapsed.TotalSeconds, 0.1)
            $vel = $pos / 1MB / $s
            Write-Progress -Activity $titulo -Status ('{0:N0} de {1:N0} MB  ({2:N1} MB/s, falta ~{3:N0} min)' -f ($pos / 1MB), ($limite / 1MB), $vel, (($limite - $pos) / 1MB / $vel / 60)) -PercentComplete ([int](100 * $pos / $limite))
        }
    } finally {
        $fs.Close(); if ($out) { $out.Close() }; if ($ref) { $ref.Close() }
        Write-Progress -Activity $titulo -Completed
    }
    [void]$md5Total.TransformFinalBlock($buf, 0, 0)
    $total = [BitConverter]::ToString($md5Total.Hash).Replace('-', '').ToLower()
    '  {0}: {1:N0} MB em {2:N1} min, md5 {3}' -f $titulo, ($limite / 1MB), $relogio.Elapsed.TotalMinutes, $total | Write-Host
    return @{ total = $total; pedacos = $pedacos; difs = $difs }
}

function MostraDiferencas($lista) {
    foreach ($k in $lista) {
        '    pedaco {0}: de {1:N0} a {2:N0} MB do cartao' -f $k, ([int64]$k * $PEDACO / 1MB), ([Math]::Min(([int64]$k + 1) * $PEDACO, $TAM) / 1MB) | Write-Host
    }
}

# ---------- rele: le alguns pedacos de 16 MB varias vezes ----------
# (para achar, bloco a bloco, onde um cartao instavel le diferente; o Claude compara os arquivos)
if ($Modo -eq 'rele') {
    $lista = @($Arquivo -split '[ ,;+]+' | Where-Object { $_ } | ForEach-Object { [int]$_ })
    if ($lista.Count -eq 0) { Sai 'diga os pedacos: le_cartao.bat rele 386+387' }
    $VEZES = 7
    $pasta = Join-Path $Destino ('cartaoReserva-relido-{0}' -f (Get-Date -Format 'yyyy-MM-dd_HHmm'))
    New-Item -ItemType Directory -Force -Path $pasta | Out-Null
    $h = [DiscoCru]::CreateFile($dispositivo, [uint32]2147483648, 3, [IntPtr]::Zero, 3, 0, [IntPtr]::Zero)
    if ($h.IsInvalid) { Sai "nao consegui abrir $dispositivo" }
    $fs = New-Object IO.FileStream($h, [IO.FileAccess]::Read, 4096)
    $buf = New-Object byte[] $PEDACO
    $md5 = [Security.Cryptography.MD5]::Create()
    try {
        for ($v = 1; $v -le $VEZES; $v++) {
            foreach ($k in $lista) {
                $pos = [int64]$k * $PEDACO
                $quer = [int][Math]::Min([int64]$PEDACO, $TAM - $pos)
                [void]$fs.Seek($pos, [IO.SeekOrigin]::Begin)
                $tem = 0
                while ($tem -lt $quer) { $r = $fs.Read($buf, $tem, $quer - $tem); if ($r -le 0) { Sai "o cartao acabou no pedaco $k" }; $tem += $r }
                $o = [IO.File]::Create((Join-Path $pasta ('pedaco{0}_{1}.bin' -f $k, $v))); $o.Write($buf, 0, $quer); $o.Close()
                '  leitura {0}/{1}, pedaco {2}: md5 {3}' -f $v, $VEZES, $k, [BitConverter]::ToString($md5.ComputeHash($buf, 0, $quer)).Replace('-', '').ToLower() | Write-Host
            }
        }
    } finally { $fs.Close() }
    Write-Host "`nPRONTO: $pasta"
    exit 0
}

# ---------- confere: cartao x arquivo ----------
if ($Modo -eq 'confere') {
    $tamArq = (Get-Item -LiteralPath $Arquivo).Length
    '  arquivo: {0} ({1:N0} bytes)' -f $Arquivo, $tamArq | Write-Host
    if ($TAM -lt $tamArq) { Sai ('o cartao ({0:N0} bytes) e MENOR que o arquivo: a gravacao cortou o fim' -f $TAM) }
    if ($TAM -gt $tamArq) { '  o cartao e {0:N0} bytes maior que o arquivo; confiro so o tamanho do arquivo' -f ($TAM - $tamArq) | Write-Host }
    $r = LeCartao 'Conferindo o cartao com o arquivo' $null $Arquivo $tamArq
    # md5 de cada pedaco do cartao e a lista dos diferentes, ao lado do arquivo (para comparar depois)
    $base = '{0}.confere-{1}' -f $Arquivo, (Get-Date -Format 'yyyyMMdd_HHmm')
    try {
        $r.pedacos | Set-Content -LiteralPath "$base.pedacos.txt" -Encoding ascii
        $r.difs | Set-Content -LiteralPath "$base.diferentes.txt" -Encoding ascii
        Write-Host "  md5 por pedaco: $base.pedacos.txt"
    } catch { Write-Host "  (nao consegui gravar $base.*: $($_.Exception.Message))" }
    if ($r.difs.Count -eq 0) {
        Write-Host "`nCARTAO IGUAL AO ARQUIVO." -ForegroundColor Green
        exit 0
    }
    Write-Host ("`nO CARTAO ESTA DIFERENTE DO ARQUIVO em {0} pedaco(s) de 16 MB:" -f $r.difs.Count) -ForegroundColor Red
    MostraDiferencas $r.difs
    exit 1
}

# ---------- le: duas leituras ----------
if (-not (Test-Path -LiteralPath $Destino)) { Sai "a pasta de destino $Destino nao existe" }
$livre = (New-Object IO.DriveInfo((Resolve-Path -LiteralPath $Destino).Path)).AvailableFreeSpace
if ($livre -lt $TAM + 100MB) { Sai ('falta espaco em {0}: tem {1:N1} GB, precisa de {2:N1} GB' -f $Destino, ($livre / 1GB), ($TAM / 1GB)) }
$img = Join-Path $Destino ('cartaoReserva-{0}.img' -f (Get-Date -Format 'yyyy-MM-dd'))
if (Test-Path -LiteralPath $img) {
    $resp = Read-Host "$img ja existe. Sobrescrever? (s/n)"
    if ($resp -ne 's') { Sai 'cancelado' }
}
'  1a leitura vai para {0} ({1:N1} GB); a 2a so confere' -f $img, ($TAM / 1GB) | Write-Host
$parcial = "$img.parcial"
$a = LeCartao '1a leitura do cartao (gravando no arquivo)' $parcial $null $TAM
$b = LeCartao '2a leitura do cartao' $null $null $TAM
Move-Item -LiteralPath $parcial -Destination $img -Force
"$($a.total)  $(Split-Path -Leaf $img)" | Set-Content -LiteralPath "$img.md5" -Encoding ascii
$a.pedacos | Set-Content -LiteralPath "$img.pedacos1.txt" -Encoding ascii
$b.pedacos | Set-Content -LiteralPath "$img.pedacos2.txt" -Encoding ascii

$difs = @(for ($k = 0; $k -lt $a.pedacos.Count; $k++) { if ($a.pedacos[$k] -ne $b.pedacos[$k]) { $k } })
Write-Host ''
if ($difs.Count -eq 0) {
    Write-Host 'AS DUAS LEITURAS DERAM IGUAIS: neste leitor o cartao le estavel.' -ForegroundColor Green
} else {
    Write-Host ('AS DUAS LEITURAS DERAM DIFERENTES em {0} pedaco(s) de 16 MB:' -f $difs.Count) -ForegroundColor Red
    MostraDiferencas $difs
    Write-Host '  O cartao le instavel tambem no PC: ele esta com defeito.'
    Write-Host '  O arquivo ficou com a 1a leitura (os md5 por pedaco estao nos .pedacos1/2.txt).'
}
Write-Host "`nImagem: $img"
Write-Host "md5:    $($a.total)"
