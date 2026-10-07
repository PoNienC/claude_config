"""Coordinate reference system validation.

Spatial input/output: validates any user-supplied CRS; analyses require a
projected, metre-based CRS (the tool is not UK-specific — EPSG:27700,
EPSG:3035, EPSG:5070 or any other projected metre CRS are all acceptable).
Data layer: preprocessing.
"""
from __future__ import annotations

from pyproj import CRS

METRE_UNIT_NAMES = {"metre", "meter", "metres", "meters"}


class CrsValidationError(ValueError):
    """Raised when a CRS is unsuitable for space syntax analysis."""


def validate_metric_crs(crs_input: object) -> CRS:
    """Return the CRS if it is projected with metre units, else raise.

    Accepts anything ``pyproj.CRS.from_user_input`` accepts (EPSG code,
    "EPSG:27700" string, WKT, or an existing CRS object).
    """
    if crs_input is None:
        raise CrsValidationError(
            "The layer has no CRS. Supply one explicitly (e.g. --assume-crs "
            "EPSG:27700) after confirming what the coordinates really are."
        )
    crs = CRS.from_user_input(crs_input)
    if not crs.is_projected:
        raise CrsValidationError(
            f"CRS '{crs.name}' is not a projected CRS. Distances and angles "
            "are meaningless in geographic coordinates — reproject the "
            "network to a projected, metre-based CRS first."
        )
    unit_names = {axis.unit_name.lower() for axis in crs.axis_info}
    if not unit_names & METRE_UNIT_NAMES:
        raise CrsValidationError(
            f"CRS '{crs.name}' uses units {sorted(unit_names)}, not metres. "
            "Metric radii require a metre-based CRS."
        )
    return crs


def assert_expected_crs(actual: CRS, expected_input: object) -> None:
    """Raise if the layer CRS does not match the CRS the user expects."""
    expected = CRS.from_user_input(expected_input)
    if not actual.equals(expected):
        raise CrsValidationError(
            f"Layer CRS is '{actual.name}' but '{expected.name}' was "
            "expected. Reproject the input or correct the expected CRS."
        )
