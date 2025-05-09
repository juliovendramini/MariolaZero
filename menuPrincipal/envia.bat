@echo off
scp * banana@192.168.2.208:~\menuPrincipal
ssh banana@192.168.2.208 "killall main.py"
