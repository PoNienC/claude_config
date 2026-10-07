"""Join segment-level results (catchment or space syntax) onto buildings.

Spatial input/output: a building polygon GeoPackage in any projected CRS
(reprojected to the results CRS if they differ) and a segment-results
GeoPackage in a projected metre CRS; output is the buildings with joined
value columns, written in the results CRS. Never geographic coordinates.
Data layer: analysis (post-processing join).

Join rule
---------
Each building is attached to the network segment with the minimum
Euclidean distance between the building POLYGON and the segment polyline —
the shortest straight line from any point of the building's edge to any
point along the segment (zero if they touch). The polygon geometry is used
deliberately instead of the centroid: a large building (mall, depot) can
touch a street its centroid is 100 m away from.

Safeguards:
- ``max_distance`` cap — a building farther than the cap from every
  candidate segment gets NULL values, never a far-fetched join.
- ``exclude_classes`` — segments whose ``highway`` class cannot be entered
  from a doorway (motorways by default) are removed from the candidates
  before the join, when the results layer carries a ``highway`` column.
- Every join is auditable: ``joined_segment_fid`` and ``join_dist_m`` are
  written alongside the joined values.

The join carries the segment's values to the building unchanged ("pure"
nearest-segment join): the building-to-street access distance is reported,
not added to any cost.
"""
from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd

from .crs import validate_metric_crs

logger = logging.getLogger(__name__)

EXCLUDE_CLASSES_DEFAULT = ("motorway", "motorway_link")
INTERNAL_COLUMNS = {"geometry"}


def join_to_buildings(
    buildings_gpkg: Path,
    results_gpkg: Path,
    out_gpkg: Path,
    columns: list[str] | str = "all",
    buildings_layer: str | None = None,
    results_layer: str | None = None,
    out_layer: str = "buildings_joined",
    max_distance: float = 100.0,
    exclude_classes: tuple[str, ...] = EXCLUDE_CLASSES_DEFAULT,
) -> dict:
    """Attach segment result values to buildings by nearest-segment join.

    ``columns`` is an explicit list of result columns to carry, or ``"all"``
    for every non-geometry column of the results layer. Returns a
    step-summary dict for the reproducibility manifest.
    """
    results = gpd.read_file(results_gpkg, layer=results_layer)
    results_crs = validate_metric_crs(results.crs)
    if isinstance(columns, str):
        if columns != "all":
            columns = [c.strip() for c in columns.split(",") if c.strip()]
        else:
            columns = [c for c in results.columns if c not in INTERNAL_COLUMNS]
    missing = [c for c in columns if c not in results.columns]
    if missing:
        raise ValueError(
            f"Columns not present in the results layer: {missing}. "
            f"Available: {[c for c in results.columns if c != 'geometry']}"
        )

    excluded_count = 0
    if exclude_classes and "highway" in results.columns:
        before = len(results)
        results = results[~results["highway"].isin(exclude_classes)]
        excluded_count = before - len(results)
        if excluded_count:
            logger.info(
                "Excluded %d segments from join candidates (highway in %s).",
                excluded_count, ", ".join(exclude_classes),
            )
    candidates = results[columns + ["geometry"]].reset_index(drop=True)
    candidates.index.name = "joined_segment_fid"

    # A result column with the same name as a building column (e.g. both
    # carrying 'id') would otherwise come out as pandas merge artefacts
    # id_left/id_right — rename the segment-side copy explicitly.
    buildings_preview = gpd.read_file(
        buildings_gpkg, layer=buildings_layer, rows=1
    )
    collisions = {
        c: f"{c}_seg" for c in columns if c in buildings_preview.columns
    }
    if collisions:
        candidates = candidates.rename(columns=collisions)
        columns = [collisions.get(c, c) for c in columns]
        logger.info(
            "Renamed colliding result columns: %s",
            ", ".join(f"{k} -> {v}" for k, v in collisions.items()),
        )

    buildings = gpd.read_file(buildings_gpkg, layer=buildings_layer)
    total_features = len(buildings)
    buildings = buildings[
        buildings.geometry.geom_type.isin(["Polygon", "MultiPolygon"])
    ].reset_index(drop=True)
    skipped_geom = total_features - len(buildings)
    if skipped_geom:
        logger.warning(
            "Skipped %d non-polygon building features.", skipped_geom
        )
    if buildings.empty:
        raise ValueError(f"No polygon features found in {buildings_gpkg}.")
    reprojected = False
    if not buildings.crs.equals(results_crs):
        building_crs = validate_metric_crs(buildings.crs)
        buildings = buildings.to_crs(results_crs)
        reprojected = True
        logger.info(
            "Buildings reprojected %s -> %s for the join.",
            building_crs.to_string(), results_crs.to_string(),
        )

    joined = gpd.sjoin_nearest(
        buildings,
        candidates,
        how="left",
        max_distance=max_distance,
        distance_col="join_dist_m",
    )
    # sjoin_nearest duplicates rows on exact distance ties — resolve
    # deterministically to the lowest segment fid.
    joined = (
        joined.rename(columns={"index_right": "joined_segment_fid"})
        .sort_values(["join_dist_m", "joined_segment_fid"])
        .groupby(level=0)
        .first()
    )
    joined = gpd.GeoDataFrame(joined, geometry="geometry", crs=results_crs)
    joined["join_dist_m"] = joined["join_dist_m"].round(1)

    out_gpkg.parent.mkdir(parents=True, exist_ok=True)
    joined.to_file(out_gpkg, layer=out_layer, driver="GPKG")
    unjoined = int(joined["joined_segment_fid"].isna().sum())
    logger.info(
        "Joined %d of %d buildings (%d beyond %.0f m): %s layer=%s",
        len(joined) - unjoined, len(joined), unjoined, max_distance,
        out_gpkg, out_layer,
    )

    join_dist = joined["join_dist_m"].dropna()
    authority = results_crs.to_authority()
    return {
        "step": "join_to_buildings",
        "parameters": {
            "buildings": str(buildings_gpkg),
            "buildings_layer": buildings_layer,
            "results": str(results_gpkg),
            "results_layer": results_layer,
            "columns": columns,
            "max_distance_m": max_distance,
            "exclude_classes": list(exclude_classes),
            "join_rule": "minimum Euclidean distance between building "
                "polygon and segment polyline; ties resolved to the lowest "
                "segment fid; values carried unchanged (pure join)",
            "crs": f"{authority[0]}:{authority[1]}" if authority else None,
            "buildings_reprojected": reprojected,
        },
        "results": {
            "building_features": total_features,
            "polygon_buildings": int(len(joined)),
            "skipped_non_polygon": skipped_geom,
            "joined": int(len(joined) - unjoined),
            "beyond_tolerance": unjoined,
            "join_candidates_excluded_by_class": excluded_count,
            "join_dist_m_median": (
                float(join_dist.median()) if len(join_dist) else None
            ),
            "join_dist_m_p95": (
                float(join_dist.quantile(0.95)) if len(join_dist) else None
            ),
        },
        "output": {"gpkg": str(out_gpkg), "layer": out_layer},
    }
