"""Vehicular (drive-time) and walking (metric) catchment analysis.

Spatial input/output: a street network GeoPackage in any projected,
metre-based CRS (input); a segment-level catchment GeoPackage written in the
same CRS (output). No reprojection is performed.
Data layer: analysis.

Method
------
The network is filtered to the mode's subset (``network_class`` values), its
polylines are exploded into two-point segments, coincident duplicates are
collapsed, and the segments are built into a pstalgo axial graph. pstalgo's
``AttractionDistance`` is run reversed — the origins are passed as the
"attraction" points with ``origin_type=LINES`` — so every segment receives
the minimum cost to its nearest origin:

- ``drive`` mode uses ``distance_type=WEIGHTS`` with per-segment free-flow
  travel time. The speed comes from an explicit per-segment speed column
  (``speed_column``) when given, otherwise from the segment's street class
  (``class_column``, default ``highway``) looked up in a cited speed-profile
  CSV. Results in seconds, banded in minutes.
- ``walk`` mode uses ``distance_type=WALKING`` (network metres). Results and
  bands in metres; an optional flat ``walk_speed_kmh`` adds a minutes column.

Origins are snapped to the nearest point ON the nearest segment of the
LARGEST endpoint-connected component, and that segment is SPLIT at the snap
point, so the entry cost is exact (no jump to the nearest junction). Origins
further than ``max_snap_m`` from the component (when set) are dropped and
reported. Every run writes audit layers: ``origins_snapped``,
``origin_links`` (raw point -> snap point) and ``origins_dropped``.

``group_by`` runs one catchment per origin group (e.g. one per district)
on a single shared graph: the output carries one cost column per group plus, when
bands are given, per-band counts of groups reached.

Model limitations (recorded in every manifest): the graph is undirected, so
one-way streets and turn restrictions are not respected; there is no junction
delay or congestion model; drive times are optimistic free-flow estimates.
For defensible isochrones use a routing engine, not this tool.
"""
from __future__ import annotations

import array
import csv
import logging
import re
from dataclasses import dataclass
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import CRS
from shapely.geometry import LineString, Point

from .crs import validate_metric_crs
from .pstalgo_loader import import_pstalgo

logger = logging.getLogger(__name__)

MODES = ("drive", "walk")
DRIVE_CLASSES_DEFAULT = ("drive", "drive_walk")
WALK_CLASSES_DEFAULT = ("drive_walk", "walk_only")
DRIVE_BANDS_DEFAULT = (5.0, 10.0, 15.0)  # minutes
WALK_BANDS_DEFAULT = (400.0, 800.0, 1200.0)  # metres
UNREACHED_SENTINEL = -1.0  # pstalgo AttractionDistance for unreachable lines
SPLIT_ENDPOINT_EPS_M = 0.05  # snap points closer than this reuse the endpoint

MODEL_CAVEATS = [
    "Undirected graph: one-way streets and turn restrictions are not "
    "respected; drive times are optimistic free-flow estimates.",
    "No junction delay or congestion model.",
    "Speed per street class (or per-segment speed column) is a free-flow "
    "modelling assumption; see speed_profile_source.",
    "Not a substitute for a routing engine where defensible isochrones "
    "are required.",
    "Network coverage is the input file's full extent (see "
    "network_bbox_extent_km); the open-ended top band is not a bounded "
    "catchment.",
]


@dataclass
class SpeedProfile:
    """Average speed in km/h per street class, with provenance."""

    speeds_kmh: dict[str, float]
    source_path: Path
    source_note: str

    @classmethod
    def from_csv(cls, path: Path) -> "SpeedProfile":
        """Read a profile CSV with columns highway, speed_kmh, source.

        Lines starting with ``#`` are comments; the source column of the
        last data row is kept as the provenance note.
        """
        speeds: dict[str, float] = {}
        note = ""
        with open(path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(
                line for line in handle if not line.startswith("#")
            ):
                speeds[row["highway"].strip()] = float(row["speed_kmh"])
                note = row.get("source", note) or note
        if not speeds:
            raise ValueError(f"No speed entries found in {path}.")
        return cls(speeds_kmh=speeds, source_path=path, source_note=note)


def load_network_subset(
    gpkg: Path,
    layer: str | None,
    network_classes: tuple[str, ...],
    class_column: str = "highway",
    speed_column: str | None = None,
) -> gpd.GeoDataFrame:
    """Read the network layer and filter to the requested mode subset."""
    gdf = gpd.read_file(gpkg, layer=layer)
    validate_metric_crs(gdf.crs)
    required = ["network_class", class_column]
    if speed_column:
        required.append(speed_column)
    for column in required:
        if column not in gdf.columns:
            raise ValueError(
                f"Network layer must carry a '{column}' column — use the "
                "output of the urban network simplification tool, or pass "
                "--class-column / --speed-column for a custom network."
            )
    subset = gdf[gdf["network_class"].isin(network_classes)].copy()
    if subset.empty:
        raise ValueError(
            f"No features with network_class in {network_classes} found."
        )
    subset = subset.explode(index_parts=False).reset_index(drop=True)
    logger.info(
        "Network subset: %d of %d features (network_class in %s)",
        len(subset), len(gdf), ", ".join(network_classes),
    )
    return subset


def explode_to_segments(
    subset: gpd.GeoDataFrame,
    profile: SpeedProfile | None,
    class_column: str = "highway",
    speed_column: str | None = None,
) -> tuple[gpd.GeoDataFrame, dict[str, int], int, int]:
    """Explode polylines into deduplicated two-point segments.

    In drive mode (``profile`` given) each segment gets a free-flow traverse
    time. The speed for a feature is, in order: its ``speed_column`` value
    when given and non-null, else the profile entry for its class. Features
    with neither are excluded and counted. Coincident duplicate segments
    (same physical geometry from overlapping source features) collapse to
    the faster copy. Returns (segments, excluded class counts, duplicates
    removed, sub-metre connector count).
    """
    geoms: list[LineString] = []
    rows: dict[str, list] = {
        "parent_fid": [], "highway": [], "oneway": [],
        "length_m": [], "traverse_time_s": [],
    }
    excluded: dict[str, int] = {}
    has_oneway = "oneway" in subset.columns
    class_values = subset[class_column].astype(str)
    speed_values = (
        pd.to_numeric(subset[speed_column], errors="coerce")
        if speed_column else None
    )
    for idx, row in enumerate(subset.itertuples(index=False)):
        street_class = class_values.iloc[idx]
        if profile is not None:
            speed_kmh = None
            if speed_values is not None and pd.notna(speed_values.iloc[idx]):
                speed_kmh = float(speed_values.iloc[idx])
            if speed_kmh is None:
                speed_kmh = profile.speeds_kmh.get(street_class)
            if speed_kmh is None or speed_kmh <= 0:
                excluded[street_class] = excluded.get(street_class, 0) + 1
                continue
            speed_ms = speed_kmh / 3.6
        coords = list(row.geometry.coords)
        for (x0, y0, *_), (x1, y1, *_) in zip(coords[:-1], coords[1:]):
            seg = LineString([(x0, y0), (x1, y1)])
            if seg.length <= 0.0:
                continue
            geoms.append(seg)
            rows["parent_fid"].append(idx)
            rows["highway"].append(street_class)
            rows["oneway"].append(row.oneway if has_oneway else None)
            rows["length_m"].append(seg.length)
            rows["traverse_time_s"].append(
                seg.length / speed_ms if profile is not None else None
            )
    segments = gpd.GeoDataFrame(
        pd.DataFrame(rows), geometry=geoms, crs=subset.crs
    )
    if excluded:
        logger.warning(
            "Excluded %d features with no usable speed: %s",
            sum(excluded.values()), excluded,
        )

    def canonical_key(geom: LineString) -> tuple:
        # 1 mm rounding so float noise between overlapping source
        # features still collapses to one segment
        (a, b) = (
            (round(x, 3), round(y, 3)) for x, y in geom.coords
        )
        return (a, b) if a <= b else (b, a)

    segments["_key"] = [canonical_key(g) for g in segments.geometry]
    before = len(segments)
    sort_col = "traverse_time_s" if profile is not None else "length_m"
    segments = (
        segments.sort_values(sort_col)
        .drop_duplicates(subset="_key", keep="first")
        .drop(columns="_key")
        .reset_index(drop=True)
    )
    duplicates_removed = before - len(segments)
    if duplicates_removed:
        logger.warning(
            "Removed %d coincident duplicate segments (kept the faster copy).",
            duplicates_removed,
        )
    # Sub-metre segments join near-coincident junction nodes; dropping them
    # would disconnect the graph, so they are retained and only counted.
    tiny = int((segments["length_m"] < 1.0).sum())
    if tiny:
        logger.info("%d segments shorter than 1 m retained as connectors.", tiny)
    logger.info("Exploded to %d weighted two-point segments.", len(segments))
    return segments, excluded, duplicates_removed, tiny


def origins_from_layer(
    gpkg: Path,
    layer: str | None,
    where: str | None,
    target_crs: object,
    group_by: str | None = None,
) -> tuple[list[tuple[float, float]], list[str], dict]:
    """Read origin coordinates (and optional group labels) from a layer.

    ``where`` is an optional pandas ``query`` expression evaluated with
    ``engine="python"`` so string methods work. Polygon features contribute
    their representative point. The layer is reprojected to the network CRS
    when it differs (both must be projected metre CRS). ``group_by`` names a
    column whose value labels each origin's group (e.g. a zone id).
    Returns (coordinates, group labels, selection summary for the manifest).
    """
    gdf = gpd.read_file(gpkg, layer=layer)
    total = len(gdf)
    if where:
        gdf = gdf.query(where, engine="python")
    if gdf.empty:
        raise ValueError(
            f"Origin selection matched 0 of {total} features in {gpkg} "
            f"(where: {where!r})."
        )
    if group_by and group_by not in gdf.columns:
        raise ValueError(
            f"Origins layer has no '{group_by}' column for --group-by."
        )
    target = CRS.from_user_input(target_crs)
    reprojected = False
    if not gdf.crs.equals(target):
        source = validate_metric_crs(gdf.crs)
        gdf = gdf.to_crs(target)
        reprojected = True
        logger.info(
            "Origins layer reprojected %s -> %s.",
            source.to_string(), target.to_string(),
        )
    coords: list[tuple[float, float]] = []
    groups: list[str] = []
    for row in gdf.itertuples(index=False):
        geom = row.geometry
        if geom is None or geom.is_empty:
            continue
        point = geom if geom.geom_type == "Point" else geom.representative_point()
        coords.append((point.x, point.y))
        groups.append(
            str(getattr(row, group_by)) if group_by else "all"
        )
    if not coords:
        raise ValueError("Origin selection produced no usable geometries.")
    logger.info(
        "Origins from layer: %d of %d features selected (where: %s, "
        "groups: %d).",
        len(coords), total, where or "none", len(set(groups)),
    )
    return coords, groups, {
        "origins_layer": str(gpkg),
        "origins_layer_name": layer,
        "origins_where": where,
        "origins_group_by": group_by,
        "features_in_layer": total,
        "origins_selected": len(coords),
        "origins_reprojected": reprojected,
    }


def connected_components(
    segments: gpd.GeoDataFrame,
) -> tuple[list[int], dict[int, int]]:
    """Label endpoint-connected components via union-find on exact endpoints.

    A conservative lower bound on graph connectivity: pstalgo additionally
    connects lines that cross without sharing an endpoint.
    """
    parent = list(range(len(segments)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    owner: dict[tuple[float, float], int] = {}
    for i, geom in enumerate(segments.geometry):
        coords = list(geom.coords)
        for pt in (coords[0], coords[-1]):
            if pt in owner:
                ra, rb = find(i), find(owner[pt])
                if ra != rb:
                    parent[ra] = rb
            else:
                owner[pt] = i
    labels = [find(i) for i in range(len(segments))]
    sizes: dict[int, int] = {}
    for label in labels:
        sizes[label] = sizes.get(label, 0) + 1
    return labels, sizes


def snap_and_split_origins(
    origins_xy: list[tuple[float, float]],
    segments: gpd.GeoDataFrame,
    max_snap_m: float | None = None,
) -> tuple[gpd.GeoDataFrame, list[Point | None], list[float], list[str],
           float, int]:
    """Snap origins to the nearest point on the main component and split.

    Each origin snaps to the nearest point ON the nearest segment of the
    largest endpoint-connected component. Unless the snap point lies within
    ``SPLIT_ENDPOINT_EPS_M`` of a segment endpoint, the segment is split
    there so the snap point becomes a graph node and the entry cost is
    exact. Origins beyond ``max_snap_m`` (when set) are dropped.

    Returns (segments after splitting, snap node per origin — None when
    dropped, snap offsets in metres, snap method per origin, largest
    component share, number of segments split).
    """
    labels, sizes = connected_components(segments)
    largest = max(sizes, key=lambda k: sizes[k])
    main_mask = [label == largest for label in labels]
    main_net = segments[main_mask]
    main_share = sizes[largest] / len(segments)
    logger.info(
        "Largest endpoint-connected component: %d of %d segments (%.1f%%).",
        sizes[largest], len(segments), 100.0 * main_share,
    )
    sindex = main_net.sindex
    nodes: list[Point | None] = [None] * len(origins_xy)
    offsets: list[float] = []
    methods: list[str] = []
    cuts: dict[int, list[float]] = {}
    pending: list[tuple[int, int, float]] = []  # origin i, seg idx, position
    for i, (x, y) in enumerate(origins_xy):
        raw = Point(x, y)
        near_local = sindex.nearest(raw, return_all=False)[1][0]
        seg_idx = int(main_net.index[near_local])
        line = segments.geometry.loc[seg_idx]
        position = line.project(raw)
        snap_point = line.interpolate(position)
        offset = raw.distance(snap_point)
        offsets.append(offset)
        if max_snap_m is not None and offset > max_snap_m:
            methods.append("dropped")
            continue
        if position <= SPLIT_ENDPOINT_EPS_M:
            nodes[i] = Point(list(line.coords)[0])
            methods.append("endpoint")
        elif position >= line.length - SPLIT_ENDPOINT_EPS_M:
            nodes[i] = Point(list(line.coords)[-1])
            methods.append("endpoint")
        else:
            cuts.setdefault(seg_idx, []).append(position)
            pending.append((i, seg_idx, position))
            methods.append("split")

    n_split = len(cuts)
    if n_split:
        replacement_geoms: dict[int, list[LineString]] = {}
        cut_points: dict[tuple[int, float], Point] = {}
        for seg_idx, positions in cuts.items():
            line = segments.geometry.loc[seg_idx]
            unique_positions = sorted(set(positions))
            stops = [0.0] + unique_positions + [line.length]
            points = [line.interpolate(p) for p in stops]
            for p, pt in zip(stops, points):
                cut_points[(seg_idx, p)] = pt
            pieces = [
                LineString([(a.x, a.y), (b.x, b.y)])
                for a, b in zip(points[:-1], points[1:])
                if a.distance(b) > 0
            ]
            replacement_geoms[seg_idx] = pieces
        for i, seg_idx, position in pending:
            unique_positions = sorted(set(cuts[seg_idx]))
            nearest_position = min(
                unique_positions, key=lambda p: abs(p - position)
            )
            nodes[i] = cut_points[(seg_idx, nearest_position)]

        kept = segments.drop(index=list(replacement_geoms))
        new_rows = []
        for seg_idx, pieces in replacement_geoms.items():
            base = segments.loc[seg_idx]
            for piece in pieces:
                row = base.copy()
                row.geometry = piece
                share = piece.length / base["length_m"]
                row["length_m"] = piece.length
                if pd.notna(base.get("traverse_time_s")):
                    row["traverse_time_s"] = base["traverse_time_s"] * share
                new_rows.append(row)
        segments = pd.concat(
            [kept, gpd.GeoDataFrame(new_rows, crs=segments.crs)],
            ignore_index=True,
        )
        segments = gpd.GeoDataFrame(segments, crs=kept.crs)
        logger.info(
            "Split %d segments at origin snap points (+%d pieces).",
            n_split, len(new_rows) - n_split,
        )

    dropped = methods.count("dropped")
    if dropped:
        logger.warning(
            "Dropped %d origins beyond the %.0f m snap limit.",
            dropped, max_snap_m,
        )
    series = pd.Series([o for o, m in zip(offsets, methods)
                        if m != "dropped"])
    if len(series):
        logger.info(
            "Snapped %d origins to the main component "
            "(offset median %.1f m, max %.1f m; %d splits).",
            len(series), series.median(), series.max(), n_split,
        )
    return segments, nodes, offsets, methods, main_share, n_split


def _search(
    segments: gpd.GeoDataFrame,
    origins: list[Point],
    unlinks_coords: array.array | None,
    mode: str,
) -> array.array:
    """Build the pstalgo graph and return min cost per segment.

    Cost is seconds in drive mode, network metres in walk mode;
    ``UNREACHED_SENTINEL`` marks unreachable segments.
    """
    pstalgo = import_pstalgo()
    line_coords = array.array("d")
    for geom in segments.geometry:
        (x0, y0), (x1, y1) = list(geom.coords)
        line_coords.extend((x0, y0, x1, y1))
    attraction_points = array.array("d")
    for point in origins:
        attraction_points.extend((point.x, point.y))
    out = array.array("f", [0.0] * len(segments))
    graph = pstalgo.CreateGraph(
        line_coords, None, unlinks_coords, None, None, 0, None
    )
    try:
        kwargs: dict = {}
        if mode == "drive":
            kwargs["distance_type"] = pstalgo.DistanceType.WEIGHTS
            kwargs["line_weights"] = array.array(
                "f", segments["traverse_time_s"]
            )
            kwargs["weight_per_meter_for_point_edges"] = 0
        else:
            kwargs["distance_type"] = pstalgo.DistanceType.WALKING
        pstalgo.AttractionDistance(
            graph_handle=graph,
            origin_type=pstalgo.OriginType.LINES,
            radius=pstalgo.Radii(),
            attraction_points=attraction_points,
            out_min_distances=out,
            **kwargs,
        )
    finally:
        pstalgo.FreeGraph(graph)
    return out


def band_label(value: float, bands: tuple[float, ...], unit: str) -> str:
    for threshold in bands:
        if value <= threshold:
            return f"<= {threshold:g} {unit}"
    return f"> {bands[-1]:g} {unit}"


def _column_token(group: str) -> str:
    token = re.sub(r"[^0-9A-Za-z]+", "_", str(group)).strip("_")
    return token or "group"


def run_catchment(
    network_gpkg: Path,
    out_gpkg: Path,
    origins_xy: list[tuple[float, float]],
    mode: str = "drive",
    network_layer: str | None = None,
    out_layer: str = "catchment",
    speed_profile_path: Path | None = None,
    bands: tuple[float, ...] | None = None,
    unlinks_gpkg: Path | None = None,
    unlinks_layer: str | None = None,
    network_classes: tuple[str, ...] | None = None,
    class_column: str = "highway",
    speed_column: str | None = None,
    walk_speed_kmh: float | None = None,
    origin_groups: list[str] | None = None,
    max_snap_m: float | None = None,
) -> dict:
    """Run a catchment analysis and write the output GeoPackage.

    Returns a step-summary dict for the reproducibility manifest.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got '{mode}'.")
    if mode == "drive":
        if speed_profile_path is None and speed_column is None:
            raise ValueError(
                "Drive mode requires a speed profile CSV or --speed-column."
            )
        profile = (
            SpeedProfile.from_csv(speed_profile_path)
            if speed_profile_path is not None
            else SpeedProfile(
                speeds_kmh={},
                source_path=Path("(none)"),
                source_note=f"per-segment column '{speed_column}'",
            )
        )
        classes = network_classes or DRIVE_CLASSES_DEFAULT
        bands = bands or DRIVE_BANDS_DEFAULT
        unit = "min"
    else:
        profile = None
        classes = network_classes or WALK_CLASSES_DEFAULT
        bands = bands or WALK_BANDS_DEFAULT
        unit = "m"

    groups = origin_groups or ["all"] * len(origins_xy)
    if len(groups) != len(origins_xy):
        raise ValueError("origin_groups length must match origins_xy.")
    group_order = list(dict.fromkeys(groups))
    multi_group = len(group_order) > 1

    subset = load_network_subset(
        network_gpkg, network_layer, classes, class_column, speed_column
    )
    segments, excluded, duplicates_removed, tiny = explode_to_segments(
        subset, profile, class_column, speed_column
    )
    segments, nodes, snap_offsets, snap_methods, main_share, n_split = (
        snap_and_split_origins(origins_xy, segments, max_snap_m)
    )

    unlinks_coords = None
    if unlinks_gpkg is not None:
        unlinks_gdf = gpd.read_file(unlinks_gpkg, layer=unlinks_layer)
        unlinks_coords = array.array("d")
        for geom in unlinks_gdf.geometry:
            if isinstance(geom, Point):
                unlinks_coords.extend((geom.x, geom.y))
        logger.info("Read %d unlink points.", len(unlinks_coords) // 2)

    per_group_results: dict[str, dict] = {}
    value_columns: list[str] = []
    for group in group_order:
        group_nodes = [
            node for node, g in zip(nodes, groups)
            if g == group and node is not None
        ]
        if not group_nodes:
            logger.warning("Group '%s': every origin was dropped.", group)
            per_group_results[group] = {"origins_used": 0}
            continue
        costs = pd.Series(
            _search(segments, group_nodes, unlinks_coords, mode),
            dtype="float64",
        )
        unreached = (costs < 0) | costs.isna()
        values = (costs / 60.0 if mode == "drive" else costs).where(
            ~unreached
        )
        if multi_group:
            column = f"{unit}_to_{_column_token(group)}"
            segments[column] = values
            value_columns.append(column)
        else:
            if mode == "drive":
                segments["drive_time_s"] = costs.where(~unreached)
                segments["drive_time_min"] = values
            else:
                segments["walk_dist_m"] = values
                if walk_speed_kmh:
                    segments["walk_time_min"] = values / (
                        walk_speed_kmh * 1000.0 / 60.0
                    )
            segments["band"] = [
                "unreached" if bad else band_label(v, bands, unit)
                for bad, v in zip(unreached, values.fillna(0.0))
            ]
            flag_column = f"within_{bands[-1]:g}{unit}"
            segments[flag_column] = list(
                ~unreached & (values.fillna(float("inf")) <= bands[-1])
            )
        per_group_results[group] = {
            "origins_used": len(group_nodes),
            "reached_count": int((~unreached).sum()),
            "min_value": float(values.min()) if (~unreached).any() else None,
        }

    if multi_group:
        stacked = segments[value_columns]
        for threshold in bands:
            segments[f"n_groups_within_{threshold:g}{unit}"] = (
                (stacked <= threshold).sum(axis=1).astype("int32")
            )
        if mode == "walk" and walk_speed_kmh:
            metres_per_minute = walk_speed_kmh * 1000.0 / 60.0
            for column in list(value_columns):
                segments[column.replace("m_to_", "min_to_", 1)] = (
                    segments[column] / metres_per_minute
                )
    if mode == "walk" and "traverse_time_s" in segments.columns:
        segments = segments.drop(columns=["traverse_time_s"])

    out_gpkg.parent.mkdir(parents=True, exist_ok=True)
    segments.to_file(out_gpkg, layer=out_layer, driver="GPKG")

    # --- audit layers ----------------------------------------------------
    raw_points = [Point(x, y) for x, y in origins_xy]
    kept_mask = [m != "dropped" for m in snap_methods]
    audit = gpd.GeoDataFrame(
        {
            "origin_id": list(range(len(origins_xy))),
            "group": groups,
            "snap_offset_m": [round(o, 1) for o in snap_offsets],
            "snap_method": snap_methods,
        },
        geometry=[
            node if node is not None else raw
            for node, raw in zip(nodes, raw_points)
        ],
        crs=segments.crs,
    )
    audit[kept_mask].to_file(out_gpkg, layer="origins_snapped",
                             driver="GPKG")
    link_rows = [
        (i, raw, node)
        for i, (raw, node, keep) in enumerate(zip(
            raw_points,
            [n if n is not None else r
             for n, r in zip(nodes, raw_points)],
            kept_mask,
        ))
        if keep and raw.distance(node) > 0
    ]
    if link_rows:
        links = gpd.GeoDataFrame(
            audit.drop(columns="geometry").iloc[[i for i, *_ in link_rows]],
            geometry=[LineString([(raw.x, raw.y), (node.x, node.y)])
                      for _, raw, node in link_rows],
            crs=segments.crs,
        )
        links.to_file(out_gpkg, layer="origin_links", driver="GPKG")
    if not all(kept_mask):
        audit[[not k for k in kept_mask]].to_file(
            out_gpkg, layer="origins_dropped", driver="GPKG"
        )
    logger.info("Catchment written: %s layer=%s", out_gpkg, out_layer)

    bounds = segments.total_bounds
    authority = segments.crs.to_authority() if segments.crs else None
    band_counts = (
        segments["band"].value_counts().to_dict()
        if "band" in segments.columns else None
    )
    return {
        "step": "catchment",
        "mode": mode,
        "parameters": {
            "network": str(network_gpkg),
            "network_layer": network_layer,
            "unlinks": str(unlinks_gpkg) if unlinks_gpkg else None,
            "network_classes": list(classes),
            "class_column": class_column,
            "speed_column": speed_column,
            "walk_speed_kmh": walk_speed_kmh,
            "max_snap_m": max_snap_m,
            "origins_input_xy": [list(o) for o in origins_xy],
            "origin_groups": group_order,
            "origin_snap_offsets_m": [round(o, 1) for o in snap_offsets],
            "origin_snap_rule": (
                "nearest point on the nearest largest-component segment; "
                "the segment is split at the snap point (endpoint reused "
                f"within {SPLIT_ENDPOINT_EPS_M} m)"
            ),
            "origin_snap_methods": snap_methods,
            "bands": list(bands),
            "band_unit": unit,
            "speed_profile": (
                str(profile.source_path) if profile else None
            ),
            "speed_profile_source": profile.source_note if profile else None,
            "speeds_kmh": profile.speeds_kmh if profile else None,
            "crs": f"{authority[0]}:{authority[1]}" if authority else None,
        },
        "results": {
            "segment_count": int(len(segments)),
            "segments_split_for_origins": n_split,
            "band_counts": band_counts,
            "per_group": per_group_results,
            "excluded_street_classes": excluded,
            "coincident_duplicate_segments_removed": int(duplicates_removed),
            "sub_metre_connector_segments_retained": int(tiny),
            "largest_component_share": round(main_share, 4),
            "origins_dropped": snap_methods.count("dropped"),
            "network_bbox_extent_km": [
                round((bounds[2] - bounds[0]) / 1000.0, 1),
                round((bounds[3] - bounds[1]) / 1000.0, 1),
            ],
        },
        "output": {"gpkg": str(out_gpkg), "layer": out_layer},
        "model_caveats": MODEL_CAVEATS,
    }
