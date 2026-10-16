---
paths: ["sql/**/*.sql"]
---

# SQL / PostGIS rules

Loaded only when working inside `sql/`.

## Naming

**Never invent the name of a new database object on your own.** Tables,
views, materialised views, and schemas are user-facing identifiers that
the firm reuses across analyses for years. Always ask the user what to
call them before creation — even if a name "looks obvious" from the
context.

- If the user has explicitly given a name (e.g. "create
  `mob_public_right_of_way`"), use that name exactly.
- If the user has not specified, **ask via `AskUserQuestion`** before
  running any `CREATE TABLE` / `CREATE VIEW` / `CREATE SCHEMA`.
- Once a name is chosen, follow the conventions below for fields,
  indexes, and view prefixes; never quietly substitute a "better" name
  in those layers either.

This rule binds even when the convention below would suggest an
obvious value — the firm has institutional knowledge about which
abbreviations and prefixes mean what (e.g. `mob_` for mobility,
`env_` for environment) that may not be visible from a single
conversation.

### Conventions (apply once the name itself is decided)

- Table names: `<THEME>_<source>_<dataset>_<date>` — uppercase theme, lowercase rest.
- Column names: snake_case, ≤ 30 characters.
- Index names: `<table>_<column>_idx` (or `_geom_idx` for the geometry column).
- View names prefixed `v_`. Materialised views prefixed `mv_`.

## Geometry
- Every spatial table has a GIST index on the geometry column.
- Declare SRID explicitly: `GEOMETRY(POINT, 27700)`, never the typeless `GEOMETRY`.
- Validate with `ST_IsValid` before any analytical join. Don't `ST_MakeValid` silently — comment why.

## Index discipline (require approval)

**The mandatory floor — every spatial table MUST have, no exceptions:**
- **exactly one** PRIMARY KEY, and
- **exactly one** GIST index on the geometry column.

This is the SQL-import 101 invariant: a load is **not complete** until both exist
(verify with the queries under "Verification" below — they are as mandatory as
the comment checks). One PK + one GIST(geom) is also the *maximum* default set;
anything beyond it needs approval (next paragraph).

**Picking the primary key — and the exploded-multipart trap.** The PK normally
sits on the loader surrogate (`gid` / `fid` / `objectid` / equivalent). **But a
unique loader id is NOT guaranteed.** `ogr2ogr -nlt PROMOTE_TO_MULTI` and any
multipolygon→single-part explosion make the source FID **repeat across rows**, so
`-lco FID=gid` yields a *non-unique* column and **no PK constraint forms** — the
load silently finishes with a GIST but no PK. After every load, check the PK
exists (Verification below). If no column is unique + not-null, add a fresh
surrogate — `ALTER TABLE … ADD COLUMN gid bigint GENERATED ALWAYS AS IDENTITY
PRIMARY KEY` — this is part of the default set, so it needs **no** approval.
(Established 2026-06-01 after 8 exploded-multipart layers in `uk_baseline` —
built-up areas, flood zones, OS surface/tidal water, woodland, etc. — were found
with a GIST but no PK; root cause: the floor was never verified post-load.)

**Any other index OR uniqueness constraint requires explicit user approval before being created.** This includes:

- Column-level `UNIQUE` or `UNIQUE NOT NULL` shorthand declared inside `CREATE TABLE` — these create a backing unique btree index and are *not* free
- Table-level `UNIQUE (col [, col …])` constraints
- Explicit `CREATE [UNIQUE] INDEX …` statements
- btree on `source_file`, attribute, or date columns
- Partial / expression / BRIN / multi-column composites
- **Auto-created indexes from upstream tooling** (e.g. `ogr2ogr` adding a spatial index *in addition to* the one your script creates; the source GPKG carrying a spatial index that gets translated). Audit `pg_indexes` after every load; if you see more than `_pkey` + `_geom_idx`, ask whether to drop the extra one.

`NOT NULL` on a non-id column is *not* an index — it is a row-level integrity check stored with the data, not a separate object. Keeping `NOT NULL` does **not** need approval. The distinction matters: `NOT NULL` costs nothing; `UNIQUE` adds an index.

When you believe an extra index is warranted, propose it with a one-sentence rationale (e.g. "DELETE on source_file is the loader's hot path; index drops it from ~5 s to ~1 ms per file") and wait for sign-off. Temporary indexes used only during a bulk load and dropped afterwards still need approval, but a single approval covers the create + drop lifecycle. **Notify the user every time** a new index is needed, even if a similar one was approved earlier in the session.

Established 2026-05-26 during the VOA NDR load, after the agent added a `UNIQUE NOT NULL` column-level constraint on the geography code of six staging tables without asking — the user had to retroactively drop six `_<geog>cd_key` constraints. The shorthand is the trap: typing `UNIQUE NOT NULL` reads as one keyword but creates a separate index object.

Rationale: indexes are cheap to add when a query proves it needs one, hard to identify-and-remove when chosen pre-emptively. Bulk loads run faster without them. The default minimal set keeps the table easy to reason about.

## Joins
- Never join on `OBJECTID`. Always join on a domain key.
- Spatial joins must use `ST_Intersects`, `ST_Contains`, or `ST_DWithin` — these use the spatial index. Avoid `ST_Distance < x` predicates which scan.

## Heavy geometry operations — chunk first, single-shot last

PostGIS geometry operators are super-linear in the *larger* operand's
vertex count and have terrible cache behaviour for big-vs-many-small
patterns. Long-running single-shot queries also fail catastrophically:
a 70-minute query that errors at minute 71 leaves you with nothing.
**Default to chunked execution.** Reach for a single-shot global query
only when you have proved chunk overhead exceeds the saved compute.

### The chunking decision (apply in this order)

Before writing a query that does any of:

- `ST_Difference(big_side, ST_Union(many_pieces))`
- `ST_Intersection(big_side, many_pieces)` in a spatial join
- `ST_Union(geom)` aggregate over > 10 k rows
- Per-row buffer / overlay / clip over millions of features
- Raster zonal stats / mosaic / clip over a large raster
- Any operation estimated at > 5 min wall-clock

ask: **how do I chunk this?** Pick the first viable option:

#### Option A — natural partition key (cheapest)

Both operands already carry the key (`lad25cd`, `wd25cd`, `rgn22cd`,
country, postcode area, OS letter, ...). Use it directly:

```sql
-- ❌ Naive: one giant union, slow per-row clip
WITH big_union AS (
    SELECT ST_Union(geom) AS geom FROM other_table
)
SELECT my_id,
       CASE WHEN ST_Intersects(t.geom, u.geom)
            THEN ST_Difference(t.geom, u.geom)
            ELSE t.geom
       END AS new_geom
FROM my_table t CROSS JOIN big_union u;

-- ✅ Per-key: small per-partition unions, fast per-row clip,
--    parallelisable, cache-friendly
WITH per_key AS (
    SELECT lad25cd, ST_Union(geom) AS geom
    FROM other_table
    GROUP BY lad25cd
)
SELECT my_id,
       CASE WHEN u.geom IS NULL THEN t.geom
            WHEN ST_Intersects(t.geom, u.geom)
                 THEN ST_Difference(t.geom, u.geom)
            ELSE t.geom
       END AS new_geom
FROM my_table t LEFT JOIN per_key u USING (lad25cd);
```

**Validity precondition.** Per-key chunking is mathematically identical
to the global operation only when both inputs are already clipped to
the key (no row's geometry crosses partition boundaries). All `_lad`
and `_wd` deliverables produced by `split_layer_by_lad` /
`split_layer_by_ward` satisfy this. Raw national-extent inputs do not
— either pre-split them or use Option B.

#### Option B — manufactured tile grid (when no key exists)

No shared admin key? **Generate one.** PostGIS ships
`ST_SquareGrid(cell_size, extent_geom)` and `ST_HexagonGrid(...)`.
Tile size choice: aim for ~1 k to ~100 k input rows per tile.

```sql
-- One-time: build a tile grid covering the area of interest
CREATE TABLE uk.process_tiles_10km AS
SELECT row_number() OVER () AS tile_id,
       geom::geometry(Polygon, 27700) AS geom
FROM ST_SquareGrid(
    10000,                                       -- 10 km cells
    ST_SetSRID(ST_Extent(geom)::geometry, 27700) -- bbox of inputs
);
CREATE INDEX process_tiles_10km_geom_gix ON uk.process_tiles_10km USING gist (geom);

-- Then per-tile chunked execution:
WITH tile AS (
    SELECT tile_id, geom FROM uk.process_tiles_10km WHERE tile_id = :tile
),
big_local AS (
    SELECT ST_Union(ST_Intersection(b.geom, t.geom)) AS geom
    FROM big_table b, tile t
    WHERE b.geom && t.geom AND ST_Intersects(b.geom, t.geom)
)
INSERT INTO result_table (...)
SELECT ...
FROM my_table m, tile t, big_local bl
WHERE m.geom && t.geom AND ST_Intersects(m.geom, t.geom)
  AND ...;
```

Drive the per-tile loop from Python (psycopg in a `for tile_id in tiles:`)
or `psql` `\gexec`. Each tile is its own transaction — failure isolates
to one tile.

**Other manufactured-key options:** S2 cells (use `pgsphere` or pre-encode
via Python), geohash strings (4-7 chars for UK), OS National Grid 100 km
letters (`ST_LetterMethod` equivalent — encode the bottom-left corner).

#### Option C — bin by row id / hash (non-spatial chunking)

For attribute-only batch transforms with no spatial clustering benefit:

```sql
-- Process in 50 batches of equal size
WHERE fid % 50 = :batch_n
-- or
WHERE hashtext(some_col) % 50 = :batch_n
```

#### Option D — time-based chunks

For temporal data, chunk by month / year / day window. Each chunk is
typically a clean unit (a month of records) that fits the natural
update cadence.

### When NOT to chunk

- Operations with true global dependency (single-pass aggregates like
  `count(*)`, simple `sum()` over the whole table — chunk overhead is
  pure waste).
- Inputs small enough that one transaction completes in seconds
  regardless (< 10 k geometries, simple operators).
- Graph traversals that cross chunk boundaries (routing,
  connected-components — needs careful seam handling).

### Cast hygiene for geometry difference / intersection / sym-difference

`ST_Difference`, `ST_Intersection`, `ST_SymDifference` return
**`GeometryCollection`** (not `MultiPolygon`) when inputs share
coincident boundary edges — the result includes the polygon answer
*plus* dangling 1-D or 0-D fragments at touching edges. Inserting
into `geometry(MultiPolygon, 27700)` then fails with
`InvalidParameterValue: Geometry type (GeometryCollection) does not
match column type (MultiPolygon)`. The failure typically arrives
*after* the heavy computation finishes — hours wasted.

**Always** wrap the result before casting:

```sql
ST_Multi(
    ST_CollectionExtract(
        ST_MakeValid(<difference_or_intersection_expr>),
        3                               -- type 3 = polygons only
    )
)::geometry(MultiPolygon, 27700)
```

Filter rows that become empty after the cast:

```sql
WHERE new_geom IS NOT NULL AND NOT ST_IsEmpty(new_geom)
```

Same hygiene pattern as Step 3 of `split_layer_by_lad`. Apply it to
every `ST_Difference` / `ST_Intersection` / `ST_SymDifference` result
destined for a typed MultiPolygon column.

### Fresh-build over ALTER + UPDATE

When the workflow is "modify an existing large table by adding
columns, inserting new rows, and updating geometries", prefer
**CREATE TABLE AS** to a fresh target over **ALTER + UPDATE** on the
existing one. Reasons:

- `ALTER TABLE ADD COLUMN` on > 1 M rows can rewrite the whole table.
- Multiple `UPDATE`s each scan + write new MVCC versions + invalidate
  indexes — N passes × table size of bloat.
- Result needs `VACUUM FULL` to reclaim space.
- Fresh-build is one sequential write, one set of indexes built at the
  end, no bloat, parallelisable.

A typical fresh-build runs 2-4× faster than the equivalent in-place
mutation with a cleaner result table.

### Make long jobs resumable

Any chunked workflow expected to run > 30 min needs a
`--resume-from <chunk-id>` or `--resume-from <step-name>` shape so a
mid-run failure doesn't lose committed work. Pattern: each chunk
commits as it finishes; the driver reads a checkpoint (file or table)
on startup and skips already-committed chunks.

### Cost calibration

Measured on this codebase (preserve as a reality check):

| Workload | Naive single-shot | Chunked | Speedup |
|---|---|---|---|
| `ST_Difference(AW, ST_Union(40 k AWR))` over 55 k AW rows | abandoned at 74 min | per-LAD: **19 min** | ≥ 4× and counting |
| `ST_Intersection` of 800 k Priority Habitats with 361 LADs | hours in one query | per-LAD recipe: ~1 h end-to-end | comparable but chunked is resumable |
| `ST_PointOnSurface` over 1.5 M polygons | OK single-shot (~5 min) | chunking overhead > saving | don't chunk |

## Routing (pgRouting)
- Network tables need btree indexes on `source`, `target`, and `cost`.
- Use `pgr_dijkstra` for single-source; `pgr_bdDijkstra` for bidirectional; `pgr_drivingDistance` for catchments.
- For million-origin workloads, batch in groups of 10k and parallelise via `xargs -P` rather than running one query.

## Comments

`COMMENT ON TABLE` and `COMMENT ON COLUMN` are non-negotiable per
`~/.claude/CLAUDE.md § "Source fidelity and ingestion discipline" Rule 5`.
That rule is the source of truth; what follows is the SQL-specific shape.

### `COMMENT ON TABLE` template

Sectioned plain-text. The one-line description at the top is mandatory.
Uppercase section headers introduce each block; bullets give the content.
Sections marked **required** are mandatory unless explicitly N/A for the
layer; sections marked **optional** are added only when relevant.

```
[One-line plain-English description: <source organisation> <what it is>, <Month YYYY>.]

SOURCE                                                              [required]
- [Publisher full name (ACRONYM). Provenance notes for any derived columns.]

DOCUMENTATION                                                       [required]
- [Label : URL]                          (URLs aligned with spaces, not tabs)
- [Label : URL]

DEFINITIONS                                                         [required]
- "[Quote from publisher in double quotes.]" (short attribution)

SCOPE                                                               [required]
- [Geographic coverage, filter clause, row count.]

CRS                                                                 [required]
- EPSG:NNNN ([projection name]). Reprojection note if applicable.

LICENCE                                                             [required]
- [Licence name and version.]

DATA QUALITY CAVEATS                                                [optional]
- [Things a downstream reader must know before trusting counts or values.]

ENRICHMENT (added at load, not from source)                         [optional]
- [Columns added during ingestion that don't exist in the upstream file.]

UPDATE REQUIRED                                                     [optional]
- [Upstream version/date vs. ours; refresh status.]

NOT IN THIS DATASET (informational)                                 [optional]
- [What's deliberately excluded that a reader might expect, with rationale.]

DERIVED FROM                                                        [optional]
- [For materialised views and subset tables: parent table + filter / aggregation rule.]

LOADED INTO uk_baseline                                             [required when load info known; otherwise omit the block]
- Loaded by [IMPORTER], [D Month YYYY].
```

### Style rules

- **The one-line description leads with the source organisation, states what the
  layer is, and ends with the Month-Year** (e.g. "ONS Built Up Areas (BUA),
  England & Wales extent, December 2024."). It does **not** carry the grain
  ("one row per …"), the word "grain", load-time enrichment notes, column counts,
  or other detail — those belong in `SCOPE` / `ENRICHMENT` / `DATA QUALITY
  CAVEATS`. Use the source's established short form where it is well known and
  used consistently across siblings (ONS, OS, NHS, MHCLG, GeoDS, DfT, DfE);
  otherwise the full name with acronym on first use (Valuation Office Agency
  (VOA), Office for Health Improvement and Disparities (OHID), Department for
  Energy Security and Net Zero (DESNZ)). The Month-Year must reflect the data's
  own edition / reference period, never the import date. Established 2026-06-01.
- **Direct publisher quotes live only under `DEFINITIONS`.** Always in
  double-quotes (the quotes themselves signal source-faithful copy — do not
  add any explicit marker about quote fidelity), always followed by a short
  attribution in parentheses. **Do NOT include `(accessed YYYY-MM-DD)` in the
  DEFINITIONS header or anywhere else** — the access-date metadata is
  not analytically useful and clutters the comment. Save it in a local
  reference file if you need to retain it; don't ship it into the DB.
- **Acronyms** are expanded on first use anywhere in the comment, even inside
  a `DEFINITIONS` quote (the expansion goes outside the quotes — never edit
  what's between the double-quotes). **Do not add an unnecessary acronym
  in parentheses if no one uses it** (e.g. "Get Information About Schools"
  not "Get Information About Schools (GIAS)" — `GIAS` is publisher jargon
  that downstream readers don't recognise).
- **URLs** are aligned with spaces, not tabs (renders correctly in QGIS DB
  Manager and in `psql \d+` output).
- **Section ordering** is the order listed above. Don't shuffle.
- **`DATA QUALITY CAVEATS`** is for *things colleagues will get wrong* if they
  trust the obvious read (exploded multipolygons, NULL-heavy columns, partial
  coverage). Not for general "be careful" hand-waving.
- **`ENRICHMENT`** is reserved for genuinely non-standard additions
  (non-publisher data, derived columns with sign-off, fixed-string vendor
  annotations). **Do NOT ENRICHMENT-list standard infrastructure columns**
  (`fid` / `geom` / `area_ha` / admin codes joined from ONS lookups) —
  those are documented at the column-comment level only. If the only
  "enrichment" would be `fid` + `geom` + a `*_nm` admin name, omit the
  block entirely.
- **`UPDATE REQUIRED`** mirrors the register's `update_required` flag. If the
  flag is `Y`, this section is mandatory.

### DEFINITIONS — firm definitional tone

A `DEFINITIONS` bullet states what the designation or dataset IS, in the firm
tone of a glossary entry. It is not a mission statement, a product
introduction, or an explanation. When choosing or trimming the publisher's
wording:

- **No first person / organisational framing** — drop "our", "we",
  "we work with ...". ("Our Heritage at Risk programme protects ..." is a
  mission statement, not a definition; replace it with what the register
  actually contains.)
- **No introductions or date-as-lead-in** — "Established in 1984, our
  'Register ...'" → integrate the date if it matters: "the Register (established
  1984) identifies ...".
- **No explanatory connectives** — drop "because", "in other words",
  "which helps ...". State the fact: "... can be protected, to prevent
  uncontrolled interference." not "..., which helps prevent ...".
- **Prefer a publisher sentence that is already definitional** (double-quoted,
  verbatim). If the publisher's nearest wording is mission / intro / explanatory,
  select a more definitional sentence from the same publisher, or state the
  definition plainly and attribute it **without** double-quotes (it is then a
  normalised statement, not a verbatim quote). Never introduce a fact the
  publisher does not state, and never alter a fact inside double-quotes.

Established 2026-05-29.

### Banned wording

These tokens must not appear anywhere in a `COMMENT ON TABLE` / `COMMENT ON COLUMN`:

- **`vintage`** (any form: "May 2024 vintage", "Data vintage X", "multi-vintage",
  "cross-vintage", "LSOA 2011 vintage", "LAD vintage"). State the date directly,
  or use "release" / "edition" / "boundary". Drop the word from headlines:
  "May 2024 vintage" → just "May 2024". Drop from the LOADED INTO opener:
  "Data vintage X" → "Loaded by [importer], [date]." Drop from boundary
  descriptions: "LSOA 2011 vintage" → "LSOA 2011 boundary".
- **`(accessed YYYY-MM-DD)`** in any section header or body — see Style rules.
- **`at audit time`** / **`verified at audit time`** / **`not recorded at audit time`**
  — never appear in a comment. Comments are facts. If something is unknown,
  ASK the user before drafting. Don't ship a placeholder hedge.
- **`(GIAS)`** and other unused-acronym parenthetical expansions — see Style rules.
- **SQL syntax of any kind** — query instructions AND derivation expressions.
  See "No SQL in comments" below.

### No SQL in comments

Comments describe WHAT the data is, in plain English — never HOW to query or
compute it. No SQL syntax of any kind appears in `COMMENT ON TABLE` /
`COMMENT ON COLUMN`, including:

- **Query / usage instructions** — `Use COUNT(DISTINCT x)`, `COUNT(*)`,
  `GROUP BY`, `WHERE ...`, `` filter `...` ``, `Cast with to_date(...)`,
  `Use`/`Prefer ST_Area(geom)` / `ST_Perimeter(geom)` "for live values", etc.
  A colleague reads the comment to understand the column, not to be told which
  query to run. State the grain as a *fact* instead: multipolygon explosion is
  "N rows representing M sites; geometry exploded to one polygon part per row",
  NOT "use COUNT(DISTINCT key)".
- **Derivation / computation expressions** — write the rule in words, not SQL:
  - `Derived at load: ST_Area(geom)/10000` → "Area in hectares, computed at load
    from the geometry."
  - `Derived: SUM(gva_2011) of constituent LSOAs` → "Derived: sum of gva_2011
    across the constituent LSOAs."
  - `per-year SUM(staging) equals SUM(source)` → "per-year sum of staging equals
    sum of source".
  - `NTILE(10) OVER (ORDER BY ...)` → "decile rank (1 = lowest … 10 = highest)".
  - `` Source field `OBS_VALUE` where `INDUSTRY_CODE`='010' `` →
    "Source field `OBS_VALUE` for industry code 010."

**Backtick `field_name` citations are NOT SQL and remain required** — naming a
source field as `` Source field `ons_code` `` is the mandated identifier-column
format (see `COMMENT ON COLUMN` rules). Backtick a *field name*, never a SQL
*expression*.

Established 2026-05-29 after a full sweep of `uk_baseline` comments removed
query instructions and rephrased every derivation expression into plain English.

### Date format inside comments

Use `D Month YYYY` (e.g. "27 May 2026", "13 May 2026"). Reasons:

- ISO timestamps like `2026-05-13T14:59:17+00:00` carry irrelevant precision
  (sub-minute, timezone offset) that adds noise without informing the reader.
- `Mar2026` / `May2026` short forms are acceptable in register columns
  (`date_imported`) but should be humanised in comments.
- Always: `Loaded by [IMPORTER], [D Month YYYY].` — never:
  `Loaded by [IMPORTER], 2026-05-13T14:59:17+00:00.`

### LOADED INTO uk_baseline block — when to include vs drop

- **Include** when the PP Data Register's `date_imported` carries a usable
  date (real month/year or ISO date, NOT `N/A` or blank). Populate as:
  `Loaded by [data_importer column], [D Month YYYY].` If `data_importer`
  is `N/A` or blank, just write `Loaded [D Month YYYY].`
- **Drop** the entire block when `date_imported` is blank, `N/A`, or
  `unknow(n)`. Don't ship a hedge like "Load date not recorded".

### `COMMENT ON COLUMN` rules

- **One line per column.** Multi-paragraph belongs in the table comment.
- Value columns: `Unit: "<publisher's exact wording, in double-quotes>"`.
- Identifier columns: `` Source field `<source_field_name>` ``.
- Geometry / boundary-join columns: `Geometry from <boundary_table>`.
- Synthetic surrogates (`fid`): omit.
- Derived columns (only when the user has approved the derivation per
  CLAUDE.md § Rule 2): describe the derivation rule and the source
  columns it draws from, **in plain English — no SQL expressions**
  (see "No SQL in comments").

### Verification

After load, every spatial table must satisfy **all** of these (indexes first —
the SQL-import 101 floor — then metadata):

```sql
-- exactly one PRIMARY KEY (expect 1)
SELECT count(*) FROM pg_constraint
WHERE conrelid = '<schema>.<table>'::regclass AND contype = 'p';

-- exactly one GIST index on the geometry column (expect 1)
SELECT count(*) FROM pg_index ix
JOIN pg_class i ON i.oid = ix.indexrelid
JOIN pg_am am ON am.oid = i.relam
JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = ANY(ix.indkey)
JOIN pg_type ty ON ty.oid = a.atttypid
WHERE ix.indrelid = '<schema>.<table>'::regclass
  AND am.amname = 'gist' AND ty.typname = 'geometry';

-- metadata
SELECT obj_description('<schema>.<table>'::regclass) IS NOT NULL;
SELECT count(*) FROM pg_description
WHERE objoid = '<schema>.<table>'::regclass
  AND objsubid > 0;   -- column comments
```

Run the schema-wide audit after any batch load (script:
`scan_index_discipline.py` pattern — one row per non-conformant table):

```sql
SELECT c.relname,
       (SELECT count(*) FROM pg_constraint k WHERE k.conrelid=c.oid AND k.contype='p') AS pks
FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
WHERE n.nspname='<schema>' AND c.relkind='r'
  AND (SELECT count(*) FROM pg_constraint k WHERE k.conrelid=c.oid AND k.contype='p') <> 1;
```

**Zero or >1 PK, zero or >1 GIST(geom), a `NULL` table comment, or zero column
comments — any of these means the load is INCOMPLETE.** Fix it (add the missing
PK / GIST, drop the duplicate, write the metadata) before declaring the load
done.

## Catalogue refresh (uk_baseline)

The `uk_baseline` schema is published as a colleague-facing catalogue in **three
forms**, all generated from the database's own metadata. **Whenever a layer is
loaded, renamed, re-commented, dropped, or otherwise changed in `uk_baseline`,
the change is NOT finished until all three are refreshed:**

1. **Excel** — `G:\0_Practice\10_Data management resources\04_Spreadsheets\uk_baseline_catalogue.xlsx`
2. **Standalone HTML** — `…\04_Spreadsheets\uk_baseline_catalogue.html`
3. **Live site (GitHub Pages)** — https://prior-partners.github.io/PP_uk_baseline/
   (repo `Prior-Partners/PP_uk_baseline`)

Refresh procedure, run from the uk_baseline working dir
(`…\Documents\03_Data_Management\uk_baseline`). The preview map comes from the
style registry, so a new or restyled layer first needs its style decision and a
registry rebuild (`C:\dev\uk_baseline_phase2\style_maplibre_build.py`; never edit
`styles/uk_baseline_style_registry.json` by hand).

```bash
python scripts/catalogue/preview_meta.py               # read-only: keys, extents, comment text the map prints
# PowerShell — QGIS 4.2.2 Python; table substrings, or --all (all 183 take ~1.5 h)
& "C:\Program Files\QGIS 4.2.2\bin\python-qgis.bat" scripts\catalogue\build_previews_qgis.py <table>
python scripts/catalogue/install_previews.py --apply   # staged PNG -> catalogue/docs/maps (dry run without --apply)
python scripts/catalogue/build_catalogue.py            # regenerates Excel + HTML (G: share) + MkDocs docs/
git -C catalogue add -A && git -C catalogue commit -m "Refresh catalogue: <what changed>"
cd catalogue && python -m mkdocs gh-deploy             # publish the live site — run FROM catalogue/, after the owner's OK
```

Notes:
- **Maps first.** A layer page shows a map only if `catalogue/docs/maps/<table>.png`
  exists when `build_catalogue.py` runs. Skipping the map step left 42 layers
  without a map from 10 June to 15 October 2026. Check the staged PNG
  (`C:\dev\catalogue_previews_qgis\<table>.png`, `render_report.json`) before installing.
- **QGIS previews since 16 October 2026.** `build_previews_qgis.py` draws each layer
  only from the registry, in the A4 announcement layout. Fine, dense or sparse
  layers get a close-up from `LOCAL_FRAMES` (basemap: water, roads, railways, town
  names, UK inset): pick the place by counting features at least 6 px across, or
  distinct names, not rows. Northern Ireland close-ups get no basemap and
  Scotland ones no town names (OS data is GB only; built-up areas England and Wales).
- **`build_maps.py` is retired for catalogue maps** (folium). It still writes the
  Dashboard's shared styles JSON on G:, but it also overwrites
  `catalogue/docs/maps/<table>.png` — if a Dashboard entry is needed, run it
  BEFORE `install_previews.py --apply`, so the QGIS preview is what stays.
- **Live audit after every deploy**: every layer page and map returns 200 and each
  live PNG is byte-identical to `catalogue/docs/maps` (method:
  `reviews/catalogue_site_audit_261016.md`). Wait until the GitHub Pages build
  reports `built` for the new gh-pages commit.
- **Close the Excel file first**, or the `.xlsx` rebuild is skipped (file lock).
- The generator reads the live DB and **preserves the hand-edited "About & how
  to use" sheet** — it rebuilds only the Layers + Columns sheets.
- `mkdocs gh-deploy` **must run from inside `catalogue/`** (it finds the git repo
  from the current directory, not the `-f` config path).
- One regeneration covers all three outputs; the same step also picks up new
  columns (e.g. a surrogate `gid` PK) on changed layers.

Established 2026-06-01. Map step changed to the QGIS previews 2026-10-16.

## Migration discipline
- DDL changes in versioned migration files only. No ad-hoc `ALTER TABLE` in analysis scripts.
- Reversible migrations preferred — every up has a down.
