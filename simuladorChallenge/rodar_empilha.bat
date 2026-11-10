@echo off
rem O Bombertinho empilhando 5 cubos numa plataforma (3 embaixo, 2 em cima): exemplo_bombertinho\empilha.py
rem Na janela: Iniciar partida (F5). Aceita as opcoes do simulador.py (ex.: --velocidade 2).
cd /d "%~dp0"
call "%~dp0Simulador.bat" --robo robo_bombertinho.json --cenario cenarios\empilha.json --programa exemplo_bombertinho\empilha.py %*
