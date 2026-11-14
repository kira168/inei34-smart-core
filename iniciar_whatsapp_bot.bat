@echo off
chcp 65001 >nul
title INEI 34 Chancay - Bot Institucional de WhatsApp
color 0A

echo ======================================================================
echo           I.E. INEI Nº 34 - CHANCAY
echo        BOT INSTITUCIONAL DE CITACIONES WHATSAPP (S/ 0.00)
echo ======================================================================
echo.
echo [1/3] Verificando entorno Node.js...
node -v >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Node.js no está instalado en el sistema.
    pause
    exit /b 1
)

echo [2/3] Liberando puerto 3001 si ya estaba en uso...
for /f "tokens=5" %%a in ('netstat -aon ^| findstr :3001 ^| findstr LISTENING') do taskkill /f /pid %%a >nul 2>&1

echo [3/3] Iniciando Gateway de WhatsApp (Puerto 3001)...
echo.
echo  - Estado del Servicio: http://127.0.0.1:3001/api/whatsapp/status
echo  - Plantilla oficial: CET N° 34 - CHANCAY (Bienestar Académico)
echo ======================================================================
echo.

cd /d "%~dp0whatsapp_bot"
node server.js
pause
