#!/bin/bash
# RoadBook Pi - Deshabilita el autoarranque configurado con
# enable_autostart.sh
#
# Uso: ./installer/disable_autostart.sh

set -e

SERVICE_NAME="roadbook-pi.service"

sudo systemctl stop "$SERVICE_NAME" 2>/dev/null || true
sudo systemctl disable "$SERVICE_NAME" 2>/dev/null || true
sudo rm -f "/etc/systemd/system/$SERVICE_NAME"
sudo systemctl daemon-reload

echo "Autoarranque de RoadBook Pi deshabilitado."
