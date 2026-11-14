@echo off
chcp 65001 >nul
title Reiniciando Bot de WhatsApp - CET 34 Chancay
color 0B

echo ======================================================================
echo           I.E. INEI Nº 34 - CHANCAY
echo       REINICIO DEL BOT CON NUEVA PLANTILLA (CET Nº 34)
echo ======================================================================
echo.
echo [1/3] Cerrando todas las instancias anteriores de Node.js...
taskkill /F /IM node.exe >nul 2>&1
timeout /t 2 /nobreak >nul
echo [OK] Procesos anteriores finalizados.
echo.
echo [2/3] Plantilla oficial cargada:
echo  - Titulo: CET N° 34 - CHANCAY
echo  - Indicacion: Bienestar Académico
echo ======================================================================
echo.
echo [3/3] Iniciando WhatsApp Bot oficial (Puerto 3001)...
echo.
cd /d "%~dp0whatsapp_bot"
node server.js
pause
