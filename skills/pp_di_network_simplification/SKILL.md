---
name: pp_di_network_simplification
description: >-
  Download and simplify an OpenStreetMap street network for any place (Phase 1),
  then optionally refine it with the space-syntax modelling rules (Phase 2) —
  saving clean GeoPackages ready for QGIS or space-syntax (SSx) analysis. Use this
  whenever the user wants to simplify, clean, neaten, tidy, or refine a road /
  street / urban network; build a "clean network", "morphological network",
  "SSx network", or "axial-ready" network; run neatnet; consolidate dual
  carriageways, roundabouts, junction forks or parallel twin lines; recompute
  unlinks; or capture a drive and/or pedestrian network for a town, city, or area
  by name or coordinates. Trigger phrases include "simplify the network",
  "clean the road network", "network simplification", "prepare a network for
  space syntax", "neatnet", "refine the network", "run phase 2",
  "preserve / keep the dual carriageways", "don't merge the dual carriageways",
  "simplify roads and footpaths for <place>".
---

# Network simplification (Prior+Partners — Digital Innovation)

This skill turns a plain-English request like *"clean the street network for Bath,
10 km, roads and footpaths"* into a finished set of simplified GeoPackages. The
user does not need to know any Python.

The tool has **two phases**, and you should make sure the user knows both exist:

- **Phase 1 — simplification** (`run_simplification.py`): download the
  OpenStreetMap network and consolidate it with neatnet. This is the main run.
- **Phase 2 — refinement** (`run_refinement.py`): optional second pass on the
  Phase 1 output, applying the space-syntax modelling rules — junction forks,
  roundabouts, parallel twin lines, undershoot gaps, slip roads, smoothing —
  plus review layers and recomputed unlinks. **Always offer it after Phase 1
  finishes**, and run it directly when the user asks to "refine" an existing
  simplified network.

## Where this skill's files live

The engine and helper scripts are **bundled inside this skill's own folder**, in a
`scripts/` subfolder. This is a personal skill, so it lives under the user's Claude
profile:

- Windows: `%USERPROFILE%\.claude\skills\pp_di_network_simplification\`
  (e.g. `C:\Users\<name>\.claude\skills\pp_di_network_simplification\`)
- macOS/Linux: `~/.claude/skills/pp_di_network_simplification/`

Resolve the home directory for the active shell and build absolute paths from it:
- PowerShell: `$env:USERPROFILE\.claude\skills\pp_di_network_simplification\...`
- bash: `$HOME/.claude/skills/pp_di_network_simplification/...`

Call that folder `SKILL_DIR` below. The engine is `SKILL_DIR\scripts\run_simplification.py`.
**Outputs always go to the folder the user chooses** (default `./output` in their
current project), never inside the skill folder.

## Step 1 — Open with the two-phase overview, then ask for the choices

These colleagues are non-coders who don't know the options exist, so **do not
silently infer settings and run** — open with a short orientation and present
the choices. Keep it to ONE friendly message.

**First, tell them the process has two phases** (so it's never a surprise):

> This runs in **two phases**: **Phase 1** downloads and simplifies the street
> network (the main run — a few minutes up to about an hour for a large area),
> then **Phase 2** is an optional refinement pass that tidies roundabouts, dual
> carriageways and junctions (under a minute). I'll do Phase 1 first and offer
> Phase 2 when it finishes. A quick manual check in QGIS is always the last step.

**Then ask for the choices below, in the same message — always present all
three**, even if the user already stated some. Pre-select whatever they
specified (otherwise the default) and show it as the chosen option, so they can
confirm or change. Mark every default so they can simply reply *"defaults are
fine"*.

*Essentials* — ask if missing, never guess:
- **Place** (town/city/area name, or coordinates) and **radius** (e.g. 3 km).
- **Output folder** — where to save (default: `./output` in the current folder).

*Choices* — always offer these three:

1. **Network type** — *Road only* (driving network) **[default]**, or
   *Road + footpaths* (adds pavements, paths and steps; richer but roughly
   twice as slow and large). → `drive` / `drive_plus_pedestrian`.

2. **Dual carriageways & motorways** — three options:
   - *Simplify them with the rest* **[default]** — neatnet consolidates each
     divided road into a single centre line. → omit the flag.
   - *Preserve main roads* — hold motorway / trunk / primary (and their slip
     roads) back, untouched. → `--preserve-main-roads`.
   - *Preserve main + secondary* — also hold secondary roads back. →
     `--preserve-main-roads --preserve-secondary`.
   *If asked, explain:* preservation is by road **class**. With *main roads* a
   dual carriageway tagged `secondary` or below is still simplified — choose
   *main + secondary* to keep those too; tertiary and below are always
   simplified. Phase 2 likewise keeps preserved duals and only merges them if
   explicitly asked.

3. **Simplification strength** — show the configuration and invite a change.
   Present this table and say you'll use **aggressive** unless they prefer
   another level:

   | Strength | neatnet consolidation tolerance | Small dangles kept | Character |
   |----------|---------------------------------|--------------------|-----------|
   | `default` | 10 m | ≥ 20 m | lightest — keeps the most detail |
   | `moderate` | 15 m | ≥ 25 m | light cleaning |
   | **`aggressive`** *(default)* | 20 m | ≥ 30 m | recommended balance |
   | `very_aggressive` | 30 m | ≥ 40 m | strong — small features vanish |
   | `extreme_aggressive` | 50 m | ≥ 50 m | maximum reduction, coarse models |

   Ask: *"I'll use **aggressive** (the recommended balance). Want it lighter or
   stronger?"* (The per-tile `--chunks` count can also be tuned for memory, but
   most colleagues won't need it — only mention it if they hit an out-of-memory.)

*Also:* if the user mentions **space syntax / depthmapX / unlinks**, plan to add
`--detect-unlinks` and say so.

You do **not** need coordinates (the engine geocodes the place name) or a CRS /
chunk count (auto-picked: British National Grid for the UK, otherwise a UTM
zone; chunk grid sized from the radius).

## Step 2 — Confirm the plan in one line, then proceed

Once the choices are settled, play them back in a single sentence and start —
don't re-ask anything they've answered. For example:

> Right: **Phase 1**, **road-only** network for **Bath**, **3 km**,
> **aggressive** simplification, **dual carriageways preserved**, saving to
> `./output`. Starting now — I'll keep you posted, then offer Phase 2.

## Step 3 — Make sure the Python dependencies are installed

Run the bundled dependency check (resolve `SKILL_DIR` first):

```powershell
python "$env:USERPROFILE\.claude\skills\pp_di_network_simplification\scripts\_check_deps.py"
```

It prints `OK`, or `NEED_INSTALL: <module>`. If anything is missing, install the
bundled requirements once (a couple of minutes the first time):

```powershell
python -m pip install -r "$env:USERPROFILE\.claude\skills\pp_di_network_simplification\requirements.txt"
```

## Step 4 — Run the engine in the background

Build the command from the confirmed parameters and run it **in the background**
(a real run takes 5–60 minutes and would otherwise time out):

```powershell
python "$env:USERPROFILE\.claude\skills\pp_di_network_simplification\scripts\run_simplification.py" `
  --city "Bath, UK" `
  --radius 10000 `
  --mode drive_plus_pedestrian `
  --level aggressive `
  --output "<the folder the user chose>"
```

Add `--preserve-main-roads` if they chose to preserve dual carriageways/main
roads (Step 1, choice 2), and `--detect-unlinks` if they asked for unlinks /
space syntax. Use `--lat`/`--lon` instead of `--city` only if the user gave
coordinates. Use the Bash tool with `run_in_background: true`; note the
output-file path it returns.

## Step 5 — Relay progress

The engine prints clear progress lines like
`[6/16] chunk_1_1 simplified: 7,712 -> 5,667 (-26%) in 54s`. Every minute or so,
read the last ~15 lines of the output file and relay the newest `[N/total]` line to
the user as one short update. Don't dump the whole file. You'll be notified on
completion.

## Step 6 — Report the result and offer Phase 2

When you see `=== SIMPLIFICATION COMPLETE ===`, give the user: the total time and
reduction (e.g. "53,555 → 37,915 segments, −29%"), the output folder, and the key
file `<prefix>_simplified.gpkg`. If unlinks were produced, mention the
`_unlinks.gpkg` point layer for space-syntax import. A typical output set:
`_original.gpkg`, `_simplified.gpkg`, `_buildings.gpkg`, `_chunks.gpkg`, optional
`_main_roads.gpkg`, optional `_unlinks.gpkg`, and a `_run_manifest.json`.

Then **offer Phase 2** in one sentence, for example:

> There's an optional **Phase 2 (refinement)** that collapses roundabouts,
> contracts junction forks, merges parallel twin lines, closes small gaps and
> smooths the geometry — recommended before space-syntax analysis. Run it now?

## Step 7 — Phase 2 (refinement), on request or acceptance

Phase 2 reads the Phase 1 `*_simplified.gpkg` and writes a `*_refined.gpkg` plus
a multi-layer review GeoPackage. It never modifies the Phase 1 files. Run it when
the user accepts the offer above, or whenever they ask to "refine" / "run phase 2
on" an existing simplified network (then ask which `*_simplified.gpkg` to use if
it isn't obvious).

```powershell
python "$env:USERPROFILE\.claude\skills\pp_di_network_simplification\scripts\run_refinement.py" `
  --input "<the *_simplified.gpkg>" `
  --output "<same folder as the Phase 1 outputs>" `
  --detect-unlinks
```

(bash: `python "$HOME/.claude/skills/pp_di_network_simplification/scripts/run_refinement.py" ...`)

Notes:

- Keep the Phase 1 siblings (`*_buildings.gpkg`, `*_unlinks.gpkg`,
  `*_original.gpkg`) next to the input — they are auto-discovered and power the
  building guards and unlink recovery.
- **Do not add `--merge-dual-carriageways` unless the user explicitly asks** —
  some regions need dual carriageways preserved. Pedestrian paths are never
  absorbed; motorway/trunk/primary dual lines are kept by default.
- Phase 2 is fast (well under a minute for a city) — a background run is tidy
  but not essential.
- Report the per-rule lines (junctions, roundabouts, parallels, gaps, slip
  roads, smoothing, unlinks) and the output files: `*_refined.gpkg` (the new
  main result), `*_refinement_review.gpkg`, `*_refined_unlinks.gpkg`.

## Step 8 — Always close with the manual check

End every Phase 1 and Phase 2 report with this caveat, in your own words —
it is part of the method, not boilerplate:

> **A manual sense-check in QGIS is still required** before the network is used
> for analysis. Automated cleaning is roughly 90% right; overlay the model on
> aerial imagery and check (1) the simplified/refined network — especially big
> junctions, squares and anywhere geometry looks surprising — and (2) every
> unlink point. The `*_refinement_review.gpkg` layers (`changed_or_added`,
> `roundabouts`, `square_links`, `deletion_candidates`,
> `unresolved_crossings`) exist precisely to make that review fast.

## Handling problems

- **Geocode failed** (`could not geocode`): ask for a fuller place name ("Bath, UK")
  or coordinates.
- **A chunk prints `FALLBACK`**: expected and harmless — `neatnet` has a known
  internal bug on some geometries; that chunk keeps its original edges and the run
  continues. Mention it only if several chunks fall back.
- **Out of memory / killed**: re-run adding `--chunks N` with a larger N, e.g.
  `--chunks 6`.
- **`python` not found**: Python isn't on PATH — the user needs to finish the
  one-time setup (run `Setup_Windows.bat` from the repo, which installs Python
  with "Add to PATH").

## Notes

- All distances/areas are computed in a projected CRS in metres, never raw lat/lon.
- This skill runs Python on the user's machine, so it needs a **local** Claude Code
  session (not a remote/cloud one).
