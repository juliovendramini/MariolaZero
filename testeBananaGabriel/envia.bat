@echo off
scp -r * banana@192.168.1.113:~\testeBananaGabriel
ssh banana@192.168.1.113 "killall main.py"
@REM ssh banana@192.168.2.151 "bash ~/testeBanana/executa.sh" || (
@REM     echo "Interrupção detectada! Enviando sinal para o script remoto..."
@REM     ssh banana@192.168.2.151 "bash ~/testeBanana/stop.sh"
@REM )