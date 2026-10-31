@echo off
rem Abre o simulador (aceita as mesmas opcoes do simulador.py).
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
"%PY%" "%RAIZ%simulador.py" %*
if errorlevel 1 pause
