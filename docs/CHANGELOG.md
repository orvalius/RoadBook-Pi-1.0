# Changelog

Todas las modificaciones relevantes de este proyecto se documentan aquí.

## [0.1.0] - Sprint 1: Framework

### Agregado

- Estructura de carpetas completa: `core/`, `ui/`, `database/`,
  `resources/`, `tests/`, `installer/`, `docs/`.
- `core/logger.py`: logging centralizado (consola + archivo rotativo).
- `core/config_manager.py`: gestión de configuración persistente en
  `config.json`, con claves anidadas (`gps.port`, `display.width`, etc.).
- `database/schema.sql` y `database/db_manager.py`: tabla `waypoints`
  según especificación (id, nombre, latitud, longitud, radio,
  categoria, imagen, audio, velocidad, angulo, prioridad, descripcion,
  activo).
- Interfaces stub del Core, listas para implementación en sprints
  futuros sin romper compatibilidad:
  - `gps_manager.py` (Sprint 3)
  - `navigation_engine.py` (Sprint 4) — incluye cálculo haversine
    funcional desde ya.
  - `event_engine.py` (Sprint 8)
  - `action_dispatcher.py` (Sprint 6/9)
  - `resource_manager.py` (Sprint 5)
  - `audio_manager.py` (Sprint 6/8)
  - `plugin_manager.py` (Sprint 9)
- UI con PyQt6: `MainWindow` con navegación lateral y pantallas stub
  (Navegación, Waypoints, Biblioteca, Logs). Pantalla de Configuración
  ya funcional, conectada a `ConfigManager`.
- `main.py`: punto de entrada que arma Config → Database → UI.
- Tests con pytest: `ConfigManager`, `DatabaseManager`,
  `NavigationEngine.haversine_distance`.
- `requirements.txt`, `pyproject.toml` (black, ruff, pytest),
  `.gitignore`, `README.md`.

### Notas de arquitectura

- Se respeta estrictamente: `GPS → Navigation Engine → Event Engine →
  Action Dispatcher → UI / Audio / Logger / Plugins`.
- La UI no importa `gps_manager` ni `database` directamente en ningún
  punto; solo recibe `ConfigManager` inyectado.
- Todos los módulos del Core usan `core.logger.get_logger` y type
  hints completos.

### Próximo sprint

Sprint 2 — CRUD de waypoints (alta, baja, edición, listado) sobre
`database/db_manager.py` y `ui/screens/waypoints.py`.

## [0.2.0] - Sprint 2: CRUD + correcciones de arquitectura

### Decisiones de arquitectura (acordadas antes de codear)

- MVC se aplica **solo dentro de la capa UI**; el Core es una
  arquitectura en capas + event-driven, no MVC.
- `GpsManager` correrá en hilo dedicado (Sprint 3); nunca bloqueará
  el hilo de Qt. El Core sigue sin importar PyQt.
- `EventEngine` deberá ser una máquina de estados asincrónica para
  soportar acciones tipo "esperar" sin congelar la UI (implementación
  completa en Sprint 8, contrato ya reflejado en la arquitectura).
- `NavigationEngine` implementa histéresis por waypoint: el evento
  solo se dispara en la transición fuera→dentro.
- Nueva columna `re_triggerable` en `waypoints`: si es falso, el
  evento se dispara una única vez por sesión; si es verdadero
  (default), vuelve a dispararse en cada re-entrada al radio.
- Condiciones de `velocidad`/`angulo` quedan sin resolver por ahora
  (nulas = sin restricción); se definen en un sprint futuro.
- Se reemplaza el `schema.sql` único por un sistema de **migraciones
  versionadas** (`database/migrations/NNN_*.sql` + tabla
  `schema_version`), para no romper bases de datos existentes a
  medida que el schema crezca en sprints futuros.

### Agregado

- `database/migration_runner.py` + `database/migrations/001_initial_schema.sql`.
- `database/models.py`: dataclass `Waypoint`.
- `database/waypoint_repository.py`: CRUD completo (`create`, `get`,
  `list_all`, `update`, `delete`, `set_active`) + `WaypointNotFoundError`.
- `core/navigation_engine.py`: histéresis por waypoint (`ProximityState`),
  respeta `re_triggerable`.
- `ui/screens/waypoints.py`: pantalla funcional con tabla, alta, edición
  (diálogo `WaypointFormDialog`), borrado y activar/desactivar.
- `main.py` y `ui/main_window.py`: inyectan `WaypointRepository` en vez
  de crear dependencias dentro de la UI.
- Tests: `test_migration_runner.py`, `test_waypoint_repository.py`,
  `test_navigation_hysteresis.py`.

### Compatibilidad

- `database/schema.sql` fue removido; su contenido pasó a
  `migrations/001_initial_schema.sql` sin cambios funcionales,
  más la columna nueva `re_triggerable`.

### Próximo sprint

Sprint 3 — GPS: implementación real de `GpsManager` (gpsd/pyserial)
sobre el hilo dedicado ya definido en la arquitectura.

## [0.3.0] - Sprint 3: GPS

### Agregado

- `core/nmea_parser.py`: parser NMEA puro (GGA, RMC, checksum),
  sin I/O, 100% testeable.
- `core/gps_manager.py` reescrito con 3 backends intercambiables:
  - `gpsd`: cliente JSON propio sobre socket TCP (sin dependencias
    nuevas, no requiere `python-gps`/`gps3`).
  - `serial`: lectura NMEA directa con pyserial.
  - `simulator`: genera posiciones sintéticas (o un track custom),
    para desarrollar y testear sin hardware real.
  - Siempre corre en `threading.Thread` dedicado; nunca importa PyQt.
- `ui/gps_adapter.py`: `QtGpsAdapter`, único puente entre el hilo del
  GPS y el hilo principal de Qt (señal `position_received`).
- `main.py`: arma el pipeline completo GPS -> Navigation Engine
  (conecta la señal del adapter a `NavigationEngine.update_position`).
- `ui/main_window.py` / `ui/screens/waypoints.py`: la UI ahora
  recarga automáticamente el `NavigationEngine` cada vez que se
  crea/edita/borra/activa un waypoint, sin reiniciar la app.
- Configuración de GPS actualizada: `gps.backend`, `gps.gpsd_host`,
  `gps.gpsd_port`, `gps.serial_port`, `gps.serial_baudrate`,
  `gps.simulator_interval_seconds` (reemplaza las claves viejas
  `gps.port` / `gps.use_gpsd`).
- Tests: `test_nmea_parser.py`, `test_gps_manager.py`,
  `test_integration_gps_navigation.py` (pipeline GPS->Nav completo,
  sin Qt ni hardware).

### Compatibilidad

- Instalaciones existentes con `config.json` viejo: las claves
  `gps.port`/`gps.use_gpsd` quedan huérfanas pero no rompen nada;
  `ConfigManager.get()` devuelve los defaults nuevos si faltan.

### Próximo sprint

Sprint 4 — Navigation Engine: ya adelantado en gran parte (histéresis,
haversine). Queda pulir condiciones opcionales de velocidad/rumbo por
waypoint y afinar el intervalo de polling del GPS real en campo.

## [0.4.0] - Sprint 4: Navigation Engine

### Agregado

- Condiciones opcionales por waypoint en `NavigationEngine`:
  - `velocidad`: el evento solo dispara si la velocidad actual del
    vehículo es >= al valor configurado (km/h).
  - `angulo`: el evento solo dispara si el rumbo actual está dentro de
    `heading_tolerance_degrees` (configurable, default 45°) respecto
    al ángulo del waypoint. Requiere heading disponible; si el GPS no
    lo provee, el waypoint direccional no dispara.
- `NavigationEngine.angular_difference()`: diferencia angular mínima
  entre dos rumbos, con manejo correcto de wraparound (350° vs 10°).
- `NavigationEngine.get_nearest_waypoint()`: waypoint activo más
  cercano + distancia, sin disparar eventos (para UI informativa).
- Nueva clave de configuración `navigation.heading_tolerance_degrees`.
- `ui/screens/navigation.py`: readout en vivo (posición, velocidad,
  rumbo) conectado directamente a `QtGpsAdapter.position_received`,
  útil para validar el pipeline completo sin esperar al Graphic Engine.
- Tests: `test_navigation_conditions.py` (velocidad, ángulo, nearest),
  `test_navigation_concurrency.py`.

### Corregido

- **Race condition real** entre el hilo del GPS (`update_position`) y
  el hilo de la UI (`load_waypoints`, disparado al editar waypoints
  en pantalla): se agregó un `threading.Lock` en `NavigationEngine`
  que protege todo acceso a `_waypoints` y `_state`. Verificado con
  test de concurrencia dedicado (dos hilos, 200 recargas concurrentes,
  sin errores).

### Próximo sprint

Sprint 5 — Resource Library: completar `ResourceManager` con UI
funcional en `ui/screens/library.py` para administrar imágenes, audio
e iconos asociados a los waypoints.

## [0.5.0] - Sprint 5: Resource Library

### Agregado

- `ResourceManager` completo: `import_resource` (ahora evita
  sobreescribir en silencio ante colisión de nombres, agregando sufijo
  `_1`, `_2`...), `list_resources`, `get_absolute_path`,
  `to_relative_path`, `resolve_relative_path`, `delete_resource`.
- `ui/screens/library.py`: pantalla funcional con selector de
  categoría (imágenes/audio/iconos), lista de recursos, previsualización
  (imagen escalada o nombre + botón reproducir para audio), importar
  (vía `QFileDialog`) y eliminar con confirmación.
- `ui/screens/waypoints.py`: el formulario de alta/edición ahora
  incluye selectores de imagen y audio poblados desde la biblioteca
  (`ResourceManager.list_resources`), en vez de campos de texto libre.
  Los waypoints existentes preseleccionan su recurso actual.
- `main.py` / `ui/main_window.py`: inyectan `ResourceManager` y
  `AudioManager` (compartidos entre `LibraryScreen` y `WaypointsScreen`)
  en vez de crearlos dentro de la UI.
- Tests: `test_resource_manager.py` (import, colisión de nombres,
  listado, borrado, resolución de rutas).

### Compatibilidad

- Los waypoints ya existentes con `imagen`/`audio` seteados como ruta
  relativa siguen funcionando: el formulario los preselecciona
  buscando el nombre de archivo en el combo de la biblioteca.

### Próximo sprint

Sprint 6 — Graphic Engine: reemplazar el readout de texto de
`NavigationScreen` por la visualización real de imágenes/overlays
disparados por waypoints (usa los recursos ya administrados acá).

## [0.6.0] - Sprint 6: Graphic Engine

### Agregado

- `core/graphic_utils.py`: `compute_scaled_size()`, lógica pura de
  escalado preservando aspect ratio (testeable sin Qt), usada para
  adaptar imágenes a distintas resoluciones de pantalla (TFT HDMI,
  TFT DSI, HDMI estándar).
- `ui/screens/navigation.py`: overlay de imagen a pantalla completa
  sobre el readout de posición. `show_image()` / `hide_image()` con
  auto-ocultado no bloqueante vía `QTimer` (reinicia el timer si llega
  una imagen nueva antes de que se oculte la anterior). Se reescala
  automáticamente ante cambios de tamaño de la ventana.
- `ui/waypoint_event_adapter.py`: `WaypointEventAdapter`, mismo patrón
  que `QtGpsAdapter` — traduce `NavigationEngine.on_waypoint_reached`
  (que corre en el hilo del GPS) a una señal Qt segura entre hilos.
- `ui/main_window.py`: `handle_waypoint_reached()` conecta el evento
  con la imagen/audio del waypoint (resueltos vía `ResourceManager`) y
  cambia automáticamente a la pantalla de Navegación para que el
  conductor vea el evento sin importar en qué pantalla esté.
- Nueva clave de configuración `graphics.image_display_seconds`
  (default 5s).
- Tests: `test_graphic_utils.py` (escalado con distintos aspect
  ratios, casos límite).

### Notas de arquitectura

- Esta es una reacción **directa** waypoint→imagen/audio, todavía sin
  pasar por un Event Engine real. Sirve para validar todo el pipeline
  visual de punta a punta antes de construir la máquina de estados
  del Sprint 8, que reemplazará `handle_waypoint_reached` por
  secuencias de acciones configurables (mostrar → esperar → ocultar →
  audio, en cualquier orden y con múltiples pasos).

### Próximo sprint

Sprint 7 — Offline Maps: sigue pendiente la decisión de formato
(MBTiles vs. tiles vectoriales vs. extractos OSM renderizados en
runtime) marcada como abierta en la arquitectura.

## [0.7.0] - Sprint 7: Offline Maps

### Decisión de arquitectura (cierra el punto abierto)

Se eligió **MBTiles con tiles raster** sobre tiles vectoriales o
extractos OSM renderizados en runtime. Motivo: el hardware mínimo
objetivo (Raspberry Pi 2) no tiene margen de CPU/GPU para renderizar
geometrías vectoriales en tiempo real; leer un blob PNG pre-renderizado
de una tabla SQLite es prácticamente gratis en comparación, y MBTiles
es sencillamente un archivo SQLite (cero dependencias nuevas).

### Agregado

- `core/map_manager.py`: `MapManager` (lee tiles desde un archivo
  `.mbtiles`, maneja la conversión TMS↔XYZ automáticamente) +
  `deg2num`/`num2deg`/`deg2num_fractional` (matemática estándar de
  "slippy map", pura y testeable).
- `core/map_compositor.py`: `compose_map_image()` arma el raster final
  centrado en una coordenada combinando los tiles necesarios (usa
  Pillow, no Qt); `should_redraw()`, throttling puro por distancia
  mínima recorrida (evita recomponer tiles en cada update GPS si el
  vehículo apenas se movió — importante en Raspberry Pi 2).
- `ui/screens/map_widget.py`: `MapWidget`, única pieza que combina
  Pillow + Qt (convierte la imagen compuesta a `QPixmap`). Si no hay
  `.mbtiles` cargado, muestra "Sin mapa offline cargado" en vez de
  fallar.
- `ui/screens/navigation.py`: ahora tiene 3 capas superpuestas — mapa
  (fondo) + readout semi-transparente (medio) + overlay de imagen de
  waypoints del Sprint 6 (frente, sin cambios de comportamiento).
- Nueva sección de configuración `maps`: `mbtiles_path`,
  `default_zoom`, `redraw_threshold_meters`.
- Tests: `test_map_manager.py` (incluye un `.mbtiles` real armado con
  SQLite en el test, verifica explícitamente el flip TMS/XYZ),
  `test_map_compositor.py` (dimensiones, fuente vacía, throttling).

### Notas

- El proyecto no incluye ningún archivo `.mbtiles` real (son
  típicamente de cientos de MB a GB); el usuario debe colocar el suyo
  en `resources/maps/` y apuntar `maps.mbtiles_path` a él. Sin ese
  archivo, la app sigue funcionando normalmente, solo sin mapa visual.

### Próximo sprint

Sprint 8 — Event Engine: reemplazar `MainWindow.handle_waypoint_reached`
(reacción directa) por la máquina de estados asincrónica que permite
secuencias configurables de acciones por waypoint.

## [0.8.0] - Sprint 8: Event Engine

### Agregado

- `database/migrations/002_actions.sql`: tabla `actions`
  (waypoint_id, orden, tipo, payload JSON), con `ON DELETE CASCADE`
  para que borrar un waypoint borre su secuencia automáticamente.
- `database/models.py`: dataclass `Action`.
- `database/action_repository.py`: CRUD de secuencias
  (`create`, `list_for_waypoint`, `replace_sequence` — atómico,
  re-numera `orden` —, `delete_all_for_waypoint`).
- `core/action_dispatcher.py` reescrito: `ActionType` ahora es un
  `str Enum` cuyo valor coincide con `actions.tipo`;
  `register_handler(tipo, handler)` + `execute()` con manejo de
  excepciones (un handler roto no tumba la secuencia).
- `core/event_engine.py` reescrito: **máquina de estados
  asincrónica real**. `ActionSequenceRunner` ejecuta cada paso; los
  pasos `WAIT` usan `threading.Timer` (nunca `time.sleep`), así una
  secuencia larga nunca bloquea el hilo del GPS ni el de la UI.
  Múltiples waypoints pueden tener su secuencia corriendo al mismo
  tiempo sin interferirse (cada uno con su propio runner).
- **Retrocompatibilidad total**: si un waypoint no tiene filas en
  `actions`, `EventEngine._default_actions()` sintetiza la secuencia
  legacy (mostrar imagen + audio + esperar + ocultar + log), idéntica
  en comportamiento a los Sprints 6-7. Todos los waypoints creados
  antes de este sprint siguen funcionando sin ningún cambio.
- `ui/action_event_adapter.py`: `QtActionAdapter`, mismo patrón que
  los adapters anteriores — traduce cada acción despachada (que puede
  correr en el hilo del GPS o en un hilo de `threading.Timer`) a una
  señal Qt.
- `ui/main_window.py`: `handle_waypoint_reached` reemplazado por
  `handle_action(action_type, payload)`, que reacciona a cada tipo de
  acción individual (`show_image`, `hide_image`, `play_audio`,
  `log_event`; `run_plugin` deja un placeholder explícito para el
  Sprint 9).
- `ui/screens/navigation.py`: `show_image()` ahora acepta
  `auto_hide: bool`. El Event Engine lo usa en `False`, porque el
  ocultado lo controla la propia secuencia (`WAIT` + `HIDE_IMAGE`) en
  vez del timer interno de la pantalla.
- Tests: `test_action_dispatcher.py`, `test_action_repository.py`
  (incluye cascade delete), `test_event_engine.py` (secuencia default,
  retrocompatibilidad, **no bloqueo verificado con timing real**,
  secuencia custom sobreescribiendo el default, dos waypoints
  concurrentes sin interferencia).

### Notas de arquitectura

- `RUN_PLUGIN` deja explícitamente un placeholder de log: la carga
  real de plugins (descubrimiento, sandboxing) es Sprint 9 y no se
  adelantó acá para no invadir su alcance.
- No se construyó todavía una UI para autorar secuencias custom de
  acciones (`WaypointsScreen` sigue usando el flujo simple imagen/audio
  del Sprint 5). El motor y la base de datos ya soportan secuencias
  arbitrarias vía `ActionRepository`; falta la pantalla para editarlas
  visualmente. Se puede agregar como pulido posterior sin tocar el
  Event Engine.

### Próximo sprint

Sprint 9 — Plugins: implementar el descubrimiento/carga real de
`PluginManager` y conectar `RUN_PLUGIN` al plugin correspondiente.

## [0.8.1] - UI de autoría de secuencias de acciones

Cierra el pendiente explícito que había quedado del Sprint 8.

### Agregado

- `core/action_descriptions.py`: `describe_action()`, formateo legible
  de una acción para mostrar en UI (ej: "Mostrar imagen: curva.jpg"),
  lógica pura testeada sin Qt.
- `ui/screens/action_sequence_dialog.py`:
  - `ActionStepDialog`: configura un paso individual — el combo de
    tipo cambia dinámicamente los campos disponibles (imagen/audio
    poblados desde la Biblioteca, segundos para `wait`, mensaje para
    `log_event`, nombre de plugin para `run_plugin` con nota de que
    se activa en el Sprint 9).
  - `ActionSequenceDialog`: arma la secuencia completa de un waypoint
    — agregar, editar, eliminar, reordenar (subir/bajar) pasos, ver
    un resumen legible de cada uno, y "Restablecer a comportamiento
    por defecto" (borra la secuencia custom, vuelve al legacy
    imagen/audio). Guarda vía `ActionRepository.replace_sequence`
    (atómico) o `delete_all_for_waypoint` si se restablece a default.
- `ui/screens/waypoints.py`: nuevo botón "Secuencia de acciones..."
  que abre el diálogo para el waypoint seleccionado.
- Tests: `test_action_descriptions.py`.

### Notas

- No hace falta recargar nada en `NavigationEngine` al guardar una
  secuencia: `EventEngine._resolve_actions()` consulta
  `ActionRepository` en el momento exacto en que se dispara el
  waypoint, así que los cambios aplican de inmediato, sin reiniciar
  la app.
- El campo "Nombre del plugin" en un paso `run_plugin` queda
  guardado en la base de datos ya desde ahora; su ejecución real
  sigue pendiente del Sprint 9 (`ActionDispatcher` solo loguea un
  placeholder para ese tipo).

### Próximo sprint

Sprint 9 — Plugins: implementar el descubrimiento/carga real de
`PluginManager` y conectar `RUN_PLUGIN` al plugin correspondiente.

## [0.9.0] - Sprint 9: Plugins

### Decisión de seguridad (documentada, no oculta)

Los plugins corren con privilegios completos de Python, sin
sandboxing de sistema operativo. Decisión consciente para un proyecto
donde el usuario instala sus propios plugins de confianza — no está
pensado para cargar plugins de terceros sin revisar el código
primero. Como mitigación mínima: un archivo `.py` presente en
`plugins/` **no se ejecuta solo por estar ahí** — hay que habilitarlo
explícitamente por nombre en `plugins.enabled` en `config.json`.

### Agregado

- `core/plugin_manager.py` reescrito:
  - `discover_plugin_classes(directory)`: escanea `.py` sueltos,
    importa cada uno de forma aislada (un archivo con error de
    sintaxis o import se loguea y se saltea, sin tumbar el resto).
  - `PluginManager.load_from_directory(directory, enabled_names)`:
    instancia y registra solo los plugins cuyo nombre está en
    `enabled_names`. Un plugin incompleto (no implementa `execute()`
    de `RoadBookPlugin`, un ABC) no puede ni instanciarse — Python
    lo impide solo, y el loader lo loguea y continúa.
- `plugins/example_logger_plugin.py`: plugin de ejemplo real y
  funcional (anota cada ejecución con fecha/hora en
  `logs/plugin_events.log`), sirve como plantilla para escribir
  plugins propios.
- `ui/main_window.py`: `RUN_PLUGIN` ya no es un placeholder — busca
  el plugin por nombre en `PluginManager.get()` y llama a
  `.execute(payload)`; si no existe o no está habilitado, loguea una
  advertencia clara señalando dónde revisar (`plugins.enabled`).
- Nueva clave de configuración `plugins.directory` (default
  `"plugins"`).
- `ui/screens/action_sequence_dialog.py`: actualizado el placeholder
  del campo de nombre de plugin (ya no dice "pendiente Sprint 9").
- Tests: `test_plugin_manager.py` — cubre descubrimiento, carga
  filtrada por `enabled_names`, y **robustez explícita**: archivo con
  error de sintaxis, archivo sin ninguna clase de plugin, plugin
  incompleto que ABC rechaza instanciar, nombre habilitado
  inexistente. Ninguno de estos casos crashea la aplicación.

### Próximo sprint

Sprint 10 — Optimization: revisar el pipeline completo con foco en
Raspberry Pi 2 (uso de CPU/memoria del compositor de mapas, frecuencia
de polling GPS, arranque en frío).

## [0.10.0] - Sprint 10: Optimization

Optimizaciones concretas con foco en Raspberry Pi 2, todas testeadas
y verificadas sin regresión sobre la lógica de sprints anteriores.

### Agregado

- `core/lru_cache.py`: `LRUCache` genérico y reutilizable, base de
  las dos optimizaciones de cache siguientes.
- **Cache de tiles decodificados** (`core/map_compositor.py`):
  `CachedTileSource` envuelve cualquier fuente de tiles (`MapManager`)
  cacheando las imágenes PIL ya decodificadas por `(zoom, x, y)`.
  Decodificar un PNG es la parte más cara de recomponer el mapa;
  cuando el vehículo se mueve poco, la mayoría de los tiles visibles
  se repiten entre un redraw y el siguiente. `MapWidget` ahora usa
  este wrapper automáticamente.
- **Pre-filtro barato antes del haversine** (`core/navigation_engine.py`):
  `_definitely_outside()` descarta waypoints obviamente lejanos
  comparando solo la diferencia de latitud en metros (conversión
  directa, sin trigonometría) antes de pagar el costo de
  `haversine_distance` (seno/coseno/arcotangente). Nunca genera falsos
  positivos: si dice "afuera", está garantizado afuera. Se verificó
  explícitamente que el pre-filtro nunca rompe la detección de
  entradas reales, y que el estado se resetea correctamente a
  `OUTSIDE` aunque el waypoint se descarte por el pre-filtro (para no
  romper la re-entrada de waypoints `re_triggerable`).
- **Cache de sonidos cargados** (`core/audio_manager.py`): cachea los
  objetos `Sound` de pygame por ruta de archivo, evitando releer y
  decodificar el audio desde la tarjeta SD en cada disparo repetido
  del mismo waypoint. `AudioManager` ahora acepta un `sound_factory`
  inyectable, lo que permitió testear toda la lógica de cache sin
  necesitar pygame instalado.
- **PRAGMAs de SQLite** (`database/db_manager.py`): `journal_mode=WAL`
  (permite lecturas concurrentes mientras hay una escritura en
  curso — relevante porque el Event Engine puede estar leyendo
  `actions` desde un hilo de `threading.Timer` justo cuando la UI
  graba un cambio) + `synchronous=NORMAL` (menos `fsync` forzados por
  commit, más caros en una SD que en un SSD; WAL ya da suficiente
  garantía de consistencia ante un corte de energía sin necesitar
  `FULL`).
- Tests: `test_lru_cache.py`, extensión de `test_map_compositor.py`
  (cache hit/miss, tamaño máximo), `test_navigation_optimization.py`
  (pre-filtro sin falsos positivos, sin romper disparos reales, reset
  de estado correcto), `test_audio_manager.py` (cache de sonidos con
  factory inyectado).
- **Regresión verificada**: se re-corrió manualmente la lógica de
  histéresis, condiciones de velocidad, secuencia default del Event
  Engine y CRUD de waypoints (ahora sobre una base con WAL activado)
  para confirmar que ninguna optimización cambió el comportamiento
  observable.

### Notas

- No se tocó el polling del GPS (1 lectura/seg en el simulador, o lo
  que entregue el hardware real vía gpsd/serial) — ya es liviano y
  bajarlo más degradaría la precisión de detección de waypoints sin
  ahorro de CPU relevante.
- El pre-filtro de latitud es intencionalmente conservador (no filtra
  por longitud, que requeriría `cos(latitud)` para ser seguro): prioriza
  nunca generar falsos negativos por sobre exprimir el máximo de CPU.

### Próximo sprint

Sprint 11 — Beta: pruebas de integración de campo, pulido general,
manejo de casos borde reales (pérdida de fix GPS, SD corrupta, etc.).

## [0.11.0] - Sprint 11: Beta

### Corregido — bug crítico de threading en SQLite

Escribiendo el test de integración end-to-end de este sprint apareció
un bug real que hubiera crasheado en hardware desde el primer
waypoint disparado: la conexión SQLite se crea en el hilo principal,
pero `EventEngine` consulta `ActionRepository` desde el hilo del
`GpsManager` (el callback `on_waypoint_reached` corre ahí directamente,
sin marshalear a Qt — ver arquitectura del Sprint 8). SQLite prohíbe
por default usar una conexión desde un hilo distinto al que la creó.

**Corrección**: `DatabaseManager` ahora abre la conexión con
`check_same_thread=False`, documentado explícitamente en el código
como una decisión de diseño consciente para el patrón de uso de esta
app (lecturas ocasionales desde hilos secundarios, escrituras desde la
UI) — combinado con WAL (Sprint 10), es seguro para este caso. Si en
el futuro se necesitara más concurrencia de escritura real, la nota en
el código señala la alternativa (conexión por hilo / cola de
escritura).

### Agregado

- **Recuperación ante base de datos corrupta** (`database/db_manager.py`):
  antes de conectar, se verifica la base con `PRAGMA integrity_check`.
  Si el archivo no es un SQLite válido o falla la verificación, se
  preserva con un sufijo `.corrupt-TIMESTAMP` (para intentar
  recuperarlo manualmente después) y se arranca con una base nueva, en
  vez de crashear. Escenario real en Raspberry Pi: corte de energía en
  medio de una escritura, sector dañado de la SD.
- **Reconexión automática del GPS** (`core/gps_manager.py`): los
  backends `gpsd` y `serial` ahora reintentan la conexión con un
  intervalo configurable (`gps.reconnect_interval_seconds`, default
  5s) en vez de morir silenciosamente tras el primer fallo. Cubre:
  gpsd que todavía no arrancó al bootear, dongle USB-GPS desconectado
  un instante, gpsd que cierra la conexión. `stop()` sigue siendo
  responsivo incluso durante una espera de backoff larga.
- **Indicador de tiempo sin fix** (`ui/screens/navigation.py` +
  `core/time_format.py`): en vez de solo "Sin fix GPS", ahora muestra
  "Sin fix GPS (última posición hace 1m 30s)". `format_duration_seconds()`
  es lógica pura, testeada sin Qt.
- Tests: `test_time_format.py`, `test_db_corruption_recovery.py`,
  `test_gps_manager_reconnect.py`, y el más importante:
  `test_integration_full_pipeline.py` — simula una sesión de manejo
  completa (GPS simulado con track de 2 paradas, un waypoint legacy y
  uno con secuencia custom) usando los componentes reales de punta a
  punta, sin mocks del Core.

### Notas

- La regresión se corrió manualmente sobre histéresis, condiciones de
  velocidad, secuencia default del Event Engine y CRUD tras el fix de
  threading — todo sigue funcionando igual, solo que ahora sin
  crashear.
- No se implementó reconexión para el backend `simulator` (no aplica:
  no hay conexión real que pueda fallar).

### Próximo sprint

Sprint 12 — Version 1.0: empaquetado final (`installer/`), documentación
de usuario final, y cierre del roadmap.

## [1.0.0] - Sprint 12: Version 1.0

Cierre del roadmap original de 12 sprints.

### Agregado

- `installer/install.sh`: instala dependencias de sistema (Python,
  gpsd) y crea el entorno virtual con las dependencias del proyecto.
- `installer/enable_autostart.sh` / `disable_autostart.sh` +
  `roadbook-pi.service.template`: autoarranque vía `systemd` al
  bootear la Raspberry Pi, con logs accesibles por `journalctl`.
- `LICENSE`: texto completo de la licencia MIT (la especificación la
  pedía desde el Sprint 1; nunca había existido como archivo real).
- `README.md` reescrito como documentación final de usuario: estado
  del roadmap, funcionalidad, arquitectura, instalación (Pi y
  desarrollo), configuración, cómo escribir un plugin, y
  convenciones de contribución.
- Versión bumpeada a `1.0.0` en `pyproject.toml` y en la configuración
  por defecto (`ConfigManager`).

### Verificado antes del release

- Regresión manual sobre piezas de los 12 sprints (config, DB/CRUD,
  GPS, histéresis de navegación, recursos, escalado gráfico, mapas,
  Event Engine, plugins, cache LRU, recuperación de DB corrupta) —
  todo funcionando de forma consistente.

### Notas de cierre

- El proyecto queda con: arquitectura en capas documentada y
  respetada en los 12 sprints, migraciones de base de datos
  versionadas, tests para toda la lógica crítica del Core, 3 backends
  de GPS intercambiables, mapas offline vía MBTiles, sistema de
  eventos con máquina de estados asincrónica y secuencias de acciones
  editables desde la UI, sistema de plugins con carga controlada por
  configuración, y varias optimizaciones + correcciones de robustez
  pensadas específicamente para Raspberry Pi 2.
- Áreas identificadas para una v1.1 futura (no bloquean el release):
  UI de gestión de mapas offline (elegir/importar `.mbtiles` desde la
  app en vez de editar `config.json` a mano), soporte de tiles
  vectoriales para hardware más potente (Pi 4/5), y tests
  automatizados de la capa Qt (actualmente no ejecutables en este
  entorno de desarrollo por falta de PyQt6/display).

## [1.1.0] - Rediseño: Roadbook Rendering Engine

Reemplaza el "visor de imágenes" simple del Sprint 6 por un motor de
renderizado continuo, similar a los sistemas profesionales de rally
raid (TripY, Rally Navigator): en vez de reaccionar solo a un waypoint
puntual, la app ahora mantiene una tira de notas en vivo (estilo
tulip), sincronizada con la posición GPS, junto al mapa.

### Decisiones de arquitectura (acordadas antes de codear)

- El origen de la ruta admite las dos opciones: un track GPX
  configurado (`roadbook.gpx_path`) si existe, o conectar los
  waypoints activos por `orden_ruta`/id como fallback.
- El "odómetro virtual" usa distancia en línea recta (haversine) al
  próximo punto, no proyección sobre la geometría real de la ruta —
  decisión deliberada por simplicidad: no necesita que la ruta sea
  precisa para funcionar.
- El `NavigationEngine`/`EventEngine` (Sprints 2-8) quedan
  **completamente intactos**: siguen disparando las secuencias de
  acciones por radio, sin ningún cambio de comportamiento. El
  `RoadbookEngine` es una capa nueva y complementaria, solo para
  decidir qué mostrar en la tira — nunca dispara acciones.
- Antes de tocar código real se armó un mockup interactivo en HTML
  (`docs/mockups/roadbook_rendering_engine_mockup.html`) para validar
  el layout y la interacción.

### Agregado

- `database/migrations/003_roadbook_engine.sql`: agrega `icono` y
  `orden_ruta` a `waypoints` (solo columnas nuevas, nada existente se
  toca ni pierde datos).
- `core/route.py`: `parse_gpx()` (stdlib `xml.etree`, sin dependencias
  nuevas), `order_waypoints_by_track()`, `order_waypoints_fallback()`,
  `resolve_route_order()` — resuelve el orden de la ruta.
- `core/roadbook_engine.py`: `build_entries()` (calcula distancias
  parcial/total) + `RoadbookEngine` (avanza el puntero de progreso
  ante cada posición GPS, calcula distancia al próximo y fracción de
  avance del tramo actual). Lógica pura, sin Qt.
- `ui/screens/roadbook_strip_widget.py`: `RoadbookStripWidget`, la
  tira scrolleable real en PyQt6 — ícono + distancia parcial/total +
  texto, entrada actual resaltada con su propia barra de progreso,
  pasadas atenuadas, auto-scroll a la actual.
- `ui/screens/navigation.py` rediseñado: mapa + tira lado a lado como
  capa base, con el readout y el overlay de imagen del Event Engine
  superpuestos exactamente como antes.
- `ui/screens/waypoints.py`: el formulario ahora tiene selector de
  ícono (`ICONO_CHOICES`) y campo de orden manual de ruta.
- `main.py` / `ui/main_window.py`: arman el `RoadbookEngine` al
  arrancar y lo reconstruyen automáticamente cada vez que se
  crea/edita/borra/activa un waypoint (mismo mecanismo que ya recarga
  el `NavigationEngine`).
- Nueva clave de configuración `roadbook.gpx_path` (default `None`).
- `docs/libro_de_ruta_rally_cordoba/importar_waypoints.py` actualizado:
  los 14 waypoints reales del Rally de Córdoba ahora incluyen
  `icono`/`orden_ruta`, sirviendo como demo real del Roadbook
  Rendering Engine (verificado: arma una tira de ~96km coherente).
- Tests: `test_route.py`, `test_roadbook_engine.py` — cubren parseo
  GPX (válido, inexistente, XML inválido), ordenamiento por track y
  por fallback, avance del motor, progreso dentro de un tramo, sin
  fix GPS, fin de ruta, reset.

### Compatibilidad

- Ningún waypoint existente pierde datos: `icono` tiene default
  `'generico'`, `orden_ruta` queda `NULL` (se ordena por id como
  último recurso).
- Instalaciones sin `roadbook.gpx_path` configurado siguen
  funcionando exactamente igual, solo que la tira conecta los
  waypoints activos por orden en vez de por un track real.

### Notas

- No se construyó todavía una UI para elegir/importar el archivo GPX
  desde la app (hoy se edita `roadbook.gpx_path` a mano en
  `config.json`) — queda como pulido posterior, igual que la gestión
  de mapas offline mencionada en el release 1.0.0.
