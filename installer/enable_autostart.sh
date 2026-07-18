#!/bin/bash
# RoadBook Pi - Habilita el autoarranque al bootear la Raspberry Pi
#
# Uso: ./installer/enable_autostart.sh
#
# Genera el servicio systemd a partir de la plantilla, sustituyendo
# el usuario y el directorio de instalación reales, y lo activa.

set -e

INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_NAME="roadbook-pi.service"
TEMPLATE="$INSTALL_DIR/installer/roadbook-pi.service.template"
TARGET="/etc/systemd/system/$SERVICE_NAME"

if [ ! -d "$INSTALL_DIR/.venv" ]; then
    echo "No se encontró $INSTALL_DIR/.venv — corré primero ./installer/install.sh"
    exit 1
fi

echo "Generando servicio systemd en $TARGET..."
sed -e "s|__INSTALL_DIR__|$INSTALL_DIR|g" -e "s|__USER__|$(whoami)|g" "$TEMPLATE" \
    | sudo tee "$TARGET" > /dev/null

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo ""
echo "RoadBook Pi configurado para arrancar automáticamente al bootear."
echo ""
echo "Comandos útiles:"
echo "  Ver estado:        systemctl status $SERVICE_NAME"
echo "  Ver logs en vivo:   journalctl -u $SERVICE_NAME -f"
echo "  Reiniciar:          sudo systemctl restart $SERVICE_NAME"
echo "  Deshabilitar:       ./installer/disable_autostart.sh"
