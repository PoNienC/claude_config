"""CLI: build zone-edge origin points for grouped catchment runs.

Spatial input/output: a zone polygon GeoPackage and a network
GeoPackage in the same projected metre CRS (input); an origins GeoPackage
(output) whose ``points`` layer feeds ``run_catchment.py --origins-layer
... --group-by <id-field>``. No reprojection is performed.
Data layer: preprocessing.

A "zone" here is simply an area you want its own catchment for: a
district, a neighbourhood, a development parcel, a service area.

Method (approved 21 August 2026): the primary origins are the TRUE
CROSSING POINTS — the geometric intersections of the network lines with
each zone's boundary. Where a boundary runs parallel to the streets and
is never crossed (common where networks follow road centrelines and
boundaries follow plot edges), the fallback samples the boundary every
``--spacing`` metres and snaps each sample to the nearest network segment
within ``--snap-limit``; the snapped points (deduplicated against the
crossing points and each other) join the origin set, and the snap links
are written for audit. Zones with neither crossings nor snaps are
reported as unreachable — never silently dropped.

Audit layers written alongside ``points``: ``links`` (boundary sample ->
snap point), ``zones_summary`` (per zone: crossings, snapped points,
method, unreachable flag) and the input zone polygons.

Example:
    python scripts/make_zone_edge_origins.py `
      --zones zones.gpkg --id-field zone_id `
      --network network.gpkg --network-classes drive_walk,walk_only `
      --out zone_edge_origins.gpkg --expected-crs EPSG:32640
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import LineString, Point

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pp_space_syntax.catchment import connected_components  # noqa: E402
from pp_space_syntax.crs import assert_expected_crs, validate_metric_crs  # noqa: E402
from pp_space_syntax.manifest import write_manifest  # noqa: E402

WALK_CLASSES_DEFAULT = ("drive_walk", "walk_only")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zones", type=Path, required=True,
                        help="Zone polygon GeoPackage (any area needing its "
                             "own catchment)")
    parser.add_argument("--zones-layer", default=None,
                        help="Layer name (default: only layer)")
    parser.add_argument("--id-field", required=True,
                        help="Column that identifies each zone")
    parser.add_argument("--network", type=Path, required=True,
                        help="Network GeoPackage")
    parser.add_argument("--network-layer", default=None,
                        help="Layer name (default: only layer)")
    parser.add_argument(
        "--network-classes", default=",".join(WALK_CLASSES_DEFAULT),
        help="network_class values to use (default: walk subset). Pass "
             "'all' to skip the filter",
    )
    parser.add_argument("--spacing", type=float, default=50.0,
                        help="Boundary sample spacing in metres (default 50)")
    parser.add_argument("--snap-limit", type=float, default=50.0,
                        help="Max snap distance for fallback points "
                             "(default 50 m)")
    parser.add_argument("--inside-tolerance", type=float, default=1.0,
                        help="A fallback snap may sit at most this far "
                             "INSIDE the zone (default 1 m); anything "
                             "deeper is rejected — edge origins must sit "
                             "on or outside the boundary")
    parser.add_argument("--dedupe", type=float, default=25.0,
                        help="Drop a fallback point within this distance of "
                             "an already-kept point of the same zone "
                             "(default 25 m)")
    parser.add_argument("--out", type=Path, required=True,
                        help="Output GeoPackage path")
    parser.add_argument("--expected-crs", default=None,
                        help="Fail unless both layers match (e.g. EPSG:32640)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    zones = gpd.read_file(args.zones, layer=args.zones_layer)
    network = gpd.read_file(args.network, layer=args.network_layer)
    crs = validate_metric_crs(network.crs)
    if args.expected_crs:
        assert_expected_crs(crs, args.expected_crs)
    if not zones.crs.equals(network.crs):
        validate_metric_crs(zones.crs)
        zones = zones.to_crs(network.crs)
        logging.info("Zones reprojected to the network CRS.")
    if args.id_field not in zones.columns:
        raise SystemExit(f"Zones layer has no '{args.id_field}' column.")

    if args.network_classes.strip().lower() != "all":
        wanted = tuple(c.strip() for c in args.network_classes.split(","))
        if "network_class" not in network.columns:
            raise SystemExit(
                "Network has no network_class column — pass "
                "--network-classes all to skip the filter."
            )
        network = network[network["network_class"].isin(wanted)]
        logging.info("Network filtered to %s: %d features.",
                     wanted, len(network))
    # Restrict to the largest endpoint-connected component so no origin
    # lands on a detached fragment (run_catchment would silently re-snap
    # it much further away).
    network = network.explode(index_parts=False).reset_index(drop=True)
    labels, sizes = connected_components(network)
    largest = max(sizes, key=lambda k: sizes[k])
    network = network[[label == largest for label in labels]]
    logging.info(
        "Restricted to the largest connected component: %d features "
        "(%.1f%%).", len(network), 100.0 * sizes[largest] / sum(sizes.values()),
    )
    lines = network.geometry.values
    tree = shapely.STRtree(lines)

    points: list[dict] = []
    links: list[dict] = []
    summary: list[dict] = []
    for zone in zones.itertuples(index=False):
        sid = str(getattr(zone, args.id_field))
        boundary = zone.geometry.boundary
        kept: list[Point] = []

        # 1 — true crossing points (the primary, exact method)
        n_cross = 0
        for k in tree.query(boundary, predicate="intersects"):
            inter = shapely.intersection(lines[k], boundary)
            parts = getattr(inter, "geoms", [inter])
            for part in parts:
                if part.geom_type == "Point":
                    candidates = [part]
                elif part.geom_type == "LineString":
                    # street lies along the boundary: use its midpoint
                    candidates = [part.interpolate(0.5, normalized=True)]
                else:
                    continue
                for pt in candidates:
                    kept.append(pt)
                    n_cross += 1
                    points.append({"zone": sid, "method": "crossing",
                                   "side": "edge", "snap_m": 0.0,
                                   "geometry": pt})

        # 2 — fallback: boundary samples snapped OUTSIDE the zone only.
        # An origin inside the polygon would measure "getting INTO the
        # zone", not "touching its edge" (rule approved 21 August
        # 2026);
        # inside candidates are rejected and counted.
        n_snap = 0
        n_rejected_inside = 0
        interior = zone.geometry.buffer(-args.inside_tolerance)
        length = boundary.length
        n_samples = max(int(length // args.spacing), 4)
        for j in range(n_samples):
            sample = boundary.interpolate(j * length / n_samples)
            best = None
            best_d = None
            had_candidate = False
            for k in tree.query(sample.buffer(args.snap_limit),
                                predicate="intersects"):
                line = lines[k]
                snap = line.interpolate(line.project(sample))
                distance = sample.distance(snap)
                if distance > args.snap_limit:
                    continue
                had_candidate = True
                if interior.contains(snap):
                    continue
                if best_d is None or distance < best_d:
                    best, best_d = snap, distance
            if best is None:
                if had_candidate:
                    n_rejected_inside += 1
                continue
            if any(best.distance(p) < args.dedupe for p in kept):
                continue
            kept.append(best)
            n_snap += 1
            points.append({"zone": sid, "method": "snap",
                           "side": "outside", "snap_m": round(best_d, 1),
                           "geometry": best})
            links.append({"zone": sid, "snap_m": round(best_d, 1),
                          "geometry": LineString([sample, best])})

        summary.append({
            "zone": sid, "n_crossing": n_cross, "n_snap": n_snap,
            "n_rejected_inside": n_rejected_inside,
            "method": ("crossing" if n_cross and not n_snap else
                       "snap" if n_snap and not n_cross else
                       "both" if n_cross else "UNREACHABLE"),
        })

    points_gdf = gpd.GeoDataFrame(pd.DataFrame(points), crs=network.crs)
    points_gdf = points_gdf.rename(columns={"zone": args.id_field})
    summary_df = pd.DataFrame(summary)
    unreachable = summary_df[summary_df["method"] == "UNREACHABLE"]

    args.out.parent.mkdir(parents=True, exist_ok=True)
    points_gdf.to_file(args.out, layer="points", driver="GPKG")
    if links:
        gpd.GeoDataFrame(pd.DataFrame(links), crs=network.crs).to_file(
            args.out, layer="links", driver="GPKG")
    zones_out = zones.merge(
        summary_df.rename(columns={"zone": args.id_field}),
        on=args.id_field, how="left")
    zones_out.to_file(args.out, layer="zones_summary", driver="GPKG")

    write_manifest(
        args.out.with_suffix(".manifest.json"),
        [{
            "step": "zone_edge_origins",
            "parameters": {
                "zones": str(args.zones), "id_field": args.id_field,
                "network": str(args.network),
                "network_classes": args.network_classes,
                "spacing_m": args.spacing,
                "snap_limit_m": args.snap_limit,
                "inside_tolerance_m": args.inside_tolerance,
                "dedupe_m": args.dedupe,
                "crs": crs.to_string(),
            },
            "results": {
                "zones": len(zones),
                "points_total": len(points_gdf),
                "crossing_points": int(
                    (points_gdf["method"] == "crossing").sum()),
                "snap_points": int((points_gdf["method"] == "snap").sum()),
                "samples_rejected_inside": int(
                    summary_df["n_rejected_inside"].sum()),
                "zones_unreachable": unreachable["zone"].tolist(),
            },
            "output": {"gpkg": str(args.out)},
        }],
        [args.zones, args.network],
    )

    print(f"Origin points written: {args.out} layer=points "
          f"({len(points_gdf)} points for {len(zones)} zones)")
    print(f"Crossing points: {int((points_gdf['method'] == 'crossing').sum())}; "
          f"fallback snap points (outside only): "
          f"{int((points_gdf['method'] == 'snap').sum())}")
    print(f"Boundary samples rejected (inside streets only): "
          f"{int(summary_df['n_rejected_inside'].sum())}")
    print(f"Unreachable zones: {len(unreachable)} "
          f"{unreachable['zone'].tolist() if len(unreachable) else ''}")
    print("Audit layers: links (sample->snap), zones_summary")
    return 0


if __name__ == "__main__":
    sys.exit(main())
