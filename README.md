# RoadBook Pi

**v1.0.0** — Plataforma de navegación basada en eventos geográficos
para Raspberry Pi.

No es un GPS tradicional: ejecuta acciones automáticamente (mostrar
imagen, reproducir audio, registrar eventos, ejecutar plugins) cuando
el vehículo llega a una posición determinada. Pensado para roadbooks
de rally, turismo guiado, rutas educativas, o cualquier recorrido
donde quieras disparar contenido en puntos geográficos específicos,
funcionando completamente offline.

Licencia: [MIT](LICENSE).

## Estado

Los 12 sprints del roadmap original están completos. Ver
`docs/CHANGELOG.md` para el detalle de cada uno.

| Sprint | Descripción         | Estado        |
|--------|----------------------|----------------|
| 1      | Framework             | ✅ |
| 2      | CRUD                   | ✅ |
| 3      | GPS                     | ✅ |
| 4      | Navigation Engine       | ✅ |
| 5      | Resource Library        | ✅ |
| 6      | Graphic Engine          | ✅ |
| 7      | Offline Maps            | ✅ |
| 8      | Event Engine            | ✅ |
| 9      | Plugins                 | ✅ |
| 10     | Optimization             | ✅ |
| 11     | Beta                     | ✅ |
| 12     | Version 1.0              | ✅ |

## Funcionalidad

- **Waypoints con condiciones**: radio de disparo, velocidad mínima,
  rumbo de aproximación, re-disparo o disparo único por sesión.
- **Secuencias de acciones configurables** por waypoint: mostrar
  imagen, reproducir audio, esperar, ocultar, registrar log, ejecutar
  un plugin propio — en cualquier orden, editables desde la UI.
- **GPS con 3 backends**: `gpsd`, `serial` (NEO-6M/NEO-M8N directo), o
  `simulator` para desarrollar sin hardware.
- **Mapas offline** vía MBTiles (raster, pensado para el límite de
  CPU/GPU de una Raspberry Pi 2).
- **Biblioteca de recursos** (imágenes, audio, iconos) con importación
  y organización propia — nunca rutas absolutas.
- **Plugins** en Python puro, opt-in explícito por nombre en la config.
- **100% offline** — sin dependencias de red en ningún módulo.

## Arquitectura

```
GPS → Navigation Engine → Event Engine → Action Dispatcher → UI / Audio / Logger / Plugins
```

La UI nunca se conecta directamente al GPS ni a la base de datos: todo
pasa por el Core. MVC se aplica solo dentro de la capa UI; el Core es
una arquitectura en capas + event-driven.

## Estructura del proyecto

```
roadbook_pi/
├── core/                 # Lógica de negocio (GPS, navegación, eventos, etc.)
├── ui/                   # Interfaz PyQt6
│   └── screens/
├── database/             # SQLite: migraciones versionadas, repositorios
├── plugins/              # Plugins propios (ver plugins.enabled en config.json)
├── resources/            # images/ audio/ icons/ maps/
├── tests/                # Tests con pytest
├── installer/            # Instalación y autoarranque en Raspberry Pi
├── docs/                 # CHANGELOG
└── main.py               # Punto de entrada
```

## Requisitos

- Python 3.10+
- Raspberry Pi 2 o superior (o cualquier equipo con Linux/Windows/macOS
  para desarrollo, usando el backend `simulator` de GPS)

## Instalación

### En Raspberry Pi (con autoarranque)

```bash
./installer/install.sh
./installer/enable_autostart.sh
```

Ver `installer/README.md` para más detalle.

### Desarrollo (cualquier plataforma)

```bash
python -m venv .venv
source .venv/bin/activate  # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Con el backend `simulator` (default en `config.json`) la app corre
sin hardware GPS real.

## Ejecutar

```bash
python main.py
```

## Configuración

Todo vive en `config.json` (se crea con valores por defecto en el
primer arranque). Claves principales:

- `gps.backend`: `"gpsd"`, `"serial"` o `"simulator"`.
- `maps.mbtiles_path`: ruta a un archivo `.mbtiles` propio (no se
  incluye ninguno — ver nota abajo).
- `plugins.enabled`: lista de nombres de plugins a cargar desde
  `plugins/`.
- `navigation.heading_tolerance_degrees`, `graphics.image_display_seconds`,
  `audio.volume`: ajustes finos de comportamiento.

### Mapas offline

El proyecto no incluye ningún archivo `.mbtiles` (son de cientos de MB
a varios GB). Generá el tuyo con herramientas como
[MOBAC](https://mobac.sourceforge.io/) o `mb-util`, colocalo en
`resources/maps/`, y apuntá `maps.mbtiles_path` en la config. Sin ese
archivo, la app funciona igual — solo sin mapa visual de fondo.

## Escribir un plugin propio

Copiá `plugins/example_logger_plugin.py`, cambiá `name`, implementá
`execute()`, y agregá el nombre a `plugins.enabled` en `config.json`.
Un archivo en `plugins/` nunca se ejecuta solo por estar ahí — hay que
habilitarlo explícitamente.

## Tests

```bash
pip install pytest
pytest
```

## Formato y linting

```bash
black .
ruff check .
```

## Contribuir

El proyecto sigue las convenciones documentadas en
`RoadBookPi_MASTER_SPECIFICATION_FOR_CLAUDE.md` / `CLAUDE.md`: código
en inglés, documentación en español, type hints obligatorios, logging
obligatorio, tests para lógica crítica, arquitectura en capas sin
acoplar UI y Core. Cada cambio de schema de base de datos va en una
migración nueva (`database/migrations/NNN_*.sql`), nunca modificando
una existente.

## Licencia

MIT — ver [LICENSE](LICENSE).
