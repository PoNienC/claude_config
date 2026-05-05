---
globs: sql/**/*.sql
---

# SQL / PostGIS rules

Loaded only when working inside `sql/`.

## Naming
- Table names: `<THEME>_<source>_<dataset>_<date>` — uppercase theme, lowercase rest.
- Column names: snake_case, ≤ 30 characters.
- Index names: `<table>_<column>_idx` (or `_geom_idx` for the geometry column).
- View names prefixed `v_`. Materialised views prefixed `mv_`.

## Geometry
- Every spatial table has a GIST index on the geometry column.
- Declare SRID explicitly: `GEOMETRY(POINT, 27700)`, never the typeless `GEOMETRY`.
- Validate with `ST_IsValid` before any analytical join. Don't `ST_MakeValid` silently — comment why.

## Joins
- Never join on `OBJECTID`. Always join on a domain key.
- Spatial joins must use `ST_Intersects`, `ST_Contains`, or `ST_DWithin` — these use the spatial index. Avoid `ST_Distance < x` predicates which scan.

## Routing (pgRouting)
- Network tables need btree indexes on `source`, `target`, and `cost`.
- Use `pgr_dijkstra` for single-source; `pgr_bdDijkstra` for bidirectional; `pgr_drivingDistance` for catchments.
- For million-origin workloads, batch in groups of 10k and parallelise via `xargs -P` rather than running one query.

## Comments
- Every `CREATE TABLE` must have a `COMMENT ON TABLE` documenting source, EPSG, and ingestion date.
- Every non-obvious column gets a `COMMENT ON COLUMN`.

## Migration discipline
- DDL changes in versioned migration files only. No ad-hoc `ALTER TABLE` in analysis scripts.
- Reversible migrations preferred — every up has a down.
