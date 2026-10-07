"""Segment map creation — wraps pstalgo.CreateSegmentMap headlessly.

Spatial input/output: GeoPackage line layer (+ optional unlink points) in,
GeoPackage segment layer out, all in the input layer's projected metre CRS.
Data layer: preprocessing.

Mirrors the PST QGIS plugin's CreateSegmentMapAnalysis: snap / tail /
collinear-deviation thresholds, unlinks honoured for axial/segment input,
and an unlinks point layer emitted for road-centre-line input.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import LineString, Point

from .crs import validate_metric_crs
from .network_io import read_points, read_polylines, write_lines, write_points
from .pstalgo_loader import import_pstalgo

logger = logging.getLogger(__name__)

NETWORK_TYPES = ("axial_segment", "rcl")


@dataclass
class SegmentMapParams:
    """Editing thresholds, in metres (defaults match pstalgo's own)."""

    snap: float = 1.0
    tail: float = 10.0
    deviation: float = 1.0


def create_segment_map(
    network_gpkg: Path,
    out_gpkg: Path,
    out_layer: str,
    network_layer: str | None = None,
    network_type: str = "axial_segment",
    unlinks_gpkg: Path | None = None,
    unlinks_layer: str | None = None,
    params: SegmentMapParams | None = None,
    copy_columns: tuple[str, ...] = (),
) -> dict:
    """Create a line-segment map from an axial/segment or RCL network.

    Returns a summary dictionary for the reproducibility manifest.
    """
    if network_type not in NETWORK_TYPES:
        raise ValueError(f"network_type must be one of {NETWORK_TYPES}.")
    params = params or SegmentMapParams()
    pstalgo = import_pstalgo()

    polylines = read_polylines(network_gpkg, network_layer)
    crs = validate_metric_crs(polylines.crs)

    road_network_type = (
        pstalgo.RoadNetworkType.AXIAL_OR_SEGMENT
        if network_type == "axial_segment"
        else pstalgo.RoadNetworkType.ROAD_CENTER_LINES
    )

    # Unlinks are an input only for axial/segment networks; for RCL input
    # pstalgo derives the unlink points itself (grade-separated crossings).
    unlinks = None
    if unlinks_gpkg is not None:
        if network_type != "axial_segment":
            raise ValueError(
                "An unlinks layer is only accepted for axial/segment input; "
                "road-centre-line input derives unlinks itself."
            )
        unlinks, unlinks_crs = read_points(unlinks_gpkg, unlinks_layer)
        if not validate_metric_crs(unlinks_crs).equals(crs):
            raise ValueError(
                "Unlinks layer CRS differs from the network layer CRS."
            )

    missing = [c for c in copy_columns if c not in polylines.source_frame.columns]
    if missing:
        raise ValueError(f"copy_columns not found in network layer: {missing}")

    algo = None
    try:
        res, algo = pstalgo.CreateSegmentMap(
            road_network_type=road_network_type,
            poly_coords=polylines.coords,
            poly_sections=polylines.counts,
            unlinks=unlinks,
            snap=params.snap,
            tail=params.tail,
            deviation=params.deviation,
            extrude=params.snap,  # the plugin passes the snap value here
        )
        segment_count = int(res.m_SegmentCount)
        if segment_count == 0:
            raise RuntimeError("CreateSegmentMap produced no segments.")

        seg_coords = res.m_SegmentCoords
        seg_index = res.m_Segments  # triplets (P0, P1, BaseIndex)
        geometries: list[LineString] = []
        base_indices: list[int] = []
        for i in range(segment_count):
            p0 = seg_index[i * 3]
            p1 = seg_index[i * 3 + 1]
            base_indices.append(int(seg_index[i * 3 + 2]))
            geometries.append(
                LineString(
                    [
                        (seg_coords[p0 * 2], seg_coords[p0 * 2 + 1]),
                        (seg_coords[p1 * 2], seg_coords[p1 * 2 + 1]),
                    ]
                )
            )

        attributes: dict[str, list] = {
            "id": list(range(1, segment_count + 1)),
            "base_fid": base_indices,
        }
        for column in copy_columns:
            source_values = polylines.source_frame[column].tolist()
            attributes[column] = [source_values[b] for b in base_indices]

        write_lines(out_gpkg, out_layer, geometries, attributes, crs)

        derived_unlink_count = 0
        if road_network_type == pstalgo.RoadNetworkType.ROAD_CENTER_LINES and res.m_UnlinkCoords:
            derived_unlink_count = int(res.m_UnlinkCount)
            unlink_points = [
                Point(res.m_UnlinkCoords[i * 2], res.m_UnlinkCoords[i * 2 + 1])
                for i in range(derived_unlink_count)
            ]
            write_points(out_gpkg, f"{out_layer}_unlinks", unlink_points, crs)

        summary = {
            "step": "create_segment_map",
            "network_gpkg": str(network_gpkg),
            "network_layer": network_layer,
            "network_type": network_type,
            "unlinks_gpkg": str(unlinks_gpkg) if unlinks_gpkg else None,
            "unlinks_layer": unlinks_layer,
            "input_polyline_count": polylines.polyline_count,
            "input_unlinks_applied": (len(unlinks) // 2) if unlinks is not None else 0,
            "params": {
                "snap_m": params.snap,
                "tail_m": params.tail,
                "collinear_deviation_m": params.deviation,
            },
            "crs": crs.to_string(),
            "out_gpkg": str(out_gpkg),
            "out_layer": out_layer,
            "segment_count": segment_count,
        }
        # Only meaningful for RCL input, where pstalgo derives the unlink
        # points itself; omitted for axial/segment runs so a zero cannot be
        # misread as "supplied unlinks were not applied".
        if network_type == "rcl":
            summary["rcl_derived_unlink_count"] = derived_unlink_count
        logger.info(
            "Segment map created: %d polylines -> %d segments", polylines.polyline_count, segment_count
        )
        return summary
    finally:
        if algo is not None:
            pstalgo.Free(algo)
