@echo off
set IP=192.168.2.151
@REM pego como padrao o nome da pasta atual para ser o nome do projeto
for %%i in ("%CD%") do set NOMEPROJETO=%%~ni
scp -r * banana@%IP%:~\%NOMEPROJETO%
ssh banana@%IP% "killall start.py"
