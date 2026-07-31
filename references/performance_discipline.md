# Performance discipline — do the cost analysis BEFORE running

> Relocated verbatim from ~/.claude/CLAUDE.md on 4 July 2026 (backup:
> ~/.claude/backup_20260704/CLAUDE.md). READ BEFORE any heavy spatial
> operation: >100k geometries, two non-trivial geometry sets combined,
> or anything estimated over 5 minutes. SQL-side patterns and the
> chunking recipes with code: ~/.claude/rules/sql.md § "Heavy geometry
> operations".

The user pays in wall-clock for every heavy operation you launch. Do
not run a heavy query and "see how it goes". Do not translate user SQL
literally if a cheaper equivalent exists. Be brutally honest about cost
up-front.

## The brutal-upfront rule

When the user describes a heavy spatial workflow, your first response
is not "let me run that" — it is *"here is what this will cost naively;
here is the cheaper correct alternative I will use instead; here is why
it is mathematically equivalent."* If the user disagrees they will say
so. This rule overrides politeness, momentum, or the literal phrasing
of the user's SQL. The 1-hour wait that ends in failure is your fault,
not the user's.

## Default to chunked execution

For any non-trivial spatial workflow, the default execution shape is
**chunked**, not single-shot. Chunking earns you:

- **Bounded per-chunk cost** — predictable wall-clock per unit
- **Parallelism for free** — chunks run independently (xargs -P,
  multiple psycopg connections, Postgres parallel workers)
- **Cheap recovery** — if chunk N fails you re-run N, not the whole job
- **Better memory + cache behaviour** — small working sets fit in RAM
- **Visible progress** — you see N of M done, not "still active after
  47 min"

Single-shot is acceptable only when chunk overhead genuinely dominates
the work itself — small inputs where per-chunk setup exceeds the saved
compute.

## How to chunk — pick a partition key (in priority order)

1. **Natural admin partition.** `lad25cd`, `wd25cd`, `rgn22cd`, country
   code, postcode area. Use if both inputs already carry it.
   Mathematically identical to the global operation when inputs are
   pre-clipped to the key.
2. **Manufactured spatial grid.** PostGIS `ST_SquareGrid` /
   `ST_HexagonGrid`, OS National Grid letters, S2 cells (level 8–12 for
   UK), geohash (4–7 chars). The grid is a join key. Aim for ~1k–100k
   rows per cell.
3. **Bin by row id or hash.** `fid % N` or `hashtext(col) % N` — for
   attribute-only batch transforms.
4. **Time-based.** Month / year / day windows for temporal data.

## The diagnostic checklist (write the answers down before running)

1. **Order-of-magnitude wall-clock?** From row counts × vertex counts ×
   the operator's algorithmic class. If you cannot estimate within an
   order of magnitude, you do not understand the operation well enough
   to run it.
2. **Can this be chunked?** If yes, propose the chunked plan; do not
   propose the single-shot version.
3. **Is the chunked result mathematically identical** (or acceptably
   close — edge effects on chunk boundaries)? State the equivalence
   argument explicitly.
4. **Fresh-build vs in-place mutation?** Prefer `CREATE TABLE AS` +
   `INSERT ... SELECT` over `ALTER TABLE` + repeated `UPDATE`s —
   avoids MVCC bloat, table rewrites, index invalidation, VACUUM FULL.
5. **Return-type cast safety?** `ST_Difference` / `ST_Intersection` /
   `ST_Union` can return `GeometryCollection` on coincident edges. Wrap:
   `ST_Multi(ST_CollectionExtract(ST_MakeValid(<expr>), 3))::geometry(MultiPolygon, 27700)`
   or the cast fails AFTER the whole computation has finished.
6. **Resumability?** Long jobs need `--resume-from` so a failure in
   step N doesn't lose steps 1..N-1.

## Heuristic — the big-vs-many-small pattern

Spatial operators are super-linear in the *larger* operand's vertex
count. One big geometry (multi-million-vertex union) paired with many
small ones ⇒ per-row cost dominated by the big side, terrible cache
behaviour. Chunk the big side to match the small side's grouping.
Applies to: spatial joins, difference/intersection/union,
distance-to-feature, point-in-polygon over millions, buffer-and-overlay,
isochrone catchments, zonal statistics, mosaic, rasterise/vectorise.

## Anti-pattern (measured on this user's own data)

A global `ST_Union(40k national polygons)` inside a difference workflow
was abandoned at **74 minutes**; the per-LAD `GROUP BY lad25cd` rewrite
completed in **19 minutes**. The chunked solution should have been the
FIRST plan, not the recovery plan. (Designations.sql AWR-difference,
May 2026.)
