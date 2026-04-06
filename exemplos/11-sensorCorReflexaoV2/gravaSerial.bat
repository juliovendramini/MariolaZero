@echo off
REM Grava o sketch via Serial (Optiboot) - usar APOS gravar o bootloader
REM O sketch DEVE ser compilado com a board "w/Optiboot" na Arduino IDE
REM Ajuste a porta COM conforme seu adaptador USB-Serial
REM Pressione o botao de Reset para entrar no bootloader antes de gravar
REM   (ou use DTR com capacitor 100nF para auto-reset)

set PORTA_SERIAL=COM8
set ARQUIVO_HEX=sensorLinhaPro1616.ino.t1616.20c0.mD0.v2610.hex

echo Gravando %ARQUIVO_HEX% via Optiboot na porta %PORTA_SERIAL%...
echo Pressione Reset no ATtiny1616 agora (ou use auto-reset via DTR)
echo.

C:\Users\Julio\AppData\Local\Arduino15\packages\DxCore\tools\avrdude\6.3.0-arduino17or18\bin\avrdude -CC:\Users\Julio\AppData\Local\Arduino15\packages\megaTinyCore\hardware\megaavr\2.6.10\avrdude.conf -v -pattiny1616 -carduino -P%PORTA_SERIAL% -b115200 -D -Uflash:w:%ARQUIVO_HEX%:i

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERRO ao gravar! Verifique:
    echo   - A porta COM esta correta?
    echo   - O botao de Reset foi pressionado?
    echo   - O sketch foi compilado com a board "w/Optiboot"?
)

pause
