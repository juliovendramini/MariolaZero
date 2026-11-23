@echo off
@REM Manda esta pasta para o Mariola (/home/banana/<nome-da-pasta>) e encerra o main.py que estiver
@REM rodando no robo. Duplo clique, F5 ou Ctrl+Shift+B no VS Code.
@REM   envia.bat                  manda so o que mudou, com as subpastas
@REM   envia.bat tudo             manda a pasta inteira
@REM   envia.bat 192.168.2.151    usa outro IP sem mexer neste arquivo
set IP=192.168.2.167
@REM MODO=ps1: pelo envia.ps1 desta pasta (so o que mudou, subpastas, uma conexao so).
@REM           Se o Windows nao deixar rodar o envia.ps1 (PC travado), usa o scp sozinho.
@REM MODO=scp: o jeito antigo: a pasta inteira toda vez (scp -r).
set MODO=ps1

cd /d "%~dp0"
for %%i in ("%CD%") do set NOMEPROJETO=%%~nxi
if /i "%MODO%"=="scp" goto scp
if not exist envia.ps1 goto scp

powershell -NoProfile -ExecutionPolicy Bypass -File envia.ps1 %IP% %*
@REM 0 = enviado; 2 = o envio falhou (o envia.ps1 ja disse por que); outro = o PowerShell nao rodou
if %errorlevel%==0 exit /b 0
if %errorlevel%==2 exit /b 2
echo.
echo O PowerShell nao rodou o envia.ps1: mandando a pasta inteira pelo scp.

:scp
if not "%~1"=="" if /i not "%~1"=="tudo" set IP=%~1
scp -r * banana@%IP%:~\%NOMEPROJETO%
ssh banana@%IP% "killall main.py"
