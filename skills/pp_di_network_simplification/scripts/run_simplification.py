"""
Urban network simplification — command-line engine.
====================================================

A single, parametrised entry point that downloads an OpenStreetMap street
network for a place, simplifies it with `neatnet`, and writes GeoPackages.

It is the engine behind the `pp_di_network_simplification` Claude Code skill,
but it also runs perfectly well on its own:

    python scripts/run_simplification.py --city "Bath, UK" --radius 10000 \\
        --mode drive_plus_pedestrian --output ./output

You can give a place name (it is geocoded automatically) or explicit
coordinates. Sensible defaults are chosen for the coordinate reference
system (CRS) and the chunk grid; everything can be overridden.

Spatial input CRS  : EPSG:4326 (WGS84 lon/lat) from OpenStreetMap.
Spatial output CRS : a projected CRS in metres — EPSG:27700 for the UK,
                     otherwise the appropriate UTM zone (or --crs to force one).

Progress is printed as plain, human-readable lines so a person — or Claude
Code relaying them — can follow along. Every line is also machine-parseable
by scripts/_progress_monitor.py.

Licence: MIT.
"""
from __future__ import annotations

import argparse
import gc
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# --- Unbuffered stdout so progress streams immediately to Claude / the terminal
try:
    sys.stdout.reconfigure(line_buffering=True)
except Exception:
    pass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SIMPLIFICATION_PARAMS = {
    "default": {
        "consolidation_tolerance": 10, "artifact_threshold_fallback": 7,
        "area_threshold_blocks": 100000.0, "area_threshold_circles": 50000.0,
        "simplification_factor": 2, "min_dangle_length": 20,
    },
    "moderate": {
        "consolidation_tolerance": 15, "artifact_threshold_fallback": 6,
        "area_threshold_blocks": 125000.0, "area_threshold_circles": 65000.0,
        "simplification_factor": 2.5, "min_dangle_length": 25,
    },
    "aggressive": {
        "consolidation_tolerance": 20, "artifact_threshold_fallback": 5,
        "area_threshold_blocks": 150000.0, "area_threshold_circles": 75000.0,
        "simplification_factor": 3, "min_dangle_length": 30,
    },
    "very_aggressive": {
        "consolidation_tolerance": 30, "artifact_threshold_fallback": 4,
        "area_threshold_blocks": 200000.0, "area_threshold_circles": 100000.0,
        "simplification_factor": 4, "min_dangle_length": 40,
    },
    "extreme_aggressive": {
        "consolidation_tolerance": 50, "artifact_threshold_fallback": 3,
        "area_threshold_blocks": 300000.0, "area_threshold_circles": 150000.0,
        "simplification_factor": 5, "min_dangle_length": 50,
    },
}

HIGHWAY_TO_CLASS = {
    "motorway": "drive", "motorway_link": "drive",
    "trunk": "drive", "trunk_link": "drive", "busway": "drive",
    "primary": "drive_walk", "primary_link": "drive_walk",
    "secondary": "drive_walk", "secondary_link": "drive_walk",
    "tertiary": "drive_walk", "tertiary_link": "drive_walk",
    "unclassified": "drive_walk", "residential": "drive_walk",
    "living_street": "drive_walk", "road": "drive_walk",
    "service": "drive_walk", "track": "drive_walk",
    "track_grade1": "drive_walk", "track_grade2": "drive_walk",
    "footway": "walk_only", "pedestrian": "walk_only",
    "path": "walk_only", "steps": "walk_only",
    "cycleway": "walk_only", "bridleway": "walk_only", "corridor": "walk_only",
}
PRIVATE_SERVICE = {"driveway", "parking_aisle", "parking", "private", "emergency_access"}
MAIN_ROAD_TYPES_DEFAULT = [
    "motorway", "trunk", "primary", "motorway_link", "trunk_link", "primary_link",
]

# Rough UK bounding box (lon/lat). Inside -> use British National Grid.
UK_BBOX = {"min_lon": -8.65, "max_lon": 1.77, "min_lat": 49.86, "max_lat": 60.86}


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    """Print one progress line, flushed immediately."""
    print(msg, flush=True)


def fmt(n: int) -> str:
    return f"{n:,}"


def auto_utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) / 6) + 1
    return (32600 + zone) if lat >= 0 else (32700 + zone)


def pick_crs(lat: float, lon: float, override: Optional[int]) -> tuple[int, str]:
    if override is not None:
        return override, f"EPSG:{override} (user-specified)"
    if (UK_BBOX["min_lon"] <= lon <= UK_BBOX["max_lon"]
            and UK_BBOX["min_lat"] <= lat <= UK_BBOX["max_lat"]):
        return 27700, "EPSG:27700 (British National Grid, auto-selected for UK)"
    epsg = auto_utm_epsg(lon, lat)
    return epsg, f"EPSG:{epsg} (UTM zone, auto-selected)"


def auto_chunks(radius_m: int, mode: str) -> int:
    """Pick a chunk-grid side length from the radius, denser for pedestrian mode."""
    r = radius_m
    if r <= 4000:
        n = 1
    elif r <= 8000:
        n = 2
    elif r <= 14000:
        n = 3
    elif r <= 22000:
        n = 4
    elif r <= 35000:
        n = 5
    else:
        n = 6
    if mode == "drive_plus_pedestrian" and r > 6000:
        n += 1
    return n


# ---------------------------------------------------------------------------
# OSM tag parsing
# ---------------------------------------------------------------------------
def _make_parsers(pd):
    def parse_tag(v):
        if isinstance(v, list):
            valid = [x for x in v if pd.notna(x)]
            return str(valid[0]).strip().lower() if valid else None
        if pd.notna(v):
            return str(v).strip().lower()
        return None

    def derive_class(hw):
        h = parse_tag(hw)
        return HIGHWAY_TO_CLASS.get(h, "drive_walk") if h else "drive_walk"

    def derive_access(row):
        a = parse_tag(row.get("access"))
        s = parse_tag(row.get("service"))
        if a in {"private", "no", "customers", "permit", "restricted"}:
            return "private"
        if s in PRIVATE_SERVICE:
            return "private"
        return "public"

    return parse_tag, derive_class, derive_access


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run(args: argparse.Namespace) -> int:
    # Imports are inside run() so --help works even before deps are installed.
    import geopandas as gpd
    import osmnx as ox
    import pandas as pd
    from shapely.geometry import box

    parse_tag, derive_class, derive_access = _make_parsers(pd)
    t_pipeline = time.perf_counter()

    # ---- Resolve location ------------------------------------------------
    if args.lat is not None and args.lon is not None:
        lat, lon = args.lat, args.lon
        place_label = args.city or f"{lat:.5f}, {lon:.5f}"
        log(f"Location: {place_label} (coordinates supplied)")
    elif args.city:
        log(f"Geocoding '{args.city}' ...")
        try:
            lat, lon = ox.geocode(args.city)
        except Exception as e:
            log(f"!!! ERROR: could not geocode '{args.city}': {e}")
            log("    Provide explicit --lat and --lon instead.")
            return 2
        place_label = args.city
        log(f"Location: {place_label} -> {lat:.5f}, {lon:.5f}")
    else:
        log("!!! ERROR: give either --city or both --lat and --lon.")
        return 2

    centre = (lat, lon)
    radius = args.radius
    mode = args.mode
    level = args.level
    params = SIMPLIFICATION_PARAMS[level]
    crs_epsg, crs_note = pick_crs(lat, lon, args.crs)
    grid = args.chunks if args.chunks else auto_chunks(radius, mode)
    osmnx_type = "drive" if mode == "drive" else "all"

    slug = (args.name or args.city or f"{lat:.4f}_{lon:.4f}")
    slug = slug.lower().split(",")[0].strip().replace(" ", "_")
    base = f"{slug}_{radius // 1000}km_{level}_{mode}"

    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)

    log("")
    log("Plan:")
    log(f"  Place        : {place_label}  ({lat:.5f}, {lon:.5f})")
    log(f"  Radius       : {radius / 1000:.1f} km")
    log(f"  Network mode : {mode}")
    log(f"  Simplify     : {level}")
    log(f"  CRS          : {crs_note}")
    log(f"  Chunk grid   : {grid} x {grid} = {grid * grid} chunks")
    log(f"  Main roads   : "
        f"{('preserved (+secondary)' if args.preserve_secondary else 'preserved') if (args.preserve_main_roads or args.preserve_secondary) else 'simplified with the rest'}")
    log(f"  Unlinks      : {'detected' if args.detect_unlinks else 'skipped'}")
    log(f"  Buildings    : {'no (skipped)' if args.no_buildings else 'yes (exclusion mask)'}")
    log(f"  Output       : {out_dir.resolve()}")
    log(f"  File prefix  : {base}")
    log("")

    manifest: dict = {
        "place": place_label, "lat": lat, "lon": lon, "radius_m": radius,
        "crs_epsg": crs_epsg, "network_mode": mode, "simplification_level": level,
        "chunk_grid_size": grid, "preserve_main_roads": bool(args.preserve_main_roads),
        "preserve_secondary": bool(args.preserve_secondary),
        "detect_unlinks": bool(args.detect_unlinks), "use_buildings": not args.no_buildings,
        "params": params, "started_utc": datetime.now(timezone.utc).isoformat(),
        "phases": {}, "chunks": [], "outputs": {},
    }

    # ---- 1. Download network --------------------------------------------
    log(f"Downloading {mode} network for {place_label} ({radius / 1000:.1f} km) ...")
    t = time.perf_counter()
    # OSMnx does not fetch the `layer` tag by default; without it, stacked
    # grade separation (bridge over bridge) cannot be told apart in unlink
    # detection.
    ox.settings.useful_tags_way = sorted(
        set(list(ox.settings.useful_tags_way) + ["layer"]))
    graph = ox.graph_from_point(centre, dist=radius, network_type=osmnx_type, simplify=True)
    gdf = ox.graph_to_gdfs(
        ox.convert.to_undirected(graph),
        nodes=False, edges=True, node_geometry=False, fill_edge_geometry=True,
    ).reset_index(drop=True)
    gdf = gdf.to_crs(epsg=crs_epsg)
    if "highway" in gdf.columns:
        gdf["highway"] = gdf["highway"].apply(parse_tag)
        gdf["network_class"] = gdf["highway"].apply(derive_class)
    else:
        gdf["highway"], gdf["network_class"] = None, "drive_walk"
    gdf["access_class"] = gdf.apply(derive_access, axis=1)
    for col in ("layer", "bridge", "tunnel", "junction", "oneway"):
        if col not in gdf.columns:
            gdf[col] = None
    for col in ("junction", "oneway"):
        gdf[col] = gdf[col].apply(parse_tag)
    streets = gdf[["geometry", "highway", "network_class", "access_class",
                   "layer", "bridge", "tunnel", "junction", "oneway"]].copy()
    streets_ref = streets.copy()
    del graph, gdf
    gc.collect()
    dt = time.perf_counter() - t
    cc = streets["network_class"].value_counts().to_dict()
    manifest["phases"]["download"] = {
        "elapsed_s": round(dt, 1), "segments": int(len(streets)),
        "length_km": round(streets.length.sum() / 1000, 1),
        "network_class": {str(k): int(v) for k, v in cc.items()},
    }
    log(f"Network downloaded: {fmt(len(streets))} segments, "
        f"{streets.length.sum() / 1000:.0f} km in {dt:.0f}s "
        f"(drive {fmt(cc.get('drive', 0))}, drive+walk {fmt(cc.get('drive_walk', 0))}, "
        f"walk-only {fmt(cc.get('walk_only', 0))})")

    # ---- 2. Optional main-road split ------------------------------------
    # `--preserve-secondary` implies preservation and extends the held-back
    # set to secondary roads (preserving secondary but simplifying the bigger
    # roads above it would make no sense).
    preserve = args.preserve_main_roads or args.preserve_secondary
    preserved_types = list(MAIN_ROAD_TYPES_DEFAULT)
    if args.preserve_secondary:
        preserved_types += ["secondary", "secondary_link"]
    if preserve:
        main_roads = streets[streets["highway"].isin(preserved_types)].copy()
        other = streets[~streets["highway"].isin(preserved_types)].copy()
        log(f"Preserving {fmt(len(main_roads))} main-road segments "
            f"({'+secondary ' if args.preserve_secondary else ''}untouched); "
            f"simplifying {fmt(len(other))} others")
    else:
        main_roads = streets.iloc[0:0].copy()
        other = streets.copy()

    if len(other) == 0:
        log("!!! ERROR: no segments to simplify after filtering.")
        return 3

    # ---- 3. Buildings ----------------------------------------------------
    buildings, has_buildings = None, False
    if not args.no_buildings:
        log("Downloading buildings (exclusion mask) ...")
        t = time.perf_counter()
        try:
            buildings = ox.features_from_point(centre, tags={"building": True}, dist=radius)
            buildings = buildings.query('building != "roof"').to_crs(streets.crs)
            has_buildings = True
            log(f"Buildings: {fmt(len(buildings))} footprints in "
                f"{time.perf_counter() - t:.0f}s")
        except Exception as e:
            log(f"Buildings download failed ({e}); continuing without exclusion mask.")
            buildings, has_buildings = None, False
        manifest["phases"]["buildings"] = {
            "footprints": int(len(buildings)) if has_buildings else 0,
            "downloaded": has_buildings,
        }

    # ---- 4. Chunk grid ---------------------------------------------------
    minx, miny, maxx, maxy = other.total_bounds
    xs, ys = (maxx - minx) / grid, (maxy - miny) / grid
    xov, yov = xs * 0.1, ys * 0.1
    chunk_geoms, chunk_ids = [], []
    for i in range(grid):
        for j in range(grid):
            chunk_geoms.append(box(minx + i * xs - xov, miny + j * ys - yov,
                                   minx + (i + 1) * xs + xov, miny + (j + 1) * ys + yov))
            chunk_ids.append(f"chunk_{i}_{j}")
    chunks_gdf = gpd.GeoDataFrame({"chunk_id": chunk_ids, "geometry": chunk_geoms},
                                  crs=other.crs)
    log(f"Built {grid}x{grid} chunk grid ({grid * grid} tiles, "
        f"~{xs / 1000:.1f} x {ys / 1000:.1f} km each)")

    # ---- 5. Simplify -----------------------------------------------------
    import neatnet
    log(f"Simplifying {grid * grid} chunks ({level}) - this is the long part ...")
    t_simp = time.perf_counter()
    simplified_chunks, fallbacks = [], []
    total = len(chunk_geoms)
    for idx, (cid, cgeom) in enumerate(zip(chunk_ids, chunk_geoms), start=1):
        cstreets = other[other.intersects(cgeom)].copy()
        n_in = len(cstreets)
        if n_in == 0:
            continue
        cbld = buildings[buildings.intersects(cgeom)].geometry if has_buildings else None
        tc = time.perf_counter()
        try:
            if has_buildings and cbld is not None and len(cbld) > 0:
                res = neatnet.neatify(cstreets, exclusion_mask=cbld, **params)
            else:
                res = neatnet.neatify(cstreets, **params)
            n_out = len(res)
            pct = (n_in - n_out) / max(n_in, 1) * 100
            log(f"[{idx}/{total}] {cid} simplified: {fmt(n_in)} -> {fmt(n_out)} "
                f"(-{pct:.1f}%) in {time.perf_counter() - tc:.1f}s")
            manifest["chunks"].append({"chunk_id": cid, "in": n_in, "out": n_out,
                                       "elapsed_s": round(time.perf_counter() - tc, 1)})
        except Exception as e:
            log(f"[{idx}/{total}] {cid} FALLBACK ({type(e).__name__}); kept "
                f"{fmt(n_in)} original segments")
            res = cstreets.copy()
            fallbacks.append(cid)
            manifest["chunks"].append({"chunk_id": cid, "in": n_in, "out": n_in,
                                       "error": f"{type(e).__name__}: {e}"})
        res["chunk_id"] = cid
        simplified_chunks.append(res)
        del cstreets, res
        if cbld is not None:
            del cbld
        gc.collect()
    manifest["phases"]["simplify"] = {
        "elapsed_s": round(time.perf_counter() - t_simp, 1),
        "chunks": total, "fallbacks": len(fallbacks), "fallback_chunks": fallbacks,
    }

    # ---- 6. Combine + dedup (chunk_id-keyed core tile) -------------------
    log("Combining chunks ...")
    combined = pd.concat(simplified_chunks, ignore_index=True)
    core_tile_by_chunk = {
        f"chunk_{i}_{j}": box(minx + i * xs, miny + j * ys,
                              minx + (i + 1) * xs, miny + (j + 1) * ys)
        for i in range(grid) for j in range(grid)
    }
    combined["_centroid"] = combined.geometry.centroid
    keep = [k for k, row in combined.iterrows()
            if core_tile_by_chunk[row["chunk_id"]].contains(row["_centroid"])]
    simp_other = (combined.loc[keep]
                  .drop(columns=["chunk_id", "_centroid"], errors="ignore")
                  .reset_index(drop=True))

    centroids = simp_other.copy()
    centroids["geometry"] = centroids.geometry.centroid
    joined = gpd.sjoin_nearest(
        centroids[["geometry"]],
        streets_ref[["geometry", "network_class", "access_class", "highway",
                     "junction", "oneway"]],
        how="left",
    )
    joined = joined[~joined.index.duplicated(keep="first")]
    for col in ("network_class", "access_class", "highway", "junction", "oneway"):
        simp_other[col] = joined.loc[simp_other.index, col].values

    if len(main_roads) > 0:
        final = pd.concat([main_roads, simp_other], ignore_index=True)
    else:
        final = simp_other.copy()
    final = gpd.GeoDataFrame(final, geometry="geometry", crs=streets.crs)
    reduction = (len(streets) - len(final)) / max(len(streets), 1) * 100
    reduction_word = "reduction" if reduction >= 0 else "INCREASE"
    manifest["phases"]["combine"] = {"final_segments": int(len(final)),
                                     "overall_reduction_pct": round(reduction, 1)}
    log(f"Final network: {fmt(len(streets))} -> {fmt(len(final))} segments "
        f"({abs(reduction):.1f}% {reduction_word})")

    # ---- 7. Optional unlinks --------------------------------------------
    unlink_gdf = None
    if args.detect_unlinks:
        log("Detecting bridge/tunnel unlinks ...")
        t = time.perf_counter()
        work = final.copy()
        work["layer"] = pd.to_numeric(work.get("layer"), errors="coerce").fillna(0).astype(int)

        def _yes(v):
            return str(parse_tag(v)) == "yes"

        work["layer"] = work.apply(
            lambda r: r["layer"] + 1 if _yes(r.get("bridge"))
            else (r["layer"] - 1 if _yes(r.get("tunnel")) else r["layer"]), axis=1)
        sindex = work.sindex
        pts = []
        for k, row in work.iterrows():
            geom = row.geometry
            for oid in sindex.intersection(geom.bounds):
                if k >= oid:
                    continue
                other_row = work.iloc[oid]
                if row.layer == other_row.layer or not geom.intersects(other_row.geometry):
                    continue
                pt = geom.intersection(other_row.geometry)
                if pt.is_empty:
                    continue
                if pt.geom_type == "Point":
                    pts.append(pt)
                elif pt.geom_type == "MultiPoint":
                    pts.extend(list(pt.geoms))
                else:
                    try:
                        pts.append(pt.centroid)
                    except Exception:
                        pass
        unlink_gdf = (gpd.GeoDataFrame(geometry=pts, crs=final.crs)
                      .drop_duplicates().reset_index(drop=True))
        manifest["phases"]["unlinks"] = {"points": int(len(unlink_gdf)),
                                         "elapsed_s": round(time.perf_counter() - t, 1)}
        log(f"Unlinks: {fmt(len(unlink_gdf))} grade-separated crossing points")

    # ---- 8. Save ---------------------------------------------------------
    log(f"Saving outputs to {out_dir.resolve()} ...")

    def save(g, name):
        if g is None or len(g) == 0:
            return
        gg = g.copy()
        for col in gg.columns:
            if col == "geometry":
                continue
            if gg[col].apply(lambda v: isinstance(v, list)).any():
                gg[col] = gg[col].apply(
                    lambda v: ",".join(map(str, v)) if isinstance(v, list) else v)
        p = out_dir / f"{base}_{name}.gpkg"
        gg.to_file(p, driver="GPKG")
        manifest["outputs"][name] = {"path": str(p), "rows": int(len(gg)),
                                     "size_bytes": p.stat().st_size}
        log(f"Saved {p.name} ({fmt(len(gg))} rows)")

    save(streets, "original")
    save(final, "simplified")
    if has_buildings:
        save(buildings, "buildings")
    save(chunks_gdf, "chunks")
    if len(main_roads) > 0:
        save(main_roads, "main_roads")
    if args.detect_unlinks and unlink_gdf is not None and len(unlink_gdf) > 0:
        save(unlink_gdf, "unlinks")

    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["total_elapsed_s"] = round(time.perf_counter() - t_pipeline, 1)
    (out_dir / f"{base}_run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")
    save_note = f", {len(fallbacks)} fallback chunk(s)" if fallbacks else ""
    log("")
    log(f"=== SIMPLIFICATION COMPLETE in {manifest['total_elapsed_s'] / 60:.1f} min ===")
    log(f"Final: {fmt(len(final))} segments ({abs(reduction):.1f}% {reduction_word} "
        f"vs original){save_note}")
    log(f"Outputs in: {out_dir.resolve()}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Download and simplify an OpenStreetMap street network.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    loc = p.add_argument_group("location (give --city, or both --lat and --lon)")
    loc.add_argument("--city", help="Place name to geocode, e.g. 'Bath, UK'.")
    loc.add_argument("--lat", type=float, help="Centre latitude (WGS84 degrees).")
    loc.add_argument("--lon", type=float, help="Centre longitude (WGS84 degrees).")

    p.add_argument("--radius", type=int, required=True,
                   help="Extraction radius around the centre, in metres.")
    p.add_argument("--mode", choices=["drive", "drive_plus_pedestrian"], default="drive",
                   help="Vehicle network only, or vehicle + pedestrian (footways/paths/steps).")
    p.add_argument("--level", choices=list(SIMPLIFICATION_PARAMS), default="aggressive",
                   help="Simplification aggressiveness preset.")
    p.add_argument("--crs", type=int, default=None,
                   help="Projected EPSG code. Omit to auto-pick (UK=27700, else UTM).")
    p.add_argument("--chunks", type=int, default=None,
                   help="Chunk-grid side length (N gives NxN tiles). Omit to auto-size.")
    p.add_argument("--preserve-main-roads", action="store_true",
                   help="Hold motorway/trunk/primary roads back from simplification.")
    p.add_argument("--preserve-secondary", action="store_true",
                   help="Also hold secondary roads back (implies preservation; "
                        "extends the held-back set to include secondary).")
    p.add_argument("--detect-unlinks", action="store_true",
                   help="Export bridge/tunnel grade-separated crossings as points.")
    p.add_argument("--no-buildings", action="store_true",
                   help="Skip the building exclusion mask.")
    p.add_argument("--output", required=True,
                   help="Directory for the output GeoPackages.")
    p.add_argument("--name", default=None,
                   help="Override the slug used in output filenames.")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        log("!!! Interrupted by user.")
        return 130
    except Exception as e:  # noqa: BLE001 - top-level guard reports cleanly to Claude/CLI
        log(f"!!! ERROR: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
