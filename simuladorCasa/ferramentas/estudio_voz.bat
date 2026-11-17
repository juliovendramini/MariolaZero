@echo off
rem Estudio de voz do robo: abre uma pagina com 4 vozes para mexer nos botoes (tudo no PC, sem internet)
cd /d "%~dp0.."
python ferramentas\estudio_voz.py %*
pause
