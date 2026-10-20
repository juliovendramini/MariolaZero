@echo off
rem Avalia um programa nos desafios (mesmas opcoes do avalia.py; ex.: Avaliar.bat --lista).
rem Usa o Python do pacote portatil (pasta portatil\python) quando ele existe; senao, o Python do PC.
setlocal
set "RAIZ=%~dp0"
set "PY=%RAIZ%portatil\python\python.exe"
if exist "%PY%" (
    rem isola o Python portatil de outro Python instalado no PC
    set "PYTHONHOME="
    set "PYTHONPATH="
    set "PYTHONNOUSERSITE=1"
) else (
    set "PY=python"
)
"%PY%" "%RAIZ%avalia.py" %*
if errorlevel 1 pause
