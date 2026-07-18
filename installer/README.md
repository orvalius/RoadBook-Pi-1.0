# Installer de RoadBook Pi

Scripts para instalar RoadBook Pi en una Raspberry Pi (o cualquier
Linux con systemd) y configurar el autoarranque al bootear.

## Instalación

```bash
./installer/install.sh
```

Instala las dependencias de sistema (Python, gpsd) y crea el entorno
virtual `.venv` con las dependencias de `requirements.txt`.

## Autoarranque al bootear

```bash
./installer/enable_autostart.sh
```

Genera un servicio `systemd` (`roadbook-pi.service`) a partir de
`roadbook-pi.service.template`, sustituyendo el usuario y el
directorio de instalación reales, y lo activa.

Para deshabilitarlo:

```bash
./installer/disable_autostart.sh
```

## Notas

- El servicio asume una sesión gráfica en `DISPLAY=:0` (el
  comportamiento típico de Raspberry Pi OS con escritorio). Si tu
  setup usa Wayland o un display distinto, editá
  `roadbook-pi.service.template` antes de correr
  `enable_autostart.sh`.
- Revisá `config.json` (backend de GPS, ruta del `.mbtiles`, plugins
  habilitados) antes del primer arranque — ver el README principal.
- Los logs de la aplicación quedan en `logs/roadbook_pi.log`
  (rotativo) además de en `journalctl -u roadbook-pi.service`.
