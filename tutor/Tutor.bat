@echo off
rem Abre a pagina do robo tutor no navegador (tutor\servidor.py). Feche esta janela para parar.
rem Usa o Python portatil do simulador (..\simuladorLine\portatil\python) quando ele existe e tem o
rem pacote anthropic; senao, o Python do PC.
setlocal
set "RAIZ=%~dp0"
set "PY=python"
set "PORTATIL=%RAIZ%..\simuladorLine\portatil\python\python.exe"
if exist "%PORTATIL%" (
    "%PORTATIL%" -I -c "import anthropic" 2>nul && set "PY=%PORTATIL%"
)
if not "%PY%"=="python" (
    rem isola o Python portatil de outro Python instalado no PC
    set "PYTHONHOME="
    set "PYTHONPATH="
    set "PYTHONNOUSERSITE=1"
)
"%PY%" "%RAIZ%servidor.py" %*
if errorlevel 1 pause
