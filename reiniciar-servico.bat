@echo off
chcp 65001 >nul
title Reiniciar servico do Sistema de RH

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo.
  echo  *** PRECISA SER ADMINISTRADOR ***
  echo  Clique com o botao direito neste arquivo e escolha "Executar como administrador".
  echo.
  pause
  exit /b 1
)

echo Reiniciando o servico "RH"...
schtasks /End /TN "RH" >nul 2>&1
timeout /t 2 >nul
schtasks /Run /TN "RH"
echo.
echo Pronto. Use isto sempre que alterar o config.json.
echo.
pause
