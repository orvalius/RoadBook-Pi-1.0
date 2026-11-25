"""Genera un mapa offline (.mbtiles) de la zona de la ruta activa.

Para probar la app o navegar cuando no hay un mapa real de la zona.
Usa los waypoints activos y, si hay un track GPX activo, su recorrido.
El mapa resultante NO es cartografía real (el relieve es ilustrativo):
ver core/map_generator.py.

Uso, parado en la raíz del proyecto:

    python tools/generar_mapa_ruta.py                # genera y activa
    python tools/generar_mapa_ruta.py --zoom-max 16  # más detalle
    python tools/generar_mapa_ruta.py --no-activar   # solo genera

Después se puede elegir también desde la pantalla "Mapas y ruta".
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config_manager import ConfigManager  # noqa: E402
from core.map_generator import RouteMap, generate_mbtiles  # noqa: E402
from core.resource_manager import ResourceManager  # noqa: E402
from core.route import resolve_route  # noqa: E402
from database.db_manager import DatabaseManager  # noqa: E402
from database.waypoint_repository import WaypointRepository  # noqa: E402

OUTPUT = "resources/maps/ruta_generada.mbtiles"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--zoom-min", type=int, default=11)
    parser.add_argument("--zoom-max", type=int, default=15)
    parser.add_argument("--margen-km", type=float, default=3.0)
    parser.add_argument("--salida", default=OUTPUT, help=f"default: {OUTPUT}")
    parser.add_argument(
        "--no-activar",
        action="store_true",
        help="no cambiar maps.mbtiles_path en config.json",
    )
    args = parser.parse_args(argv)

    config = ConfigManager(PROJECT_ROOT / "config.json")
    resources = ResourceManager(PROJECT_ROOT / "resources")
    db = DatabaseManager(
        PROJECT_ROOT / config.get("database.path", "database/roadbook.db")
    )
    db.initialize_schema()
    waypoints = WaypointRepository(db).list_all(only_active=True)
    db.close()
    if not waypoints:
        print("No hay waypoints activos: cargá la ruta antes de generar el mapa.")
        return 1

    gpx_path = config.get("roadbook.gpx_path", None)
    ordered, track = resolve_route(
        waypoints, resources.resolve_relative_path(gpx_path) if gpx_path else None
    )
    route = RouteMap(
        line=track or [(wp.latitud, wp.longitud) for wp in ordered],
        notes=[(wp.latitud, wp.longitud, wp.nombre) for wp in ordered],
    )

    def show(done: int, total: int) -> None:
        if done == total or done % 50 == 0:
            print(f"\r  {done}/{total} tiles", end="", flush=True)

    output = PROJECT_ROOT / args.salida
    print(
        f"Generando mapa de {len(ordered)} notas "
        f"({'track GPX' if track else 'tramos entre notas'})..."
    )
    generate_mbtiles(
        output,
        route,
        min_zoom=args.zoom_min,
        max_zoom=args.zoom_max,
        margin_km=args.margen_km,
        progress=show,
    )
    size_mb = output.stat().st_size / 1024**2
    print(f"\nListo: {args.salida} ({size_mb:.1f} MB)")

    if not args.no_activar:
        config.set("maps.mbtiles_path", args.salida)
        config.save()
        print("Activado como mapa offline (maps.mbtiles_path).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
