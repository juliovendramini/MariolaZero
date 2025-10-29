@echo off
REM Script para enviar arquivos do exemplo pinosDigitais para Banana Pi
echo Enviando arquivos para Banana Pi...

scp main.py root@192.168.2.151:/root/
scp ../../libs/pinosDigitais.py root@192.168.2.151:/root/libs/

echo.
echo Arquivos enviados com sucesso!
echo Para executar: ssh root@192.168.2.151 "python3 /root/main.py"
pause
