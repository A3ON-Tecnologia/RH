@echo off
chcp 65001 >nul
title Instalar Sistema de RH (iniciar com o Windows)

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo.
  echo  *** PRECISA SER ADMINISTRADOR ***
  echo.
  echo  Feche esta janela, clique com o BOTAO DIREITO neste arquivo
  echo  e escolha "Executar como administrador".
  echo.
  pause
  exit /b 1
)

cd /d "%~dp0"
echo Instalando o Sistema de RH para iniciar junto com o Windows...
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0instalar-servico.ps1"
echo.
pause
