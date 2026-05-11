---
description: Run the accessibility_equity_auditor skill to quantify spatial accessibility and equity gaps between origins (residents, depots) and destinations (services, facilities). Output includes findings, equity-by-decile chart, web map, and reproducibility manifest.
allowed-tools: mcp__geoai__*, Read, Write, Edit, Bash
argument-hint: <origins> <destinations> [--mode walking|cycling|driving|transit] [--minutes 15] [--locale UK|EU|CONUS]
---

Trigger the `accessibility_equity_auditor` skill to audit
accessibility between the provided origins and destinations.

**Arguments:**
- First positional `origins`: path to point file (addresses, depots,
  demographic centroids) OR polygon file with a `population` attribute.
- Second positional `destinations`: path to point file of facilities
  (pharmacies, hospitals, schools, shops, depots).
- `--mode`: travel mode. Options: `walking` (default), `cycling`,
  `driving`, `transit`.
- `--minutes`: travel-time budget. Defaults: walking 15, cycling 15,
  driving 30, transit 45. Override with this flag.
- `--locale`: working CRS and deprivation index. Defaults to `UK`.

**Workflow you must execute:**

1. Fork the `accessibility_equity_auditor` skill. Follow its
   documented four-pattern logic (one-to-many, many-to-one,
   many-to-many, equity audit).
2. If `origins` is a population-weighted polygon file and
   `destinations` is a point file, default to the **equity audit**
   pattern.
3. Validate inputs: confirm both files exist, have valid geometry,
   share the locale's expected coordinate envelope, and that any
   demographic attribute is plausible.
4. Run `geoai_calculate_isochrone` for each origin (one-to-many) or
   each destination (many-to-one), or fall back to a route-matrix
   pattern for many-to-many.
5. Compute equity metrics: coverage gap by deprivation decile, mean
   access time by decile.
6. Invoke the `geoai_critic` subagent on the assembled findings.
7. Final deliverables: a findings JSON, an equity-by-decile chart
   description, a web map description, and the reproducibility
   manifest. (Actual chart/map rendering requires future
   cartographer tools — when those are not yet wired, output the
   findings as structured data the user can render externally.)

**Examples:**

```
/audit_accessibility ./demographics/lsoa_population.gpkg ./services/pharmacies.geojson
/audit_accessibility ./depots.geojson ./demand_points.geojson --mode driving --minutes 30
/audit_accessibility ./hospitals.geojson ./elderly_residents.gpkg --mode driving --minutes 20 --locale UK
```

Refuse:
- Equity audits over fewer than 100 individuals — privacy floor.
- Causal claims. You produce correlations and gaps, not causes.
- Requests to redraw service boundaries on equity grounds without
  human consultation — flag the recommendation, do not implement it.
