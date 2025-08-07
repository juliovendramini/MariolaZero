@echo off
scp * banana@192.168.2.151:~\menuPrincipal
ssh banana@192.168.2.151 "killall main.py"
