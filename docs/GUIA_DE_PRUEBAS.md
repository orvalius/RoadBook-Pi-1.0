# Guía de pruebas — RoadBook Pi en tu PC

Esta guía te lleva de cero a ver la app corriendo con datos simulados
(sin necesitar Raspberry Pi ni GPS real), y después a probar el flujo
completo: waypoint → imagen/audio → evento, y la tira de roadbook en
vivo (Roadbook Rendering Engine).

## 1. Requisitos previos

- **Python 3.10 o superior** instalado. Verificalo con:
  ```bash
  python3 --version
  ```
  En Windows, puede ser `python --version` en vez de `python3`.

- **pip** (viene con Python normalmente).

No hace falta nada de hardware: el backend de GPS por defecto en
`config.json` es `"simulator"`, que genera posiciones falsas para
poder probar todo sin un receptor GPS conectado.

## 2. Descomprimir el proyecto

Descomprimí el `.zip` que te pasé en una carpeta, por ejemplo
`roadbook_pi/`.

## 3. Crear el entorno virtual e instalar dependencias

Desde una terminal, parado dentro de la carpeta del proyecto:

```bash
cd roadbook_pi

python3 -m venv .venv

# Activar el entorno virtual:
source .venv/bin/activate        # Linux / macOS
.venv\Scripts\activate           # Windows (cmd o PowerShell)

pip install --upgrade pip
pip install -r requirements.txt
```

Esto instala PyQt6, pygame, Pillow, pyserial, pytest, etc. Puede
tardar unos minutos la primera vez, especialmente PyQt6.

### Si falla la instalación de PyQt6

- **Windows/macOS**: normalmente instala sin problemas con `pip`. Si
  falla, asegurate de tener `pip` actualizado (`pip install --upgrade pip`)
  y probá de nuevo.
- **Linux**: si `pip install PyQt6` falla, puede faltar alguna
  librería de sistema. En Debian/Ubuntu:
  ```bash
  sudo apt-get install python3-pyqt6
  ```
  o instalá las dependencias de Qt6 (`libgl1`, `libegl1`,
  `libxkbcommon0`) antes de reintentar el `pip install`.

## 4. Primer arranque

```bash
python main.py
```

**Qué deberías ver:**

- Una ventana con un menú lateral (Navegación, Waypoints, Biblioteca,
  Configuración, Logs).
- En "Navegación", la pantalla dividida en dos: a la izquierda un mapa
  gris con el texto "Sin mapa offline cargado" (es normal — no
  incluimos ningún `.mbtiles`, ver el README principal); a la derecha
  la tira de roadbook, con el texto "Sin ruta de roadbook activa"
  hasta que crees algún waypoint. Arriba, superpuesta, la posición GPS
  actualizándose sola cada segundo con coordenadas de Buenos Aires —
  eso es el backend `simulator` funcionando.

Si ves eso, el pipeline completo (GPS simulado → Navigation Engine →
UI) ya está andando. Cerralo con `Ctrl+C` en la terminal o cerrando la
ventana.

## 5. Probar el flujo completo: waypoint → imagen/audio

Este es el test más representativo de lo que hace la app.

### 5.1. Conseguí una imagen y un audio de prueba

Cualquier `.jpg`/`.png` y cualquier `.wav`/`.mp3` que tengas a mano
sirven (no importa el contenido).

### 5.2. Importalos en la Biblioteca

1. Andá a la pestaña **Biblioteca**.
2. Elegí la categoría "Imágenes", tocá **Importar...**, elegí tu
   archivo.
3. Cambiá a la categoría "Audio", **Importar...** de nuevo con tu
   archivo de audio.

### 5.3. Creá un waypoint en las coordenadas del track simulado

El track por defecto del simulador pasa por estas 3 posiciones (podés
verlas en `core/gps_manager.py`, `_default_simulator_track`):

```
-34.6037, -58.3816
-34.6100, -58.3900
-34.6200, -58.4000
```

1. Andá a **Waypoints** → **Agregar**.
2. Nombre: "Prueba".
3. Latitud: `-34.6037`, Longitud: `-58.3816`.
4. Radio: `500` (metros — le damos margen generoso).
5. En "Imagen" y "Audio", elegí los que recién importaste.
6. Guardá.

### 5.4. Andá a Navegación y esperá

En unos segundos, cuando el GPS simulado "pase" por esa coordenada,
deberías ver:

- La imagen aparece a pantalla completa.
- El audio se reproduce.
- Después de 5 segundos (configurable en
  `graphics.image_display_seconds`), la imagen se oculta sola.
- La tira de roadbook, a la derecha, también resalta ese waypoint
  como "actual" con su barra de progreso propia.

Si el track simulado vuelve a pasar por ahí (se repite en loop), el
evento se vuelve a disparar — a menos que hayas desmarcado "Puede
volver a dispararse" al crear el waypoint.

## 6. Probar la tira de Roadbook (Roadbook Rendering Engine)

Esta es la parte nueva: la tira de notas en vivo junto al mapa,
similar a los sistemas de rally raid.

### 6.1. Camino rápido: importar los waypoints reales del Rally de Córdoba

El proyecto incluye un script con 14 waypoints reales (con
coordenadas, imágenes y orden ya cargados) extraídos de un libro de
ruta real:

```bash
python docs/libro_de_ruta_rally_cordoba/importar_waypoints.py
```

Andá a **Navegación**: la tira de la derecha debería mostrar los 14
puntos en orden (Parque de Servicios → Shakedown → cada Prueba
Especial → RZ Combustible), con distancias parcial/total en
kilómetros. Como el GPS simulado no pasa por Córdoba, no vas a ver la
nota "actual" avanzar sola — para eso, seguí el punto 6.2.

### 6.2. Ver la tira avanzar en vivo

Para que el motor avance de verdad necesitás que el track simulado
del GPS pase cerca de tus waypoints. La forma más simple:

1. Creá 3-4 waypoints con coordenadas cercanas a
   `-34.6037, -58.3816` (el punto de partida del simulador), separados
   por ~500-1000 metros entre sí.
2. A cada uno asignale un **orden en la ruta** (0, 1, 2, 3...) desde el
   formulario de edición — así el Roadbook Engine sabe en qué
   secuencia mostrarlos (al no haber un track GPX configurado, usa
   este campo).
3. Opcionalmente, elegí un **ícono** distinto para cada uno (curva,
   peligro, vado, etc.) para ver los pictogramas cambiar en la tira.
4. Volvé a Navegación: deberías ver la nota actual resaltada en
   naranja con su barra de progreso, las pasadas atenuadas, y
   auto-scroll manteniendo la actual visible.

### 6.3. Usar un track GPX propio (opcional, más fiel a un reconocimiento real)

Si tenés un archivo `.gpx` (grabado con una app de tracking durante un
reconocimiento, o el que publica el organizador):

1. Andá a **Mapas y ruta** → "Track de la ruta (.gpx)" → **Importar…**
   y elegí el archivo.
2. La app lo valida (muestra cantidad de puntos y km), lo copia a
   `resources/routes/` y lo activa en el momento, sin reiniciar.
3. Volvé a **Navegación**: la tira ahora ordena tus waypoints según su
   posición a lo largo de ese track. Para volver al orden de los
   waypoints, elegí "(sin GPX…)" y tocá **Usar esta ruta**.

Sirven tanto GPX con track (`trkpt`) como con ruta (`rtept`).

### 6.4. Cargar un mapa offline (opcional)

1. Generá un `.mbtiles` **raster** de la zona (MOBAC, `mb-util`, etc.).
2. **Mapas y ruta** → "Mapa offline (.mbtiles)" → **Importar…**. Se
   valida antes de copiar (rechaza archivos que no son MBTiles o que
   tienen tiles vectoriales) y la copia muestra progreso; se puede
   cancelar.
3. Queda activo apenas termina. Si el zoom configurado no existe en
   ese mapa, se ajusta solo al más cercano disponible.

## 7. Probar secuencias de acciones custom

En **Waypoints**, seleccioná el waypoint de prueba y tocá **Secuencia
de acciones...**. Ahí podés armar tu propia secuencia (por ejemplo:
solo un log, o audio sin imagen, o varios pasos con esperas entre
medio) en vez del comportamiento por defecto. Los cambios aplican al
instante, sin reiniciar la app.

## 8. Probar el plugin de ejemplo

1. Abrí `config.json` (se crea solo en la carpeta del proyecto la
   primera vez que corriste `main.py`).
2. Agregá `"example_logger"` a la lista `plugins.enabled`:
   ```json
   "plugins": {
       "directory": "plugins",
       "enabled": ["example_logger"]
   }
   ```
3. En **Waypoints** → **Secuencia de acciones...**, agregá un paso de
   tipo "Ejecutar plugin" con nombre `example_logger`.
4. Cuando se dispare, revisá `logs/plugin_events.log` — debería
   aparecer una línea nueva con fecha/hora.

## 9. Ver los logs

- **En la app**: pestaña **Logs**, muestra las últimas líneas.
- **En disco**: `logs/roadbook_pi.log` (rotativo, no crece sin límite).

## 10. Correr los tests automatizados

```bash
pytest
```

Deberían pasar todos (son más de 230 tests entre lógica de negocio,
GPS, base de datos, event engine, plugins, roadbook engine y la
interfaz Qt, que se prueba sin abrir ventanas). Si
alguno falla, copiame el error y lo reviso.

## 11. Usar GPS real (opcional)

Cuando tengas la Raspberry Pi con un receptor NEO-6M/NEO-M8N conectado:

- Con `gpsd` corriendo: `"gps": {"backend": "gpsd", "gpsd_host": "127.0.0.1", "gpsd_port": 2947}`
- Sin `gpsd`, directo por serie: `"gps": {"backend": "serial", "serial_port": "/dev/ttyUSB0", "serial_baudrate": 9600}`

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| No suena el audio | pygame no encontró dispositivo de audio | Revisá los logs; en Linux headless puede necesitar `sudo apt-get install libasound2` |
| La imagen no aparece | Radio del waypoint muy chico, o coordenadas no coinciden con el track | Aumentá el radio, o revisá las coordenadas del track en `gps_manager.py` |
| La tira de roadbook no avanza | El GPS simulado no pasa cerca de tus waypoints | Usá coordenadas cercanas al track simulado (ver 6.2), o cargá un GPX real |
| La tira muestra "Sin ruta de roadbook activa" | No hay waypoints activos, o ninguno tiene `orden_ruta` ni hay GPX configurado | Creá al menos un waypoint activo; el orden por id ya alcanza para ver algo |
| El mapa se ve gris aunque cargué un .mbtiles | La zona del mapa no cubre la posición actual (el GPS simulado recorre Buenos Aires) | Revisá en **Mapas y ruta** el rango del archivo; con el simulador, generá el mapa de esa zona |
| `ModuleNotFoundError` al arrancar | El entorno virtual no está activado | Volvé a correr `source .venv/bin/activate` (o el equivalente en Windows) antes de `python main.py` |
| La ventana no aparece / crashea sin error visible | Revisá `logs/roadbook_pi.log`, ahí queda el traceback completo |
