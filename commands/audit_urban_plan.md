---
description: Run the urban_plan_evaluator skill against a site to audit solar access, view corridors, active frontage, and walkability. Output includes findings table, web map, and reproducibility manifest.
allowed-tools: mcp__geoai__*, Read, Write, Edit, Bash
argument-hint: <site_geojson_or_bbox> [--threads solar,frontage,permeability,density] [--locale UK|EU|CONUS]
---

Trigger the `urban_plan_evaluator` skill to audit the urban
masterplan or scheme identified by the argument.

**Arguments:**
- First positional: site identifier — either a path to a GeoJSON file
  describing the site boundary, or a bbox in `minx,miny,maxx,maxy`
  WGS84 format.
- `--threads`: comma-separated subset of `solar`, `frontage`,
  `permeability`, `density`. Defaults to all four.
- `--locale`: regulatory and CRS context. Defaults to `UK`. Options:
  `UK` (EPSG:27700), `EU` (EPSG:3035), `CONUS` (EPSG:5070).

**Workflow you must execute:**

1. Fork the `urban_plan_evaluator` skill. Do not improvise the
   workflow — follow the skill's documented sequence.
2. Validate input: confirm the site geometry exists, is valid, and
   sits within the locale's expected coordinate envelope.
3. Run only the requested threads. Each thread should produce its
   findings structured JSON.
4. At the end, invoke the `geoai_critic` subagent on the assembled
   findings before returning to the user.
5. If `geoai_critic` returns `fail`, remediate before returning. If
   it returns `warn`, present findings to the user with explicit
   warnings displayed.
6. Final deliverables: a findings table, a web map (when the
   cartographer tool is available), and the reproducibility manifest.

**Examples:**

```
/audit_urban_plan ./site_boundaries/canada_water.geojson
/audit_urban_plan -0.05,51.49,-0.03,51.51 --threads solar,frontage --locale UK
/audit_urban_plan ./proposals/proposed_block.geojson --threads density --locale UK
```

If the user has not yet provided a site geometry, ask for one. Do not
generate a synthetic geometry to proceed.
