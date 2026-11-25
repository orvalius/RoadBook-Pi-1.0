# RoadBook Pi

**v1.2.0** — Plataforma de navegación basada en eventos geográficos
para Raspberry Pi.

No es un GPS tradicional: ejecuta acciones automáticamente (mostrar
imagen, reproducir audio, registrar eventos, ejecutar plugins) cuando
el vehículo llega a una posición determinada, y muestra una tira de
roadbook en vivo (Roadbook Rendering Engine) sincronizada con el GPS,
similar a los sistemas de navegación de rally raid. Pensado para
roadbooks de rally, turismo guiado, rutas educativas, o cualquier
recorrido donde quieras disparar contenido en puntos geográficos
específicos, funcionando completamente offline.

Licencia: [MIT](LICENSE).

## Estado

Los 12 sprints del roadmap original están completos, más un
rediseño posterior del Graphic Engine (Sprint 6) como Roadbook
Rendering Engine y una ronda de pulido (v1.2.0: cierre ordenado bajo
systemd, pantalla "Mapas y ruta", tests de la capa Qt). Ver `docs/CHANGELOG.md` para el detalle de cada uno.

| Sprint | Descripción         | Estado        |
|--------|----------------------|----------------|
| 1      | Framework             | ✅ |
| 2      | CRUD                   | ✅ |
| 3      | GPS                     | ✅ |
| 4      | Navigation Engine       | ✅ |
| 5      | Resource Library        | ✅ |
| 6      | Graphic Engine          | ✅ (rediseñado como Roadbook Rendering Engine, ver v1.1.0) |
| 7      | Offline Maps            | ✅ |
| 8      | Event Engine            | ✅ |
| 9      | Plugins                 | ✅ |
| 10     | Optimization             | ✅ |
| 11     | Beta                     | ✅ |
| 12     | Version 1.0              | ✅ |

## Funcionalidad

- **Roadbook Rendering Engine**: tira de notas en vivo (estilo tulip
  de rally raid) junto al mapa, sincronizada con la posición GPS —
  ícono, distancia parcial/total, texto de instrucción, con la nota
  actual resaltada y auto-scroll. Independiente del disparo de
  eventos: solo visualiza.
- **Waypoints con condiciones**: radio de disparo, velocidad mínima,
  rumbo de aproximación, re-disparo o disparo único por sesión.
- **Secuencias de acciones configurables** por waypoint: mostrar
  imagen, reproducir audio, esperar, ocultar, registrar log, ejecutar
  un plugin propio — en cualquier orden, editables desde la UI.
- **GPS con 3 backends**: `gpsd`, `serial` (NEO-6M/NEO-M8N directo), o
  `simulator` para desarrollar sin hardware.
- **Mapas offline** vía MBTiles (raster, pensado para el límite de
  CPU/GPU de una Raspberry Pi 2), elegibles e importables desde la
  pantalla **Mapas y ruta**, sin reiniciar.
- **Biblioteca de recursos** (imágenes, audio, iconos) con importación
  y organización propia — nunca rutas absolutas.
- **Plugins** en Python puro, opt-in explícito por nombre en la config.
- **100% offline** — sin dependencias de red en ningún módulo.

## Arquitectura

```
GPS → Navigation Engine → Event Engine → Action Dispatcher → UI / Audio / Logger / Plugins
GPS → Roadbook Engine → tira de roadbook (UI)
```

Dos ramas independientes que comparten la misma posición GPS: la
primera dispara acciones por radio (sin cambios desde el Sprint 8); la
segunda solo decide qué mostrar en la tira de notas en vivo, avanzando
secuencialmente sobre una ruta armada desde un track GPX o
conectando waypoints por orden. Ninguna de las dos dispara nada de la
otra.

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
- `maps.mbtiles_path`: mapa offline activo (no se incluye ninguno —
  ver nota abajo). Se elige desde la pantalla **Mapas y ruta**.
- `roadbook.gpx_path`: track GPX para ordenar la tira del roadbook
  (opcional). También se elige desde **Mapas y ruta**.
- `plugins.enabled`: lista de nombres de plugins a cargar desde
  `plugins/`.
- `navigation.heading_tolerance_degrees`, `graphics.image_display_seconds`,
  `audio.volume`: ajustes finos de comportamiento.

### Roadbook Rendering Engine

La tira de notas junto al mapa conecta los waypoints **activos** en
un orden determinado así:

1. Si hay un GPX activo (pantalla **Mapas y ruta** → "Track de la
   ruta"), ordena los waypoints según su posición a lo largo de ese
   track. Se aceptan GPX con track (`trkpt`) o, si no tienen, con
   ruta (`rtept`).
2. Si no, ordena por el campo `orden_ruta` de cada waypoint (editable
   desde el formulario de Waypoints), y como último recurso, por id
   de creación.

La distancia parcial/total que se muestra es en línea recta entre
puntos consecutivos, no proyectada sobre la geometría real de la
ruta — una simplificación deliberada para que funcione sin necesitar
un track preciso.

### Mapas offline

El proyecto no incluye ningún archivo `.mbtiles` (son de cientos de MB
a varios GB). Generá el tuyo con herramientas como
[MOBAC](https://mobac.sourceforge.io/) o `mb-util` (en formato raster PNG/JPG: los
tiles vectoriales no se pueden dibujar) e importalo desde **Mapas y
ruta** → "Importar…": se valida, se copia a `resources/maps/` con
barra de progreso, y queda activo al instante. Sin mapa, la app
funciona igual — solo sin mapa visual de fondo.

## Escribir un plugin propio

Copiá `plugins/example_logger_plugin.py`, cambiá `name`, implementá
`execute()`, y agregá el nombre a `plugins.enabled` en `config.json`.
Un archivo en `plugins/` nunca se ejecuta solo por estar ahí — hay que
habilitarlo explícitamente.

## Tests

```bash
pytest
```

Incluye tests de la capa Qt (`tests/test_ui_*.py`) que corren sin
pantalla (plataforma `offscreen`); necesitan `pytest-qt`, que ya está
en `requirements.txt`.

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
