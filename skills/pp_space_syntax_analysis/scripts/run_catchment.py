"""CLI: vehicular (drive-time) or walking (metric) catchment from origins.

Spatial input/output: refined network GeoPackage in, catchment GeoPackage
out (segments with cost/band columns + snapped origins layer), in the
input's projected metre CRS.
Data layer: analysis.

Examples:
    python scripts/run_catchment.py --network refined.gpkg `
        --origin 544839,258505 --mode drive `
        --speed-profile reference/speed_profiles/osrm_car_default.csv `
        --out outputs/catchment.gpkg --expected-crs EPSG:27700

    python scripts/run_catchment.py --network refined.gpkg `
        --origin 544839,258505 --mode walk --bands 400,800,1200 `
        --out outputs/walk_catchment.gpkg --expected-crs EPSG:27700
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import geopandas as gpd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pp_space_syntax.catchment import (  # noqa: E402
    DRIVE_BANDS_DEFAULT,
    MODES,
    WALK_BANDS_DEFAULT,
    origins_from_layer,
    run_catchment,
)
from pp_space_syntax.crs import assert_expected_crs, validate_metric_crs  # noqa: E402
from pp_space_syntax.manifest import write_manifest  # noqa: E402

DEFAULT_SPEED_PROFILE = (
    Path(__file__).resolve().parents[1]
    / "reference" / "speed_profiles" / "osrm_car_default.csv"
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", type=Path, required=True, help="Refined network GeoPackage")
    parser.add_argument("--network-layer", default=None, help="Layer name (default: only layer)")
    parser.add_argument("--unlinks", type=Path, default=None, help="Unlinks point GeoPackage")
    parser.add_argument("--unlinks-layer", default=None, help="Unlinks layer name")
    parser.add_argument(
        "--origin", action="append", default=None, metavar="X,Y",
        help="Origin coordinate in the network CRS; repeat for multiple origins",
    )
    parser.add_argument(
        "--origins-layer", type=Path, default=None,
        help="Point or polygon GeoPackage to take origins from (polygons "
             "contribute their representative point); reprojected to the "
             "network CRS if needed",
    )
    parser.add_argument("--origins-layer-name", default=None, help="Layer name (default: only layer)")
    parser.add_argument(
        "--origins-where", default=None,
        help="pandas query filter on the origins layer, e.g. "
             "\"landuse_type == 'education'\" or "
             "\"landuse_types_all.str.contains('cafe', na=False)\"",
    )
    parser.add_argument(
        "--group-by", default=None,
        help="Column of the origins layer that labels origin groups; runs "
             "one catchment per group (one cost column each) on a shared "
             "graph, plus per-band counts of groups reached",
    )
    parser.add_argument("--mode", choices=MODES, default="drive", help="drive or walk")
    parser.add_argument(
        "--speed-profile", type=Path, default=DEFAULT_SPEED_PROFILE,
        help="Speed profile CSV for drive mode (default: OSRM car profile)",
    )
    parser.add_argument(
        "--speed-column", default=None,
        help="Network column with a per-segment speed in km/h; takes "
             "precedence over the profile lookup where non-null",
    )
    parser.add_argument(
        "--class-column", default="highway",
        help="Network column carrying the street class (default: highway)",
    )
    def positive(text: str) -> float:
        value = float(text)
        if value <= 0:
            raise argparse.ArgumentTypeError("must be a positive number")
        return value

    parser.add_argument(
        "--walk-speed", type=positive, default=None,
        help="Flat walking speed in km/h; walk mode then also outputs "
             "minutes columns",
    )
    parser.add_argument(
        "--max-snap", type=positive, default=None,
        help="Drop origins further than this many metres from the main "
             "network component (dropped origins go to the audit layer)",
    )
    parser.add_argument(
        "--bands", default=None,
        help=(
            "Comma-separated thresholds: minutes in drive mode "
            f"(default {','.join(str(int(b)) for b in DRIVE_BANDS_DEFAULT)}), "
            f"metres in walk mode (default "
            f"{','.join(str(int(b)) for b in WALK_BANDS_DEFAULT)})"
        ),
    )
    parser.add_argument(
        "--network-classes", default=None,
        help="Override network_class filter (default: drive,drive_walk for "
             "drive mode; drive_walk,walk_only for walk mode)",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output GeoPackage path")
    parser.add_argument("--out-layer", default="catchment", help="Output layer name")
    parser.add_argument(
        "--expected-crs", default=None,
        help="Fail unless the network CRS matches (e.g. EPSG:27700)",
    )
    parser.add_argument("--manifest", type=Path, default=None, help="Manifest JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    crs = validate_metric_crs(
        gpd.read_file(args.network, layer=args.network_layer, rows=1).crs
    )
    if args.expected_crs:
        assert_expected_crs(crs, args.expected_crs)
    logging.info("Working CRS confirmed: %s", crs.to_string())

    if not args.origin and not args.origins_layer:
        raise SystemExit(
            "Provide origins via --origin X,Y (repeatable) and/or "
            "--origins-layer <gpkg>."
        )
    origins_xy = []
    origin_groups: list[str] = []
    origins_selection = None
    for part in args.origin or []:
        x_text, y_text = part.split(",")
        origins_xy.append((float(x_text), float(y_text)))
        origin_groups.append("all")
    if args.origins_layer:
        layer_coords, layer_groups, origins_selection = origins_from_layer(
            args.origins_layer, args.origins_layer_name,
            args.origins_where, crs, args.group_by,
        )
        origins_xy.extend(layer_coords)
        origin_groups.extend(layer_groups)

    summary = run_catchment(
        network_gpkg=args.network,
        network_layer=args.network_layer,
        out_gpkg=args.out,
        out_layer=args.out_layer,
        origins_xy=origins_xy,
        mode=args.mode,
        speed_profile_path=args.speed_profile if args.mode == "drive" else None,
        bands=(
            tuple(float(b) for b in args.bands.split(",")) if args.bands else None
        ),
        unlinks_gpkg=args.unlinks,
        unlinks_layer=args.unlinks_layer,
        network_classes=(
            tuple(c.strip() for c in args.network_classes.split(","))
            if args.network_classes else None
        ),
        class_column=args.class_column,
        speed_column=args.speed_column,
        walk_speed_kmh=args.walk_speed,
        origin_groups=origin_groups,
        max_snap_m=args.max_snap,
    )

    if origins_selection:
        summary["parameters"]["origins_selection"] = origins_selection

    manifest_path = args.manifest or args.out.with_suffix(".manifest.json")
    input_files = [args.network] + ([args.unlinks] if args.unlinks else [])
    if args.origins_layer:
        input_files.append(args.origins_layer)
    if args.mode == "drive":
        input_files.append(args.speed_profile)
    write_manifest(manifest_path, [summary], input_files)

    print(f"Catchment written: {args.out} layer={args.out_layer}")
    if summary["results"]["band_counts"] is not None:
        print(f"Band counts: {summary['results']['band_counts']}")
    else:
        print(f"Groups run: {len(summary['results']['per_group'])}")
    print(f"Largest component share: {summary['results']['largest_component_share']:.1%}")
    print(f"Origins dropped: {summary['results']['origins_dropped']}; "
          f"segments split: {summary['results']['segments_split_for_origins']}")
    offsets = [
        o for o, m in zip(
            summary["parameters"]["origin_snap_offsets_m"],
            summary["parameters"]["origin_snap_methods"],
        ) if m != "dropped"
    ]
    if offsets:
        median = sorted(offsets)[len(offsets) // 2]
        worst = max(offsets)
        print(f"Origin snap offsets: median {median:.1f} m, max {worst:.1f} m")
        if worst > max(10.0 * max(median, 1.0), 100.0):
            print("WARNING: at least one origin snapped much further than "
                  "the rest — check the origin_links audit layer in QGIS.")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
