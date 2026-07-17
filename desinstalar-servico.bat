@echo off
chcp 65001 >nul
title Desinstalar servico do Sistema de RH

net session >nul 2>&1
if %errorlevel% neq 0 (
  echo.
  echo  *** PRECISA SER ADMINISTRADOR ***
  echo  Clique com o botao direito neste arquivo e escolha "Executar como administrador".
  echo.
  pause
  exit /b 1
)

echo Parando e removendo o servico "RH"...
schtasks /End    /TN "RH" >nul 2>&1
schtasks /Delete /TN "RH" /F
rem remove tambem uma instalacao antiga com o nome anterior, se existir
schtasks /Delete /TN "Sistema RH" /F >nul 2>&1
echo.
echo Pronto. O sistema nao inicia mais junto com o Windows.
echo (Voce ainda pode abrir manualmente com o iniciar-servidor.bat)
echo.
pause
