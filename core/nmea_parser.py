"""Parser de sentencias NMEA 0183 para GPS (NEO-6M / NEO-M8N).

Funciones puras, sin I/O: reciben una línea de texto y devuelven un
diccionario con los datos extraídos, o ``None`` si la sentencia no es
del tipo esperado. Esto permite testearlas sin abrir un puerto serie
real.

Soporta las dos sentencias mínimas necesarias para navegación:

- ``GGA``: posición y calidad de fix.
- ``RMC``: posición, velocidad y rumbo.
"""

from __future__ import annotations


def verify_checksum(sentence: str) -> bool:
    """Verifica el checksum XOR de una sentencia NMEA.

    Args:
        sentence: Línea NMEA completa, incluyendo ``$`` y ``*checksum``.

    Returns:
        True si el checksum es válido, False en caso contrario.
    """
    sentence = sentence.strip()
    if "*" not in sentence:
        return False

    body, _, checksum_hex = sentence.partition("*")
    body = body.lstrip("$")

    calculated = 0
    for char in body:
        calculated ^= ord(char)

    try:
        return calculated == int(checksum_hex[:2], 16)
    except ValueError:
        return False


def _nmea_coord_to_decimal(raw: str, direction: str) -> float:
    """Convierte una coordenada NMEA (ddmm.mmmm) a grados decimales.

    Args:
        raw: Coordenada cruda, ej: "3444.1234" (34 grados, 44.1234 min).
        direction: Uno de "N", "S", "E", "W".

    Returns:
        Coordenada en grados decimales, negativa para S/W.
    """
    degrees_len = 2 if direction in ("N", "S") else 3
    degrees = float(raw[:degrees_len])
    minutes = float(raw[degrees_len:])
    decimal = degrees + minutes / 60.0
    if direction in ("S", "W"):
        decimal = -decimal
    return decimal


def parse_gga(sentence: str) -> dict | None:
    """Parsea una sentencia GGA (posición + calidad de fix).

    Args:
        sentence: Línea NMEA cruda.

    Returns:
        Diccionario con ``latitude``, ``longitude``, ``has_fix``, o
        ``None`` si la sentencia no es GGA.
    """
    parts = sentence.strip().split(",")
    if not parts or not parts[0].lstrip("$").endswith("GGA"):
        return None

    fix_quality_raw = parts[6] if len(parts) > 6 else ""
    try:
        fix_quality = int(fix_quality_raw)
    except ValueError:
        fix_quality = 0

    if fix_quality == 0 or not parts[2] or not parts[4]:
        return {"has_fix": False}

    latitude = _nmea_coord_to_decimal(parts[2], parts[3])
    longitude = _nmea_coord_to_decimal(parts[4], parts[5])
    return {"latitude": latitude, "longitude": longitude, "has_fix": True}


def parse_rmc(sentence: str) -> dict | None:
    """Parsea una sentencia RMC (posición + velocidad + rumbo).

    Args:
        sentence: Línea NMEA cruda.

    Returns:
        Diccionario con ``latitude``, ``longitude``, ``speed`` (km/h),
        ``heading`` (grados) y ``has_fix``, o ``None`` si la sentencia
        no es RMC.
    """
    parts = sentence.strip().split(",")
    if not parts or not parts[0].lstrip("$").endswith("RMC"):
        return None

    status = parts[2] if len(parts) > 2 else "V"
    if status != "A" or len(parts) < 8 or not parts[3] or not parts[5]:
        return {"has_fix": False}

    latitude = _nmea_coord_to_decimal(parts[3], parts[4])
    longitude = _nmea_coord_to_decimal(parts[5], parts[6])
    speed_knots = float(parts[7]) if parts[7] else 0.0
    heading = float(parts[8]) if len(parts) > 8 and parts[8] else None
    speed_kmh = speed_knots * 1.852

    return {
        "latitude": latitude,
        "longitude": longitude,
        "speed": speed_kmh,
        "heading": heading,
        "has_fix": True,
    }
