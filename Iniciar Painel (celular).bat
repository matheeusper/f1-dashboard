@echo off
title Painel F1 25 - rede local (celular/tablet)
echo.
echo No celular (na mesma rede deste PC), abra no navegador:
for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4"') do (
  for /f "tokens=* delims= " %%b in ("%%a") do (
    echo     Painel:   http://%%b:8025
    echo     Evolucao: http://%%b:8025/evolucao
  )
)
echo.
call "%~dp0painel.cmd" --abrir --lan %*
