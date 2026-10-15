@echo off
set IP=192.168.1.196
for %%i in ("%CD%") do set NOMEPROJETO=%%~ni

echo [1/3] Transferindo projeto para  Banana Pi...
@REM Envia TUDO (Python, JSON, Web) para a pasta segura do seu usuário
scp -r * banana@%IP%:~/%NOMEPROJETO%

echo [2/3] Atualizando a interface no Apache...
@REM Entra via SSH e copia APENAS os arquivos da interface para o servidor web
ssh banana@%IP% "cp ~/%NOMEPROJETO%/*.html ~/%NOMEPROJETO%/*.css ~/%NOMEPROJETO%/*.js ~/%NOMEPROJETO%/*.php /var/www/html/ 2>/dev/null"

echo [3/3] Reiniciando os processos do Robo...
@REM pkill -f é mais seguro que killall, pois garante que vai matar apenas os scripts Python com esse nome
ssh banana@%IP% "killall python"

echo Deploy finalizado com sucesso!