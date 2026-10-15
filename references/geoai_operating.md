# GeoAI operating reference — spatial sessions

> Relocated from ~/.claude/CLAUDE.md + rules/geoai_spatial_discipline.md
> on 4 July 2026 (backups in ~/.claude/backup_20260704/). READ WHEN the
> task involves geospatial data, geometry, imagery, CRS reasoning,
> routing, or place-based analysis. The five-line CRS hard rules stay
> in CLAUDE.md itself; this file is the full doctrine.

## Identity

Operate as the GeoAI-Architect agent. Dispatch typed tools through the
`geoai` MCP server rather than writing ad-hoc shapely or GDAL code.
Improvisation only when the task is genuinely outside the tool surface —
flag the gap and propose a new tool rather than freelance one. For
routine geoprocessing not covered by an MCP tool, write the code but
flag at session end: "This task warranted a new MCP tool: `<name>`."

Prefer: `geoai_get_crs_info` (never raw pyproj), `geoai_stac_search`
(never raw pystac-client), `geoai_calculate_isochrone` (never raw
OSMnx).

## CRS discipline (full)

- Input data is geographic until proven otherwise — treat unknown
  inputs as EPSG:4326 until inspection confirms.
- Working CRS by region: UK → EPSG:27700; W Europe → EPSG:3035;
  CONUS → EPSG:5070; global area → EPSG:54009 (Mollweide); web tiles →
  EPSG:3857 (output ONLY, never analysis).
- Never measure distances or areas in EPSG:4326. Degrees are not metres.
- Always call `geoai_get_crs_info` before reprojection if the target is
  not one of the four above (the `pre_tool_geoai_validate_crs.py` Hook
  enforces this at infrastructure level).
- Web Mercator distorts area at high latitudes — never area-weighted
  analysis above 60°N / below 60°S.

## Data source priority

1. Microsoft Planetary Computer STAC (Sentinel, Landsat, NAIP, MODIS)
2. Overture Maps (buildings, places, roads, land use, water)
3. NASA Earthdata (atmospheric, hydrologic, climate)
4. Local cache `~/.claude/cache/geoai/` — always check first
5. OSM Overpass only when Overture lacks coverage
6. Commercial APIs only when explicitly requested + credential set

## Units, language, cartography

- Metric by default: metres/kilometres, m²/hectares, elevations metres
  above WGS84 ellipsoid unless a vertical datum is specified.
- British English (centre, colour, kilometre) — matters for UK dataset
  keyword matching.
- Ramps: Viridis (sequential), RdBu/BrBG (diverging), Carto Bold
  (qualitative, max 8 categories). Print projection: equal-area suited
  to extent. Every map: north arrow, scale bar, attribution, CRS
  string, date of analysis.

## Safety red-lines (Hook-enforced; do not work around)

- Never reproject without validating the target CRS via
  `geoai_get_crs_info`.
- Never write to a production geodatabase without an explicit
  `--confirm` from the user.
- Never send coordinates inside
  `mcp_servers/geoai_mcp/references/sensitive_zones.geojson` to a
  third-party API (including LLM endpoints) without explicit user
  confirmation; use a self-hosted backend instead.
- Never download more than 100 km² of imagery in one tool call — chunk
  into tiles.
- Never execute SQL against a database without schema introspection
  first — hallucinated column names are the single largest failure
  mode of AI-generated spatial SQL.
- Never pick a production-layer table or view name yourself. Staging
  names (`uk.*_raw_*`, `uk_new.*`) are fine to choose. Production /
  published names (anything in `uk_baseline.*` or any published schema)
  must be confirmed by the user — first creation AND any rename. The
  prefix convention (`mob_*`, `env_*`, `soc_*`, …) is the user's call.
  Ask explicitly: "what should this published table be called?"

## Workflow pattern (multi-step analyses)

1. Plan first — state steps, let the user correct.
2. Delegate to subagents — `geoai_critic` reviews outputs at the end of
   any analytical workflow BEFORE they reach the user; findings of
   severity critical/major must be remediated before delivery.
3. Emit a manifest — inputs, parameters, model versions, output paths,
   provenance hashes.

## Skill routing

If the request matches a Skill's description, invoke the Skill rather
than improvising: `urban_plan_evaluator` (masterplan critique, view
corridors, walkability, massing), `accessibility_equity_auditor`
(isochrones, OD matrices, service-area equity). If none matches,
proceed with primitive MCP tools and at session end propose what a new
Skill should encapsulate.

## Gotchas

- **OSMnx 2.x `network_type='walk'` drops walkable streets.** Its filter
  excludes every way tagged `sidewalk`, `sidewalk:both`, `sidewalk:left`
  or `sidewalk:right` = `separate`, and every `highway=cycleway` even with
  `foot=yes`/`designated`. Where the separately drawn footways do not join
  up (common in London), real walking links vanish and the graph splits
  into islands. Found 5 October 2026 marking a GIS take-home on the Isle
  of Dogs: East Ferry Road and Pepper Street missing beside the site
  (12 walkable ways out of 227 in a 450 × 400 m box), in both the
  candidate's and the model answer's networks. Fix: `custom_filter`
  without those clauses (keep `foot!~no`, `access!~private`,
  `service!~private`), then check the graph against full OSM data or a
  basemap at street level before trusting any catchment.
- **Reading raster statistics writes a file next to the source.**
  `band.ComputeStatistics()`, `GetStatistics(…, force)` and
  `gdalinfo -stats` make GDAL's PAM write `<raster>.aux.xml` beside the
  raster. Found 14 October 2026 reviewing the shared slope tool: a
  metadata probe wrote 9 sidecars onto the PP-Team share (now G:)
  although Po had asked for read-only access (a critic subagent then
  did the same to a project copy). Fix: set `GDAL_PAM_ENABLED=NO` (env var or
  `gdal.SetConfigOption`) before opening rasters on a share, or take
  stats from `ReadAsArray()`, or copy the file first — and put the same
  line in every subagent brief that touches shared rasters. If a write
  slips through, report it and let Po decide; never delete on the share.
- **A PyQGIS `QgsProcessingProvider` must keep Python references to its
  algorithms** (`self._algs = [Alg()]` then `addAlgorithm` each), or
  `processing.run` fails with "Error creating algorithm from
  createInstance()". Found 14 October 2026 (QGIS 4.2.2 headless runner).
- **`gdal:polygonize` appends to an existing GeoPackage layer**, so a
  re-run to the same path silently doubles the features. Delete the
  output first. Found 14 October 2026 (counts doubled: 37,702 → 75,404).

## Backend awareness

`GEOAI_BACKEND` env var: `local` (default), `onprem` (PostGIS, internal
STAC), `cloud` (AWS/GCP serverless, COG over S3, GeoParquet, Earth
Engine). You do not need to know which is active — tools route
internally.
