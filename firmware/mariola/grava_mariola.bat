@echo off
rem Copia esta pasta para o brick e roda o grava_mariola.sh nele (pelo SSH, interativo).
rem O RESET do Mariola e apertado a mao, na hora do ENTER. Explicacao: LEIAME.md
cd /d "%~dp0"
set IP=192.168.2.110
set /p IP=IP do brick [%IP%]:
echo.
echo Copiando o firmware para o brick (%IP%)...
ssh banana@%IP% "mkdir -p ~/firmware_mariola"
if errorlevel 1 goto erro
scp grava_mariola.sh placaBrickVendra.ino.eightanaloginputs_328pb.hex LEIAME.md banana@%IP%:firmware_mariola/
if errorlevel 1 goto erro
echo.
ssh -t banana@%IP% "bash ~/firmware_mariola/grava_mariola.sh"
echo.
pause
exit /b

:erro
echo.
echo Nao consegui falar com o brick em %IP% (ligado? mesma rede? IP certo?).
pause
