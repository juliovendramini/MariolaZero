@echo off
set IP=192.168.2.151
@REM pego como padrao o nome da pasta atual para ser o nome do projeto
for %%i in ("%CD%") do set NOMEPROJETO=%%~ni
scp -r * banana@%IP%:~\%NOMEPROJETO%
ssh banana@%IP% "killall main.py"
@REM o código abaixo é para rodar o script remoto direto do terminal do vscode
@REM porém nao ficou muito bom. Recomendo manter comentado e executar o código por um terminal ssh a parte
@REM ssh banana@%IP% "bash ~/%NOMEPROJETO%/executa.sh" || (
@REM     echo "Interrupção detectada! Enviando sinal para o script remoto..."
@REM     ssh banana@%IP% "bash ~/%NOMEPROJETO%/stop.sh"
@REM )