"""Importa los waypoints del Rally de Córdoba 2021 a RoadBook Pi.

Extraído de LIBRO_DE_RUTA_-_Definitivo.pdf: las coordenadas GPS oficiales
de la sección "Posiciones G.P.S. Reconocimiento de Caminos", y las
imágenes de mapas satelitales de cada Prueba Especial embebidas en el
mismo PDF.

Uso (parado en la raíz del proyecto roadbook_pi/):

    python docs/libro_de_ruta_rally_cordoba/importar_waypoints.py

Es seguro correrlo más de una vez: no duplica waypoints si ya existen
(se identifican por nombre).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Permite correr el script desde cualquier lado, ubicando la raíz del proyecto
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config_manager import ConfigManager  # noqa: E402
from core.resource_manager import ResourceManager  # noqa: E402
from database.db_manager import DatabaseManager  # noqa: E402
from database.models import Waypoint  # noqa: E402
from database.waypoint_repository import WaypointRepository  # noqa: E402

IMAGES_DIR = Path(__file__).resolve().parent / "images"

# (nombre, latitud, longitud, radio_metros, categoria, archivo_imagen o None, descripcion)
WAYPOINTS = [
    (
        "Parque de Servicios - Autódromo Cabalén",
        -31.578473, -64.367698, 300,
        "Parque de Servicios",
        "plano_parque_servicios.png",
        "Ubicación y layout del Parque de Servicios del Rally de Córdoba 2021.",
    ),
    (
        "Largada Shakedown",
        -31.575018, -64.366411, 200,
        "Shakedown",
        None,
        "Punto de largada de las pruebas de shakedown, previas a la competencia.",
    ),
    (
        "Llegada Shakedown",
        -31.572374, -64.361557, 200,
        "Shakedown",
        None,
        "Punto de llegada del shakedown.",
    ),
    (
        "PE Estancia - La Calera (Largada)",
        -31.332533, -64.356054, 300,
        "Prueba Especial",
        "pe_estancia_la_calera.png",
        "Prueba Especial Nº 2 y 10. 12,42 km. Superficie de tierra/montaña.",
    ),
    (
        "PE Estancia - La Calera (Llegada)",
        -31.341654, -64.351627, 300,
        "Prueba Especial",
        "pe_estancia_la_calera.png",
        "Llegada de la PE Estancia - La Calera.",
    ),
    (
        "PE Temático RUS (Largada)",
        -31.403465, -64.456121, 300,
        "Prueba Especial",
        "pe_tematico_rus.png",
        "Prueba Especial Nº 3 y 11. 2,90 km, la más corta del rally.",
    ),
    (
        "PE Temático RUS (Llegada)",
        -31.403804, -64.455032, 300,
        "Prueba Especial",
        "pe_tematico_rus.png",
        "Llegada de la PE Temático RUS.",
    ),
    (
        "PE / PSE Jac Motors Cabalén (Largada)",
        -31.575018, -64.366411, 300,
        "Prueba Especial",
        "pe_jac_motors_cabalen.png",
        "PSE Nº 1 y 9 (nocturna) / PE Nº 4 y 12. Circuito dentro del autódromo.",
    ),
    (
        "PE Jac Motors Cabalén (Llegada)",
        -31.578098, -64.364514, 300,
        "Prueba Especial",
        "pe_jac_motors_cabalen.png",
        "Llegada de la PE Jac Motors Cabalén.",
    ),
    (
        "PE Pirelli Cabalén (Largada)",
        -31.577206, -64.367641, 300,
        "Prueba Especial",
        "pe_pirelli_cabalen.png",
        "PE Nº 6, 8, 14 y 16. 9,54 km.",
    ),
    (
        "PE Pirelli Cabalén (Llegada)",
        -31.579039, -64.363999, 300,
        "Prueba Especial",
        "pe_pirelli_cabalen.png",
        "Llegada de la PE Pirelli Cabalén.",
    ),
    (
        "PE Berta YPF (Largada)",
        -31.632018, -64.397012, 300,
        "Prueba Especial",
        "pe_berta_ypf.png",
        "PE Nº 5, 7, 13 y 15. 2,87 km, circuito tipo rallycross.",
    ),
    (
        "PE Berta YPF (Llegada)",
        -31.634255, -64.396522, 300,
        "Prueba Especial",
        "pe_berta_ypf.png",
        "Llegada de la PE Berta YPF.",
    ),
    (
        "RZ Combustible Remoto",
        -31.401975, -64.447246, 200,
        "Reabastecimiento",
        None,
        "Zona de reabastecimiento de combustible remota, según Libro de Ruta.",
    ),
]


def main() -> None:
    config = ConfigManager(str(PROJECT_ROOT / "config.json"))
    db = DatabaseManager(config.get("database.path", "database/roadbook.db"))
    db.initialize_schema()

    resource_manager = ResourceManager(PROJECT_ROOT / "resources")
    waypoint_repo = WaypointRepository(db)

    existentes = {wp.nombre for wp in waypoint_repo.list_all()}
    imagenes_importadas: dict[str, str] = {}  # archivo -> ruta relativa ya importada

    creados = 0
    saltados = 0

    for nombre, lat, lon, radio, categoria, archivo_imagen, descripcion in WAYPOINTS:
        if nombre in existentes:
            print(f"  [SALTEADO] '{nombre}' ya existe")
            saltados += 1
            continue

        imagen_relativa = None
        if archivo_imagen:
            if archivo_imagen in imagenes_importadas:
                imagen_relativa = imagenes_importadas[archivo_imagen]
            else:
                origen = IMAGES_DIR / archivo_imagen
                if origen.exists():
                    imagen_relativa = resource_manager.import_resource(origen, "images")
                    imagenes_importadas[archivo_imagen] = imagen_relativa
                else:
                    print(f"  [AVISO] no se encontró la imagen {origen}")

        waypoint = Waypoint(
            nombre=nombre,
            latitud=lat,
            longitud=lon,
            radio=radio,
            categoria=categoria,
            imagen=imagen_relativa,
            descripcion=descripcion,
            activo=True,
            re_triggerable=True,
        )
        waypoint_repo.create(waypoint)
        print(f"  [CREADO] '{nombre}' ({lat}, {lon})" + (f" + imagen" if imagen_relativa else ""))
        creados += 1

    db.close()
    print(f"\nListo: {creados} waypoints creados, {saltados} ya existían.")


if __name__ == "__main__":
    main()
