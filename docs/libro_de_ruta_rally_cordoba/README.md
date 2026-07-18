# Waypoints del Rally de Córdoba 2021

Extraído de `LIBRO_DE_RUTA_-_Definitivo.pdf` (Rally Argentino, 4ª fecha
2021, Rally de Córdoba, 8-11 de julio de 2021).

## Contenido

- `images/`: 8 imágenes extraídas del PDF (portada, plano general de la
  competencia, plano del parque de servicios, y los 5 mapas
  satelitales de cada Prueba Especial). Son las únicas imágenes
  "de contenido" del PDF — el resto de las ~300 imágenes embebidas son
  logos de sponsors repetidos en cada página y se descartaron.
- `importar_waypoints.py`: script que crea 14 waypoints en tu base de
  datos de RoadBook Pi, usando las coordenadas GPS oficiales de la
  sección "Posiciones G.P.S. Reconocimiento de Caminos" del libro
  (página con el listado de Largada/Llegada de cada tramo), asociando
  a cada uno la imagen correspondiente cuando existe.

## Cómo usarlo

Desde la raíz del proyecto (`roadbook_pi/`):

```bash
python docs/libro_de_ruta_rally_cordoba/importar_waypoints.py
```

Es seguro correrlo más de una vez — no duplica waypoints ya creados
(los identifica por nombre), y reutiliza la misma imagen importada si
dos waypoints la comparten (ej: Largada y Llegada de la misma prueba).

## Waypoints creados

| Nombre | Categoría | Tiene imagen |
|---|---|---|
| Parque de Servicios - Autódromo Cabalén | Parque de Servicios | Sí (plano) |
| Largada / Llegada Shakedown | Shakedown | No |
| PE Estancia - La Calera (Largada/Llegada) | Prueba Especial | Sí |
| PE Temático RUS (Largada/Llegada) | Prueba Especial | Sí |
| PE / PSE Jac Motors Cabalén (Largada/Llegada) | Prueba Especial | Sí |
| PE Pirelli Cabalén (Largada/Llegada) | Prueba Especial | Sí |
| PE Berta YPF (Largada/Llegada) | Prueba Especial | Sí |
| RZ Combustible Remoto | Reabastecimiento | No |

## Limitaciones

- El libro no incluye una foto/imagen específica para los puntos de
  Shakedown ni para la zona de reabastecimiento remota — esos
  waypoints se crearon sin imagen asociada. Si tenés fotos propias de
  esos puntos, podés asignarlas después desde la pantalla de
  Waypoints en la app.
- El radio de cada waypoint (200-300m) es un valor razonable por
  defecto para un tramo de rally, pero puede ajustarse según qué tan
  preciso sea tu GPS real en el auto.
- Estas coordenadas son las de **reconocimiento de caminos**
  (verificación previa), que es exactamente la etapa donde este tipo
  de app tiene más sentido usarse.
