---
globs: "**/scripts/load_*_to_postgis.py,**/scripts/*ingest*.py,**/*Natural_England*/**,**/*postgis_ingest*/**"
---

# GeoPackage → PostGIS ingestion rules

Use this pattern whenever a task asks to load one or more `.gpkg` files into PostGIS as standalone tables (i.e. each GPKG is its own dataset, not a tiled split).

## Reference implementation

The canonical working scripts live at:
`OneDrive - priorpartners.com/Documents/05_Code_Scripts/Working_Scripts/Natural_England/scripts/`

- `common.py` — env loader, ISO-timestamped dual-sink logger, subprocess runner with secret redaction, `ogrinfo_layers()` parser, `gdal_data_env()` PROJ/GDAL_DATA override.
- `load_gpkg_to_postgis.py` — single-GPKG CLI loader with `--gpkg --schema --table [--append] [--add-area-ha] [--dry-run]`.
- `run_all.py` — batch driver with the per-file `(gpkg, table)` mapping; supports `--only`, `--from`, `--dry-run`.

### Optional flags

- `--add-area-ha` — adds a plain `area_ha double precision` column populated once via `ST_Area(geom)/10000`. Requires a projected CRS in metres (BNG works directly). Column has a `COMMENT ON COLUMN` noting it's computed at load and goes stale if the geometry is later edited. The loader auto-detects geometry type via `classify_geometry()`: Point/Line layers cause the flag to be silently skipped with a warning, polygon layers proceed, `Unknown (any)` proceeds with a notice. Honouring the flag literally on point layers used to produce a column of zero hectares — that footgun is gone.

### Origin geometry reporting

Every load logs a one-line "Origin geometry: <type> (bucket=<polygon|point|line|unknown>, SRID=..., features=...)" banner immediately after ogrinfo inspection. The bucket is the same one `--add-area-ha`'s guard reads, so a misapplied flag is visible at a glance even when scrolling through logs.

For a new dataset cohort, **copy the three scripts**, edit the `MAPPING` and `SCHEMA` constants in `run_all.py`, and run. Don't re-derive the pattern from scratch.

## ogr2ogr flag set (memorise)

```
ogr2ogr -f PostgreSQL "PG:" <gpkg> <layer>
  -nln <schema>.<table>
  -nlt PROMOTE_TO_MULTI
  -t_srs EPSG:27700
  -lco GEOMETRY_NAME=geom -lco FID=gid -lco PRECISION=NO -lco SCHEMA=<schema>
  --config PG_USE_COPY YES -gt 65536 -progress
  -overwrite      # or -append
```

PG credentials go in env (`PGHOST`, `PGPORT`, `PGDATABASE`, `PGUSER`, `PGPASSWORD`), **not** in the connection string. After load, always: GIST index on `geom`, `VACUUM ANALYZE`, and a `COMMENT ON TABLE` recording source filename + ISO load timestamp + SRID.

**`FID=gid` does NOT guarantee a primary key.** `-nlt PROMOTE_TO_MULTI` (and any
multipolygon→single-part explosion) makes the source FID **repeat across the
exploded rows**, so `-lco FID=gid` produces a *non-unique* `gid` and **no PK
constraint is created** — the load finishes with a GIST but silently no PK.
**Verify the PK after every load** (see `sql.md` § "Verification"); if the FID
column isn't unique, add a fresh surrogate
`ALTER TABLE <schema>.<table> ADD COLUMN gid bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY;`
(part of the default set — no approval needed).

**Index discipline (see `sql.md` § "Index discipline"):** the floor is **exactly
one PK + exactly one GIST(geom)** — a load is not complete without both. That is
also the maximum default set: any other index — btree on tile/region column,
`source_file`, date column, attribute — requires per-instance sign-off, even
mid-load. Notify and wait.

**Catalogue refresh (if loading into / promoting to `uk_baseline`):** the load is
not finished until the published catalogue is regenerated and all three outputs
are refreshed — Excel, standalone HTML, and the live GitHub Pages site. Full
procedure and commands in `sql.md` § "Catalogue refresh (uk_baseline)".

## Two Windows environment gotchas

**1. Empty `password=` breaks libpq's parser.**
**Why:** if `.env` has `PG_PASSWORD=` (empty) — common when the server uses peer/trust/Kerberos auth — emitting `password=` literally into the libpq conninfo throws `missing "=" after "..."`. **How to apply:** never embed PG creds in the conninfo string for ogr2ogr — use `PG:` (just the prefix) and pass `PGHOST`/`PGUSER`/etc via the subprocess env. For psycopg, omit the `password=` token from conninfo when the value is empty.

**2. A PostgreSQL 17 install on Windows poisons `PROJ_LIB` and `GDAL_DATA` for the whole user environment.**
**Why:** the PostgreSQL installer registers `PROJ_LIB=C:\Program Files\PostgreSQL\17\share\contrib\postgis-3.5\proj` and `GDAL_DATA=C:\Program Files\PostgreSQL\17\gdal-data`. Those bundled copies have an incompatible PROJ database layout (`DATABASE.LAYOUT.VERSION.MINOR = 2`, OSGeo4W's PROJ 9 needs ≥ 6) and ogr2ogr fails with `Failed to process SRS definition: EPSG:27700`. **How to apply:** for any subprocess that calls OSGeo4W's `ogr2ogr` / `ogrinfo`, override these in the subprocess environment using `gdal_data_env(ogr2ogr_path)` from `common.py`, which derives them from the binary location (`<root>\share\proj` and `<root>\apps\gdal\share\gdal`). Set both `PROJ_LIB` and `PROJ_DATA` (PROJ 9 prefers the latter).

## Other anti-bug notes

- **Don't trust `ogrinfo`'s `srid` output as gospel.** Some GPKGs (Natural England's, for example) have a valid CRS in the GPKG metadata table but ogrinfo's text output reports `srid=None`. The downstream `-t_srs EPSG:27700` still works because ogr2ogr reads the actual `srs_id` from the GPKG. Log a warning, don't fail.
- **`PROMOTE_TO_MULTI` handles 3D/Measured polygons silently.** "3D Measured Multi Polygon" sources (e.g. Ancient Woodland Revised) load fine; M/Z values are preserved.
- **One layer per GPKG is the common case but assert it.** If `ogrinfo_layers()` returns more than one, fail loud — don't silently pick the first.
- **Driver naming convention:** target tables follow `<theme>_<source>_<dataset>_<date>` per the global SQL rules. For Natural England: `env_naturalengland_<dataset>_<MMMyyyy>`.

## Script invocation cheat sheet

```powershell
# From an OSGeo4W shell (so ogrinfo/ogr2ogr are on PATH), or from any shell after
# prepending C:\OSGeo4W\bin to PATH:
$env:PATH = "$env:PATH;C:\OSGeo4W\bin"
python scripts/run_all.py --dry-run                    # preview all
python scripts/run_all.py                               # load all
python scripts/run_all.py --only <table_name>           # one
python scripts/run_all.py --from <table_name>           # resume
```

Logs land at `_state/logs/<table>_<utc-timestamp>.log` per invocation.
