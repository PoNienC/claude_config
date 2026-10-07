"""CLI: create a PST line-segment map from a network GeoPackage.

Spatial input/output: GeoPackage line layer (+ optional unlink points) in,
GeoPackage segment layer out, all in the input's projected metre CRS.
Data layer: preprocessing.

Example:
    python scripts/make_segment_map.py --network refined.gpkg \
        --network-layer drive_refined --unlinks refined.gpkg \
        --unlinks-layer unlinks --out outputs/segment_map.gpkg \
        --out-layer segments --expected-crs EPSG:27700
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pp_space_syntax.crs import assert_expected_crs, validate_metric_crs  # noqa: E402
from pp_space_syntax.manifest import write_manifest  # noqa: E402
from pp_space_syntax.network_io import read_polylines  # noqa: E402
from pp_space_syntax.segment_map import (  # noqa: E402
    NETWORK_TYPES,
    SegmentMapParams,
    create_segment_map,
)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--network", type=Path, required=True, help="Network GeoPackage path")
    parser.add_argument("--network-layer", default=None, help="Layer name (default: only layer)")
    parser.add_argument(
        "--network-type", choices=NETWORK_TYPES, default="axial_segment",
        help="axial_segment (default; supply unlinks) or rcl (derives unlinks)",
    )
    parser.add_argument("--unlinks", type=Path, default=None, help="Unlink points GeoPackage")
    parser.add_argument("--unlinks-layer", default=None, help="Unlinks layer name")
    parser.add_argument("--out", type=Path, required=True, help="Output GeoPackage path")
    parser.add_argument("--out-layer", required=True, help="Output segment layer name")
    parser.add_argument("--snap", type=float, default=1.0, help="Snap threshold in metres")
    parser.add_argument("--tail", type=float, default=10.0, help="Tail removal threshold in metres")
    parser.add_argument(
        "--deviation", type=float, default=1.0, help="Collinear merge deviation in metres"
    )
    parser.add_argument(
        "--copy-column", action="append", default=[],
        help="Source column to copy onto segments (repeatable)",
    )
    parser.add_argument(
        "--expected-crs", default=None,
        help="Fail unless the network layer CRS matches (e.g. EPSG:27700)",
    )
    parser.add_argument("--manifest", type=Path, default=None, help="Manifest JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    crs = validate_metric_crs(read_polylines(args.network, args.network_layer).crs)
    if args.expected_crs:
        assert_expected_crs(crs, args.expected_crs)
    logging.info("Working CRS confirmed: %s", crs.to_string())

    summary = create_segment_map(
        network_gpkg=args.network,
        network_layer=args.network_layer,
        network_type=args.network_type,
        unlinks_gpkg=args.unlinks,
        unlinks_layer=args.unlinks_layer,
        out_gpkg=args.out,
        out_layer=args.out_layer,
        params=SegmentMapParams(snap=args.snap, tail=args.tail, deviation=args.deviation),
        copy_columns=tuple(args.copy_column),
    )

    manifest_path = args.manifest or args.out.with_suffix(".manifest.json")
    inputs = [args.network] + ([args.unlinks] if args.unlinks else [])
    write_manifest(manifest_path, [summary], inputs)

    print(f"Segment map written: {args.out} layer={args.out_layer} "
          f"({summary['segment_count']} segments)")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
