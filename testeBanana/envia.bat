@echo off
scp * banana@192.168.2.208:~\testeBanana
ssh banana@192.168.2.208 "killall main.py"
@REM ssh banana@192.168.2.151 "bash ~/testeBanana/executa.sh" || (
@REM     echo "Interrupção detectada! Enviando sinal para o script remoto..."
@REM     ssh banana@192.168.2.151 "bash ~/testeBanana/stop.sh"
@REM )