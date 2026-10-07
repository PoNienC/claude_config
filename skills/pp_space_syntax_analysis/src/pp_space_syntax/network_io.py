"""GeoPackage input/output for street network geometry.

Spatial input/output: GeoPackage layers in any projected, metre-based CRS;
geometry is passed to pstalgo as flat coordinate arrays in the layer's own
CRS (no reprojection is performed here).
Data layer: data_ingestion.
"""
from __future__ import annotations

import array
import logging
from dataclasses import dataclass, field
from pathlib import Path

import geopandas as gpd
import pandas as pd
from pyproj import CRS
from shapely.geometry import LineString, Point

logger = logging.getLogger(__name__)


@dataclass
class PolylineData:
    """Flat polyline buffers in pstalgo's expected layout.

    ``coords`` holds x, y pairs for every vertex of every polyline;
    ``counts`` holds the vertex count of each polyline. Multipart
    geometries are exploded, one entry in ``counts`` per part, matching
    the PST plugin's readPolylines behaviour.
    """

    coords: array.array  # typecode 'd'
    counts: array.array  # typecode 'i'
    crs: CRS
    source_frame: gpd.GeoDataFrame = field(repr=False)

    @property
    def polyline_count(self) -> int:
        return len(self.counts)


@dataclass
class SegmentData:
    """Two-point segment buffers for graph building.

    ``line_coords`` holds x0, y0, x1, y1 per segment, matching the PST
    plugin's readLines behaviour (which rejects polylines with more than
    two vertices).
    """

    line_coords: array.array  # typecode 'd'
    crs: CRS
    frame: gpd.GeoDataFrame = field(repr=False)

    @property
    def segment_count(self) -> int:
        return len(self.line_coords) // 4


def read_polylines(gpkg: Path, layer: str | None = None) -> PolylineData:
    """Read a line layer into flat polyline buffers (multiparts exploded)."""
    gdf = gpd.read_file(gpkg, layer=layer)
    if gdf.empty:
        raise ValueError(f"No features found in {gpkg} (layer={layer}).")
    exploded = gdf.explode(index_parts=False).reset_index(drop=True)
    coords = array.array("d")
    counts = array.array("i")
    for geom in exploded.geometry:
        if geom is None or geom.is_empty:
            continue
        if not isinstance(geom, LineString):
            raise TypeError(
                f"Expected LineString geometry, found {geom.geom_type}. "
                "The network layer must contain lines only."
            )
        vertices = list(geom.coords)
        for x, y in ((c[0], c[1]) for c in vertices):
            coords.append(x)
            coords.append(y)
        counts.append(len(vertices))
    logger.info(
        "Read %d polylines (%d vertices) from %s layer=%s",
        len(counts), len(coords) // 2, gpkg, layer,
    )
    return PolylineData(coords=coords, counts=counts, crs=CRS(gdf.crs), source_frame=exploded)


def read_points(gpkg: Path, layer: str | None = None) -> tuple[array.array, CRS]:
    """Read a point layer into a flat x, y buffer."""
    gdf = gpd.read_file(gpkg, layer=layer)
    coords = array.array("d")
    for geom in gdf.geometry:
        if geom is None or geom.is_empty:
            continue
        if not isinstance(geom, Point):
            raise TypeError(
                f"Expected Point geometry, found {geom.geom_type}. "
                "The unlinks layer must contain points only."
            )
        coords.append(geom.x)
        coords.append(geom.y)
    logger.info("Read %d points from %s layer=%s", len(coords) // 2, gpkg, layer)
    return coords, CRS(gdf.crs)


def read_segments(gpkg: Path, layer: str | None = None) -> SegmentData:
    """Read a segment map layer as two-point lines for graph building.

    Raises if any feature has more than two vertices — run the segment
    map creation step first, exactly as the PST QGIS plugin requires.
    """
    gdf = gpd.read_file(gpkg, layer=layer)
    if gdf.empty:
        raise ValueError(f"No features found in {gpkg} (layer={layer}).")
    line_coords = array.array("d")
    for fid, geom in zip(gdf.index, gdf.geometry):
        if geom is None or geom.is_empty:
            raise ValueError(f"Feature {fid} has no geometry.")
        if not isinstance(geom, LineString):
            raise TypeError(
                f"Feature {fid}: expected LineString, found {geom.geom_type}."
            )
        vertices = list(geom.coords)
        if len(vertices) != 2:
            raise ValueError(
                f"Feature {fid} has {len(vertices)} vertices. A segment map "
                "must contain straight two-point segments only — run "
                "'create segment map' on this network first."
            )
        line_coords.extend((vertices[0][0], vertices[0][1], vertices[1][0], vertices[1][1]))
    logger.info(
        "Read %d segments from %s layer=%s", len(line_coords) // 4, gpkg, layer
    )
    return SegmentData(line_coords=line_coords, crs=CRS(gdf.crs), frame=gdf)


def write_lines(
    gpkg: Path,
    layer: str,
    geometries: list[LineString],
    attributes: dict[str, list],
    crs: CRS,
) -> None:
    """Write line geometries with attribute columns to a GeoPackage layer."""
    frame = gpd.GeoDataFrame(pd.DataFrame(attributes), geometry=geometries, crs=crs)
    gpkg.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(gpkg, layer=layer, driver="GPKG")
    logger.info("Wrote %d lines to %s layer=%s", len(frame), gpkg, layer)


def write_points(
    gpkg: Path,
    layer: str,
    geometries: list[Point],
    crs: CRS,
) -> None:
    """Write point geometries (no attributes) to a GeoPackage layer."""
    frame = gpd.GeoDataFrame(geometry=geometries, crs=crs)
    gpkg.parent.mkdir(parents=True, exist_ok=True)
    frame.to_file(gpkg, layer=layer, driver="GPKG")
    logger.info("Wrote %d points to %s layer=%s", len(frame), gpkg, layer)
