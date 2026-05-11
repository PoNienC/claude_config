"""
Tool: geoai_get_crs_info

The simplest tool in this server. It takes an EPSG code (integer) and
returns human-readable metadata about that coordinate reference system.

WHY THIS TOOL EXISTS:
    The single biggest silent failure mode in geospatial AI work is
    CRS hallucination — the LLM confidently asserts that EPSG:32633
    is "WGS84 lat/lon" (it is not; it is UTM zone 33N projected
    metres) and proceeds to compute distances in degrees. By forcing
    the LLM to call a deterministic tool to fetch CRS metadata, we
    collapse this entire failure category. The tool is pure, fast,
    has no side effects.

WHY IT IS A GOOD FIRST TOOL TO READ:
    1. It is fully self-contained — no network, no filesystem, no async.
    2. It demonstrates the three pieces of every MCP tool:
        - Pydantic input model (validates arguments before execution)
        - @mcp.tool decorator (registers tool with the server)
        - Async function with docstring (becomes the LLM-readable schema)
    3. The error-handling pattern shown here repeats across every
       other tool in the server.
"""

from pydantic import BaseModel, Field, ConfigDict
from pyproj import CRS
from pyproj.exceptions import CRSError

# Import the singleton FastMCP instance from server.py. Because
# settings.json sets PYTHONPATH to the geoai_mcp directory, this is
# a plain top-level import.
from server import mcp


# ---------------------------------------------------------------------------
# Input model
# ---------------------------------------------------------------------------
class CRSInfoInput(BaseModel):
    """Inputs for `geoai_get_crs_info`."""

    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra="forbid",
    )

    epsg_code: int = Field(
        ...,
        description=(
            "Integer EPSG code identifying the CRS. Examples: "
            "4326 (WGS84 geographic), "
            "3857 (Web Mercator), "
            "27700 (British National Grid), "
            "32633 (UTM zone 33N), "
            "5070 (NAD83 CONUS Albers Equal Area). "
            "Must be a positive integer; will be validated against "
            "the EPSG registry."
        ),
        ge=1024,
        le=999999,
    )


# ---------------------------------------------------------------------------
# Tool implementation
# ---------------------------------------------------------------------------
@mcp.tool(
    name="geoai_get_crs_info",
    annotations={
        "title": "Get CRS metadata",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def geoai_get_crs_info(params: CRSInfoInput) -> dict:
    """Look up human-readable metadata for a CRS by EPSG code.

    Returns the CRS name, datum, units, geographic-vs-projected
    status, and area of valid use. Use this BEFORE any reprojection
    if there is any uncertainty about the target CRS — it is the
    cheap deterministic check that prevents the entire class of
    CRS-hallucination errors.

    The implementation calls `pyproj.CRS.from_epsg(...)` which
    queries the bundled EPSG database. No network access required.

    Args:
        params: Validated input containing the EPSG code.

    Returns:
        A JSON-serialisable dictionary with the CRS metadata, OR an
        error envelope `{"error": "...", "code": "..."}` if the code
        is not found in the registry. The error case is recoverable
        — the LLM can present the error to the user and ask for
        clarification rather than the tool raising an exception that
        aborts the call.
    """
    try:
        crs = CRS.from_epsg(params.epsg_code)
    except CRSError as exc:
        return {
            "error": f"EPSG:{params.epsg_code} not found in registry",
            "code": "EPSG_NOT_FOUND",
            "details": str(exc),
        }

    area_of_use = None
    if crs.area_of_use is not None:
        area_of_use = {
            "name": crs.area_of_use.name,
            "bbox_west": crs.area_of_use.west,
            "bbox_south": crs.area_of_use.south,
            "bbox_east": crs.area_of_use.east,
            "bbox_north": crs.area_of_use.north,
        }

    primary_unit = (
        crs.axis_info[0].unit_name if crs.axis_info else "unknown"
    )

    return {
        "epsg": params.epsg_code,
        "name": crs.name,
        "is_geographic": crs.is_geographic,
        "is_projected": crs.is_projected,
        "datum": crs.datum.name if crs.datum else None,
        "primary_unit": primary_unit,
        "area_of_use": area_of_use,
        "recommendation": _recommend_use(crs),
    }


def _recommend_use(crs: CRS) -> str:
    """Editorial recommendation about appropriate use of this CRS.

    Opinionated; reflects the CLAUDE.md spatial discipline. Adjust
    as your conventions evolve.
    """
    if crs.is_geographic:
        return (
            "Geographic CRS in degrees. Suitable for storage, "
            "exchange, and tile keys. UNSUITABLE for distance, "
            "area, or buffer calculations — reproject to a "
            "projected CRS first."
        )
    if crs.to_epsg() == 3857:
        return (
            "Web Mercator. Suitable for web tile output ONLY. "
            "Distorts area and shape badly above 60 degrees "
            "latitude — do not use for analysis."
        )
    if "albers" in crs.name.lower() or "lambert" in crs.name.lower():
        return (
            "Equal-area or conformal projected CRS. Suitable for "
            "regional analysis within its area of use."
        )
    return (
        "Projected CRS. Suitable for distance and area "
        "calculations within its area of use."
    )
