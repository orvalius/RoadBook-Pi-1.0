-- Migración 001 - Schema inicial
-- Tabla waypoints según especificación maestra + columna re_triggerable
-- (acordada en el diseño de arquitectura del Sprint 2: permite que un
-- waypoint vuelva a disparar su evento en cada re-entrada al radio;
-- si es 0, el evento se dispara una única vez por sesión).

CREATE TABLE IF NOT EXISTS waypoints (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre         TEXT NOT NULL,
    latitud        REAL NOT NULL,
    longitud       REAL NOT NULL,
    radio          REAL NOT NULL DEFAULT 50,
    categoria      TEXT,
    imagen         TEXT,
    audio          TEXT,
    velocidad      REAL,
    angulo         REAL,
    prioridad      INTEGER NOT NULL DEFAULT 0,
    descripcion    TEXT,
    activo         INTEGER NOT NULL DEFAULT 1,
    re_triggerable INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_waypoints_activo ON waypoints (activo);
CREATE INDEX IF NOT EXISTS idx_waypoints_categoria ON waypoints (categoria);
