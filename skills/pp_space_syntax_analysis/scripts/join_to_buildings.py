"""CLI: join segment-level results (catchment or space syntax) to buildings.

Spatial input/output: building polygons GeoPackage (any projected CRS;
reprojected to match) + segment results GeoPackage in, buildings with
joined value columns out (written in the results CRS).
Data layer: analysis.

Examples:
    # Catchment values onto buildings
    python scripts/join_to_buildings.py `
        --buildings buildings_landuse.gpkg --buildings-layer buildings_landuse `
        --results outputs/catchment.gpkg --results-layer catchment `
        --columns drive_time_min,band --out outputs/buildings_catchment.gpkg

    # All space syntax columns onto buildings
    python scripts/join_to_buildings.py `
        --buildings buildings_landuse.gpkg --buildings-layer buildings_landuse `
        --results outputs/ssx_results.gpkg --results-layer ssx_results `
        --columns all --out outputs/buildings_ssx.gpkg
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pp_space_syntax.building_join import (  # noqa: E402
    EXCLUDE_CLASSES_DEFAULT,
    join_to_buildings,
)
from pp_space_syntax.manifest import write_manifest  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--buildings", type=Path, required=True, help="Building polygons GeoPackage")
    parser.add_argument("--buildings-layer", default=None, help="Layer name (default: only layer)")
    parser.add_argument("--results", type=Path, required=True, help="Segment results GeoPackage")
    parser.add_argument("--results-layer", default=None, help="Layer name (default: only layer)")
    parser.add_argument(
        "--columns", default="all",
        help="Comma-separated result columns to carry, or 'all' (default)",
    )
    parser.add_argument(
        "--max-distance", type=float, default=100.0,
        help="Join tolerance in metres; buildings farther from every "
             "segment get NULL values (default 100)",
    )
    parser.add_argument(
        "--exclude-classes", default=",".join(EXCLUDE_CLASSES_DEFAULT),
        help="highway classes removed from join candidates when the results "
             "layer has a highway column (default: motorway,motorway_link); "
             "pass an empty string to disable",
    )
    parser.add_argument("--out", type=Path, required=True, help="Output GeoPackage path")
    parser.add_argument("--out-layer", default="buildings_joined", help="Output layer name")
    parser.add_argument("--manifest", type=Path, default=None, help="Manifest JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    summary = join_to_buildings(
        buildings_gpkg=args.buildings,
        buildings_layer=args.buildings_layer,
        results_gpkg=args.results,
        results_layer=args.results_layer,
        out_gpkg=args.out,
        out_layer=args.out_layer,
        columns=args.columns,
        max_distance=args.max_distance,
        exclude_classes=tuple(
            c.strip() for c in args.exclude_classes.split(",") if c.strip()
        ),
    )

    manifest_path = args.manifest or args.out.with_suffix(".manifest.json")
    write_manifest(manifest_path, [summary], [args.buildings, args.results])

    res = summary["results"]
    print(f"Buildings joined: {res['joined']} of {res['polygon_buildings']} "
          f"({res['beyond_tolerance']} beyond tolerance)")
    print(f"Median join distance: {res['join_dist_m_median']} m")
    print(f"Output: {args.out} layer={args.out_layer}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
