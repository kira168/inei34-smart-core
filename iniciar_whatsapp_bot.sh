#!/bin/bash
# INEI 34 Chancay - Script de inicio y dependencias WhatsApp Gateway
cd "$(dirname "$0")/whatsapp_bot"

echo "=========================================================="
echo "      I.E. INEI Nº 34 - BOT INSTITUCIONAL WHATSAPP"
echo "=========================================================="

if ! command -v node &> /dev/null; then
    echo "[!] Node.js no encontrado. Instalando Node.js v20 LTS..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt-get install -y nodejs
fi

echo "[*] Versión de Node.js: $(node -v)"
echo "[*] Versión de NPM: $(npm -v)"

if [ ! -d "node_modules" ]; then
    echo "[*] Instalando dependencias Baileys..."
    npm install
fi

echo "[*] Iniciando WhatsApp Gateway en puerto 3001..."
node server.js
