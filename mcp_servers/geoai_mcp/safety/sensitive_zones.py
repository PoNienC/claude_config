"""
Sensitive-zone check.

Single source of truth for "is this coordinate inside an area I refuse
to leak to a third-party API". Used by:
    - geoai_calculate_isochrone (refuses to send origin to external routing)
    - geoai_stac_search (refuses suspicious bboxes — extend later)
    - any tool that egresses coordinates over the public internet

The reference geometries live in `references/sensitive_zones.geojson`,
which is gitignored. You populate it with whatever zones matter to your
work — typical contents: defence installations, hospitals, indigenous
lands, schools, your own home.

If the file is absent, the function returns False (nothing sensitive
defined). This is the safe default for personal exploration; for
production deployment, configure the file.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Optional

# Resolve relative to this file so the safety module works regardless
# of where the server was launched from. With the new directory
# structure under ~/.claude/mcp_servers/geoai_mcp/:
#   __file__              = .../safety/sensitive_zones.py
#   _THIS_FILE.parents[0] = .../safety/
#   _THIS_FILE.parents[1] = .../geoai_mcp/        <- package root
_THIS_FILE = Path(__file__).resolve()
_PACKAGE_ROOT = _THIS_FILE.parents[1]
_SENSITIVE_GEOJSON = _PACKAGE_ROOT / "references" / "sensitive_zones.geojson"


@lru_cache(maxsize=1)
def _load_sensitive_polygons() -> Optional[list]:
    """Load the sensitive-zones GeoJSON once and cache.

    Returns a list of shapely Polygon/MultiPolygon objects, or None
    if the file is missing or shapely is not installed.
    """
    if not _SENSITIVE_GEOJSON.exists():
        return None

    try:
        from shapely.geometry import shape
    except ImportError:
        return None

    try:
        with open(_SENSITIVE_GEOJSON, "r", encoding="utf-8") as fh:
            geojson = json.load(fh)
    except (json.JSONDecodeError, OSError):
        return None

    polys = []
    if geojson.get("type") == "FeatureCollection":
        for feat in geojson.get("features", []):
            geom = feat.get("geometry")
            if geom and geom.get("type") in ("Polygon", "MultiPolygon"):
                polys.append(shape(geom))
    elif geojson.get("type") in ("Polygon", "MultiPolygon"):
        polys.append(shape(geojson))

    return polys


def is_inside_sensitive_zone(lon: float, lat: float) -> bool:
    """Return True if (lon, lat) in EPSG:4326 falls inside any sensitive zone.

    Returns False if the reference file is absent — i.e. you have not
    configured any sensitive zones. For your personal practice this
    is fine; for production deployment populate
    `references/sensitive_zones.geojson` with the polygons you care
    about.

    Args:
        lon: Longitude in WGS84 decimal degrees.
        lat: Latitude in WGS84 decimal degrees.

    Returns:
        True if inside a sensitive zone, False otherwise.
    """
    polys = _load_sensitive_polygons()
    if not polys:
        return False

    try:
        from shapely.geometry import Point
    except ImportError:
        return False

    pt = Point(lon, lat)
    return any(pt.within(poly) for poly in polys)
