---
name: split_large_polygons
description: Step-by-step runbook for splitting a multi-million-feature polygon dataset by an admin boundary (LAD / ward / tile) in PostGIS when the production split functions in uk_baseline (split_layer_by_wards, split_layer_by_lad) are timing out, OOMing, or saturating WAL. Trigger when the user mentions splitting large polygon layers, slow ST_Intersection, work_mem spills, or batch-processing PostGIS data.
---

# split_large_polygons — runbook

A decision-tree for splitting a very large polygon layer by an admin boundary in PostGIS, when the single-transaction pipeline (`uk_baseline.split_layer_by_wards` / `split_layer_by_lad`) can't cope.

**Production path:** the Python automation driver `Working_Scripts/Natural_England/scripts/split_layer_by_lad.py` implements the recipe end-to-end with parameterised per-layer configs. **Use the driver** for any new layer; the per-layer `Production_split_*_by_lad.sql` files in `SQL/Split/` are audit references, not the production entry point.

**Live cohort (11 production deliverables):** 3 DEFRA + 8 Natural England LAD-split tables, all in `uk_baseline.<full_source_name>_lad`. See `SQL/Split/HANDOVER.md` §3 for the full ledger.

**Reference docs (read in order for a new agent):**
1. This file — the decision-tree.
2. `SQL/Split/USER_GUIDE.md` — operator-facing workflow for adding a new layer.
3. `SQL/Split/Method_explained.md` — the 11-section handbook with recipe reasoning.
4. `SQL/Split/HANDOVER.md` — current state, gotchas, marine-clipping pattern.
5. `SQL/Split/techniques.md` — technique catalogue.

---

## Step 0 — Confirm the problem is actually scale

Before reaching for batching, get the numbers:

```sql
SELECT
    count(*)                              AS row_count,
    avg(ST_NPoints(geom))::int            AS avg_vertices,
    max(ST_NPoints(geom))                 AS max_vertices,
    sum(ST_NPoints(geom))                 AS total_vertices,
    pg_size_pretty(pg_relation_size('uk_baseline.<table>')) AS table_size
FROM uk_baseline.<table>;
```

Decision:

- **< 200 k rows AND avg_vertices < 200** → use the production `uk_baseline.split_layer_by_lad` function directly. Skip this skill.
- **200 k – 1 M rows OR avg_vertices 200–1 000** → production function may still work; if it fails, come back here.
- **> 1 M rows OR max_vertices > 10 000** → use the driver. Continue.

---

## The recipe in one paragraph

> Most polygons are wholly inside one LAD. Find those quickly via a boundary-line `ST_Intersects` filter plus an envelope-contains test, and assign the LAD with a cheap point-in-polygon on a precomputed `ST_PointOnSurface`. Only the polygons that actually cross a LAD boundary go through the expensive intersection work, with both source and LAD pre-subdivided to 32 vertices for bounded per-pair cost. Each per-LAD intersection runs in an isolated `DO ... EXCEPTION WHEN OTHERS` block so coastal/topology pathologies don't abort the loop.

---

## The driver (production path)

```powershell
cd "C:\Users\po.nienchen\OneDrive - priorpartners.com\Documents\05_Code_Scripts\Working_Scripts\Natural_England"

# Steps 1, 3-13. STOPS at Step 13 (no deliverable write).
python scripts\split_layer_by_lad.py --layer <layer_name>

# Full pipeline + deliverable in uk_baseline:
python scripts\split_layer_by_lad.py --layer <layer_name> --with-deliverable

# Skip Step 1 entirely (for sources > 200k rows; saves hours on 1.8):
python scripts\split_layer_by_lad.py --layer <layer_name> --no-diagnostic --with-deliverable

# Skip only the expensive 1.8 boundary scan (keep cheap 1.1-1.3, 1.10):
python scripts\split_layer_by_lad.py --layer <layer_name> --skip-1-8

# Only Block 14A (against existing dissolved staging):
python scripts\split_layer_by_lad.py --layer <layer_name> --with-deliverable --deliverable-only

# Drop staging (keeps _exp03 + _exp03_dissolved):
python scripts\split_layer_by_lad.py --layer <layer_name> --cleanup-only

# Drop staging AND _exp03 + _exp03_dissolved (after deliverable verified):
python scripts\split_layer_by_lad.py --layer <layer_name> --cleanup-only --cleanup-finals

# Standalone audit -- runs the multipart-misassignment diagnostic against
# one or more uk_baseline deliverables (auto-switches to sampled mode for
# tables > 50k rows; full-table audit otherwise). Decoupled from the
# pipeline so you can audit historical deliverables on demand:
python scripts\audit_deliverable.py <table_name>            # single deliverable
python scripts\audit_deliverable.py --cohort                # all 11 cohort deliverables
```

The driver does NOT issue any session `SET` commands — DB session config (`work_mem`, `maintenance_work_mem`, `temp_buffers`, `max_parallel_workers_per_gather`) is used as-is. The DBA has tuned the server config; don't override it in scripts.

---

## Per-layer config (`scripts/configs/<layer>.py`)

```python
CONFIG = {
    "source_schema":  "uk_baseline",
    "source_table":   "env_<theme>_<source>_<dataset>_<date>",
    "staging_schema": "uk",
    "staging_prefix": "env_ne_<abbrev>_<date>",        # ≤ 32 chars (63-char limit)
    "deliverable_schema": "uk_baseline",
    "deliverable_table":  "<full_source_name>_lad",    # full name + _lad
    "lad25cd_idx_suffix": "_lad25cd_idx",              # or _lcd_idx / _idx if name too long
    "geom_gix_suffix":    "_geom_gix",                 # or _gix if name too long
    "subdivide_cap":   32,                             # 32 if max_vx > 50,000 either side; 64 otherwise
    "heavy_poly_bypass": False,                        # True only for > 100k rows
    "smoke_lads": ["E08000019", "E06000023"],          # two LAD codes for Block 10B
}
```

### Identifier limits (63-char PostgreSQL limit)

The longest derived staging identifier is `<prefix>_exp03_needs_split_sub_geom_gix` (31-char suffix). The longest deliverable index is `<deliverable>_lad25cd_idx` (12-char suffix). If either overflows 63 chars, shorten the suffix — `_geom_gix → _gix`, `_lad25cd_idx → _lcd_idx → _idx`. The driver validates this at startup.

### When to enable `heavy_poly_bypass`

The bypass (`WHERE ST_NPoints(a.geom) <= 1000` in Step 5) was calibrated for million-row sources where Step 5 would otherwise run for hours. It is **not** a "always-on" optimisation — for small layers it needlessly pushes wholly-inside heavy polygons into slow path.

| Source scale | Heavy_count signal | Action |
|---|---|---|
| **> ~100 k rows** AND heavy_count > ~5 000 polygons (~5 % of source) | both met | **enable bypass** |
| **< ~10 k rows** | irrelevant | leave OFF (Step 5 runs in seconds either way) |
| **10 k – 100 k rows** | use Step 1.7 sample timing | judgement call — estimate Step 5 wall-clock first |

Counter-example: AONB has `heavy_count = 33 / 34` (97 %), but only 34 rows total. Step 5 takes ~1 s regardless. Enabling the bypass here would only push 2 wholly-inside polygons (max_vx 24 k, both > 1000 vx) into the slow path needlessly.

**Default for the NE small-layer tier** (AONB / LNR / SPA / ALC / SSSI): `heavy_poly_bypass: False`. Reconsider only for ancient_woodland / priority_habitats which may be large enough to qualify.

---

## Recipe (12-step pipeline)

The driver runs Steps 3–14 automatically. Step 1 is the diagnostic (read-only, captured for the record). Step 2 (cleanup of prior `_exp03_*`) is skipped on a fresh run.

### Step 1 — Diagnostic (read-only)
Captures `row_count`, vertex percentiles, validity, LAD stats, Filter B timing, `wholly_inside_pct`, index health.

**Cost note.** Section 1.8 (`wholly_inside_pct` on the FULL table) runs a boundary-line `ST_Intersects` count on every row. Time scales linearly: ~12 min on 53k rows; ~1 hr on 250k; multiple hours on 1M+. For sources > ~200k rows, pass `--skip-1-8` to skip just 1.8 and keep the cheap sections (1.1–1.3, 1.10); the production fast-path in Step 5 produces an equivalent `fast_path_pct_of_all` metric. For sources > ~1M rows, use `--no-diagnostic` to skip Step 1 entirely.

### Step 3 — Materialise clean 2D source + `ST_PointOnSurface`
Single `ST_MakeValid + ST_Force2D + ST_CollectionExtract(_, 3) + ST_Multi` pass into `uk.<prefix>_exp03_valid`. Adds `pos geometry(Point, 27700)` column.

**Step 3 auto-detects the PK column** from a priority list: `fid → gid → objectid → ogc_fid → id`. NE imports use `gid`; DEFRA imports use `fid`. The first match wins and is renamed `fid_original`.

### Step 4 — Build LAD edge lines
`ST_Boundary(geom)` over `uk.adm_ons_lad_boundary_may2025`, dumped to LineString.

### Step 5 — Fast-path assignment **(includes critical envelope-contains check)**

```sql
CREATE TABLE uk.<prefix>_exp03_fast AS
SELECT a.*, b.lad25cd, b.lad25nm
FROM uk.<prefix>_exp03_valid a
JOIN uk.adm_ons_lad_boundary_may2025 b
  ON a.pos && b.geom
 AND ST_Contains(b.geom, a.pos)
 AND ST_Contains(b.geom, ST_Envelope(a.geom))   -- multipart safety
WHERE NOT EXISTS (
    SELECT 1 FROM uk.<prefix>_exp03_lad_edges e
    WHERE a.geom && e.geom AND ST_Intersects(a.geom, e.geom)
);
```

**The `ST_Contains(b.geom, ST_Envelope(a.geom))` clause is mandatory.** Without it, MultiPolygon rows with parts in different LADs (with no individual part touching a LAD boundary) slip past the edge filter and get the lad25cd of whichever single part contains the `pos`. The other parts then carry the wrong attribute. Discovered 2026-05-08 on ALC; affected 165 ALC + 84 SPA + 243 SSSI polygons in the original cohort run.

### Step 6 — Anti-join into `_needs_split`
Btree anti-join on `fid_original` (NOT a spatial EXISTS — that's the same cost as Step 5). Saves hours on large layers; strictly more correct (catches fast-path orphans).

### Step 7 — `ST_Subdivide` crossers, cap 32
Default cap 32 keeps per-pair ST_Intersection bounded. Relax to 64 only if `max_vertices < 50,000` on both source and LAD.

### Step 8 — `ST_Subdivide` LAD layer, cap 32
One-time per cap; produces ~575k LAD pieces. Could be cached as `uk.adm_ons_lad_boundary_may2025_sub32` to skip this step on subsequent layers (see `Working_Scripts/Natural_England/scripts/build_lad_sub_cache.sql`).

### Step 9 — Empty `_split` staging

### Step 10 — Per-LAD `\gexec` loop (or Python driver equivalent)

Each per-LAD INSERT runs inside `DO $b$ ... EXCEPTION WHEN OTHERS THEN RAISE WARNING ...; END $b$;`. The driver translates this into a Python `for lad in lads: cur.execute(do_block)` loop under autocommit so each DO block is its own transaction (matching `\gexec` per-statement commit semantics). Coastal LADs (Southend, Hull, Liverpool, Falmouth) trip GEOS topology occasionally — the EXCEPTION handler isolates per-LAD failure.

`ST_ClipByBox2D` outputs are wrapped in `ST_MakeValid` before `ST_Intersection`:

```sql
ST_Intersection(
    ST_MakeValid(ST_ClipByBox2D(a.geom, ST_Envelope(lad.geom))),
    ST_MakeValid(ST_ClipByBox2D(lad.geom, ST_Envelope(a.geom)))
)
```

### Step 11 — `UNION ALL` final
Fast + slow into `uk.<prefix>_exp03` with `area_ha`, `fid bigserial`, GIST, btree on lad25cd.

### Step 12 — QA (8 checks)
- 12a stage row counts
- 12b `fast + needs_split = valid` (partition completeness)
- 12c area balance `diff_pct` (< 0.01 % target; up to ±1 % tolerated for coastal/marine; > 1 % warns but doesn't abort)
- 12d final geometry validity
- 12e missing slow-path features
- 12f LADs intersecting source but missing from output
- 12g per-LAD distribution
- **12h (added 2026-05-08) — multipart-misassignment auto-diagnostic.** Counts rows whose geometry has area outside its assigned LAD greater than the threshold `max(100 m², 1 % of row area)`. Threshold avoids false positives from coastal slow-path clip rounding. If `multipart_suspicious_rows > 0` the driver logs a WARNING but does not abort.

  **If 12h fires, the operator should:**
  1. Check the row count — single digits suggest residual edge cases; double digits or more suggest a recipe regression.
  2. Verify the Step 5 fast-path includes `AND ST_Contains(b.geom, ST_Envelope(a.geom))` in its JOIN. If absent → the multipart fast-path misassignment bug is present (see Method_explained.md §7.7); patch + re-run.
  3. If Step 5 is correct, the suspicious rows are likely slow-path clip-rounding on coastal polygons. Spot-check a few in QGIS to confirm the area-outside is microscopic; if so, accept.

### Step 13 — Dissolve
`GROUP BY fid_original, lad25cd, <all source attrs>` then `ST_Multi(ST_Union(geom))`. Collapses subdivide cuts back to one row per `(source polygon × LAD)`. Total area preserved exactly.

### Step 14A — Deliverable copy
Bulk `CREATE TABLE uk_baseline.<full_source>_lad AS SELECT * FROM uk.<prefix>_exp03_dissolved;` then drop+re-add `fid` bigserial PK, GIST, btree, ANALYZE.

### Step 14B — Staging cleanup (opt-in)
Drops the 7 staging tables. `--cleanup-finals` also drops `_exp03 + _exp03_dissolved`.

---

## Marine-clipping expected behaviour

Designations with marine / foreshore / offshore extent (NE: AONB, LNR, SPA, SSSI; DEFRA: flood zones; OS: tidal layers) will lose that area in the deliverable — the LAD layer is England land-area only. This is **correct** for a land-use deliverable, not a defect, but produces `diff_pct` warnings:

| Layer family | Expected diff_pct |
|---|---:|
| Inland-only (ALC, PHI, Ancient Woodland) | < 0.01 % |
| Coastal-fringe (AONB, LNR, SSSI) | -1 % to -10 % |
| Marine-heavy (SPA with offshore seabird designations) | up to -70 % |

Confirm marine cause with the top-N area-loss diagnostic before treating a high diff_pct as a defect. See `SQL/Split/HANDOVER.md` §6.

---

## Things to confirm with the user before starting

- Target source table (fully-qualified).
- Whether the deliverable should overwrite an existing `<full_source>_lad` (the driver refuses by default; explicit DROP required).
- Boundary vintage — `lad25*` from `uk.adm_ons_lad_boundary_may2025`, `wd21*` from `adm_bndry_ons_ward_boundaries_2022`. Note `uk.*` schema, not `uk_baseline.*` for new layers (DEFRA cohort used `uk_baseline.*` because the LAD table was moved on 2026-05-08).

---

## See also

- Operator workflow: `SQL/Split/USER_GUIDE.md`.
- Handbook: `SQL/Split/Method_explained.md`.
- Cohort handover: `SQL/Split/HANDOVER.md`.
- Technique catalogue: `SQL/Split/techniques.md`.
- Driver: `Working_Scripts/Natural_England/scripts/split_layer_by_lad.py`.
- Folder conventions: `SQL/Split/CLAUDE.md` (or `AGENTS.md`).
- Production functions to beat (smaller scale): `SQL/Working_Scripts/Function_split_layer_by_lad.sql`.
