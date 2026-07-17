@echo off
chcp 65001 >nul
title Sistema de RH - Servidor
cd /d "%~dp0"
echo Iniciando o servidor do Sistema de RH...
echo.
python server.py
echo.
echo O servidor foi encerrado.
pause
