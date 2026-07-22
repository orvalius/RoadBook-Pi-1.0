-- Migración 003 - Roadbook Rendering Engine
-- Agrega dos columnas a waypoints, sin tocar nada existente:
--   icono: pictograma a mostrar en la tira del roadbook (puramente visual)
--   orden_ruta: posición manual en la ruta, cuando no hay track GPX
-- Ningún waypoint existente pierde datos: icono usa un default sensato
-- y orden_ruta queda NULL (se ordena por id como fallback).

ALTER TABLE waypoints ADD COLUMN icono TEXT NOT NULL DEFAULT 'generico';
ALTER TABLE waypoints ADD COLUMN orden_ruta INTEGER;
