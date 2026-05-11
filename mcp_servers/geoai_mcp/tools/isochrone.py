"""
Tool: geoai_calculate_isochrone

Compute an isochrone polygon — the geographic area reachable from a
point within a given travel time, by a given mode of transport.

WHY THIS TOOL EXISTS:
    Isochrones are the primitive of accessibility analysis. Given an
    origin and a budget (e.g. 15 minutes by foot), they answer "what
    can a person reach?" — which underpins 15-minute-city evaluation,
    service-area auditing, hub-and-spoke logistics, last-mile
    coverage. Without a typed isochrone tool, the LLM tends to either
    invent a Euclidean buffer (wrong because it ignores the road
    network) or dump a 50-line OSMnx script that the user has to run
    themselves.

WHY READ THIS TOOL SECOND:
    Unlike `geoai_get_crs_info`, this tool:
        1. Performs network I/O (it can call a routing service).
        2. Demonstrates backend dispatch (local engine vs cloud API).
        3. Shows the use of Literal-typed parameters to lock the LLM
           out of inventing modes ("teleport", "rocket", etc.).
        4. Includes the sensitive-zone check (a safety hook in code).

ROUTING ENGINES:
    The implementation below is intentionally pluggable. The default
    backend uses a public OSRM demo endpoint for read-only testing —
    do not use it for production load. For real work, choose one of:
        - OSRM (self-host the docker image)
        - Valhalla (self-host; supports walking/cycling/driving/transit)
        - GraphHopper (self-host or hosted)
        - Mapbox / OpenRouteService (commercial APIs)
    Switch backends by setting GEOAI_ROUTING_ENGINE env var.
"""

from __future__ import annotations

import os
from typing import Literal

import httpx
from pydantic import BaseModel, Field, ConfigDict

from server import mcp
from safety.sensitive_zones import is_inside_sensitive_zone


class IsochroneInput(BaseModel):
    """Inputs for `geoai_calculate_isochrone`."""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    origin_lon: float = Field(
        ...,
        description="Origin longitude in WGS84 (EPSG:4326), decimal degrees.",
        ge=-180.0, le=180.0,
    )
    origin_lat: float = Field(
        ...,
        description="Origin latitude in WGS84 (EPSG:4326), decimal degrees.",
        ge=-90.0, le=90.0,
    )
    travel_minutes: int = Field(
        ...,
        description=(
            "Travel-time budget in minutes. Practical range 1-60. "
            "Larger budgets produce very large polygons and may "
            "exceed engine limits."
        ),
        ge=1, le=120,
    )
    mode: Literal["walking", "cycling", "driving", "transit"] = Field(
        default="walking",
        description=(
            "Mode of transport. Options: walking (default, "
            "pedestrian network), cycling (bicycle network), "
            "driving (road network), transit (public transport — "
            "requires a transit-capable routing backend such as "
            "Valhalla or OpenTripPlanner)."
        ),
    )


@mcp.tool(
    name="geoai_calculate_isochrone",
    annotations={
        "title": "Calculate isochrone polygon",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def geoai_calculate_isochrone(params: IsochroneInput) -> dict:
    """Compute an isochrone polygon around an origin point.

    The isochrone is returned as a GeoJSON Feature in WGS84
    (EPSG:4326) with the geometry, mode, travel time, and a manifest
    of the routing engine used. Reproject before computing area or
    distance.

    Safety: the origin is checked against the sensitive-zones
    reference; if inside one, the tool returns a structured refusal
    rather than sending coordinates to a third-party routing API.

    Args:
        params: Validated input containing origin, time budget, mode.

    Returns:
        GeoJSON Feature dict OR error envelope on failure.
    """
    if is_inside_sensitive_zone(params.origin_lon, params.origin_lat):
        return {
            "error": (
                "Origin coordinates fall inside a sensitive zone. "
                "Tool refuses to send them to an external routing "
                "API. If you have authorisation, switch to a "
                "self-hosted routing engine via "
                "GEOAI_ROUTING_ENGINE=local-osrm."
            ),
            "code": "SENSITIVE_ZONE_BLOCKED",
        }

    engine = os.environ.get("GEOAI_ROUTING_ENGINE", "osrm-demo")

    try:
        if engine == "osrm-demo":
            return await _isochrone_via_osrm_demo(params)
        if engine == "local-osrm":
            return await _isochrone_via_local_osrm(params)
        if engine == "valhalla":
            return await _isochrone_via_valhalla(params)
        return {
            "error": f"Unknown routing engine: {engine}",
            "code": "ENGINE_NOT_CONFIGURED",
        }
    except httpx.HTTPError as exc:
        return {
            "error": f"Routing engine HTTP error: {exc}",
            "code": "ENGINE_HTTP_ERROR",
        }
    except Exception as exc:  # pylint: disable=broad-except
        return {
            "error": f"Isochrone computation failed: {exc}",
            "code": "ENGINE_FAILURE",
        }


async def _isochrone_via_osrm_demo(params: IsochroneInput) -> dict:
    """Placeholder against the public OSRM demo endpoint.

    The OSRM demo does NOT natively support isochrone polygons; it
    returns point-to-point routes. A production isochrone
    implementation typically samples destinations on a grid and runs
    a many-to-one route matrix, then alpha-shapes the reachable
    points.

    For now this stub returns a placeholder structure so the tool
    round-trip works end-to-end. Replace with real implementation
    when you wire up a Valhalla or self-hosted OSRM with the
    isochrone plugin.
    """
    return {
        "type": "Feature",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                _placeholder_ring(params.origin_lon, params.origin_lat),
            ],
        },
        "properties": {
            "mode": params.mode,
            "travel_minutes": params.travel_minutes,
            "engine": "osrm-demo (placeholder)",
            "warning": (
                "This is a placeholder polygon. Configure a real "
                "routing engine via GEOAI_ROUTING_ENGINE for "
                "production use."
            ),
        },
    }


async def _isochrone_via_local_osrm(params: IsochroneInput) -> dict:
    """Self-hosted OSRM endpoint with isochrone plugin.

    Configuration: set GEOAI_OSRM_URL to the base URL of your OSRM
    server. Implementation deferred — wire up when you stand up the
    OSRM container.
    """
    return {
        "error": "local-osrm backend not yet implemented",
        "code": "BACKEND_NOT_IMPLEMENTED",
    }


async def _isochrone_via_valhalla(params: IsochroneInput) -> dict:
    """Valhalla isochrone endpoint.

    Valhalla supports isochrones natively via /isochrone. Set
    GEOAI_VALHALLA_URL to the base URL. Implementation deferred —
    wire up when you choose Valhalla as your engine.
    """
    return {
        "error": "valhalla backend not yet implemented",
        "code": "BACKEND_NOT_IMPLEMENTED",
    }


def _placeholder_ring(lon: float, lat: float) -> list[list[float]]:
    """Tiny placeholder ring around (lon, lat). Not a real isochrone."""
    delta = 0.005  # ~500m at equator
    return [
        [lon - delta, lat - delta],
        [lon + delta, lat - delta],
        [lon + delta, lat + delta],
        [lon - delta, lat + delta],
        [lon - delta, lat - delta],
    ]
