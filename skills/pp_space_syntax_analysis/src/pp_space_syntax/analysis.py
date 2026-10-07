"""Angular segment analysis driver — Choice and Integration over multiple radii.

Spatial input/output: GeoPackage segment map layer in, GeoPackage results
layer out (same geometry, new columns), in the input's projected metre CRS.
Data layer: analysis.

Replicates the PST QGIS plugin's Angular Choice and Angular Integration
analyses (vendor ``pst/analyses/angularchoiceanalysis.py`` and
``angularintegrationanalysis.py``): one full analysis pass per radius,
normalisations computed by pstalgo's own functions, and N / TD / MD
(mean depth = total depth / (node count - 1)) as extra outputs.
"""
from __future__ import annotations

import array
import logging
from dataclasses import dataclass, field
from pathlib import Path

from . import naming
from .crs import validate_metric_crs
from .network_io import read_segments, write_lines
from .pstalgo_loader import import_pstalgo

logger = logging.getLogger(__name__)

ANALYSES = ("choice", "integration")
COSTS = ("angular", "metric", "topological")
RADIUS_TYPES = ("metric", "angular", "topological")

DEFAULT_RADII = (400.0, 800.0, 1200.0, 2000.0, 5000.0, 10000.0, 20000.0)


@dataclass
class AnalysisOptions:
    """Run configuration. Defaults follow the agreed P+P standard set."""

    analyses: tuple[str, ...] = ANALYSES
    cost: str = "angular"
    radius_type: str = "metric"
    radii: tuple[float, ...] = DEFAULT_RADII
    angle_precision: int = 1
    angle_threshold: float = 0.0
    choice_normalisations: tuple[str, ...] = ("none", "nach")
    integration_normalisations: tuple[str, ...] = ("nain", "hillier")
    output_node_count: bool = True
    output_total_depth: bool = True
    output_mean_depth: bool = True

    def validate(self) -> None:
        unknown = set(self.analyses) - set(ANALYSES)
        if unknown:
            raise ValueError(f"Unknown analyses: {sorted(unknown)}")
        if self.cost not in COSTS:
            raise ValueError(f"cost must be one of {COSTS}")
        if self.cost != "angular":
            raise NotImplementedError(
                f"Cost '{self.cost}' is not implemented yet. The current "
                "release covers the default angular cost; metric and "
                "topological costs are planned (pstalgo's "
                "FastSegmentBetweenness and NetworkIntegration)."
            )
        if self.radius_type not in RADIUS_TYPES:
            raise ValueError(f"radius_type must be one of {RADIUS_TYPES}")
        if not self.radii:
            raise ValueError("At least one radius is required.")
        unknown = set(self.choice_normalisations) - set(naming.CHOICE_NORM_SUFFIX)
        if unknown:
            raise ValueError(f"Unknown choice normalisations: {sorted(unknown)}")
        unknown = set(self.integration_normalisations) - set(naming.INTEGRATION_NORM_SUFFIX)
        if unknown:
            raise ValueError(f"Unknown integration normalisations: {sorted(unknown)}")


@dataclass
class _ResultColumns:
    names: list[str] = field(default_factory=list)
    values: dict[str, list] = field(default_factory=dict)

    def add(self, name: str, data: list) -> None:
        if name in self.values:
            raise ValueError(f"Duplicate result column '{name}'.")
        self.names.append(name)
        self.values[name] = data


def _make_radius(pstalgo, radius_type: str, value: float):
    if radius_type == "metric":
        return pstalgo.Radii(walking=value)
    if radius_type == "angular":
        return pstalgo.Radii(angular=value)
    if radius_type == "topological":
        return pstalgo.Radii(steps=int(value))
    raise ValueError(f"Unknown radius type '{radius_type}'.")


def _mean_depth(total_depths: array.array, node_counts: array.array) -> list[float]:
    # Origin line is included in the node count, hence N - 1.
    return [
        td / (n - 1) if n > 1 else 0.0
        for td, n in zip(total_depths, node_counts)
    ]


def _zeros_f(n: int) -> array.array:
    return array.array("f", bytes(4 * n))


def _zeros_u(n: int) -> array.array:
    return array.array("I", bytes(4 * n))


def _run_choice_at_radius(
    pstalgo, graph, options: AnalysisOptions, radius_value: float, n: int, columns: _ResultColumns
) -> None:
    radius = _make_radius(pstalgo, options.radius_type, radius_value)
    scores = _zeros_f(n)
    node_counts = _zeros_u(n)
    total_depths = _zeros_f(n)
    pstalgo.AngularChoice(
        graph_handle=graph,
        radius=radius,
        weigh_by_length=False,
        angle_threshold=options.angle_threshold,
        angle_precision=options.angle_precision,
        out_choice=scores,
        out_node_count=node_counts,
        out_total_depth=total_depths,
    )
    rt, rv = options.radius_type, radius_value
    for norm in options.choice_normalisations:
        name = naming.score_column("choice", rt, rv, norm)
        if norm == "none":
            columns.add(name, list(scores))
        elif norm == "turner":
            out = _zeros_f(n)
            pstalgo.AngularChoiceNormalize(scores, node_counts, n, out)
            columns.add(name, list(out))
        elif norm == "standard":
            out = _zeros_f(n)
            pstalgo.StandardNormalize(scores, n, out)
            columns.add(name, list(out))
        elif norm == "nach":
            out = _zeros_f(n)
            pstalgo.AngularChoiceSyntaxNormalize(scores, total_depths, n, out)
            columns.add(name, list(out))
    if options.output_node_count:
        columns.add(naming.extra_column("choice", rt, rv, "node_count"), list(node_counts))
    if options.output_total_depth:
        columns.add(naming.extra_column("choice", rt, rv, "total_depth"), list(total_depths))
    if options.output_mean_depth:
        columns.add(
            naming.extra_column("choice", rt, rv, "mean_depth"),
            _mean_depth(total_depths, node_counts),
        )


def _run_integration_at_radius(
    pstalgo, graph, options: AnalysisOptions, radius_value: float, n: int, columns: _ResultColumns
) -> None:
    radius = _make_radius(pstalgo, options.radius_type, radius_value)
    node_counts = _zeros_u(n)
    total_depths = _zeros_f(n)
    pstalgo.AngularIntegration(
        graph_handle=graph,
        radius=radius,
        weigh_by_length=False,
        angle_threshold=options.angle_threshold,
        angle_precision=options.angle_precision,
        out_node_counts=node_counts,
        out_total_depths=total_depths,
    )
    rt, rv = options.radius_type, radius_value
    for norm in options.integration_normalisations:
        name = naming.score_column("integration", rt, rv, norm)
        out = _zeros_f(n)
        if norm == "turner":
            pstalgo.AngularIntegrationNormalize(node_counts, total_depths, n, out)
        elif norm == "nain":
            pstalgo.AngularIntegrationSyntaxNormalize(node_counts, total_depths, n, out)
        elif norm == "hillier":
            pstalgo.AngularIntegrationHillierNormalize(node_counts, total_depths, n, out)
        columns.add(name, list(out))
    if options.output_node_count:
        columns.add(naming.extra_column("integration", rt, rv, "node_count"), list(node_counts))
    if options.output_total_depth:
        columns.add(naming.extra_column("integration", rt, rv, "total_depth"), list(total_depths))
    if options.output_mean_depth:
        columns.add(
            naming.extra_column("integration", rt, rv, "mean_depth"),
            _mean_depth(total_depths, node_counts),
        )


def run_analysis(
    segment_gpkg: Path,
    out_gpkg: Path,
    out_layer: str,
    segment_layer: str | None = None,
    options: AnalysisOptions | None = None,
) -> dict:
    """Run the configured analyses over all radii and write the results layer.

    Returns a summary dictionary for the reproducibility manifest.
    """
    options = options or AnalysisOptions()
    options.validate()
    pstalgo = import_pstalgo()

    segments = read_segments(segment_gpkg, segment_layer)
    crs = validate_metric_crs(segments.crs)
    n = segments.segment_count

    columns = _ResultColumns()
    graph = pstalgo.CreateSegmentGraph(segments.line_coords, None, None)
    try:
        for radius_value in options.radii:
            logger.info(
                "Radius %s %s: running %s",
                naming.radius_token(options.radius_type, radius_value),
                options.cost,
                ", ".join(options.analyses),
            )
            if "choice" in options.analyses:
                _run_choice_at_radius(pstalgo, graph, options, radius_value, n, columns)
            if "integration" in options.analyses:
                _run_integration_at_radius(pstalgo, graph, options, radius_value, n, columns)
    finally:
        pstalgo.FreeSegmentGraph(graph)

    frame = segments.frame.copy()
    for name in columns.names:
        frame[name] = columns.values[name]
    attributes = {c: frame[c].tolist() for c in frame.columns if c != frame.geometry.name}
    write_lines(out_gpkg, out_layer, list(frame.geometry), attributes, crs)

    summary = {
        "step": "angular_segment_analysis",
        "segment_gpkg": str(segment_gpkg),
        "segment_layer": segment_layer,
        "segment_count": n,
        "crs": crs.to_string(),
        "options": {
            "analyses": list(options.analyses),
            "cost": options.cost,
            "radius_type": options.radius_type,
            "radii": list(options.radii),
            "angle_precision": options.angle_precision,
            "angle_threshold": options.angle_threshold,
            "choice_normalisations": list(options.choice_normalisations),
            "integration_normalisations": list(options.integration_normalisations),
        },
        "out_gpkg": str(out_gpkg),
        "out_layer": out_layer,
        "result_columns": columns.names,
    }
    logger.info("Analysis complete: %d result columns on %d segments", len(columns.names), n)
    return summary
