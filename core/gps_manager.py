"""GPS Manager de RoadBook Pi.

Responsable exclusivo de obtener la posición del vehículo. Soporta
tres backends intercambiables:

- ``gpsd``: se conecta al demonio gpsd vía socket TCP (protocolo JSON).
- ``serial``: lee NMEA directo del puerto serie con pyserial (NEO-6M,
  NEO-M8N sin gpsd).
- ``simulator``: genera posiciones sintéticas, para desarrollo y tests
  sin hardware.

Corre siempre en un hilo dedicado (``threading.Thread``) para nunca
bloquear el hilo principal de la UI. Este módulo NUNCA importa PyQt;
la traducción a señales Qt vive en ``ui/gps_adapter.py``.
"""

from __future__ import annotations

import json
import socket
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from core.logger import get_logger
from core.nmea_parser import parse_gga, parse_rmc

logger = get_logger(__name__)

PositionCallback = Callable[["GpsPosition"], None]


@dataclass(frozen=True)
class GpsPosition:
    """Representa una posición GPS instantánea.

    Attributes:
        latitude: Latitud en grados decimales.
        longitude: Longitud en grados decimales.
        speed: Velocidad en km/h (0 si no disponible).
        heading: Rumbo en grados (0-360), None si no disponible.
        has_fix: Indica si el GPS tiene fix válido.
    """

    latitude: float
    longitude: float
    speed: float = 0.0
    heading: float | None = None
    has_fix: bool = False


class GpsBackend(str, Enum):
    """Backends de origen de datos GPS soportados."""

    GPSD = "gpsd"
    SERIAL = "serial"
    SIMULATOR = "simulator"


class GpsManager:
    """Gestiona la conexión con el receptor GPS en un hilo dedicado.

    Attributes:
        backend: Backend activo (gpsd, serial o simulator).
    """

    def __init__(
        self,
        backend: str = GpsBackend.SIMULATOR,
        gpsd_host: str = "127.0.0.1",
        gpsd_port: int = 2947,
        serial_port: str = "/dev/ttyUSB0",
        serial_baudrate: int = 9600,
        simulator_track: list[GpsPosition] | None = None,
        simulator_interval: float = 1.0,
        reconnect_interval_seconds: float = 5.0,
    ) -> None:
        self.backend = GpsBackend(backend)
        self.gpsd_host = gpsd_host
        self.gpsd_port = gpsd_port
        self.serial_port = serial_port
        self.serial_baudrate = serial_baudrate
        self.simulator_track = simulator_track or self._default_simulator_track()
        self.simulator_interval = simulator_interval
        self.reconnect_interval_seconds = reconnect_interval_seconds

        self._callbacks: list[PositionCallback] = []
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_position: GpsPosition | None = None

        logger.info("GpsManager inicializado (backend=%s)", self.backend.value)

    @staticmethod
    def _default_simulator_track() -> list[GpsPosition]:
        """Track sintético por defecto para el backend simulador."""
        return [
            GpsPosition(latitude=-34.6037, longitude=-58.3816, speed=40, has_fix=True),
            GpsPosition(latitude=-34.6100, longitude=-58.3900, speed=45, has_fix=True),
            GpsPosition(latitude=-34.6200, longitude=-58.4000, speed=50, has_fix=True),
        ]

    def register_callback(self, callback: PositionCallback) -> None:
        """Registra un callback invocado con cada nueva posición.

        Se ejecuta en el hilo dedicado del GpsManager, no en el hilo
        principal. Si el consumidor necesita marshaling a otro hilo
        (ej: Qt), debe usar un adapter (ver ``ui/gps_adapter.py``).

        Args:
            callback: Función que recibe una ``GpsPosition``.
        """
        self._callbacks.append(callback)

    def start(self) -> None:
        """Inicia la lectura continua del GPS en un hilo dedicado."""
        if self._thread is not None and self._thread.is_alive():
            logger.warning("GpsManager.start() llamado pero ya está corriendo")
            return

        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="GpsManagerThread")
        self._thread.start()
        logger.info("GpsManager iniciado (backend=%s)", self.backend.value)

    def stop(self) -> None:
        """Detiene la lectura del GPS y espera a que el hilo termine."""
        self._stop_event.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        logger.info("GpsManager detenido")

    def get_position(self) -> GpsPosition | None:
        """Devuelve la última posición conocida.

        Returns:
            Instancia de ``GpsPosition`` o ``None`` si aún no hay datos.
        """
        return self._last_position

    @property
    def is_running(self) -> bool:
        """Indica si el hilo de lectura está activo."""
        return self._thread is not None and self._thread.is_alive()

    # --- Loop principal e implementaciones por backend ---

    def _run(self) -> None:
        try:
            if self.backend is GpsBackend.GPSD:
                self._run_gpsd()
            elif self.backend is GpsBackend.SERIAL:
                self._run_serial()
            else:
                self._run_simulator()
        except Exception:
            logger.exception("GpsManager: el hilo de lectura terminó con un error")

    def _notify(self, position: GpsPosition) -> None:
        self._last_position = position
        for callback in self._callbacks:
            try:
                callback(position)
            except Exception:
                logger.exception("Error ejecutando callback de posición GPS")

    def _run_simulator(self) -> None:
        """Recorre ``simulator_track`` en loop, para desarrollo y tests."""
        logger.info("GpsManager: backend simulador activo")
        index = 0
        while not self._stop_event.is_set():
            position = self.simulator_track[index % len(self.simulator_track)]
            self._notify(position)
            index += 1
            self._stop_event.wait(self.simulator_interval)

    def _run_gpsd(self) -> None:
        """Lee posiciones del demonio gpsd vía protocolo JSON sobre TCP.

        Reintenta la conexión con un intervalo de espera si falla o se
        corta (ej: gpsd todavía no arrancó, o el dongle GPS se
        desconectó un instante) — nunca abandona el hilo en silencio
        mientras no se pida detenerlo explícitamente.
        """
        while not self._stop_event.is_set():
            logger.info(
                "GpsManager: conectando a gpsd en %s:%s", self.gpsd_host, self.gpsd_port
            )
            try:
                with socket.create_connection(
                    (self.gpsd_host, self.gpsd_port), timeout=5
                ) as sock:
                    sock.settimeout(1.0)
                    sock.sendall(b'?WATCH={"enable":true,"json":true}\r\n')
                    buffer = ""
                    while not self._stop_event.is_set():
                        try:
                            chunk = sock.recv(4096).decode("utf-8", errors="ignore")
                        except TimeoutError:
                            continue
                        if not chunk:
                            logger.warning("GpsManager: gpsd cerró la conexión")
                            break
                        buffer += chunk
                        while "\n" in buffer:
                            line, buffer = buffer.split("\n", 1)
                            self._handle_gpsd_line(line)
            except OSError as exc:
                logger.error("GpsManager: no se pudo conectar a gpsd: %s", exc)

            if self._stop_event.is_set():
                break

            logger.info(
                "GpsManager: reintentando conexión a gpsd en %.1fs",
                self.reconnect_interval_seconds,
            )
            self._stop_event.wait(self.reconnect_interval_seconds)

    def _handle_gpsd_line(self, line: str) -> None:
        line = line.strip()
        if not line:
            return
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            return

        if message.get("class") != "TPV":
            return

        mode = message.get("mode", 0)  # 0/1 = sin fix, 2 = 2D, 3 = 3D
        if mode < 2 or "lat" not in message or "lon" not in message:
            self._notify(GpsPosition(latitude=0.0, longitude=0.0, has_fix=False))
            return

        speed_ms = message.get("speed", 0.0) or 0.0
        position = GpsPosition(
            latitude=message["lat"],
            longitude=message["lon"],
            speed=speed_ms * 3.6,
            heading=message.get("track"),
            has_fix=True,
        )
        self._notify(position)

    def _run_serial(self) -> None:
        """Lee sentencias NMEA directo del puerto serie con pyserial.

        Reintenta abrir el puerto con un intervalo de espera si falla
        (ej: el dongle USB-GPS todavía no fue reconocido por el
        sistema al bootear, o se desconectó momentáneamente).
        """
        try:
            import serial
        except ImportError:
            logger.error(
                "GpsManager: pyserial no está instalado, no se puede usar "
                "el backend 'serial'"
            )
            return

        while not self._stop_event.is_set():
            logger.info(
                "GpsManager: abriendo puerto serie %s @ %s baudios",
                self.serial_port,
                self.serial_baudrate,
            )
            try:
                with serial.Serial(
                    self.serial_port, self.serial_baudrate, timeout=1
                ) as ser:
                    pending_lat: float | None = None
                    pending_lon: float | None = None

                    while not self._stop_event.is_set():
                        raw_line = ser.readline()
                        if not raw_line:
                            continue
                        try:
                            line = raw_line.decode("ascii", errors="ignore")
                        except UnicodeDecodeError:
                            continue

                        gga = parse_gga(line)
                        if gga is not None:
                            if gga.get("has_fix"):
                                pending_lat = gga["latitude"]
                                pending_lon = gga["longitude"]
                            else:
                                self._notify(
                                    GpsPosition(latitude=0.0, longitude=0.0, has_fix=False)
                                )
                            continue

                        rmc = parse_rmc(line)
                        if rmc is not None and rmc.get("has_fix"):
                            lat = rmc.get("latitude", pending_lat)
                            lon = rmc.get("longitude", pending_lon)
                            if lat is not None and lon is not None:
                                self._notify(
                                    GpsPosition(
                                        latitude=lat,
                                        longitude=lon,
                                        speed=rmc.get("speed", 0.0),
                                        heading=rmc.get("heading"),
                                        has_fix=True,
                                    )
                                )
            except Exception as exc:  # noqa: BLE001 - errores de hardware variados
                logger.error("GpsManager: error leyendo puerto serie: %s", exc)

            if self._stop_event.is_set():
                break

            logger.info(
                "GpsManager: reintentando abrir puerto serie en %.1fs",
                self.reconnect_interval_seconds,
            )
            self._stop_event.wait(self.reconnect_interval_seconds)
