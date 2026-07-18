"""Resource Manager de RoadBook Pi.

Administra la biblioteca de recursos (imágenes, audio, iconos,
plantillas). Regla clave de la especificación: nunca guardar rutas
absolutas; los recursos se copian dentro del proyecto
(resources/images, resources/audio, resources/icons, resources/maps).

Ningún otro módulo debe copiar/borrar archivos de ``resources/``
directamente; siempre pasa por acá.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from core.logger import get_logger

logger = get_logger(__name__)

RESOURCES_ROOT = Path(__file__).resolve().parent.parent / "resources"
VALID_CATEGORIES = ("images", "audio", "icons", "maps")


class ResourceManager:
    """Gestiona la copia, listado y borrado de recursos multimedia.

    Attributes:
        resources_root: Carpeta raíz de recursos (contiene
            images/, audio/, icons/, maps/).
    """

    def __init__(self, resources_root: str | Path = RESOURCES_ROOT) -> None:
        self.resources_root = Path(resources_root)
        for sub in VALID_CATEGORIES:
            (self.resources_root / sub).mkdir(parents=True, exist_ok=True)
        logger.info("ResourceManager inicializado en %s", self.resources_root)

    def _validate_category(self, category: str) -> None:
        if category not in VALID_CATEGORIES:
            raise ValueError(
                f"Categoría de recurso inválida: {category!r}. "
                f"Válidas: {VALID_CATEGORIES}"
            )

    def import_resource(self, source_path: str | Path, category: str) -> str:
        """Copia un recurso externo dentro del proyecto.

        Si ya existe un archivo con el mismo nombre en esa categoría,
        se agrega un sufijo numérico para no pisarlo (nunca se
        sobrescribe un recurso existente en silencio).

        Args:
            source_path: Ruta absoluta del archivo original.
            category: Subcarpeta destino ("images", "audio", "icons",
                "maps").

        Returns:
            Ruta relativa (desde la raíz del proyecto) del recurso ya
            copiado, ej: "resources/images/curva.jpg". Esta es la
            ruta que debe guardarse en `Waypoint.imagen` / `.audio`.

        Raises:
            ValueError: Si la categoría no es válida.
            FileNotFoundError: Si el archivo origen no existe.
        """
        self._validate_category(category)

        source = Path(source_path)
        if not source.exists():
            raise FileNotFoundError(f"Recurso no encontrado: {source}")

        target_dir = self.resources_root / category
        destination = target_dir / source.name

        if destination.exists():
            stem, suffix = source.stem, source.suffix
            counter = 1
            while destination.exists():
                destination = target_dir / f"{stem}_{counter}{suffix}"
                counter += 1

        shutil.copy2(source, destination)
        relative_path = str(destination.relative_to(self.resources_root.parent))
        logger.info("Recurso importado: %s -> %s", source, relative_path)
        return relative_path

    def list_resources(self, category: str) -> list[str]:
        """Lista los nombres de archivo de una categoría.

        Args:
            category: "images", "audio", "icons" o "maps".

        Returns:
            Nombres de archivo (no rutas completas), orden alfabético.
        """
        self._validate_category(category)
        folder = self.resources_root / category
        return sorted(p.name for p in folder.iterdir() if p.is_file())

    def get_absolute_path(self, category: str, filename: str) -> Path:
        """Resuelve un nombre de archivo de una categoría a ruta absoluta.

        Args:
            category: "images", "audio", "icons" o "maps".
            filename: Nombre de archivo dentro de esa categoría.

        Returns:
            Ruta absoluta al archivo.
        """
        self._validate_category(category)
        return self.resources_root / category / filename

    def resolve_relative_path(self, relative_path: str) -> Path:
        """Resuelve una ruta relativa guardada en un Waypoint a ruta absoluta.

        Args:
            relative_path: Ruta tal como se guarda en `Waypoint.imagen`
                / `.audio`, ej: "resources/images/curva.jpg".

        Returns:
            Ruta absoluta al archivo.
        """
        return self.resources_root.parent / relative_path

    def to_relative_path(self, category: str, filename: str) -> str:
        """Construye la ruta relativa que debe guardarse en un Waypoint.

        Args:
            category: "images", "audio", "icons" o "maps".
            filename: Nombre de archivo dentro de esa categoría.

        Returns:
            Ruta relativa desde la raíz del proyecto, ej:
            "resources/images/curva.jpg".
        """
        self._validate_category(category)
        absolute = self.resources_root / category / filename
        return str(absolute.relative_to(self.resources_root.parent))

    def delete_resource(self, category: str, filename: str) -> None:
        """Elimina un recurso de la biblioteca.

        Args:
            category: "images", "audio", "icons" o "maps".
            filename: Nombre de archivo a eliminar.

        Raises:
            ValueError: Si la categoría no es válida.
            FileNotFoundError: Si el archivo no existe.
        """
        path = self.get_absolute_path(category, filename)
        if not path.exists():
            raise FileNotFoundError(f"Recurso no encontrado: {path}")
        path.unlink()
        logger.info("Recurso eliminado: %s/%s", category, filename)
