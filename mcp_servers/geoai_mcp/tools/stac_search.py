"""
Tool: geoai_stac_search

Search the Microsoft Planetary Computer STAC catalogue for satellite
or aerial imagery matching a bbox, datetime range, and collection.

See server-level docstring in `crs_info.py` for the rationale common
to all tools. This one demonstrates the realistic pattern for any
"search a catalogue and return paginated results" tool — same shape
works for Overture Maps API, NASA Earthdata CMR, OpenAerialMap, and
commercial imagery vendors.

The tool returns up to 50 STAC Items per call. For larger result
sets, use the bbox subdivision pattern: split the bbox into
quadrants and query each. The LLM orchestrates this from the agent
layer.
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field, ConfigDict, field_validator

from server import mcp


class STACSearchInput(BaseModel):
    """Inputs for `geoai_stac_search`."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    collection: str = Field(
        ...,
        description=(
            "STAC collection ID. Common values: "
            "'sentinel-2-l2a' (Sentinel-2 surface reflectance), "
            "'sentinel-1-rtc' (Sentinel-1 SAR), "
            "'landsat-c2-l2' (Landsat Collection 2 Level 2), "
            "'naip' (US aerial 1m), "
            "'cop-dem-glo-30' (Copernicus 30m DEM)."
        ),
        min_length=1, max_length=100,
    )
    bbox_west: float = Field(..., ge=-180, le=180,
        description="Western longitude in WGS84 decimal degrees.")
    bbox_south: float = Field(..., ge=-90, le=90,
        description="Southern latitude in WGS84 decimal degrees.")
    bbox_east: float = Field(..., ge=-180, le=180,
        description="Eastern longitude in WGS84 decimal degrees.")
    bbox_north: float = Field(..., ge=-90, le=90,
        description="Northern latitude in WGS84 decimal degrees.")

    datetime_start: Optional[str] = Field(
        default=None,
        description=(
            "Start of datetime range, ISO 8601 (e.g. '2024-06-01' "
            "or '2024-06-01T00:00:00Z'). Inclusive. Omit for no "
            "lower bound."
        ),
    )
    datetime_end: Optional[str] = Field(
        default=None,
        description=(
            "End of datetime range, ISO 8601. Inclusive. Omit for "
            "no upper bound."
        ),
    )
    max_items: int = Field(
        default=10,
        description="Maximum number of items to return (1-50).",
        ge=1, le=50,
    )
    cloud_cover_max: Optional[int] = Field(
        default=None,
        description=(
            "Optional maximum cloud cover percentage (0-100). Only "
            "applies to optical collections that publish "
            "eo:cloud_cover. Ignored for SAR and DEM collections."
        ),
        ge=0, le=100,
    )

    @field_validator("bbox_east")
    @classmethod
    def _east_greater_than_west(cls, v: float, info) -> float:
        west = info.data.get("bbox_west")
        if west is not None and v <= west:
            raise ValueError(
                f"bbox_east ({v}) must be greater than bbox_west "
                f"({west}). If your bbox crosses the antimeridian, "
                "split into two queries."
            )
        return v

    @field_validator("bbox_north")
    @classmethod
    def _north_greater_than_south(cls, v: float, info) -> float:
        south = info.data.get("bbox_south")
        if south is not None and v <= south:
            raise ValueError(
                f"bbox_north ({v}) must be greater than "
                f"bbox_south ({south})."
            )
        return v


@mcp.tool(
    name="geoai_stac_search",
    annotations={
        "title": "Search STAC catalogue (Microsoft Planetary Computer)",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def geoai_stac_search(params: STACSearchInput) -> dict:
    """Search Microsoft Planetary Computer STAC for matching imagery.

    Returns up to `max_items` STAC Items with their IDs, datetime,
    geometry, and signed asset URLs ready for download. Items are
    sorted most-recent-first.

    Note on signed URLs: Planetary Computer issues short-lived signed
    URLs (typically 1 hour). Pass the returned URLs to download
    tooling promptly; do not store them long-term.

    Args:
        params: Validated bbox, collection, datetime, and filters.

    Returns:
        Dict with collection, counts, and items list — or an error
        envelope on failure.
    """
    try:
        from pystac_client import Client
        import planetary_computer
    except ImportError:
        return {
            "error": (
                "pystac-client and planetary-computer not "
                "installed. Run: pip install pystac-client "
                "planetary-computer"
            ),
            "code": "DEPENDENCY_MISSING",
        }

    bbox = [params.bbox_west, params.bbox_south,
            params.bbox_east, params.bbox_north]

    datetime_range: Optional[str] = None
    if params.datetime_start and params.datetime_end:
        datetime_range = f"{params.datetime_start}/{params.datetime_end}"
    elif params.datetime_start:
        datetime_range = f"{params.datetime_start}/.."
    elif params.datetime_end:
        datetime_range = f"../{params.datetime_end}"

    query: Optional[dict] = None
    if params.cloud_cover_max is not None:
        query = {"eo:cloud_cover": {"lt": params.cloud_cover_max}}

    try:
        catalog = Client.open(
            "https://planetarycomputer.microsoft.com/api/stac/v1",
            modifier=planetary_computer.sign_inplace,
        )
        search = catalog.search(
            collections=[params.collection],
            bbox=bbox,
            datetime=datetime_range,
            query=query,
            max_items=params.max_items,
        )
        items = list(search.items())
    except Exception as exc:  # pylint: disable=broad-except
        return {
            "error": f"STAC search failed: {exc}",
            "code": "STAC_SEARCH_FAILED",
        }

    item_summaries = []
    for item in items:
        cloud_cover = item.properties.get("eo:cloud_cover")
        item_summaries.append({
            "id": item.id,
            "datetime": item.datetime.isoformat() if item.datetime else None,
            "bbox": list(item.bbox) if item.bbox else None,
            "cloud_cover": cloud_cover,
            "assets": {
                k: v.href
                for k, v in list(item.assets.items())[:6]
            },
        })

    return {
        "collection": params.collection,
        "returned_count": len(item_summaries),
        "matched_count": len(item_summaries),
        "items": item_summaries,
    }
