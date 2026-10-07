"""CLI: run angular segment analysis (Choice / Integration) over multiple radii.

Spatial input/output: GeoPackage segment map layer in, GeoPackage results
layer out (same geometry plus result columns), in the input's projected
metre CRS.
Data layer: analysis.

Example (P+P default set):
    python scripts/run_analysis.py --gpkg outputs/segment_map.gpkg \
        --layer segments --out outputs/results.gpkg --out-layer ssx_results \
        --expected-crs EPSG:27700
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from pp_space_syntax.analysis import (  # noqa: E402
    ANALYSES,
    COSTS,
    DEFAULT_RADII,
    RADIUS_TYPES,
    AnalysisOptions,
    run_analysis,
)
from pp_space_syntax.crs import assert_expected_crs, validate_metric_crs  # noqa: E402
from pp_space_syntax.manifest import write_manifest  # noqa: E402
from pp_space_syntax.network_io import read_segments  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpkg", type=Path, required=True, help="Segment map GeoPackage path")
    parser.add_argument("--layer", default=None, help="Segment layer name (default: only layer)")
    parser.add_argument("--out", type=Path, required=True, help="Output GeoPackage path")
    parser.add_argument("--out-layer", required=True, help="Output results layer name")
    parser.add_argument(
        "--analyses", default="choice,integration",
        help=f"Comma-separated subset of {ANALYSES} (default: both)",
    )
    parser.add_argument(
        "--cost", choices=COSTS, default="angular",
        help="Distance mode for shortest paths (default: angular)",
    )
    parser.add_argument(
        "--radius-type", choices=RADIUS_TYPES, default="metric",
        help="Radius mode (default: metric, i.e. walking distance in metres)",
    )
    parser.add_argument(
        "--radii", default=",".join(str(int(r)) for r in DEFAULT_RADII),
        help="Comma-separated radii values (default: P+P standard set)",
    )
    parser.add_argument("--angle-precision", type=int, default=1, help="Degrees (default 1)")
    parser.add_argument("--angle-threshold", type=float, default=0.0, help="Degrees (default 0)")
    parser.add_argument(
        "--choice-norms", default="none,nach",
        help="Comma-separated: none, nach, turner, standard (default: none,nach)",
    )
    parser.add_argument(
        "--integration-norms", default="nain,hillier",
        help="Comma-separated: nain, hillier, turner (default: nain,hillier)",
    )
    parser.add_argument(
        "--expected-crs", default=None,
        help="Fail unless the layer CRS matches (e.g. EPSG:27700)",
    )
    parser.add_argument("--manifest", type=Path, default=None, help="Manifest JSON output path")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args = parse_args(argv)

    crs = validate_metric_crs(read_segments(args.gpkg, args.layer).crs)
    if args.expected_crs:
        assert_expected_crs(crs, args.expected_crs)
    logging.info("Working CRS confirmed: %s", crs.to_string())

    options = AnalysisOptions(
        analyses=tuple(s.strip() for s in args.analyses.split(",") if s.strip()),
        cost=args.cost,
        radius_type=args.radius_type,
        radii=tuple(float(s) for s in args.radii.split(",") if s.strip()),
        angle_precision=args.angle_precision,
        angle_threshold=args.angle_threshold,
        choice_normalisations=tuple(s.strip() for s in args.choice_norms.split(",") if s.strip()),
        integration_normalisations=tuple(
            s.strip() for s in args.integration_norms.split(",") if s.strip()
        ),
    )

    summary = run_analysis(
        segment_gpkg=args.gpkg,
        segment_layer=args.layer,
        out_gpkg=args.out,
        out_layer=args.out_layer,
        options=options,
    )

    manifest_path = args.manifest or args.out.with_suffix(".manifest.json")
    write_manifest(manifest_path, [summary], [args.gpkg])

    print(f"Results written: {args.out} layer={args.out_layer}")
    print(f"Columns added: {', '.join(summary['result_columns'])}")
    print(f"Manifest: {manifest_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
