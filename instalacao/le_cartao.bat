@echo off
rem Le o cartao SD inteiro no Windows (o trabalho fica no le_cartao.ps1, ao lado).
rem   le_cartao.bat                       le o cartao duas vezes e grava D:\cartaoReserva-AAAA-MM-DD.img
rem   le_cartao.bat confere ARQUIVO.img   compara o cartao com o arquivo (caminho completo, sem espacos)
rem Precisa de administrador: se nao for, pede (janela do UAC) e abre outra janela.
net session >nul 2>&1
if not errorlevel 1 goto admin
if "%~1"=="" (
    powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0'"
) else (
    powershell -NoProfile -Command "Start-Process -Verb RunAs -FilePath '%~f0' -ArgumentList '%*'"
)
exit /b

:admin
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0le_cartao.ps1" %*
echo.
pause
