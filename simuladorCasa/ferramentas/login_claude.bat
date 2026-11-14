@echo off
rem Faz o login do Claude Code que vem dentro do pacote claude-agent-sdk, com a conta da mensalidade.
rem E o que o cerebro do robo usa com CEREBRO=assinatura (exemplo_casa\cerebro.py).
rem Abre o navegador para voce entrar com a sua conta do Claude. Precisa ser feito uma vez so.
setlocal
for /f "delims=" %%i in ('python -c "import claude_agent_sdk, os; print(os.path.join(os.path.dirname(claude_agent_sdk.__file__), '_bundled', 'claude.exe'))"') do set "CLAUDE=%%i"
if not exist "%CLAUDE%" (
    echo Nao achei o Claude Code do pacote. Rode antes:  pip install claude-agent-sdk
    pause
    exit /b 1
)
"%CLAUDE%" auth login --claudeai
echo.
"%CLAUDE%" auth status
pause
