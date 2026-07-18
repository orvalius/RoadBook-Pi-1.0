# Guía de pruebas — RoadBook Pi en tu PC

Esta guía te lleva de cero a ver la app corriendo con datos simulados
(sin necesitar Raspberry Pi ni GPS real), y después a probar el flujo
completo: waypoint → imagen/audio → evento.

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
- En "Navegación", un mapa gris con el texto "Sin mapa offline
  cargado" (es normal — no incluimos ningún `.mbtiles`, ver el README
  principal), y arriba la posición GPS actualizándose sola cada
  segundo con coordenadas de Buenos Aires — eso es el backend
  `simulator` funcionando.

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

Si el track simulado vuelve a pasar por ahí (se repite en loop), el
evento se vuelve a disparar — a menos que hayas desmarcado "Puede
volver a dispararse" al crear el waypoint.

## 6. Probar secuencias de acciones custom

En **Waypoints**, seleccioná el waypoint de prueba y tocá **Secuencia
de acciones...**. Ahí podés armar tu propia secuencia (por ejemplo:
solo un log, o audio sin imagen, o varios pasos con esperas entre
medio) en vez del comportamiento por defecto. Los cambios aplican al
instante, sin reiniciar la app.

## 7. Probar el plugin de ejemplo

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

## 8. Ver los logs

- **En la app**: pestaña **Logs**, muestra las últimas líneas.
- **En disco**: `logs/roadbook_pi.log` (rotativo, no crece sin límite).

## 9. Correr los tests automatizados

```bash
pytest
```

Deberían pasar todos (son más de 150 tests entre lógica de negocio,
GPS, base de datos, event engine, plugins, etc.). Si alguno falla,
copiame el error y lo reviso.

## 10. Usar GPS real (opcional)

Cuando tengas la Raspberry Pi con un receptor NEO-6M/NEO-M8N conectado:

- Con `gpsd` corriendo: `"gps": {"backend": "gpsd", "gpsd_host": "127.0.0.1", "gpsd_port": 2947}`
- Sin `gpsd`, directo por serie: `"gps": {"backend": "serial", "serial_port": "/dev/ttyUSB0", "serial_baudrate": 9600}`

## Problemas comunes

| Síntoma | Causa probable | Solución |
|---|---|---|
| No suena el audio | pygame no encontró dispositivo de audio | Revisá los logs; en Linux headless puede necesitar `sudo apt-get install libasound2` |
| La imagen no aparece | Radio del waypoint muy chico, o coordenadas no coinciden con el track | Aumentá el radio, o revisá las coordenadas del track en `gps_manager.py` |
| `ModuleNotFoundError` al arrancar | El entorno virtual no está activado | Volvé a correr `source .venv/bin/activate` (o el equivalente en Windows) antes de `python main.py` |
| La ventana no aparece / crashea sin error visible | Revisá `logs/roadbook_pi.log`, ahí queda el traceback completo |
