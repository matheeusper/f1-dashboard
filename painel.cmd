@echo off
rem Inicia o servidor do painel com os argumentos recebidos.
rem Usa o uv (baixa o Python e as dependencias sozinho na primeira vez).
rem Sem o uv, tenta o Python do sistema.
cd /d "%~dp0"

where uv >nul 2>nul
if not errorlevel 1 (
  uv run -q server.py %*
  goto :fim
)

where python >nul 2>nul
if not errorlevel 1 (
  echo [aviso] uv nao encontrado: usando o Python do sistema.
  echo         Para a voz natural do engenheiro: python -m pip install edge-tts
  python server.py %*
  goto :fim
)

echo.
echo Nao encontrei o uv nem o Python neste PC.
echo Instale o uv (leva 1 minuto) colando este comando no PowerShell:
echo.
echo     powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
echo.
echo Depois feche esta janela e abra o atalho de novo.

:fim
pause
