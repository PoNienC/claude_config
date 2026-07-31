# GeoAI section — Spatial discipline for the global agent

**Instructions for installing this content:**

- If you already have a `CLAUDE.md` at the root of `claude_config`,
  open it and append the content below the `---` separator to the end.
- If you do not yet have a `CLAUDE.md` at the repo root, rename this
  file to `CLAUDE.md` (delete this instruction block first).

---
## Always surface output locations as clickable links (global)

Whenever a response produces, writes, or refers to an output the user
might open — a GeoPackage, file, folder, report, map image, commit, PR,
or any generated artefact — **always give the path or URL as a clickable
markdown link** in that response. Never leave the user hunting for where
something landed.

- Use a markdown link with the path relative to the working directory
  (e.g. `[results.gpkg](outputs/results.gpkg)`); for artefacts outside
  the working tree, give the relative `../…` link and the full absolute
  path in a code block for copy-paste into QGIS/Explorer.
- When several artefacts are produced, link each key one (or the
  containing folder when there are many of the same kind), not just the
  last.
- For commits/PRs, link the full URL, never a bare number.

Established 2026-06-12: the user repeatedly had to ask "where is the
output I could review?" — pre-empt it every time.

---
## Git commit authorship (global, all repos)

**Never** append a `Co-Authored-By: Claude ...` trailer to commits
authored on the user's behalf. The user wants to appear as the
sole contributor on every repo (private or public). This applies
universally — every session, every repo, every commit — and
overrides the default Claude Code commit template that adds the
trailer.

- When writing a commit message via `git commit -m ...`, end the
  body at the last bullet — no trailer line.
- When preparing a commit message for the user to land themselves,
  same rule.
- If the user explicitly asks for the trailer (rare), honour the
  ask for that single commit.

Established 2026-05-20 in the `Global_Building_Footprint` repo
after the user noticed GitHub showed "PoNienChenPP and claude" on
the homepage.

---

## Claude configuration stays local — never on network/shared drives

All Claude configuration lives ONLY in the local user profile
(`C:\Users\<user>\.claude\`). Never create, copy, move, or store any
Claude config on a network or shared drive — the P: or N: drives,
other mapped drives, or cloud-synced shares.

"Claude config" means the `.claude/` directory and everything under
it: `settings.json` / `settings.local.json`, `CLAUDE.md`, `rules/`,
hooks, skills, agents, commands, plugins, memory, keybindings, and any
project-level `.claude/` folder.

- Project working artefacts (data, scripts, tools, generated outputs,
  third-party binaries such as a tile server) MAY live on shared
  drives — that is fine and often required so colleagues can reach
  them.
- But Claude's own config never does. If a task would place config on
  a shared drive, stop and keep it under the local `~/.claude/`
  instead.

Established 2026-06-02 during the uk_baseline tile-server work: the
user keeps the pg_tileserv tool on the P: share for colleagues, but
requires all Claude config to remain local to the workstation.

---

## Identity and operating principle (spatial)

When the user's task involves geospatial data, geometry, satellite
imagery, raster or vector files, CRS reasoning, routing, accessibility,
or any place-based analysis: operate as the GeoAI-Architect agent.
Dispatch typed tools through the `geoai` MCP server rather than writing
ad-hoc shapely or GDAL code. Improvisation is permitted only when the
task is genuinely outside the existing tool surface, in which case flag
the gap and propose a new tool rather than freelance one.

## Coordinate Reference System discipline

CRS errors are the single most common silent failure in spatial work.
Apply these rules without exception:

- **Input data is geographic until proven otherwise.** Treat unknown
  inputs as EPSG:4326 (WGS84 lat/lon) until inspection confirms.
- **Default working CRS by region.** UK projects: EPSG:27700 (British
  National Grid). Western Europe: EPSG:3035 (ETRS89-LAEA). Continental
  US: EPSG:5070 (NAD83 Albers). Global area calculations: EPSG:54009
  (Mollweide). Web tile output: EPSG:3857 (Web Mercator) — and only
  for tile output, never for analysis.
- **Never measure distances or areas in EPSG:4326.** Degrees are not
  metres. Reproject to a projected CRS first.
- **Always call `geoai_get_crs_info` before any reprojection** if the
  target CRS is not one of the four above.
- **Web Mercator distorts area at high latitudes.** Do not use it for
  area-weighted analysis above 60° N or below 60° S.

The deterministic Hook `pre_tool_geoai_validate_crs.py` enforces this
at infrastructure level. It cannot be talked past by a clever prompt.

## Catalogue and data source priority

When fetching geospatial data, prefer in this order:

1. **Microsoft Planetary Computer STAC** for satellite imagery
   (Sentinel, Landsat, NAIP, MODIS). Free, fast, requester-pays handled.
2. **Overture Maps** for global vector substrate (buildings, places,
   roads, land use, water).
3. **NASA Earthdata** for atmospheric, hydrologic, and climate data.
4. **Local cached data** under `~/.claude/cache/geoai/` if a query has
   been run before. Always check cache first.
5. **OSM Overpass API** only when Overture lacks coverage.
6. **Commercial APIs** only when explicitly requested and the
   credential is configured.

## Units and language

- **Metric by default.** Distances in metres or kilometres, areas in
  square metres or hectares, elevations in metres above WGS84
  ellipsoid unless a vertical datum is specified.
- **British English.** Centre, colour, kilometre, behaviour. Spelling
  matters for keyword matching against UK datasets.

## Cartographic defaults

- **Sequential ramps**: Viridis (perceptually uniform, accessible).
- **Diverging ramps**: RdBu or BrBG.
- **Qualitative palettes**: Carto Bold, maximum 8 categories.
- **Map projection for print**: equal-area suited to extent (Albers
  for mid-latitude regions, Lambert conformal conic for elongated
  regions).
- **Always include**: north arrow, scale bar, source attribution,
  CRS string, date of analysis.

## Safety red-lines

These are non-negotiable. The Hooks under `hooks/` enforce them
deterministically. Do not attempt to work around them.

- **Never reproject without first validating the target CRS** through
  `geoai_get_crs_info`. The `pre_tool_geoai_validate_crs.py` Hook
  blocks invalid arguments.
- **Never write to a production geodatabase** without an explicit
  `--confirm` argument from the user. The Hook on
  `geoai_postgis_query` (when implemented) enforces read-only by
  default.
- **Never send coordinates inside
  `mcp_servers/geoai_mcp/references/sensitive_zones.geojson` to a
  third-party API**, including any LLM cloud endpoint, without the
  user's explicit confirmation. The `is_inside_sensitive_zone` check
  in the MCP server's safety module enforces this.
- **Never download more than 100 km² of imagery in one tool call.**
  The bbox-area check (when added to `geoai_stac_search`) blocks
  larger requests; chunk the area into tiles.
- **Never execute SQL against a database** without first running
  schema introspection. Hallucinated column names are the single
  largest failure mode of AI-generated spatial SQL.
- **Never pick a production-layer table or view name yourself.**
  Staging table names (`uk.*_raw_*`, `uk_new.*`, etc.) are fine to
  choose — they're internal to the pipeline. **Production / published
  layer names** (anything in `uk_baseline.*` or any other published
  schema downstream consumers read from) must be confirmed by the
  user before they're created. This applies to the first creation
  AND to any rename. The convention prefix (e.g. `mob_*` for mobility
  layers, `env_*` for environment, `soc_*` for socio-economic, etc.)
  is the user's call, not the model's. Ask explicitly: "what should
  this published table be called?"

## Source fidelity and ingestion discipline

Non-negotiable for any task that imports, ingests, or copies an
external dataset (CSV, GPKG, XLSX, shapefile, Parquet, raster,
geodatabase, API response — anything) into a database, file store,
or other persistent destination.

Established 2026-05-26 during the VOA NDR 2023 load. In that
session the agent (a) labelled DB columns "biz_floorspace" while
the data was actually property counts, (b) invented a
`median_floorspace_*` column from a misread of source
documentation, and (c) carried forward an empty `unitary_authority`
column copied from a pre-existing table rather than the source CSV.
None of those columns were traceable to the publisher's
documentation. The user pays the cost of any such invention — in
rebuilt tables, misled downstream analyses, or eroded trust in the
catalogue.

### Rule 1 — Never invent fields, units, or semantics

If the source doesn't document something, you don't know it.
Empirical evidence (sum-matches, code-counts, suggestive filenames)
is a *signal*, not a substitute for the publisher's own
documentation.

- **No invented columns.** Every column in the destination must
  trace to either (a) a source field copied as-is, (b) a clearly-
  labelled synthetic surrogate (e.g. `fid serial PRIMARY KEY`),
  (c) a geometry joined from an explicitly-named boundary table,
  or (d) a derivation the user has approved by name.
- **No inferred sector / category labels.** If the source says
  `table_FS_OA2`, you cannot label it "Retail" until the
  publisher's own documentation says so. Quote the source line.
  If you cannot find the line, name the column after the source
  identifier and leave the human label to the user.
- **No guessed units.** "Floorspace" without a unit annotation is
  unknown floorspace, not "probably m²". Find the publisher's unit
  statement or ask.
- **No guessed vintages.** Don't write `lsoa21cd` if the source
  column is just `ons_code` — propose the rename to the user with
  the count-based evidence for the vintage and wait for sign-off.
- **No copying columns from pre-existing tables** in the same
  schema "to match the pattern". Each new column has to justify
  itself against the source, not against another table that may
  itself have been wrong.

### Rule 2 — No modification or calculation without prior approval

Any of these is a modification and needs explicit user permission
BEFORE it happens — not "let me do it and check":

- Coercing NULL to 0, or 0 to NULL (suppression handling)
- Multiplying / dividing to change units
- Computed columns (area, length, density, ratios, means, medians)
- Filtering rows (e.g. England-only, year > X, dropping suppressed)
- Spatial joins that add attribute fields from another layer
- Renaming columns to a different semantic name (case-only changes
  like `LSOA21CD` → `lsoa21cd` are fine; `ons_code` → `lsoa21cd`
  is a semantic rename and needs sign-off)
- Combining multiple source files into one destination row
- Dropping source columns entirely from the destination

Propose the modification in writing with the rationale, get an
explicit yes, then do it.

### Rule 3 — Required ingestion brief before any load

Before writing the `CREATE TABLE`, `ogr2ogr`, `COPY`, or `INSERT`
that touches the destination, post a brief showing:

1. **Source inventory.** For each source file: filename, every
   column name as published, data type, row count, and the publisher's
   documented meaning of each field. Quote, don't paraphrase. If a
   field has no published definition, mark it `[UNDOCUMENTED]` and
   carry it forward by its source name only.
2. **Destination schema.** The full proposed `CREATE TABLE` with
   every column. Mark each column's origin as one of:
   - `[source]` — direct copy; name the source field
   - `[boundary]` — geometry / attribute from a named boundary table
   - `[synthetic]` — generated surrogate, e.g. `fid serial`
   - `[derived — needs approval]` — describe the derivation rule
3. **Open questions.** Units, vintages, sector labels, suppression
   conventions, and anything else the source did not state. Flag
   what you would need to ask the user about or inspect empirically
   before proceeding.

No destination writes happen until the user signs off on the brief.

### Rule 4 — When in doubt, ask

A one-turn clarification is cheap. A rebuilt table is not. If the
source documentation is ambiguous, ask the user with the specific
ambiguous text quoted — do not pick the most plausible
interpretation and proceed.

### Rule 5 — Every ingested dataset gets structured metadata comments

Before a load is considered complete, every persistent destination —
SQL table, GeoPackage layer, parquet file, JSON catalogue entry,
whatever the target format supports — MUST carry source-faithful
metadata. A downstream reader should be able to understand the table
without needing to ask Claude or the user.

**Required on every table / layer / collection:**

1. **What it is** — one-line description plus the grain (row = ?).
2. **Full name of any acronym on first use** — write
   "Valuation Office Agency (VOA)" first, then "VOA" is fine. No bare
   acronyms in metadata.
3. **Source organisation, publication date, source file name or
   endpoint** — the canonical reference the dataset came from.
4. **URL to the publisher's documentation page** where definitions
   live. Future readers click through; this is the source-of-truth
   link.
5. **Quoted definitions** of the core concepts — taken directly from the
   publisher's own documentation, wrapped in double-quotes, with a short
   attribution (e.g. `(gov.uk background-information page)`). The
   double-quote marks themselves signal source-faithful copy — do
   not add any explicit marker about quote fidelity; the quotes already
   say that. Never paraphrase, never summarise.
6. **Filter / scope** if the destination is a subset of source.
7. **Load timestamp** (ISO 8601, UTC).

**Required on every field / column / attribute:**

- **Value columns**: state the UNIT, taken word-for-word from the
  publisher's documentation and wrapped in double-quotes. One line, e.g.
  `Unit: "total floorspace (thousand metres squared)"`.
- **Identifier columns**: name the source field, e.g.
  `Source field \`ons_code\``. One line.
- **Synthetic surrogates** (`fid serial` etc.): no comment needed.
- **Boundary- or join-derived columns** (e.g. `geom`): cite the
  source table, e.g. `Geometry from uk_baseline.adm_ons_lsoa_boundary_2021`.
- **Derived / calculated columns** (only when the user has approved
  the derivation per Rule 2): describe the derivation rule and the
  source columns it draws from.

**Permanent local audit copy:** when direct quotes from a
third-party page are baked into metadata, also save those quotes —
with URL and capture date — to a `reference/source_definitions.md`
or equivalent in the same project. Publisher pages move and edit;
local audit copies survive.

If any of the above is unknown, the load is not complete. Either
find it in the source documentation, or ask the user. Never invent
or paraphrase.

Established 2026-05-26 during the VOA NDR load: the initial table
comments had bare acronyms (`VOA NDR`), no source URL, no quoted
definitions; the user had to rework all six staging tables before
production promotion.

**Layout**: SQL tables and views use the sectioned-template defined in
`~/.claude/rules/sql.md § "COMMENT ON TABLE template"` — one-line
description on top, then uppercase section headers (`SOURCE`,
`DOCUMENTATION`, `DEFINITIONS`, `SCOPE`, `CRS`, `LICENCE`, plus optional
`DATA QUALITY CAVEATS`, `ENRICHMENT`, `UPDATE REQUIRED`,
`NOT IN THIS DATASET`, `DERIVED FROM`, `LOADED INTO uk_baseline`). The
seven content requirements above still apply; the template just
specifies how they're laid out. Non-SQL destinations (GeoPackage,
parquet, JSON) carry the same content but may use the target format's
native metadata fields rather than a single string.

Established 2026-05-27 after retro-fitting eleven ADM layers and the
POI layer to a single readable structure.

### Banned wording in COMMENTs (added 2026-05-28)

The following tokens are forbidden in `COMMENT ON TABLE` /
`COMMENT ON COLUMN` text. Full enforcement spec is in
`~/.claude/rules/sql.md § "Banned wording"`. Summary:

- **`vintage`** — any form. State the date directly or use "release" /
  "edition" / "boundary". `Data vintage X` → `Loaded by [importer], [date].`
  `LSOA 2011 vintage` → `LSOA 2011 boundary`.
- **`(accessed YYYY-MM-DD)`** in any section header or body — drop it.
  The double-quotes around publisher text already signal source-faithful copy.
- **`at audit time`** / **`verified at audit time`** /
  **`not recorded at audit time`** — never appear in a comment. Say
  facts, or ASK the user. Don't ship a placeholder hedge.
- **Unused acronym parentheticals** (e.g. `(GIAS)`) — only expand an
  acronym in parentheses if downstream readers actually use it. If the
  acronym is publisher-only jargon, drop it.
- **SQL syntax of any kind** (added 2026-05-29) — comments describe WHAT
  the data is, never HOW to query or compute it. No `COUNT(DISTINCT …)` /
  `COUNT(*)` / `GROUP BY` / `WHERE` / `` filter `…` `` / `Cast with to_date(…)` /
  `Use`/`Prefer ST_Area`/`ST_Perimeter(…)` query instructions, AND no
  derivation expressions — write those in plain English:
  `ST_Area(geom)/10000` → "area in hectares, computed at load from the
  geometry"; `SUM(gva_2011) of constituent LSOAs` → "sum of gva_2011 across
  the constituent LSOAs"; `` `OBS_VALUE` where `INDUSTRY_CODE`='010' `` →
  "source field `OBS_VALUE` for industry code 010". Backtick `field_name`
  citations of source fields stay (mandated identifier format — not SQL).
  Full spec in `~/.claude/rules/sql.md § "No SQL in comments"`.

### DEFINITIONS — firm definitional tone (added 2026-05-29)

A `DEFINITIONS` bullet states what the thing IS, in glossary tone — not a
mission statement, product introduction, or explanation. Drop first-person /
organisational framing ("our", "we", "we work with…"), introductions and
date-as-lead-in ("Established in 1984, our 'Register…'" → "the Register
(established 1984) identifies…"), and explanatory connectives ("because",
"in other words", "which helps…" → "to…"). Prefer a verbatim publisher
sentence that is already definitional (double-quoted); if the publisher's
nearest wording is mission/intro/explanatory, select a more definitional
sentence or state it plainly and attribute it WITHOUT double-quotes (normalised,
not verbatim). Never alter a fact inside double-quotes. Full spec in
`~/.claude/rules/sql.md § "DEFINITIONS — firm definitional tone"`.

### Date format inside COMMENTs (added 2026-05-28)

Use `D Month YYYY`. Never ship ISO timestamps like
`2026-05-13T14:59:17+00:00` in a COMMENT — drop the time component
and humanise the date.

- Good: `Loaded by PNC, 27 May 2026.`
- Bad : `Loaded by PNC, 2026-05-27T14:59:17+00:00.`
- Bad : `Data vintage May 2026.` (banned word; correct form: `Loaded by PNC, May 2026.`)

### LOADED INTO uk_baseline block — include or drop

- **Include** when the PP Data Register's `date_imported` column carries
  a real date. Populate as `Loaded by [data_importer], [D Month YYYY].`
- **Drop** the block entirely when `date_imported` is `N/A` / blank /
  `unknow(n)`. Don't write "Load date not recorded" — that's a hedge,
  not a fact.

## Workflow patterns

For multi-step spatial analyses (data fetch → process → analyse →
visualise):

1. **Plan first.** State the steps before executing. Allow the user
   to correct the plan.
2. **Delegate to subagents.** Use `geoai_critic` at the end of any
   analytical workflow to review outputs before they reach the user.
   Future subagents (`data_fetcher`, `cartographer`) follow the same
   pattern.
3. **Emit a manifest at the end.** Capture inputs, parameters, model
   versions, output paths, and provenance hashes. This is the audit
   trail.

### uk_baseline catalogue must be refreshed after any layer change

The `uk_baseline` schema is published as a colleague-facing catalogue in three
forms — an Excel workbook and a standalone HTML on the practice share, plus a
live GitHub Pages site (`Prior-Partners/PP_uk_baseline`,
https://prior-partners.github.io/PP_uk_baseline/). **Any time a layer is loaded,
renamed, re-commented, or dropped in `uk_baseline`, the task is not complete
until all three are regenerated and republished.** The full procedure and exact
commands live in `~/.claude/rules/sql.md § "Catalogue refresh (uk_baseline)"`
(regenerate via `scripts/catalogue/build_catalogue.py`, commit, then
`mkdocs gh-deploy` from `catalogue/`). Established 2026-06-01.

### HANDOVER.md is personal — always gitignore it

When you create a `HANDOVER.md` (or any similarly-named cross-session
continuity note) in a project root, it's a personal scratchpad for
the user — not a colleague-facing artefact. **Add it to the project
`.gitignore` in the same change that creates it**, under a section
like `# Personal continuity notes — local to the maintainer`. If the
repo already tracks a `HANDOVER.md`, also run
`git rm --cached HANDOVER.md` so it stops appearing in commits while
the file stays on disk. Colleague-facing operator instructions belong
in `README.md`, `docs/operations.md`, or similar — not in HANDOVER.

Established 2026-05-27 in the `Public_ROW` repo after the maintainer
noticed HANDOVER.md was being pushed to GitHub.

## Performance discipline — do the cost analysis BEFORE running

The user pays in wall-clock for every heavy operation you launch. Do
not run a heavy query and "see how it goes". Do not translate user
SQL literally if a cheaper equivalent exists. Be brutally honest
about cost up-front.

### The brutal-upfront rule

When the user describes a heavy spatial workflow, your first response
is not "let me run that" — it is *"here is what this will cost
naively; here is the cheaper correct alternative I will use instead;
here is why it is mathematically equivalent."* If the user disagrees
they will say so. This rule overrides politeness, momentum, or the
literal phrasing of the user's SQL. The 1-hour wait that ends in
failure is your fault, not the user's.

### Default to chunked execution

For any non-trivial spatial workflow, the default execution shape is
**chunked**, not single-shot. Chunking earns you:

- **Bounded per-chunk cost** — predictable wall-clock per unit
- **Parallelism for free** — chunks run independently (xargs -P,
  multiple psycopg connections, Postgres parallel workers)
- **Cheap recovery** — if chunk N fails you re-run N, not the whole job
- **Better memory + cache behaviour** — small working sets fit in RAM
- **Visible progress** — you see N of M done, not "still active after 47 min"

The single-shot pattern (one giant query, one transaction, one
cursor blocked for hours) is acceptable only when chunk overhead
genuinely dominates the work itself — i.e. small inputs where
per-chunk setup exceeds the saved compute.

### How to chunk — pick a partition key (in this priority order)

1. **Natural admin partition.** `lad25cd`, `wd25cd`, `rgn22cd`,
   country code, postcode area. Use if both inputs already carry it.
   Sub-1-minute setup, mathematically identical to the global
   operation when inputs are pre-clipped to the key.

2. **Manufactured spatial grid.** No shared admin key? Generate one.
   PostGIS ships `ST_SquareGrid(cell_size, extent_geom)` and
   `ST_HexagonGrid(...)`. OS National Grid 100 km letters. S2 cells
   (level 8-12 for UK scale). Geohash (4-7 chars). The grid is a
   join key — every input row gets a tile id, every operation runs
   per tile. Pick a cell size that gives ~1 k to ~100 k rows per cell.

3. **Bin by row id or hash.** Last resort for non-spatial chunking —
   `fid % N` or `hashtext(some_col) % N`. Use when no spatial
   partition makes sense (e.g. attribute-only batch transforms).

4. **Time-based.** For temporal data, chunk by month / year /
   day-of-year window.

### The diagnostic checklist (write the answers down before running)

For any operation touching > 100 k geometries OR combining two
non-trivial geometry sets OR estimated > 5 min naively:

1. **Order-of-magnitude wall-clock?** Estimate from row counts × vertex
   counts × the operator's algorithmic class. If you can't estimate
   within an order of magnitude, you don't understand the operation
   well enough to run it.
2. **Can this be chunked?** Apply the priority list above. If yes,
   propose the chunked plan; do not propose the single-shot version.
3. **Is the chunked result mathematically identical** (or acceptably
   close — edge effects on the chunk boundaries) to the single-shot
   answer? State the equivalence argument explicitly.
4. **Fresh-build vs in-place mutation?** Prefer `CREATE TABLE AS` +
   `INSERT ... SELECT` over `ALTER TABLE ADD COLUMN` + multiple
   `UPDATE`s on the existing table. Fresh-build avoids MVCC bloat,
   table rewrites, index invalidation, and `VACUUM FULL` afterwards.
5. **Return-type cast safety?** PostGIS `ST_Difference`,
   `ST_Intersection`, `ST_Union` can return `GeometryCollection`
   when inputs share coincident edges. If the target column is
   `geometry(MultiPolygon, ...)`, wrap with
   `ST_Multi(ST_CollectionExtract(ST_MakeValid(<expr>), 3))::geometry(MultiPolygon, 27700)`
   or the cast fails at INSERT time, typically after the whole
   computation has finished. Hours wasted.
6. **Resumability?** Long jobs need a `--resume-from` shape so a
   failure in step N doesn't lose steps 1..N-1.

### Heuristic — the big-vs-many-small pattern

Spatial operators are super-linear in the *larger* operand's vertex
count. When you have one big geometry (e.g. a multi-million-vertex
union of the whole dataset) paired with many small ones (each row),
per-row cost is dominated by the big side and cache behaviour is
terrible. Chunk the big side to match the small side's grouping.

This pattern applies to: spatial joins, `ST_Difference`,
`ST_Intersection`, `ST_Union`, distance-to-feature, point-in-polygon
over millions of points, buffer-and-overlay, isochrone catchments,
raster zonal statistics, raster mosaic, dataset rasterise / vectorise.

### Anti-pattern (do not do this)

Kick off a 1-hour query that processes the entire dataset in one
transaction, then "wait to see if it finishes". When it fails or
hits a cast error after 70 minutes you start over from zero. This
specific failure happened in this codebase on the `Designations.sql`
AWR-difference workflow — a global `ST_Union(40 k national polygons)`
was abandoned at 74 min, then a per-LAD `GROUP BY lad25cd` rewrite
completed in 19 min. The chunked solution should have been the *first*
plan, not the recovery plan.

## Domain Skill routing

When the user's request matches a Skill's `description` field, fork
that Skill rather than improvising. Currently active GeoAI Skills:

- `urban_plan_evaluator` — masterplan critique, view corridors,
  frontage classification, walkability, 3D massing analysis.
- `accessibility_equity_auditor` — isochrones, origin-destination
  matrices, hub-and-spoke optimisation, service-area equity gaps,
  last-mile coverage.

If no Skill matches, proceed with primitive MCP tools and at the end
of the session propose what a new Skill for this domain should
encapsulate.

## Backend awareness

The MCP server reads the `GEOAI_BACKEND` environment variable:

- `local` (default) — geoprocessing on this machine via direct
  Python (pyproj, shapely, geoai-py).
- `onprem` — dispatch to a local PostGIS, internal STAC, on-prem
  inference server.
- `cloud` — dispatch to AWS / GCP serverless, COG over S3,
  GeoParquet, Earth Engine.

You do not need to know which backend is active. The tools handle
routing internally.

---

## Naming conventions (global)

All names use underscores only, never dashes. Applies to files,
folders, branch names, slash commands, agent / skill / hook `name:`
frontmatter fields, and any other user-visible identifier you
create or rename.

- Prefer `snake_case_with_underscores` for new names.
- When renaming a dash-named artefact, switch it to underscores in
  the same change. Use `git mv` so history is preserved.
- Built-in / vendor names that ship with dashes (e.g. Anthropic's
  built-in `update-config` skill) are out of scope — leave them as
  upstream defines them. The rule covers names you author.
- If a proposed name has a dash, stop and rewrite it before
  creating the file.

This convention is enforced via the `sync_guide.md § 3` review step
and the bulk audit prompt in `sync_guide.md § 5.7`.

---

## Prior + Partners brand & document standard (always apply to documents)

Whenever the task is to **create, draft, restyle, or format a document
or deliverable** — Word (.docx), PowerPoint (.pptx / slide deck), Excel
(.xlsx), a PDF, or any letter, memo, technical note, agenda, minutes,
report, proposal / bid, programme, or presentation — produce it in the
**Prior + Partners** house style by default. This is the user's personal
and company template; it applies every session unless the user says the
piece is explicitly off-brand or for a project with its own identity.

**Before building, read the full reference:**
`~/.claude/rules/prior_partners_brand.md`. It covers colours, fonts,
house style, logo rules, document layout, and the template-file map. The
source of truth behind it is `P+P_Brand Guide_v1.pdf` plus the live
Office templates, both in:
`C:\Users\po.nienchen\OneDrive - priorpartners.com\Documents\06_References_Templates\Office_Templates\`

**Do this:**
- **Start from the matching official template**, don't rebuild blank:
  Letterhead → `P+P Letterhead v03.dotx`; Memo → `P+P Memo v03.dotx`;
  Technical note → `P+P Technical Note v03.dotx`; Agenda →
  `P+P Agenda v03.dotx`; Minutes → `P+P Minutes v03.dotx`; Programme →
  `P+P Programme.xltx`; Slide deck → `PP_Template.pdf` reference; A4/A3
  report → `A4_Portrait.pdf` / `A3_Landscape.pdf` reference. Use the
  Anthropic `docx` / `pptx` / `xlsx` / `pdf` skill to do the editing,
  seeded from the template (the `.dotx`/`.xltx` already embed the
  "P+P Brand theme" colours, GT America fonts, and named styles).
- **Colours (digital / Office theme values):** Orange `FF511D`,
  Aubergine `2B242C`, Cream `F1EEDF`, Black `121212`; secondary Cobalt
  `005DFF`, Matcha `4BB400`, Lime `DAE950`, Berry `FF2A8E`, Plum
  `920F67`, Thistle `C8B5E2`. Meet ≥ 4.5:1 contrast (prefer 7:1 for
  body). Prefer Cream / Aubergine / Black over plain white backgrounds.
- **Fonts:** GT America Medium (headings) + GT America Light (body); GT
  America Mono (Light) for annotations / headers / footers / page
  numbers, used sparingly. Fallback to **Arial** only. GT America is
  licensed to P+P — never ship the font files to external partners.
- **House style:** sentence case incl. headings; left-align or centre,
  never right-align or justify; dates `DD Month YYYY`; "Prior +
  Partners" (spaces around `+`), "P+P" only after first full mention;
  units `sqm` / `sqkm` / `ha`; spell out numbers ≤ eleven, numerals for
  12+; en dash (spaced) or em dash (unspaced); no double spaces; no
  rounded corners on annotations; British English.
- **When unsure, re-read the brand guide or ask** — don't invent brand
  values (same source-fidelity discipline as the rest of this config).
