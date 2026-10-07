"""PST result column naming.

Spatial input/output: none — string handling only, CRS-agnostic.
Data layer: analysis (output schema).

Mirrors the naming convention in the vendored plugin's
``pst/analyses/columnnaming.py`` so that headless results are directly
comparable with results produced by the PST QGIS plugin. Examples:
``ACw400C`` = Angular Choice, walking radius 400 m, NACH;
``AIw10kA`` = Angular Integration, walking radius 10 km, NAIN;
suffixes ``N`` / ``D`` / ``M`` = node count / total depth / mean depth.
"""
from __future__ import annotations

ANALYSIS_PREFIX = {
    "choice": "AC",
    "integration": "AI",
}

RADIUS_PREFIX = {
    "metric": "w",  # walking (network metric) distance
    "angular": "a",
    "topological": "s",  # axial/segment steps
}

# Normalisation suffixes, matching the plugin exactly. Note the plugin
# inconsistency preserved deliberately: Angular Integration's
# "Normalization (Turner 2007)" carries NO suffix, whereas Angular
# Choice's raw (no normalisation) output carries no suffix and its
# Turner-normalised output is suffixed "T".
CHOICE_NORM_SUFFIX = {
    "none": "",
    "turner": "T",
    "standard": "S",
    "nach": "C",
}
INTEGRATION_NORM_SUFFIX = {
    "turner": "",
    "nain": "A",
    "hillier": "H",
}

EXTRA_SUFFIX = {
    "node_count": "N",
    "total_depth": "D",
    "mean_depth": "M",
}


def format_radius_value(value: float) -> str:
    """Format a radius value as PST does: 10000 -> '10k', 1200 -> '1200'."""
    value = int(value)
    if value > 0 and value % 1000 == 0:
        return f"{value // 1000}k"
    return str(value)


def radius_token(radius_type: str, value: float) -> str:
    """Return the radius token, e.g. ('metric', 400) -> 'w400'."""
    return RADIUS_PREFIX[radius_type] + format_radius_value(value)


def score_column(analysis: str, radius_type: str, radius_value: float, normalisation: str) -> str:
    """Column name for a centrality score."""
    suffix_map = CHOICE_NORM_SUFFIX if analysis == "choice" else INTEGRATION_NORM_SUFFIX
    return (
        ANALYSIS_PREFIX[analysis]
        + radius_token(radius_type, radius_value)
        + suffix_map[normalisation]
    )


def extra_column(analysis: str, radius_type: str, radius_value: float, extra: str) -> str:
    """Column name for an extra statistic (node count, total/mean depth)."""
    return (
        ANALYSIS_PREFIX[analysis]
        + radius_token(radius_type, radius_value)
        + EXTRA_SUFFIX[extra]
    )
