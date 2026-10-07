---
name: pp_space_syntax_analysis
description: >
  Run headless space syntax angular segment analysis (PST Choice and
  Integration centrality) and network catchment analysis (drive-time or
  walking-distance from origins) on a street network GeoPackage — no
  QGIS required. Use whenever the user wants space syntax analysis,
  segment angular analysis, Choice/betweenness or Integration/closeness
  centrality, NACH or NAIN, a segment map from a refined network,
  centrality at multiple radii, or a catchment / service area / reach
  analysis from one or more origin points. Trigger phrases include "run
  space syntax", "run PST", "angular choice", "angular integration",
  "NACH", "NAIN", "segment analysis", "centrality analysis", "create
  segment map", "run the SSx analysis", "vehicular catchment",
  "drive-time catchment", "drive time from", "walking catchment",
  "catchment analysis", "service area", "how far can you drive/walk in
  X minutes", "catchment of the cafes/schools", "join results to
  buildings", "space syntax on buildings", "accessibility of every
  building".
---

# P+P space syntax analysis (headless PST)

Runs the PST (Place Syntax Tool) 3.3.2 analysis core directly from
Python — no QGIS. This skill is **self-contained**: the vendored pstalgo
binary, the wrapper package and the CLI scripts are all bundled inside
the skill's own folder (put there by `Setup_Windows.bat`), so it runs
from any project folder.

Requirements: Windows x64, Python 3.10+. The one-click installer sets
these up; Step 0 re-checks them. No QGIS.

Source repository: https://github.com/Prior-Partners/PP_space_syntax_analysis

## Where this skill's files live

The engine, wrapper package and the native pstalgo core are **bundled
inside this skill's folder**, under the user's Claude profile:

- Windows: `%USERPROFILE%\.claude\skills\pp_space_syntax_analysis\`
  (e.g. `C:\Users\<name>\.claude\skills\pp_space_syntax_analysis\`)
- macOS/Linux: `~/.claude/skills/pp_space_syntax_analysis/` (note: the
  vendored core is Windows-only, so analyses run on Windows)

Resolve the home directory for the active shell and build absolute paths
from it:
- PowerShell: `$env:USERPROFILE\.claude\skills\pp_space_syntax_analysis\...`
- bash: `$HOME/.claude/skills/pp_space_syntax_analysis/...`

Call that folder `SKILL_DIR` below; the scripts are at `SKILL_DIR\scripts\`.
**Outputs always go to the folder the user chooses** (default `./output`
in their current project), never inside the skill folder. This skill runs
Python and a native DLL on the user's machine, so it needs a **Local**
Claude session (not a remote/cloud one).

## What this tool needs as input (say this up front)

This tool does **not** download maps. It analyses a street network the
user already has — normally the output of the P+P **Urban Network
Simplification** tool
(https://github.com/Prior-Partners/Urban_Network_Simplification):

- **Space syntax** runs on the **refined** network (`*_refined.gpkg`)
  plus its **unlinks** (`*_refined_unlinks.gpkg`).
- **Catchment** runs on the **original** network (`*_original.gpkg`) —
  not the refined one (refinement fragments the drivable subset).

If the user has no network yet, point them to the simplification tool
first. Building inputs (for layer-based origins, or as a join surface)
come from the `Global_Building_Footprint` repo's `landuse_enrichment`
tool.

## How to run the conversation (house rules)

These shape every exchange with a colleague:

- **Always ask, never assume.** Confirm the CRS, the input files, and
  (for space syntax) the analysis settings every time — even if the
  colleague seems in a hurry or already mentioned some of it. Use
  AskUserQuestion for the settings; don't silently run on defaults.
- **Explain the method only on request.** Don't lecture. Report the
  results plainly, then OFFER an explanation in one line — e.g. "Do you
  want me to explain the method (what these measures mean, how to read
  them, and the caveats)?" Explain only if the colleague says yes, and
  answer the specific question they ask, drawing from "Explaining the
  method on request" near the end. Keep any always-on flag to a single
  line (see Step C5).
- **Always offer the building join.** End every space syntax or
  catchment delivery by offering the optional join-to-buildings step
  (last section) for the colleague to accept or decline.
- Keep messages friendly and brief; give output locations as clickable
  paths and always point to the manifest JSON.

## Step 0 — check dependencies (first run on a machine)

Run the bundled checker (resolve `SKILL_DIR` first):

```powershell
python "$env:USERPROFILE\.claude\skills\pp_space_syntax_analysis\scripts\_check_deps.py"
```

It prints `OK`, or `NEED_INSTALL: <module>`, or `PSTALGO_LOAD_FAILED:
<reason>`. If a module is missing, install the bundled requirements once
(a couple of minutes the first time):

```powershell
python -m pip install -r "$env:USERPROFILE\.claude\skills\pp_space_syntax_analysis\requirements.txt"
```

If it reports `PSTALGO_LOAD_FAILED`, the machine is probably not Windows
x64 (the native core is Windows-only) or the bundle is incomplete —
re-run `Setup_Windows.bat` from the downloaded repo.

## Step 1 — ask the working CRS FIRST

Before anything else, ask the user which projected CRS the network is
in. This tool is used worldwide — never assume EPSG:27700. Any
projected, metre-based CRS is valid; geographic CRS (EPSG:4326) is
always rejected. Pass the answer as `--expected-crs` so the run fails
loudly if the data does not match.

## Step 2 — collect the inputs

Ask for:
1. The network GeoPackage and layer — the *refined* output of the P+P
   urban network simplification tool.
2. The unlinks point layer (bridges/tunnels). The simplification tool
   produces this; if the user has none, confirm the network genuinely
   has no grade separation before proceeding without it.
3. An output folder (default `./output` in the user's current project).

The network must be line geometry only. Remind the user of the PST
representation rule: lines touch at endpoints at level junctions and
cross without touching at grade separation (with an unlink point).

## Step 3 — ask which analyses to run (offer the defaults)

Present these choices with AskUserQuestion, defaults first:

| Choice | Options (default in bold) |
|---|---|
| Analysis | **Choice + Integration**, Choice only, Integration only |
| Cost (distance mode) | **Angular**, Metric, Topological |
| Radius type | **Metric (walking, metres)**, Angular, Topological |
| Radii | **400, 800, 1200, 2000, 5000, 10000, 20000 m**, or custom list |

Fixed defaults (do not ask unless the user raises them): Choice
normalisations = raw + NACH; Integration normalisations = NAIN +
Hillier; angle precision 1 degree; angle threshold 0; node count,
total depth and mean depth always output.

Note: only Angular cost is currently implemented; Metric and
Topological cost raise a clear not-implemented error. Radius type
Metric/Angular/Topological all work.

## Step 4 — create the segment map

```powershell
python "$env:USERPROFILE\.claude\skills\pp_space_syntax_analysis\scripts\make_segment_map.py" `
  --network <network.gpkg> --network-layer <layer> `
  --unlinks <unlinks.gpkg> --unlinks-layer <layer> `
  --out <outdir>\segment_map.gpkg --out-layer segments `
  --expected-crs <EPSG:xxxx>
```

- Defaults: snap 1 m, tail 10 m, collinear deviation 1 m — fine for
  simplified networks; surface them if the user wants control.
- If the input is a raw road-centre-line map instead of a refined
  network, use `--network-type rcl` (no unlinks input; PST derives an
  unlinks layer which the user MUST review in QGIS before trusting).
- Report the segment count and suggest a quick visual check in QGIS
  before the analysis step.

## Step 5 — run the analysis

```powershell
python "$env:USERPROFILE\.claude\skills\pp_space_syntax_analysis\scripts\run_analysis.py" `
  --gpkg <outdir>\segment_map.gpkg --layer segments `
  --out <outdir>\ssx_results.gpkg --out-layer ssx_results `
  --radii 400,800,1200,2000,5000,10000,20000 `
  --expected-crs <EPSG:xxxx>
```

Add `--analyses`, `--radius-type`, `--choice-norms`,
`--integration-norms`, `--angle-precision`, `--angle-threshold` only
when the user deviated from the defaults.

Runtime scales with segment count squared per radius; for city-scale
networks (>100k segments) warn the user it may take a while and run
radii from small to large.

## Step 6 — report the outputs, then offer to explain

Tell the colleague, briefly:
- The results GeoPackage and layer (as a clickable path), and the
  manifest JSON path (inputs, hashes, parameters, environment — keep it
  with the deliverable).
- Where their headline numbers sit, by column name only — e.g. "NACH at
  400 m is `ACw400C`, NAIN is `AIw400A`" — without explaining the theory.

Then OFFER, in one line: "Do you want me to explain the method — what
these measures mean, how to read the column names, how to style them, and
the caveats?" Explain only if the colleague says yes (see "Explaining the
method on request"), answering the specific question they ask. Finally,
offer the building join (last section).

---

# Catchment analysis (drive time / walking distance)

A separate mode: given one or more origin points, every network segment
gets its minimum cost to the nearest origin — free-flow drive time in
minutes (`--mode drive`) or network walking distance in metres
(`--mode walk`) — banded into thresholds. Runs on the refined network
directly; NO segment map step is needed.

Origins snap to the nearest point ON the nearest main-component segment
and that segment is SPLIT there, so the entry cost is exact (upgraded
21 August 2026 — before that, origins jumped to the nearest junction,
shifting results by the junction offset). Every run writes audit
layers: `origins_snapped` (with `snap_method`), `origin_links` (line
from the raw origin to its snap point) and `origins_dropped` (origins
beyond `--max-snap`, when set). QA gate: ask the colleague to open
`origin_links` in QGIS and confirm the links look short and sensible
before trusting the run.

## Step C1 — ask the working CRS first (same rule as above)

Origins are coordinates in the network CRS, so this matters doubly.

## Step C2 — collect the inputs

1. The network GeoPackage — **use the simplification tool's Phase 1
   `*_original.gpkg`, NOT the refined network**: refinement fragments
   the drivable subset (Cambridge evidence: 51.9% vs 99.4% connected;
   32% of buildings unserved on refined). It MUST carry
   `network_class` and `highway` columns. Drive mode uses
   `network_class` drive + drive_walk; walk mode uses drive_walk +
   walk_only.
2. The origins, one of:
   - coordinates in the network CRS (`--origin X,Y`, repeatable);
   - **a point or polygon layer** (`--origins-layer` +
     `--origins-layer-name` + optional `--origins-where` pandas
     filter). Polygons contribute their representative point; the
     layer is reprojected to the network CRS automatically. For
     "catchment of the cafés/schools", use the buildings file from the
     Global_Building_Footprint repo's landuse_enrichment tool
     (https://github.com/Prior-Partners/Global_Building_Footprint —
     `python landuse_enrichment/get_building_landuse.py --lat … --lon …
     --radius-km … --name … --out-dir …`) and filter e.g.
     `"landuse_type == 'education'"` or
     `"landuse_types_all.str.contains('cafe|coffee|restaurant',
     case=False, na=False)"` (Overture's POI taxonomy is fine-grained —
     pattern-match, don't exact-match food categories).
   If the user describes a place by name, geocode it, reproject to the
   network CRS, and CONFIRM the coordinate with them.
3. The unlinks layer (recommended for drive mode where the network has
   grade separation).
4. Mode, and the band thresholds: defaults are 5,10,15 minutes (drive)
   or 400,800,1200 metres (walk). For networks much larger than the
   bands, suggest adding wider bands (e.g. 5,10,15,30,60) so the
   open-ended top band stays informative.

## Step C3 — speed profile (drive mode only)

The default profile is bundled at
`SKILL_DIR\reference\speed_profiles\osrm_car_default.csv` — free-flow
speeds per OSM highway class from the OSRM car profile, citable,
Europe-flavoured. The script uses it automatically; you only pass
`--speed-profile` to override. For regions with materially different
speeds (e.g. UAE highways at 100–140 km/h), offer to copy the CSV,
adjust the values with the user, and pass `--speed-profile`. Never
invent speeds silently — the profile is a modelling decision the user
owns: ALWAYS show the speed table you are about to use in the chat and
get a yes before running. Street classes missing from the profile are
EXCLUDED from the drive network and reported.

Custom networks (e.g. a proposed design network, not the OSM output):
- `--class-column <col>` — street-class column when it is not called
  `highway`. The layer still needs a `network_class` column with
  drive / drive_walk / walk_only values.
- `--speed-column <col>` — per-segment speed in km/h; where non-null it
  wins over the profile lookup. A network carrying approved design
  speeds runs without any CSV edit.
- If the network has NO classification, ask the colleague to fix it
  manually or assign classes from a reference layer by a
  nearest-line-within-tolerance join — and save the join links for a
  QGIS review. Never guess classes.
- Walk mode: `--walk-speed <km/h>` also outputs minutes
  (`walk_time_min`, or `min_to_<group>` columns in grouped runs).
- `--max-snap <m>` drops origins too far from the network into the
  `origins_dropped` audit layer instead of silently including them.

## Step C4 — run

```powershell
python "$env:USERPROFILE\.claude\skills\pp_space_syntax_analysis\scripts\run_catchment.py" `
  --network <original.gpkg> --network-layer <layer> `
  --unlinks <unlinks.gpkg> `
  --origin <x>,<y> `
  --mode drive `
  --out <outdir>\catchment.gpkg `
  --expected-crs <EPSG:xxxx>
```

Repeat `--origin` for multiple origins (the result is the combined
catchment — time to the NEAREST origin). Add `--bands 5,10,15,30,60`
for large networks, `--mode walk` for walking distance. To take origins
from a filtered layer, use `--origins-layer <gpkg>` +
`--origins-where "<pandas filter>"` instead of `--origin`.

## Step C4b — grouped catchment (one catchment per group of origins)

**What grouping is.** An ordinary catchment pools every origin together
and answers "how far is each street from the NEAREST origin?". A grouped
run keeps the origins apart and answers "how far is each street from EACH
group, separately?". You label every origin with a group name held in a
column of the origins layer, pass that column to `--group-by`, and the
tool runs one catchment per group on the same network.

You get one cost column per group (`m_to_<group>`, plus `min_to_<group>`
with `--walk-speed`) and, for each band, an `n_groups_within_<T>` column
counting how many groups that street reaches within T. Reach for it
whenever the groups must NOT be merged into a single nearest-origin
surface — one group per district, per neighbourhood, per development
parcel, per town centre, per depot — so you can ask "how many of them can
each street reach within 10 minutes' walk?".

Any origins layer carrying a label column works; nothing else is needed.
Explain that much to the colleague before running, in their own terms.

**The edge-origins helper (optional).** Use it for one common case: the
origins should sit on the EDGE of each area, where the streets meet its
boundary — measuring "how far to reach that area at all", not "how far to
its centre". A zone here is any area needing its own catchment. Two
steps, both with QA gates:

1. Build the zone-edge origin points. TRUE crossing points of the network
   and each zone boundary come first; where a boundary runs parallel to
   the streets and is never crossed, boundary samples snapped within
   `--snap-limit` fill the gap — **outside the zone only**: a snap onto an
   internal street would measure "getting into the zone", not "touching
   its edge", so inside candidates (beyond `--inside-tolerance`, default
   1 m) are rejected and counted in `zones_summary.n_rejected_inside`.

```powershell
python "$env:USERPROFILE\.claude\skills\pp_space_syntax_analysis\scripts\make_zone_edge_origins.py" `
  --zones <zones.gpkg> --id-field <zone_id> `
  --network <network.gpkg> --network-layer <layer> `
  --out <outdir>\zone_edge_origins.gpkg --expected-crs <EPSG:xxxx>
```

   QA gate 1 (ask, do not skip): open `points` (colour by `method`:
   crossing vs snap), `links` and `zones_summary` in QGIS. Check the
   points sit on streets at the zone edges and no zone is unexpectedly
   UNREACHABLE. Only continue after a yes.

2. Run the grouped catchment on one shared graph:

```powershell
python "$env:USERPROFILE\.claude\skills\pp_space_syntax_analysis\scripts\run_catchment.py" `
  --network <network.gpkg> --network-layer <layer> `
  --origins-layer <outdir>\zone_edge_origins.gpkg --origins-layer-name points `
  --group-by <zone_id> --mode walk --walk-speed 5 --max-snap 250 `
  --bands 417,833,1250,1667 `
  --out <outdir>\catchment_grouped.gpkg --expected-crs <EPSG:xxxx>
```

   For zone-edge origins the `n_groups_within_<T>` count IS "how many
   zones this street reaches within T". Join it to plots or buildings
   with the join tool as usual. Note: grouped runs skip the
   single-origin `band` and `within_…` columns by design.

   QA gate 2: open `origin_links` and one or two `m_to_<group>` columns
   in QGIS before delivering numbers, and check the "Origin snap offsets"
   line the tool prints — a max far above the median means one origin
   snapped somewhere unexpected.

   Two documented simplifications: where a street runs ALONG the boundary
   (collinear overlap), only the overlap midpoint becomes a crossing
   point; and grouped runs rebuild the graph per group (validated to a
   handful of groups — benchmark before running hundreds).

## Step C5 — report, then offer to explain

- Output layers: `catchment` (segments with `drive_time_min`/
  `walk_dist_m`, `band`, `within_…` flag — or per-group cost columns in
  grouped runs), plus the audit layers `origins_snapped`,
  `origin_links` and (when `--max-snap` dropped any) `origins_dropped`.
  Report these as clickable paths; the manifest JSON sits next to the
  output.
- Report the plain numbers: the band counts, the "largest component
  share" the tool prints, and the duplicate-segments-removed count.
- Do NOT add a separate caveat line — method detail stays on request.

Then OFFER in one line, and in **drive mode** put the one essential flag
in the offer itself, so a colleague who declines still sees it:
- Drive: "Do you want me to explain how to read this — including why
  these are comparative free-flow times, not a planning isochrone (plus
  the `unreached` band, the component share, and styling)?"
- Walk: "Do you want me to explain how to read this — the `unreached`
  band, the component share, and how to style it?"

Explain only if the colleague says yes (see "Explaining the method on
request"), answering the specific question asked. Then offer the building
join.

---

# Explaining the method on request

Use this only when the colleague accepts the offer, and answer the
specific question they ask — don't recite all of it.

**Space syntax**
- Angular Choice = through-movement potential (betweenness — how often a
  segment lies on the angularly simplest routes between all pairs of
  segments). NACH is its normalised, cross-system-comparable form (suffix
  `C`). Angular Integration = to-movement potential (closeness — how
  easily a segment is reached from all others); NAIN (`A`) and Hillier
  (`H`) are its normalisations.
- Column names: prefix `AC`/`AI`, then the radius-type letter and value
  (`w` = walking metres, `a` = angular, `s` = topological steps; thousands
  abbreviate, so `w2k` = 2000 m), then a normalisation suffix (`C` NACH,
  `A` NAIN, `H` Hillier) or an extra letter `N`/`D`/`M` (node count,
  total depth, mean depth). So `ACw400C` = NACH, walking radius 400 m.
- Mean depth = total depth / (node count - 1); isolated segments get 0.
- PST's NACH uses +2 in the divisor where depthmapX uses +3 — never
  compare NACH values across the two tools.
- Results are tool-version-specific; the manifest records PST 3.3.2 and
  the binary hash.
- Styling: NACH/NAIN with a quantile or natural-breaks classification,
  Viridis ramp.

**Catchment**
- Every segment gets its cost to the NEAREST origin, banded. Origins snap
  to the largest connected component; the "component share" is how much of
  the network that component is. Segments off it carry NULL cost and band
  `unreached` — genuine fragmentation (e.g. clusters reachable only by
  footpath), not an error.
- Drive times are free-flow and UNDIRECTED: one-way streets, turn
  restrictions, junction delay and congestion are all ignored. Good for
  comparison, not a defensible isochrone — for that use a routing engine
  (OSRM/Valhalla/pgRouting). Times depend on the speed profile used.
- Walking distances are network distances along available paths; if the
  network lacks footways they are upper bounds.
- Styling: `drive_time_min`/`walk_dist_m` with a Viridis ramp (reversed,
  capped near the top band), grey for `unreached`.

---

# Joining results to buildings (always offer this)

Any segment-level result — catchment bands or space syntax columns —
can be attached to building polygons, so every building carries e.g.
its walk distance to the nearest school AND its NACH/NAIN values. Offer
it at the end of every delivery; run it if the colleague wants it:

```powershell
python "$env:USERPROFILE\.claude\skills\pp_space_syntax_analysis\scripts\join_to_buildings.py" `
  --buildings <buildings.gpkg> --buildings-layer buildings_landuse `
  --results <catchment_or_ssx.gpkg> --results-layer <catchment|ssx_results> `
  --columns all --out <outdir>\buildings_joined.gpkg
```

- Join rule (explain only if asked): minimum Euclidean distance between
  the building POLYGON and the segment polyline, capped by
  `--max-distance` (default 100 m — beyond it the building gets NULL);
  motorways are excluded from candidates; every building records
  `joined_segment_fid` + `join_dist_m` for audit. Values are carried
  unchanged — access distance is reported, not added.
- Buildings in a different projected CRS are reprojected automatically.
- When reporting, distinguish the two NULL flavours: band `unreached`
  (street disconnected from origins) vs no value at all (no street
  within the join tolerance — typically large gated plots).
- Worked pilot with results for Cambridge and Musaffah:
  `docs/pilot_building_integration_report.md`.
