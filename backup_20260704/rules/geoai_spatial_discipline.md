---
name: geoai_spatial_discipline
description: Fires when the working directory contains geospatial files. Reinforces CRS discipline and routes work through the geoai MCP server. Triggers on geospatial file extensions (.tif, .tiff, .gpkg, .geojson, .shp, .parquet, .qgz, .qgs, .laz, .las) and on QGIS or ArcGIS project files.
globs:
  - "**/*.tif"
  - "**/*.tiff"
  - "**/*.gpkg"
  - "**/*.geojson"
  - "**/*.shp"
  - "**/*.shx"
  - "**/*.dbf"
  - "**/*.prj"
  - "**/*.parquet"
  - "**/*.qgz"
  - "**/*.qgs"
  - "**/*.qpkg"
  - "**/*.laz"
  - "**/*.las"
  - "**/*.kml"
  - "**/*.kmz"
  - "**/*.gml"
---

# Spatial discipline

This rule is active because the working directory contains geospatial
files. Apply these conventions for the duration of the session:

## Default tool choice

Prefer the `geoai_*` MCP tools over ad-hoc Python:

- For CRS inspection: `geoai_get_crs_info`, never raw pyproj snippets.
- For STAC search: `geoai_stac_search`, not raw pystac-client.
- For isochrones: `geoai_calculate_isochrone`, not raw OSMnx or
  custom HTTP calls.
- For routine geoprocessing not yet covered by an MCP tool, write
  the code yourself but flag at the end of the session: "This task
  warranted a new MCP tool: `<name>`. Should it be added to the
  `geoai_mcp` server?"

## CRS rules (recap from CLAUDE.md)

- Working CRS: UK → EPSG:27700; Europe → EPSG:3035; CONUS → EPSG:5070;
  global area → EPSG:54009; web tile output → EPSG:3857 (output only).
- Never measure distances or areas in EPSG:4326. The
  `pre_tool_geoai_validate_crs.py` Hook will block invalid CRS
  arguments at the infrastructure layer.

## Output discipline

- Cartographic outputs use Viridis (sequential), RdBu (diverging),
  Carto Bold (qualitative). Include north arrow, scale bar,
  attribution, CRS string, date.
- Quantitative outputs are accompanied by a reproducibility manifest:
  inputs, parameters, model versions, output paths, hashes.

## Subagent routing

At the end of any multi-step spatial analysis, fork the
`geoai_critic` subagent to review outputs before returning to the
user. Findings of severity `critical` or `major` must be remediated
before delivery.

## Sensitive zones

If any input geometry falls within
`mcp_servers/geoai_mcp/references/sensitive_zones.geojson`, do not
send the coordinates to a third-party API. Use a self-hosted
routing or processing backend instead, or ask the user for explicit
authorisation.
