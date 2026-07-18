#!/bin/bash
# RoadBook Pi - Instalación de dependencias
#
# Uso: ./installer/install.sh
#
# Instala las dependencias de sistema (Python, gpsd) y crea un
# entorno virtual con las dependencias de Python del proyecto.
# No configura autoarranque — para eso, correr después
# ./installer/enable_autostart.sh

set -e

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$INSTALL_DIR"

echo "=== RoadBook Pi - Instalación ==="
echo "Directorio del proyecto: $INSTALL_DIR"

echo ""
echo "--- Instalando dependencias de sistema ---"
sudo apt-get update
sudo apt-get install -y \
    python3 \
    python3-venv \
    python3-pip \
    gpsd \
    gpsd-clients \
    libgl1 \
    libegl1

echo ""
echo "--- Creando entorno virtual (.venv) ---"
python3 -m venv .venv
source .venv/bin/activate

echo ""
echo "--- Instalando dependencias de Python ---"
pip install --upgrade pip
pip install -r requirements.txt

echo ""
echo "=== Instalación completa ==="
echo ""
echo "Para ejecutar manualmente:"
echo "  source .venv/bin/activate && python main.py"
echo ""
echo "Para que arranque solo al bootear la Raspberry Pi:"
echo "  ./installer/enable_autostart.sh"
echo ""
echo "No te olvides de revisar config.json (backend de GPS, ruta del"
echo "mapa offline, etc.) antes del primer arranque."
