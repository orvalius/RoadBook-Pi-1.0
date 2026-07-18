-- Migración 002 - Tabla actions
-- Permite definir secuencias de múltiples acciones por waypoint
-- (Sprint 8: Event Engine). Si un waypoint no tiene filas en esta
-- tabla, el Event Engine sintetiza una secuencia por defecto a partir
-- de sus columnas legacy `imagen`/`audio` (retrocompatibilidad total
-- con waypoints creados en sprints anteriores).

CREATE TABLE IF NOT EXISTS actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    waypoint_id INTEGER NOT NULL,
    orden       INTEGER NOT NULL,
    tipo        TEXT NOT NULL,
    payload     TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (waypoint_id) REFERENCES waypoints (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_actions_waypoint_orden ON actions (waypoint_id, orden);
