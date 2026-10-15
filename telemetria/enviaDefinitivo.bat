@echo off
set IP=192.168.1.196
for %%i in ("%CD%") do set NOMEPROJETO=%%~ni

echo [1/3] Organizando pastas localmente...
set TEMP_DIR=%TEMP%\Deploy_%NOMEPROJETO%
if exist "%TEMP_DIR%" rmdir /S /Q "%TEMP_DIR%"
mkdir "%TEMP_DIR%\backup_completo"
mkdir "%TEMP_DIR%\instalador"

echo [2/3] Separando Backup e Instalador...
xcopy * "%TEMP_DIR%\backup_completo\" /E /H /Y /Q >nul

copy *.html "%TEMP_DIR%\instalador\" >nul 2>&1
copy *.css "%TEMP_DIR%\instalador\" >nul 2>&1
copy *.js "%TEMP_DIR%\instalador\" >nul 2>&1
copy *.php "%TEMP_DIR%\instalador\" >nul 2>&1
copy install.sh "%TEMP_DIR%\instalador\" >nul 2>&1
copy remonta.sh "%TEMP_DIR%\instalador\" >nul 2>&1
copy README.md "%TEMP_DIR%\instalador\" >nul 2>&1

echo [3/3] Transferindo projeto para a Banana Pi...
ssh banana@%IP% "mkdir -p ~/%NOMEPROJETO%"
scp -r "%TEMP_DIR%\backup_completo" "%TEMP_DIR%\instalador" banana@%IP%:~/%NOMEPROJETO%/

echo Limpando arquivos temporarios do PC...
rmdir /S /Q "%TEMP_DIR%"

echo Arquivos enviados com sucesso! Vá para o terminal do Linux para instalar.