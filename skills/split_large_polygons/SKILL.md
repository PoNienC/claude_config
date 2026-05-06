---
name: split_large_polygons
description: Step-by-step runbook for splitting a multi-million-feature polygon dataset by an admin boundary (LAD / ward / tile) in PostGIS when the production split functions in uk_baseline (split_layer_by_wards, split_layer_by_lad) are timing out, OOMing, or saturating WAL. Trigger when the user mentions splitting large polygon layers, slow ST_Intersection, work_mem spills, or batch-processing PostGIS data.
---

# split_large_polygons — runbook

A decision-tree for splitting a very large polygon layer by an admin boundary in PostGIS, when the single-transaction pipeline (`uk_baseline.split_layer_by_wards` / `split_layer_by_lad`) can't cope.

## Step 0 — Confirm the problem is actually scale

Before reaching for batching, get the numbers:

```sql
-- row count, average and max vertex count per feature
SELECT
    count(*)                              AS row_count,
    avg(ST_NPoints(geom))::int            AS avg_vertices,
    max(ST_NPoints(geom))                 AS max_vertices,
    sum(ST_NPoints(geom))                 AS total_vertices,
    pg_size_pretty(pg_relation_size('uk_baseline.<table>')) AS table_size
FROM uk_baseline.<table>;
```

Decision:

- **< 200 k rows AND avg_vertices < 200** → use the production `uk_baseline.split_layer_by_lad` directly. Skip this skill.
- **200 k – 1 M rows OR avg_vertices 200–1 000** → production function may still work; try once with raised `work_mem` (Step 6 below). If it fails, come back here.
- **> 1 M rows OR max_vertices > 10 000** → batch. Continue.

## Step 1 — Pre-process the source

```sql
-- a. validate once, materialise
CREATE TABLE uk_baseline.<table>__valid AS
SELECT
    fid AS fid_original,
    /* all other source attrs */
    ST_MakeValid(geom) AS geom
FROM uk_baseline.<table>;

-- b. subdivide if heavy-vertex
CREATE TABLE uk_baseline.<table>__sub AS
SELECT
    fid_original,
    /* all other source attrs */
    ST_Subdivide(geom, 256) AS geom
FROM uk_baseline.<table>__valid;

-- c. index + analyze
CREATE INDEX <table>__sub_geom_gix ON uk_baseline.<table>__sub USING GIST(geom);
ANALYZE uk_baseline.<table>__sub;
```

Skip (b) when `max_vertices < 1 000`. Always do (a) and (c).

## Step 2 — Pick a batching strategy

| Condition | Strategy |
|---|---|
| Splitting by LAD or ward, > 100 batches naturally | **Per-key batching** — loop over the split layer's primary key (`lad25cd` / `wd21cd`). |
| LAD sizes wildly uneven (Highland vs City of London) | **Tile batching** — `uk.generate_tessellation` over the AOI, loop over tile IDs. |
| Splitting by tessellation tiles already | Loop over tiles directly. |

Default to per-key batching. Switch to tiles only after measuring.

## Step 3 — Run the batched INSERT

Drive the loop from **PSQL with `ON_ERROR_STOP`**, not a `DO` block — a `DO` block is one transaction, defeating the resumability win.

`one_lad.sql`:
```sql
\set ON_ERROR_STOP on
BEGIN;

INSERT INTO uk_baseline.<output> (col1, col2, …, lad25nm, lad25cd, geom)
SELECT
    a.col1, a.col2, …,
    b.lad25nm, b.lad25cd,
    (ST_Dump(
        ST_Intersection(
            ST_ClipByBox2D(a.geom, ST_Envelope(b.geom)),
            ST_ClipByBox2D(b.geom, ST_Envelope(a.geom))
        )
    )).geom
FROM uk_baseline.<source>__sub a
JOIN uk_baseline.adm_ons_lad_boundary_may2025 b
  ON b.lad25cd = :'lad'
 AND a.geom && b.geom
 AND ST_Intersects(a.geom, b.geom);

COMMIT;
```

Driver (bash):
```bash
psql -At -c "SELECT lad25cd FROM uk_baseline.adm_ons_lad_boundary_may2025 ORDER BY lad25cd" \
  | while read lad; do
      echo "[$(date +%H:%M:%S)] $lad"
      psql -v ON_ERROR_STOP=1 -v lad="$lad" -f one_lad.sql || exit 1
    done
```

**Before starting the loop, set session memory:**
```sql
SET work_mem = '512MB';
SET maintenance_work_mem = '2GB';
SET max_parallel_workers_per_gather = 4;
```

## Step 4 — Post-process once at the end

After all batches succeed, do these once on the output table (do NOT do them per-batch — the index would be rebuilt every time):

```sql
-- enforce geometry type/SRID
ALTER TABLE uk_baseline.<output>
  ALTER COLUMN geom TYPE geometry(Polygon, 27700)
  USING ST_Force2D(ST_SetSRID(geom, 27700));

-- area metric
ALTER TABLE uk_baseline.<output> ADD COLUMN area_ha double precision;
UPDATE uk_baseline.<output> SET area_ha = ST_Area(geom) / 10000.0;

-- new fid PK
ALTER TABLE uk_baseline.<output> ADD COLUMN fid bigserial;
ALTER TABLE uk_baseline.<output> ADD CONSTRAINT <output>_pkey PRIMARY KEY (fid);

-- spatial index
CREATE INDEX <output>_geom_gix ON uk_baseline.<output> USING GIST(geom);

-- analyze
ANALYZE uk_baseline.<output>;
```

## Step 5 — Verify

Three checks, all cheap:

```sql
-- a. row count: output >= source (each source row may produce multiple output rows)
SELECT
    (SELECT count(*) FROM uk_baseline.<source>) AS source_rows,
    (SELECT count(*) FROM uk_baseline.<output>) AS output_rows;

-- b. total area: should match source within rounding
SELECT
    (SELECT sum(ST_Area(geom)) FROM uk_baseline.<source>) AS source_area,
    (SELECT sum(ST_Area(geom)) FROM uk_baseline.<output>) AS output_area;
-- difference should be < 0.01 % unless slivers were filtered

-- c. coverage: every LAD that intersected the source has at least one output row
SELECT b.lad25cd, b.lad25nm,
       count(o.fid) AS output_features
FROM uk_baseline.adm_ons_lad_boundary_may2025 b
LEFT JOIN uk_baseline.<output> o ON o.lad25cd = b.lad25cd
WHERE EXISTS (
    SELECT 1 FROM uk_baseline.<source> s
     WHERE s.geom && b.geom AND ST_Intersects(s.geom, b.geom)
)
GROUP BY b.lad25cd, b.lad25nm
HAVING count(o.fid) = 0;
-- should return zero rows; any rows here are LADs the loop missed
```

## Step 6 — Cut over

Only when verification passes:

```sql
-- atomic rename inside one transaction
BEGIN;
DROP TABLE uk_baseline.<source>;
ALTER TABLE uk_baseline.<output> RENAME TO <source_table_name>;
ALTER INDEX uk_baseline.<output>_geom_gix RENAME TO <source_table_name>_geom_gix;
ALTER TABLE uk_baseline.<source_table_name> RENAME CONSTRAINT <output>_pkey TO <source_table_name>_pkey;
COMMIT;

-- clean up staging
DROP TABLE IF EXISTS uk_baseline.<table>__valid;
DROP TABLE IF EXISTS uk_baseline.<table>__sub;
```

## Things to confirm with the user before starting

- Target source table (fully-qualified).
- Whether they're OK to materialise `__valid` and `__sub` staging tables (extra disk).
- Server `work_mem` headroom — propose 512 MB as default.
- Parallel worker count — propose 4 as default; ask before going higher.
- Whether downtime on the source table is OK (Step 6) or whether the rename should happen at a specific time.
- Boundary vintage — `lad25*` from `adm_ons_lad_boundary_may2025`, `wd21*` from `adm_bndry_ons_ward_boundaries_2022`.

## See also

- Catalogue of techniques and trade-offs: `…/05_Code_Scripts/SQL/Split/techniques.md`.
- Folder-level guidance for experiments: `…/05_Code_Scripts/SQL/Split/CLAUDE.md`.
- Production functions to beat: `…/05_Code_Scripts/SQL/Working_Scripts/Function_split_layer_by_wards.sql` and `Function_split_layer_by_lad.sql`.
