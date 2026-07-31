"""
Urban network refinement — Phase 2 command-line engine.
========================================================

Takes a Phase 1 simplified network (the `*_simplified.gpkg` written by
`run_simplification.py`) and applies the "modelling rules" of the space
syntax literature — Kolovou et al. (2017, SSS11 #163) and Krenz (2017,
SSS11 #150) — to fix the residual geometry that general simplification
leaves behind:

    junctions          contract residual forks / Y-splits at junctions
    roundabouts        collapse roundabouts (small -> centroid star,
                       large -> entry-to-exit chords)
    gaps               extend dangling undershoots onto the road they
                       visibly join
    sliproads          straighten meandering `*_link` slip roads
    smoothing          Douglas-Peucker with a road-hierarchy-scaled
                       tolerance (the "field of vision" rule)
    dual_carriageways  opt-in second consolidation pass on major roads
                       (some regions need dual carriageways preserved,
                       so this never runs by default)

It also emits review layers for the cases the literature says cannot be
safely automated: candidate square/open-space links and candidate
spurious-link deletions. Those are proposals for an analyst in QGIS —
nothing is deleted automatically.

    python scripts/run_refinement.py \\
        --input output/cambridge_5km_aggressive_drive_simplified.gpkg \\
        --output output

Spatial input CRS  : a projected CRS in metres (whatever Phase 1 wrote).
Spatial output CRS : unchanged from the input.

Progress is printed as plain, human-readable lines, in the same style as
the Phase 1 engine.

Licence: MIT.
"""
from __future__ import annotations

import argparse
import json
import math
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
DEFAULT_RULES = ["junctions", "roundabouts", "parallels", "gaps", "sliproads",
                 "smoothing"]
ALL_RULES = DEFAULT_RULES + ["dual_carriageways"]

# Road classes whose dual/multiple parallel lines are KEPT by the parallels
# rule (the OSM trunk tier is part of the UK primary A-road network).
PARALLEL_PROTECT_DEFAULT = "motorway,trunk,primary"

# Douglas-Peucker tolerance per highway class, in metres. Scaled to the
# street's field of vision (~width), per Krenz (2017): a centre line may
# deviate up to the extent of what a person in the street can see.
SMOOTHING_TOLERANCE = {
    "motorway": 15.0, "motorway_link": 12.0,
    "trunk": 15.0, "trunk_link": 12.0,
    "primary": 12.0, "primary_link": 10.0,
    "secondary": 10.0, "secondary_link": 8.0,
    "tertiary": 8.0, "tertiary_link": 6.0,
    "unclassified": 6.0, "residential": 6.0, "living_street": 5.0,
    "road": 6.0, "busway": 8.0,
    "service": 4.0, "track": 4.0,
    "footway": 3.0, "pedestrian": 3.0, "path": 3.0, "steps": 2.0,
    "cycleway": 3.0, "bridleway": 3.0, "corridor": 2.0,
}
SMOOTHING_DEFAULT = 4.0

MAJOR_ROAD_TYPES = [
    "motorway", "trunk", "primary", "motorway_link", "trunk_link", "primary_link",
]

MM = 1000  # coordinate key precision: millimetres


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def log(msg: str) -> None:
    """Print one progress line, flushed immediately."""
    print(msg, flush=True)


def fmt(n: int) -> str:
    return f"{n:,}"


def _key(x: float, y: float) -> tuple[int, int]:
    return (int(round(x * MM)), int(round(y * MM)))


def _yes(v) -> bool:
    """Truthy OSM tag: anything except None / NaN / 'no'."""
    if v is None:
        return False
    try:
        if v != v:  # NaN
            return False
    except Exception:
        pass
    return str(v).strip().lower() not in {"", "no", "none", "nan", "0", "false"}


def _grade_separated(row) -> bool:
    return _yes(row.get("bridge")) or _yes(row.get("tunnel"))


class _UnionFind:
    def __init__(self):
        self.parent: dict = {}

    def find(self, a):
        self.parent.setdefault(a, a)
        while self.parent[a] != a:
            self.parent[a] = self.parent[self.parent[a]]
            a = self.parent[a]
        return a

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def node_degrees(geoms) -> dict[tuple[int, int], int]:
    """Count how many line ends meet at each (mm-rounded) coordinate."""
    deg: dict[tuple[int, int], int] = {}
    for geom in geoms:
        if geom is None or geom.is_empty:
            continue
        coords = list(geom.coords)
        for c in (coords[0], coords[-1]):
            k = _key(c[0], c[1])
            deg[k] = deg.get(k, 0) + 1
    return deg


def _dedupe_coords(coords: list) -> list:
    out = [coords[0]]
    for c in coords[1:]:
        if _key(c[0], c[1]) != _key(out[-1][0], out[-1][1]):
            out.append(c)
    return out


def _move_endpoints(geom, mapping: dict[tuple[int, int], tuple[float, float]]):
    """Return geom with any endpoint found in `mapping` moved, or None if
    the result degenerates (fewer than two distinct vertices)."""
    from shapely.geometry import LineString

    coords = [(c[0], c[1]) for c in geom.coords]
    changed = False
    for pos in (0, len(coords) - 1):
        k = _key(coords[pos][0], coords[pos][1])
        if k in mapping:
            coords[pos] = mapping[k]
            changed = True
    if not changed:
        return geom
    coords = _dedupe_coords(coords)
    if len(coords) < 2:
        return None
    return LineString(coords)


def _template_attrs(gdf, idx, status: str) -> dict:
    """Non-geometry attributes copied from row idx, with _status overridden."""
    row = gdf.loc[idx]
    attrs = {c: row[c] for c in gdf.columns if c != "geometry"}
    if "_status" in attrs:
        attrs["_status"] = status
    return attrs


def _bearing_at(geom, pt) -> float:
    """Bearing (radians) of the line locally around the point nearest pt."""
    d = geom.project(pt)
    p1 = geom.interpolate(max(d - 2.0, 0.0))
    p2 = geom.interpolate(min(d + 2.0, geom.length))
    return math.atan2(p2.y - p1.y, p2.x - p1.x)


def _bearing_diff(a: float, b: float) -> float:
    """Undirected angular difference between two bearings, in [0, pi/2]."""
    return abs((a - b + math.pi / 2) % math.pi - math.pi / 2)


def _make_crossing_meter(buildings):
    """Return f(geom) -> length of geom running inside building footprints.

    The Phase 2 equivalent of Phase 1's neatnet exclusion_mask: rules that
    move geometry compare the metered length before and after a rewrite and
    reject any change that pushes a line further into a building. With no
    buildings loaded every geometry meters 0.0, so the rules degrade
    gracefully rather than failing."""
    if buildings is None or len(buildings) == 0:
        return lambda geom: 0.0
    b_sindex = buildings.sindex
    b_geo = buildings.geometry

    def meter(geom) -> float:
        if geom is None or geom.is_empty:
            return 0.0
        total = 0.0
        for bi in b_sindex.query(geom, predicate="intersects"):
            try:
                total += geom.intersection(b_geo.iloc[bi]).length
            except Exception:
                pass
        return total

    return meter


# Road-class precedence used when merging duplicate features: keep the
# highest-ranked tag (OSM overlapping ways at classification boundaries
# carry conflicting classes; the more important class wins).
HIGHWAY_RANK = [
    "motorway", "motorway_link", "trunk", "trunk_link", "primary",
    "primary_link", "secondary", "secondary_link", "tertiary",
    "tertiary_link", "busway", "unclassified", "residential",
    "living_street", "road", "service", "track", "pedestrian", "cycleway",
    "footway", "path", "steps", "bridleway", "corridor",
]


def _class_rank(hw) -> int:
    try:
        return HIGHWAY_RANK.index(str(hw))
    except ValueError:
        return len(HIGHWAY_RANK)


def cleanup_network(gdf, review: dict, manifest: dict, stage: str):
    """Always-on hygiene pass, run on load AND before save:

    (a) segments shorter than 0.1 m (near-coincident junction nodes left by
        endpoint remapping) collapse into a single node;
    (b) features sharing the same order-independent endpoint pair whose
        geometries are mutually coincident (identical, reversed, or
        differently densified) merge — the highest road class survives.
        These enter as overlapping OSM ways at classification boundaries
        and can also be folded together by Phase 2's endpoint remapping."""
    import pandas as pd

    t = time.perf_counter()
    gdf = gdf.reset_index(drop=True)

    # (a) collapse sub-decimetre slivers into one node.
    mapping: dict = {}
    tiny_drop = []
    for idx, geom in gdf.geometry.items():
        if geom is None or geom.is_empty:
            continue
        if 0 < geom.length < 0.1:
            cs = list(geom.coords)
            ka = _key(cs[0][0], cs[0][1])
            kb = _key(cs[-1][0], cs[-1][1])
            if ka != kb:
                mapping[kb] = (cs[0][0], cs[0][1])
            tiny_drop.append(idx)
    if tiny_drop:
        gdf = gdf.drop(index=tiny_drop)
        new_geoms, degenerate = [], []
        for idx, geom in gdf.geometry.items():
            g2 = _move_endpoints(geom, mapping)
            if g2 is None or g2.length < 0.05:
                degenerate.append(idx)
                new_geoms.append(geom)
            else:
                new_geoms.append(g2)
        gdf = gdf.set_geometry(pd.Series(new_geoms, index=gdf.index),
                               crs=gdf.crs)
        if degenerate:
            gdf = gdf.drop(index=degenerate)
        gdf = gdf.reset_index(drop=True)

    # (b) duplicate features over the same endpoint pair.
    groups: dict = {}
    for idx, geom in gdf.geometry.items():
        if geom is None or geom.is_empty:
            continue
        cs = list(geom.coords)
        ka = _key(cs[0][0], cs[0][1])
        kb = _key(cs[-1][0], cs[-1][1])
        k = (ka, kb) if ka <= kb else (kb, ka)
        groups.setdefault(k, []).append(idx)
    hw = gdf["highway"] if "highway" in gdf.columns else None
    dup_drop = []
    for k, idxs in groups.items():
        if len(idxs) < 2:
            continue
        kept = [idxs[0]]
        for j in idxs[1:]:
            gj = gdf.geometry[j]
            merged = False
            for pos, i in enumerate(kept):
                gi = gdf.geometry[i]
                if gj.equals(gi) or (
                        gj.within(gi.buffer(0.05))
                        and gi.within(gj.buffer(0.05))):
                    if hw is not None and _class_rank(hw[j]) < _class_rank(hw[i]):
                        kept[pos] = j
                        dup_drop.append(i)
                    else:
                        dup_drop.append(j)
                    merged = True
                    break
            if not merged:
                kept.append(j)
    if dup_drop:
        if stage == "final":
            review["removed_duplicates"] = gdf.loc[
                sorted(set(dup_drop)), ["geometry"]].copy()
        gdf = gdf.drop(index=sorted(set(dup_drop))).reset_index(drop=True)

    manifest.setdefault("cleanup", {})[stage] = {
        "tiny_segments_collapsed": len(tiny_drop),
        "duplicate_features_removed": len(set(dup_drop)),
        "elapsed_s": round(time.perf_counter() - t, 1),
    }
    if tiny_drop or dup_drop:
        log(f"Cleanup ({stage}): collapsed {len(tiny_drop)} sub-0.1 m "
            f"segments, removed {len(set(dup_drop))} duplicate features "
            f"in {time.perf_counter() - t:.1f}s")
    return gdf


def qa_metrics(gdf, review: dict) -> dict:
    """Exploded-level duplicate count (order-independent two-point key),
    tiny-segment count, and endpoint-connectivity components — recorded in
    the manifest so regressions surface in every run. Residual exploded
    duplicates (partial overlaps inside longer lines) go to review."""
    import geopandas as gpd
    from shapely.geometry import LineString

    groups: dict = {}
    uf = _UnionFind()
    for idx, geom in gdf.geometry.items():
        if geom is None or geom.is_empty:
            continue
        cs = list(geom.coords)
        ks = [_key(c[0], c[1]) for c in cs]
        for a, b, ka, kb in zip(cs[:-1], cs[1:], ks[:-1], ks[1:]):
            if ka == kb:
                continue
            k = (ka, kb) if ka <= kb else (kb, ka)
            groups.setdefault(k, []).append((a, b))
        uf.union(ks[0], ks[-1])
    comp_len: dict = {}
    for idx, geom in gdf.geometry.items():
        if geom is None or geom.is_empty:
            continue
        cs = list(geom.coords)
        r = uf.find(_key(cs[0][0], cs[0][1]))
        comp_len[r] = comp_len.get(r, 0.0) + geom.length
    total = sum(comp_len.values()) or 1.0
    dup = {k: v for k, v in groups.items() if len(v) > 1}
    if dup:
        review["duplicate_candidates"] = gpd.GeoDataFrame(
            geometry=[LineString([a, b]) for v in dup.values()
                      for a, b in v[:1]], crs=gdf.crs)
    return {
        "duplicate_groups_exploded": len(dup),
        "segments_under_0p1m": int((gdf.length < 0.1).sum()),
        "components": len(comp_len),
        "largest_component_pct": round(100 * max(comp_len.values()) / total, 1),
    }


# ---------------------------------------------------------------------------
# Rule: junctions — contract residual forks / Y-splits
# ---------------------------------------------------------------------------
def rule_junctions(gdf, tolerance: float, buildings, review: dict,
                   manifest: dict):
    """Contract sub-tolerance edges whose BOTH endpoints are junctions
    (degree >= 3). Splayed Y-forks and tiny junction triangles collapse to
    a single node — one decision point, one node (Kolovou et al. 2017).

    Two guards stop the rule eating dense yard/courtyard fabric:
    - clusters of chained short edges wider than 2x the tolerance never
      merge (the source of long zigzag diagonals), and
    - a contraction is rejected if any rewritten line would run further
      through a building than it did before (the buildings play the same
      role as Phase 1's neatnet exclusion_mask)."""
    import pandas as pd

    t = time.perf_counter()
    deg = node_degrees(gdf.geometry)
    uf = _UnionFind()
    cand_edges: dict[int, tuple[int, int]] = {}  # row idx -> one endpoint key
    member_coords: dict = {}

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty or geom.length >= tolerance:
            continue
        if _grade_separated(row):
            continue
        coords = list(geom.coords)
        ka = _key(coords[0][0], coords[0][1])
        kb = _key(coords[-1][0], coords[-1][1])
        if ka == kb:
            continue
        if deg.get(ka, 0) >= 3 and deg.get(kb, 0) >= 3:
            uf.union(ka, kb)
            member_coords[ka] = (coords[0][0], coords[0][1])
            member_coords[kb] = (coords[-1][0], coords[-1][1])
            cand_edges[idx] = ka

    if not cand_edges:
        log("Junctions: no residual forks found")
        manifest["rules"]["junctions"] = {"contracted_edges": 0}
        return gdf

    member_root = {k: uf.find(k) for k in member_coords}
    root_pts: dict = {}
    for k, r in member_root.items():
        root_pts.setdefault(r, []).append(member_coords[k])

    # Guard 1: a chain of short edges must not merge nodes spread wider
    # than 2x the tolerance — that is what created zigzag diagonals.
    rejected: set = set()
    for r, pts in root_pts.items():
        spread = max((math.hypot(a[0] - b[0], a[1] - b[1])
                      for a in pts for b in pts), default=0.0)
        if spread > tolerance * 2.0:
            rejected.add(r)

    def build_mapping() -> dict:
        m: dict[tuple[int, int], tuple[float, float]] = {}
        for k, r in member_root.items():
            if r in rejected:
                continue
            pts = root_pts[r]
            m[k] = (sum(p[0] for p in pts) / len(pts),
                    sum(p[1] for p in pts) / len(pts))
        return m

    # Guard 2: simulate every rewrite and reject clusters whose moved
    # lines would cross further into buildings than they already do.
    meter = _make_crossing_meter(buildings)
    mapping = build_mapping()
    for _ in range(3):
        if not mapping:
            break
        newly: set = set()
        for idx, geom in gdf.geometry.items():
            g2 = _move_endpoints(geom, mapping)
            if g2 is geom or g2 is None:
                continue
            if meter(g2) > meter(geom) + 0.5:
                coords = list(geom.coords)
                for pos in (0, -1):
                    k = _key(coords[pos][0], coords[pos][1])
                    r = member_root.get(k)
                    if r is not None and r not in rejected:
                        newly.add(r)
        if not newly:
            break
        rejected |= newly
        mapping = build_mapping()

    drop_idx = [idx for idx, k in cand_edges.items()
                if uf.find(k) not in rejected]
    if not drop_idx:
        log("Junctions: all fork candidates rejected by the guards")
        manifest["rules"]["junctions"] = {"contracted_edges": 0,
                                          "clusters_rejected": len(rejected)}
        return gdf

    review["contracted_junctions"] = gdf.loc[drop_idx, ["geometry"]].copy()

    keep = gdf.drop(index=drop_idx).copy()
    new_geoms, degenerate = [], []
    for idx, geom in keep.geometry.items():
        g2 = _move_endpoints(geom, mapping)
        if g2 is None or g2.length < 0.5:
            degenerate.append(idx)
            new_geoms.append(geom)
        else:
            new_geoms.append(g2)
    keep = keep.set_geometry(pd.Series(new_geoms, index=keep.index), crs=gdf.crs)
    if degenerate:
        keep = keep.drop(index=degenerate)

    # Contracting can leave exact duplicates (two fork prongs become one).
    wkb = keep.geometry.to_wkb()
    keep = keep[~wkb.duplicated()].reset_index(drop=True)

    n_clusters = len({r for r in (uf.find(k) for k in member_coords)
                      if r not in rejected})
    manifest["rules"]["junctions"] = {
        "contracted_edges": len(drop_idx), "node_clusters": n_clusters,
        "clusters_rejected": len(rejected),
        "degenerate_dropped": len(degenerate),
        "elapsed_s": round(time.perf_counter() - t, 1),
    }
    log(f"Junctions: contracted {fmt(len(drop_idx))} fork edges into "
        f"{fmt(n_clusters)} nodes ({len(rejected)} clusters rejected by "
        f"guards) in {time.perf_counter() - t:.1f}s")
    return keep


# ---------------------------------------------------------------------------
# Rule: roundabouts — collapse to star or chords
# ---------------------------------------------------------------------------
def detect_faces(gdf):
    """Polygonise the (noded) network and return the enclosed faces."""
    from shapely.ops import polygonize, unary_union

    merged = unary_union(list(gdf.geometry.values))
    lines = [merged] if merged.geom_type == "LineString" else list(merged.geoms)
    return list(polygonize(lines))


def _radius_cv(face, n: int = 32) -> float:
    """Coefficient of variation of the boundary-to-centroid distance,
    sampled at n equal arc-length steps. A circle scores ~0; a square
    ~0.11; elongated blocks much higher. This is what separates a true
    roundabout ring from a merely compact urban block."""
    ext = face.exterior
    length = ext.length
    if length <= 0:
        return 9.9
    cx, cy = face.centroid.x, face.centroid.y
    ds = []
    for i in range(n):
        pt = ext.interpolate(length * i / n)
        ds.append(math.hypot(pt.x - cx, pt.y - cy))
    mean = sum(ds) / len(ds)
    if mean <= 0:
        return 9.9
    var = sum((d - mean) ** 2 for d in ds) / len(ds)
    return math.sqrt(var) / mean


def _strategy_for(args, diam: float) -> str:
    if args.roundabout_strategy == "star":
        return "star"
    if args.roundabout_strategy == "chords":
        return "chords"
    return "star" if diam < args.star_max_diameter else "chords"


def _make_chords(pts: list, cx: float, cy: float, attrs: dict) -> list[dict]:
    """Straight chords between consecutive entry/exit points around (cx, cy)."""
    from shapely.geometry import LineString

    pts = sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
    rows = []
    n = len(pts)
    pairs = [(i, (i + 1) % n) for i in range(n)] if n > 2 else [(0, 1)]
    for i, j in pairs:
        chord = LineString([pts[i], pts[j]])
        if chord.length >= 0.5:
            rows.append({**attrs, "geometry": chord})
    return rows


def _apply_roundabout_edits(gdf, ring_drop: set, star_mapping: dict,
                            chord_rows: list):
    """Drop ring segments, move star arms to their centres, append chords."""
    import geopandas as gpd
    import pandas as pd

    out = gdf.drop(index=list(ring_drop)).copy()
    if star_mapping:
        new_geoms, degenerate = [], []
        for idx, geom in out.geometry.items():
            g2 = _move_endpoints(geom, star_mapping)
            if g2 is None or g2.length < 0.5:
                degenerate.append(idx)
                new_geoms.append(geom)
            else:
                new_geoms.append(g2)
        out = out.set_geometry(pd.Series(new_geoms, index=out.index), crs=gdf.crs)
        if degenerate:
            out = out.drop(index=degenerate)
    if chord_rows:
        chords_gdf = gpd.GeoDataFrame(chord_rows, geometry="geometry", crs=gdf.crs)
        out = pd.concat([out, chords_gdf], ignore_index=True)
    return gpd.GeoDataFrame(out, geometry="geometry",
                            crs=gdf.crs).reset_index(drop=True)


def rule_roundabouts(gdf, faces, args, buildings, review: dict, manifest: dict):
    """Collapse roundabouts per Kolovou et al. rule 1: no route choice exists
    between entering and the next exit. Small roundabouts become a star of
    arms meeting at the centre; large ones become straight chords between
    consecutive entry/exit points (--roundabout-strategy hybrid|star|chords).

    Detection is tag-driven (`junction=roundabout`, carried through Phase 1)
    whenever tags are present. On legacy untagged inputs the geometric
    detector only WRITES CANDIDATES to the review layer — measured precision
    of pure geometry on Cambridge was 0.16, far too low to act on — unless
    the user opts in with --geometric-roundabouts."""
    has_tags = ("junction" in gdf.columns and gdf["junction"].astype(str)
                .str.lower().isin(["roundabout", "circular"]).any())
    if has_tags:
        return _roundabouts_tagged(gdf, args, buildings, review, manifest)
    return _roundabouts_geometric(gdf, faces, args, buildings, review,
                                  manifest, collapse=args.geometric_roundabouts)


def _building_inside(pts: list, buildings) -> bool:
    """True if a building sits substantially inside the convex hull of the
    entry points — Kolovou et al.: a roundabout with a building in the
    middle behaves like an urban block and must not be collapsed."""
    if buildings is None or len(buildings) == 0 or len(pts) < 3:
        return False
    from shapely.geometry import MultiPoint

    hull = MultiPoint(pts).convex_hull
    if hull.geom_type != "Polygon":
        return False
    for bi in buildings.sindex.query(hull, predicate="intersects"):
        try:
            if hull.intersection(buildings.geometry.iloc[bi]).area > 25.0:
                return True
        except Exception:
            pass
    return False


def _roundabouts_tagged(gdf, args, buildings, review: dict, manifest: dict):
    import geopandas as gpd

    t = time.perf_counter()
    jt = gdf["junction"].astype(str).str.lower()
    is_tagged = jt.isin(["roundabout", "circular"])
    # A genuine ring arc is short; a tag on a long line is attribute smear
    # from the Phase 1 nearest-centroid rejoin. Exclude smeared segments.
    plausible = is_tagged & (gdf.length <= args.roundabout_max_diameter * 1.5)
    n_smeared = int(is_tagged.sum() - plausible.sum())
    if n_smeared:
        log(f"Roundabouts (tagged): ignoring {n_smeared} over-long tagged "
            f"segment(s) (likely attribute smear)")
    tagged = set(gdf.index[plausible])
    if not tagged:
        log("Roundabouts: no usable tagged segments")
        manifest["rules"]["roundabouts"] = {"mode": "tagged", "detected": 0}
        return gdf
    tag_geom = gdf.loc[list(tagged)].geometry
    blobs = gpd.GeoDataFrame(geometry=[tag_geom.buffer(5.0).union_all()],
                             crs=gdf.crs).explode(index_parts=False) \
        .reset_index(drop=True)

    sindex = gdf.sindex
    geoms = gdf.geometry
    detections, ring_drop, star_mapping, chord_rows = [], set(), {}, []
    skipped = 0

    for blob in blobs.geometry:
        cand = sindex.query(blob, predicate="intersects")
        ring_labels = [gdf.index[i] for i in cand
                       if gdf.index[i] in tagged
                       and gdf.index[i] not in ring_drop
                       and geoms.iloc[i].within(blob)]
        if not ring_labels:
            continue
        ring_keys = set()
        ring_pts: list[tuple[float, float]] = []
        for lbl in ring_labels:
            c = list(gdf.geometry[lbl].coords)
            for end in (c[0], c[-1]):
                ring_keys.add(_key(end[0], end[1]))
                ring_pts.append((end[0], end[1]))
        attach: dict[tuple[int, int], tuple[float, float]] = {}
        for i in cand:
            lbl = gdf.index[i]
            if lbl in tagged:
                continue
            c = list(geoms.iloc[i].coords)
            for end in (c[0], c[-1]):
                k = _key(end[0], end[1])
                # Exact node match, or a near-miss within 2.5 m — earlier
                # rules can shift an arm end slightly off the ring node,
                # which used to leave that arm dangling after collapse.
                if k in ring_keys or any(
                        math.hypot(end[0] - rp[0], end[1] - rp[1]) <= 2.5
                        for rp in ring_pts):
                    attach[k] = (end[0], end[1])
        if len(attach) < 2:
            skipped += 1
            continue
        pts = list(attach.values())
        diam = max(math.hypot(a[0] - b[0], a[1] - b[1])
                   for a in pts for b in pts)
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        if diam > args.roundabout_max_diameter:
            # Oversized blob: a complex gyratory system or a chain of
            # tagged features — analyst judgement needed, never automatic.
            detections.append({
                "geometry": blob, "eq_diameter_m": round(diam, 1),
                "circularity": None, "n_arms": len(attach),
                "strategy": "review_too_large", "confidence": "tagged",
            })
            continue
        if _building_inside(pts, buildings):
            detections.append({
                "geometry": blob, "eq_diameter_m": round(diam, 1),
                "circularity": None, "n_arms": len(attach),
                "strategy": "review_building_inside", "confidence": "tagged",
            })
            continue
        strategy = _strategy_for(args, diam)
        if strategy == "star":
            for k in attach:
                star_mapping[k] = (cx, cy)
        else:
            template_lbl = max(ring_labels, key=lambda l: gdf.geometry[l].length)
            attrs = _template_attrs(gdf, template_lbl, "refined_roundabout")
            attrs["junction"] = None  # the chords are no longer a roundabout
            chord_rows.extend(_make_chords(pts, cx, cy, attrs))
        ring_drop.update(ring_labels)
        detections.append({
            "geometry": blob, "eq_diameter_m": round(diam, 1),
            "circularity": None, "n_arms": len(attach),
            "strategy": strategy, "confidence": "tagged",
        })

    if not detections:
        log("Roundabouts: none detected (tagged mode)")
        manifest["rules"]["roundabouts"] = {"mode": "tagged", "detected": 0,
                                            "skipped_no_arms": skipped}
        return gdf

    out = _apply_roundabout_edits(gdf, ring_drop, star_mapping, chord_rows)
    review["roundabouts"] = gpd.GeoDataFrame(detections, geometry="geometry",
                                             crs=gdf.crs)
    n_star = sum(1 for d in detections if d["strategy"] == "star")
    n_chord = sum(1 for d in detections if d["strategy"] == "chords")
    n_review = sum(1 for d in detections if d["strategy"].startswith("review"))
    manifest["rules"]["roundabouts"] = {
        "mode": "tagged", "detected": len(detections), "star": n_star,
        "chords": n_chord, "review_too_large": n_review,
        "skipped_no_arms": skipped, "smeared_tags_ignored": n_smeared,
        "ring_segments_removed": len(ring_drop),
        "chord_segments_added": len(chord_rows),
        "elapsed_s": round(time.perf_counter() - t, 1),
    }
    log(f"Roundabouts (tagged): {n_star + n_chord} collapsed ({n_star} star, "
        f"{n_chord} chords), {n_review} oversized sent to review, "
        f"{fmt(len(ring_drop))} ring segments removed "
        f"in {time.perf_counter() - t:.1f}s")
    return out


def _roundabouts_geometric(gdf, faces, args, buildings, review: dict,
                           manifest: dict, collapse: bool):
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import LineString, Point

    t = time.perf_counter()
    has_junction_tag = "junction" in gdf.columns
    sindex = gdf.sindex
    geoms = gdf.geometry

    detections, ring_drop, star_mapping, chord_rows = [], set(), {}, []

    for face in faces:
        area, perim = face.area, face.exterior.length
        if perim <= 0:
            continue
        eq_diam = 2.0 * math.sqrt(area / math.pi)
        circularity = 4.0 * math.pi * area / (perim * perim)
        if not (args.roundabout_min_diameter <= eq_diam <= args.roundabout_max_diameter):
            continue
        if circularity < args.roundabout_min_circularity:
            continue
        if _radius_cv(face) > args.roundabout_max_radius_cv:
            continue

        ring_buf = face.exterior.buffer(0.5)
        cand = sindex.query(face.exterior, predicate="intersects")
        ring = [i for i in cand
                if geoms.iloc[i].within(ring_buf) and gdf.index[i] not in ring_drop]
        if len(ring) < 2:
            continue
        ring_labels = [gdf.index[i] for i in ring]

        # Must carry vehicular movement (or be tagged) — excludes circular
        # park paths and courtyards.
        classes = gdf.loc[ring_labels, "network_class"] \
            if "network_class" in gdf.columns else pd.Series(dtype=object)
        drivable = bool(classes.isin(["drive", "drive_walk"]).any())
        tagged = bool(
            has_junction_tag
            and gdf.loc[ring_labels, "junction"].astype(str)
                  .str.lower().isin(["roundabout", "circular"]).any()
        )
        if not (drivable or tagged):
            continue

        # Attachment points: ring nodes where a non-ring segment arrives.
        ring_keys = set()
        for lbl in ring_labels:
            c = list(gdf.geometry[lbl].coords)
            ring_keys.add(_key(c[0][0], c[0][1]))
            ring_keys.add(_key(c[-1][0], c[-1][1]))
        ring_set = set(ring_labels)
        attach: dict[tuple[int, int], tuple[float, float]] = {}
        for i in sindex.query(face.buffer(2.0), predicate="intersects"):
            lbl = gdf.index[i]
            if lbl in ring_set:
                continue
            c = list(geoms.iloc[i].coords)
            for end in (c[0], c[-1]):
                k = _key(end[0], end[1])
                if k in ring_keys:
                    attach[k] = (end[0], end[1])
        if len(attach) < (2 if tagged else 3):
            continue

        strategy = _strategy_for(args, eq_diam)
        cx = sum(p[0] for p in attach.values()) / len(attach)
        cy = sum(p[1] for p in attach.values()) / len(attach)

        if collapse and _building_inside(list(attach.values()), buildings):
            detections.append({
                "geometry": face, "eq_diameter_m": round(eq_diam, 1),
                "circularity": round(circularity, 3), "n_arms": len(attach),
                "strategy": "review_building_inside",
                "confidence": "tagged" if tagged else "geometric",
            })
            continue
        if collapse:
            if strategy == "star":
                for k in attach:
                    star_mapping[k] = (cx, cy)
            else:
                template_lbl = max(ring_labels,
                                   key=lambda l: gdf.geometry[l].length)
                attrs = _template_attrs(gdf, template_lbl, "refined_roundabout")
                chord_rows.extend(_make_chords(list(attach.values()), cx, cy,
                                               attrs))
            ring_drop.update(ring_labels)
        detections.append({
            "geometry": face, "eq_diameter_m": round(eq_diam, 1),
            "circularity": round(circularity, 3), "n_arms": len(attach),
            "strategy": strategy,
            "confidence": "tagged" if tagged else "geometric",
        })

    if not detections:
        log("Roundabouts: none detected (geometric mode)")
        manifest["rules"]["roundabouts"] = {"mode": "geometric", "detected": 0}
        return gdf

    review["roundabouts"] = gpd.GeoDataFrame(detections, geometry="geometry",
                                             crs=gdf.crs)
    n_star = sum(1 for d in detections if d["strategy"] == "star")
    n_chord = len(detections) - n_star
    mode = "geometric" if collapse else "geometric_review_only"
    manifest["rules"]["roundabouts"] = {
        "mode": mode, "detected": len(detections), "star": n_star,
        "chords": n_chord, "ring_segments_removed": len(ring_drop),
        "chord_segments_added": len(chord_rows),
        "elapsed_s": round(time.perf_counter() - t, 1),
    }
    if not collapse:
        log(f"Roundabouts (geometric, REVIEW ONLY): {len(detections)} candidates "
            f"written to the review layer — no junction tags in the input. "
            f"Re-run Phase 1 to carry tags, or opt in with "
            f"--geometric-roundabouts to collapse on geometry alone.")
        return gdf

    out = _apply_roundabout_edits(gdf, ring_drop, star_mapping, chord_rows)
    log(f"Roundabouts (geometric): {len(detections)} collapsed ({n_star} star, "
        f"{n_chord} chords), {fmt(len(ring_drop))} ring segments removed "
        f"in {time.perf_counter() - t:.1f}s")
    return out


# ---------------------------------------------------------------------------
# Rule: parallels — collapse same-type vehicular twins to a medial line
# ---------------------------------------------------------------------------
def rule_parallels(gdf, tolerance: float, protect: list[str], buildings,
                   review: dict, manifest: dict, majors_only: bool = False,
                   layer_name: str = "collapsed_parallels",
                   rule_key: str = "parallels"):
    """Collapse bundles of parallel VEHICULAR lines of the same highway type
    into a single medial centre line (Kolovou et al. rule 5: parallel lanes
    are drawn as a single medial line).

    Matching is one-to-many: a long carriageway matches the CHAIN of
    shorter segments running beside it (real twin lines are split
    differently on each side), and matched segments cluster into bundles.
    Every member's end nodes are remapped onto the NEAREST point of the
    medial, which is split there — so side roads and alleys rejoin the
    merged road perpendicular at their true position instead of being
    dragged to the strand ends; median crossover stubs degenerate and drop.

    Scope stays deliberately narrow:
    - the pedestrian network is never touched (walk_only lines are kept);
    - protected classes (default motorway/trunk/primary, plus all `*_link`
      slip roads) keep their dual carriageways;
    - only lines of the SAME highway type merge (two parallel secondaries
      become one secondary — a service road beside a secondary is a distinct
      element and stays);
    - the medial line must not run through buildings, and a segment only
      counts as twinned when >= 70% of it runs within the tolerance at
      near-identical bearing."""
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import LineString, Point

    t = time.perf_counter()
    label = "Dual carriageways" if majors_only else "Parallels"
    if "highway" not in gdf.columns or "network_class" not in gdf.columns:
        manifest["rules"][rule_key] = {"skipped": "missing columns"}
        return gdf

    hw = gdf["highway"].astype(str)
    protected = set(protect) | {p + "_link" for p in protect}
    if majors_only:
        # Dual-carriageway mode: the SAME bundle machinery, but applied to
        # the protected major classes at the wider dual tolerance.
        eligible = (
            hw.isin(set(protect))
            & (gdf.length >= 10.0)
            & ~gdf.apply(_grade_separated, axis=1)
        )
    else:
        eligible = (
            gdf["network_class"].isin(["drive", "drive_walk"])
            & ~hw.isin(protected)
            & ~hw.str.endswith("_link")
            & (gdf.length >= 10.0)
            & ~gdf.apply(_grade_separated, axis=1)
        )
    cand = set(gdf.index[eligible])
    if len(cand) < 2:
        manifest["rules"][rule_key] = {"bundles": 0}
        return gdf

    geoms = gdf.geometry
    sindex = gdf.sindex
    meter = _make_crossing_meter(buildings)

    # Pass 1 — one-to-many sample matching. Real twin lines are split
    # differently on each side (one long carriageway vs a chain of shorter
    # companions), so each sample may match a DIFFERENT partner.
    coverage: dict = {}
    partners: dict = {}
    for idx in cand:
        g = geoms[idx]
        length = g.length
        k = max(5, min(25, int(length / 10)))
        hits = 0
        contrib: dict = {}
        for s in range(k):
            pt = g.interpolate(length * (s + 0.5) / k)
            ba = _bearing_at(g, pt)
            best = None
            for j_pos in sindex.query(pt.buffer(tolerance),
                                      predicate="intersects"):
                j = gdf.index[j_pos]
                if j == idx or j not in cand or hw[j] != hw[idx]:
                    continue
                gj = geoms.iloc[j_pos]
                d = gj.distance(pt)
                if not (0.05 < d <= tolerance):
                    continue
                near = gj.interpolate(gj.project(pt))
                if _bearing_diff(ba, _bearing_at(gj, near)) \
                        > math.radians(25.0):
                    continue
                if best is None or d < best[0]:
                    best = (d, j)
            if best is not None:
                hits += 1
                contrib[best[1]] = contrib.get(best[1], 0) + 1
        coverage[idx] = hits / k
        partners[idx] = contrib

    twinned = {idx for idx in cand if coverage[idx] >= 0.7}
    if not twinned:
        log(f"{label}: no same-type twins found")
        manifest["rules"][rule_key] = {"bundles": 0}
        return gdf

    # Pass 2 — bundle mutually-matched segments via union-find.
    uf = _UnionFind()
    for idx in twinned:
        total = max(1, sum(partners[idx].values()))
        for j, n in partners[idx].items():
            if j in twinned and n >= 0.3 * total:
                uf.union(idx, j)
    bundles: dict = {}
    for idx in twinned:
        bundles.setdefault(uf.find(idx), []).append(idx)

    def _frac_near(geom, ref, tol) -> float:
        n = max(5, min(15, int(geom.length / 10)))
        near = sum(1 for s in range(n)
                   if ref.distance(geom.interpolate(
                       geom.length * (s + 0.5) / n)) <= tol)
        return near / n

    from shapely.ops import substring

    node_deg = node_degrees(gdf.geometry)
    mapping: dict = {}
    drop: set = set()
    medial_rows = []
    n_bundles, bundle_types = 0, {}
    for members in bundles.values():
        if len(members) < 2:
            continue
        spine = max(members, key=lambda i: geoms[i].length)
        g = geoms[spine]
        length = g.length
        if length < 25.0:
            continue
        # Members must lie along the spine — anything extending beyond it
        # stays in the network rather than losing its connectivity.
        members = [i for i in members
                   if i == spine
                   or _frac_near(geoms[i], g, tolerance * 1.1) >= 0.8]
        if len(members) < 2:
            continue
        others = [geoms[i] for i in members if i != spine]

        # Medial: average the spine with its nearest companion point.
        n = max(8, min(60, int(length / 6)))
        mids = []
        for s in range(n + 1):
            pa = g.interpolate(length * s / n)
            best = None
            for go in others:
                d = go.distance(pa)
                if d <= tolerance and (best is None or d < best[0]):
                    best = (d, go)
            if best is None:
                mids.append((pa.x, pa.y))
            else:
                pb = best[1].interpolate(best[1].project(pa))
                mids.append(((pa.x + pb.x) / 2, (pa.y + pb.y) / 2))
        mids = _dedupe_coords(mids)
        if len(mids) < 2:
            continue
        medial = LineString(mids)
        if meter(medial) > sum(meter(geoms[i]) for i in members) + 0.5:
            continue  # the centre of the bundle runs through a building

        # Anchor the medial ENDS on the dominant existing junction node
        # (e.g. a star-collapsed roundabout centre): every approach bundle
        # then meets at ONE point instead of zigzagging between nearby
        # medial endpoints.
        cluster_eps = max(8.0, tolerance * 0.5)
        ends_nodes = []
        seen_keys = set()
        for i in members:
            c = list(geoms[i].coords)
            for end in (c[0], c[-1]):
                k2 = _key(end[0], end[1])
                if k2 in seen_keys:
                    continue
                seen_keys.add(k2)
                p = Point(end)
                dd = medial.project(p)
                if p.distance(medial.interpolate(dd)) <= tolerance * 1.2:
                    ends_nodes.append((k2, (end[0], end[1]), dd))
        coords_m = [(c[0], c[1]) for c in medial.coords]
        Lm = medial.length
        for at_start in (True, False):
            best = None
            for k2, coord, dd in ends_nodes:
                near = dd <= cluster_eps if at_start else dd >= Lm - cluster_eps
                if near and node_deg.get(k2, 0) >= 3 \
                        and (best is None or node_deg[k2] > best[0]):
                    best = (node_deg[k2], coord)
            if best is not None:
                coords_m[0 if at_start else -1] = best[1]
        medial = LineString(_dedupe_coords(coords_m))
        Lm = medial.length

        # Re-project on the FINAL medial and CLUSTER nearby cut points,
        # so a cross street meets the merged road at a single node.
        proj = sorted(((medial.project(Point(coord)), k2, coord)
                       for k2, coord, _ in ends_nodes), key=lambda r: r[0])
        groups = []
        for r in proj:
            if groups and r[0] - groups[-1][-1][0] <= cluster_eps:
                groups[-1].append(r)
            else:
                groups.append([r])
        cuts = {0.0, round(Lm, 3)}
        m0 = (coords_m[0][0], coords_m[0][1])
        m1 = (coords_m[-1][0], coords_m[-1][1])
        for grp in groups:
            mean_dd = sum(r[0] for r in grp) / len(grp)
            if mean_dd <= cluster_eps:
                target = m0
            elif mean_dd >= Lm - cluster_eps:
                target = m1
            else:
                dd_r = round(mean_dd, 3)
                pt = medial.interpolate(dd_r)
                target = (pt.x, pt.y)
                cuts.add(dd_r)
            for _, k2, coord in grp:
                if coord != target:
                    mapping[k2] = target
        attrs = _template_attrs(gdf, spine, "refined_parallel")
        if "oneway" in attrs:
            attrs["oneway"] = None  # the merged centre line is two-way
        cut_list = sorted(cuts)
        for a, b in zip(cut_list[:-1], cut_list[1:]):
            if b - a < 0.5:
                continue
            piece = substring(medial, a, b)
            if piece.geom_type == "LineString" and piece.length >= 0.5:
                medial_rows.append({**attrs, "geometry": piece})
        drop.update(members)
        n_bundles += 1
        bundle_types[hw[spine]] = bundle_types.get(hw[spine], 0) + 1

    if not drop:
        log(f"{label}: no same-type twins found")
        manifest["rules"][rule_key] = {"bundles": 0}
        return gdf

    review[layer_name] = gdf.loc[sorted(drop), ["geometry"]].copy()

    out = gdf.drop(index=list(drop)).copy()
    new_geoms, degenerate = [], []
    for ridx, geom in out.geometry.items():
        g2 = _move_endpoints(geom, mapping)
        if g2 is None or g2.length < 0.5:
            degenerate.append(ridx)
            new_geoms.append(geom)
        else:
            new_geoms.append(g2)
    out = out.set_geometry(pd.Series(new_geoms, index=out.index), crs=gdf.crs)
    if degenerate:
        out = out.drop(index=degenerate)  # median crossover stubs collapse
    add = gpd.GeoDataFrame(medial_rows, geometry="geometry", crs=gdf.crs)
    out = pd.concat([out, add], ignore_index=True)
    out = gpd.GeoDataFrame(out, geometry="geometry", crs=gdf.crs)
    wkb = out.geometry.to_wkb()
    out = out[~wkb.duplicated()].reset_index(drop=True)

    manifest["rules"][rule_key] = {
        "bundles": n_bundles, "segments_collapsed": len(drop),
        "by_type": bundle_types,
        "crossover_stubs_dropped": len(degenerate),
        "elapsed_s": round(time.perf_counter() - t, 1),
    }
    log(f"{label}: collapsed {n_bundles} twin bundles "
        f"({fmt(len(drop))} segments) to medial lines "
        f"({len(degenerate)} crossover stubs dropped) "
        f"in {time.perf_counter() - t:.1f}s")
    return out


# ---------------------------------------------------------------------------
# Rule: gaps — extend dangling undershoots
# ---------------------------------------------------------------------------
def rule_gaps(gdf, tolerance: float, unlinks, buildings, review: dict,
              manifest: dict):
    """Directionally extend dangling line ends that stop just short of the
    road they visibly join (Krenz's topological inconsistency). The dangle's
    own bearing decides where it lands — sideways snaps are never made, so
    genuine cul-de-sacs survive. Bridge/tunnel dangles and ends near a
    Phase 1 unlink point are left alone."""
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import LineString, Point
    from shapely.ops import split as shp_split
    from shapely import snap as shp_snap

    t = time.perf_counter()
    gdf = gdf.reset_index(drop=True)
    deg = node_degrees(gdf.geometry)
    sindex = gdf.sindex
    unlink_buf = None
    if unlinks is not None and len(unlinks) > 0:
        unlink_buf = unlinks.geometry.union_all().buffer(15.0)
    b_sindex = buildings.sindex if buildings is not None else None

    extensions: dict[int, dict[int, tuple[float, float]]] = {}
    splits: dict[int, list] = {}
    connector_pts = []

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty or _grade_separated(row):
            continue
        coords = list(geom.coords)
        for end_flag, pos, prev in ((0, 0, 1),
                                    (-1, len(coords) - 1, len(coords) - 2)):
            p = coords[pos]
            if deg.get(_key(p[0], p[1]), 0) != 1:
                continue
            if unlink_buf is not None and unlink_buf.contains(Point(p)):
                continue
            q = coords[prev]
            dx, dy = p[0] - q[0], p[1] - q[1]
            norm = math.hypot(dx, dy)
            if norm < 1e-9:
                continue
            dx, dy = dx / norm, dy / norm
            ray = LineString([p, (p[0] + dx * tolerance, p[1] + dy * tolerance)])
            best = None
            for ci in sindex.query(ray, predicate="intersects"):
                if ci == idx:
                    continue
                inter = gdf.geometry.iloc[ci].intersection(ray)
                if inter.is_empty:
                    continue
                pts = []
                if inter.geom_type == "Point":
                    pts = [inter]
                elif inter.geom_type == "MultiPoint":
                    pts = list(inter.geoms)
                for pt in pts:
                    d = math.hypot(pt.x - p[0], pt.y - p[1])
                    if 0.05 < d <= tolerance and (best is None or d < best[0]):
                        best = (d, ci, (pt.x, pt.y))
            if best is None:
                continue
            d, ci, hit = best
            connector = LineString([p, hit])
            if b_sindex is not None:
                blocked = False
                for bi in b_sindex.query(connector, predicate="intersects"):
                    if connector.crosses(buildings.geometry.iloc[bi]):
                        blocked = True
                        break
                if blocked:
                    continue
            extensions.setdefault(idx, {})[end_flag] = hit
            splits.setdefault(ci, []).append(hit)
            connector_pts.append(Point(hit))

    if not extensions:
        log("Gaps: no undershoots found")
        manifest["rules"]["gaps"] = {"extended_dangles": 0}
        return gdf

    # Apply dangle extensions (a fully isolated line may gain both ends).
    geo = gdf.geometry.copy()
    n_ext = 0
    for idx, hits in extensions.items():
        coords = [(c[0], c[1]) for c in geo.iloc[idx].coords]
        if -1 in hits:
            coords.append(hits[-1])
            n_ext += 1
        if 0 in hits:
            coords.insert(0, hits[0])
            n_ext += 1
        geo.iloc[idx] = LineString(coords)
    gdf = gdf.set_geometry(geo, crs=gdf.crs)

    # Split target lines at the new junction points so topology is real.
    new_rows, drop_targets = [], []
    for ci, hits in splits.items():
        target = gdf.geometry.iloc[ci]
        pts = [Point(h) for h in hits]
        try:
            snapped = target
            for pt in pts:
                snapped = shp_snap(snapped, pt, 0.05)
            parts = snapped
            for pt in pts:
                pieces = []
                geoms = parts.geoms if parts.geom_type != "LineString" else [parts]
                for g in geoms:
                    try:
                        sp = shp_split(g, pt)
                        pieces.extend(list(sp.geoms))
                    except Exception:
                        pieces.append(g)
                from shapely.geometry import MultiLineString
                parts = MultiLineString([g for g in pieces
                                         if g.geom_type == "LineString"])
            attrs = _template_attrs(gdf, gdf.index[ci], "refined_split")
            kept = [g for g in parts.geoms if g.length > 0.05]
            if len(kept) >= 2:
                drop_targets.append(gdf.index[ci])
                for g in kept:
                    new_rows.append({**attrs, "geometry": g})
        except Exception:
            continue  # leave the target unsplit rather than corrupt it

    if drop_targets:
        gdf = gdf.drop(index=drop_targets)
    if new_rows:
        add = gpd.GeoDataFrame(new_rows, geometry="geometry", crs=gdf.crs)
        gdf = pd.concat([gdf, add], ignore_index=True)
    gdf = gpd.GeoDataFrame(gdf, geometry="geometry", crs=gdf.crs).reset_index(drop=True)

    review["gap_connectors"] = gpd.GeoDataFrame(geometry=connector_pts, crs=gdf.crs)
    manifest["rules"]["gaps"] = {
        "extended_dangles": n_ext, "targets_split": len(drop_targets),
        "elapsed_s": round(time.perf_counter() - t, 1),
    }
    log(f"Gaps: extended {fmt(n_ext)} undershoot dangles, split "
        f"{fmt(len(drop_targets))} target lines in {time.perf_counter() - t:.1f}s")
    return gdf


# ---------------------------------------------------------------------------
# Rule: sliproads — straighten *_link roads
# ---------------------------------------------------------------------------
def rule_sliproads(gdf, review: dict, manifest: dict):
    """Replace each `*_link` slip road's meandering geometry with the
    straight chord between its endpoints. Endpoints (and therefore
    connectivity) are untouched; only the angular noise of the curve goes
    (Krenz: traffic management detail has no cognitive route meaning)."""
    from shapely.geometry import LineString

    t = time.perf_counter()
    if "highway" not in gdf.columns:
        manifest["rules"]["sliproads"] = {"straightened": 0}
        return gdf
    mask = gdf["highway"].astype(str).str.endswith("_link")
    n = 0
    geo = gdf.geometry.copy()
    for idx in gdf.index[mask]:
        geom = geo[idx]
        if geom is None or geom.is_empty:
            continue
        coords = list(geom.coords)
        if len(coords) <= 2:
            continue
        a, b = coords[0], coords[-1]
        if _key(a[0], a[1]) == _key(b[0], b[1]):
            continue  # closed loop link — leave alone
        geo[idx] = LineString([a, b])
        n += 1
    gdf = gdf.set_geometry(geo, crs=gdf.crs)
    manifest["rules"]["sliproads"] = {
        "straightened": n, "elapsed_s": round(time.perf_counter() - t, 1),
    }
    log(f"Slip roads: straightened {fmt(n)} link segments "
        f"in {time.perf_counter() - t:.1f}s")
    return gdf


# ---------------------------------------------------------------------------
# Rule: smoothing — hierarchy-scaled Douglas-Peucker
# ---------------------------------------------------------------------------
def rule_smoothing(gdf, buildings, review: dict, manifest: dict):
    """Douglas-Peucker per segment with a tolerance scaled to the road
    hierarchy (a proxy for street width / field of vision, Krenz 2017).
    Endpoints are preserved by the algorithm, so connectivity is safe.

    Building guard: if straightening a curve would cut the corner of a
    building the original line skirted, retry at half tolerance, and if
    still blocked keep the original geometry."""
    t = time.perf_counter()
    hw = gdf["highway"].astype(str) if "highway" in gdf.columns else None
    meter = _make_crossing_meter(buildings)
    geo = gdf.geometry.copy()
    n_changed, n_vetoed, before = 0, 0, 0
    for idx in gdf.index:
        geom = geo[idx]
        if geom is None or geom.is_empty:
            continue
        tol = SMOOTHING_TOLERANCE.get(hw[idx], SMOOTHING_DEFAULT) \
            if hw is not None else SMOOTHING_DEFAULT
        before += len(geom.coords)
        g2 = geom.simplify(tol, preserve_topology=True)
        if len(g2.coords) >= len(geom.coords):
            continue
        base_cross = meter(geom)
        if meter(g2) > base_cross + 0.5:
            g2 = geom.simplify(tol / 2.0, preserve_topology=True)
            if (len(g2.coords) >= len(geom.coords)
                    or meter(g2) > base_cross + 0.5):
                n_vetoed += 1
                continue
        geo[idx] = g2
        n_changed += 1
    gdf = gdf.set_geometry(geo, crs=gdf.crs)
    after = int(sum(len(g.coords) for g in gdf.geometry if g is not None))
    manifest["rules"]["smoothing"] = {
        "segments_smoothed": n_changed, "vetoed_by_buildings": n_vetoed,
        "vertices_before": int(before), "vertices_after": after,
        "elapsed_s": round(time.perf_counter() - t, 1),
    }
    log(f"Smoothing: {fmt(n_changed)} segments, vertices {fmt(int(before))} -> "
        f"{fmt(after)} ({n_vetoed} vetoed by buildings) "
        f"in {time.perf_counter() - t:.1f}s")
    return gdf


# ---------------------------------------------------------------------------
# Rule: dual_carriageways — opt-in second consolidation pass on major roads
# ---------------------------------------------------------------------------
def rule_dual_carriageways(gdf, tolerance: float, protect: list[str],
                           buildings, review: dict, manifest: dict):
    """Opt-in (--merge-dual-carriageways): merge dual carriageways on the
    protected major classes using the SAME bundle machinery as `parallels`,
    at the wider --dual-tolerance. Side roads are re-noded onto the medial
    line, so minor-road junctions survive the merge — the previous
    neatnet-subset implementation rebuilt major geometry in isolation and
    left every minor road that joined it dangling."""
    return rule_parallels(gdf, tolerance, protect, buildings, review,
                          manifest, majors_only=True,
                          layer_name="collapsed_dual_carriageways",
                          rule_key="dual_carriageways")


# ---------------------------------------------------------------------------
# Review-only detectors (nothing is changed automatically)
# ---------------------------------------------------------------------------
def detect_square_candidates(gdf, faces, buildings, review: dict, manifest: dict):
    """Kolovou rule 3 needs an analyst: detect square-like faces bounded
    mostly by pedestrian segments and propose straight entry-to-exit links
    between every mutually visible pair. Written to the review GeoPackage
    only — accept or reject in QGIS."""
    import geopandas as gpd
    from shapely.geometry import LineString

    t = time.perf_counter()
    if "network_class" not in gdf.columns:
        return
    sindex = gdf.sindex
    geoms = gdf.geometry
    face_rows, link_rows = [], []
    b_sindex = buildings.sindex if buildings is not None else None

    for face in faces:
        area, perim = face.area, face.exterior.length
        if perim <= 0:
            continue
        eq_diam = 2.0 * math.sqrt(area / math.pi)
        if not (10.0 <= eq_diam <= 80.0):
            continue
        ring_buf = face.exterior.buffer(0.5)
        cand = sindex.query(face.exterior, predicate="intersects")
        ring = [i for i in cand if geoms.iloc[i].within(ring_buf)]
        if len(ring) < 3:
            continue
        ring_labels = [gdf.index[i] for i in ring]
        lens = gdf.geometry[ring_labels].length
        walk = gdf.loc[ring_labels, "network_class"] == "walk_only"
        if lens.sum() <= 0 or (lens[walk.values].sum() / lens.sum()) < 0.6:
            continue
        ring_keys = set()
        for lbl in ring_labels:
            c = list(gdf.geometry[lbl].coords)
            ring_keys.add(_key(c[0][0], c[0][1]))
            ring_keys.add(_key(c[-1][0], c[-1][1]))
        ring_set = set(ring_labels)
        attach = {}
        for i in sindex.query(face.buffer(2.0), predicate="intersects"):
            lbl = gdf.index[i]
            if lbl in ring_set:
                continue
            c = list(geoms.iloc[i].coords)
            for end in (c[0], c[-1]):
                k = _key(end[0], end[1])
                if k in ring_keys:
                    attach[k] = (end[0], end[1])
        if len(attach) < 3:
            continue
        from shapely.geometry import Point

        def _blocked(link) -> bool:
            if b_sindex is None:
                return False
            return any(link.crosses(buildings.geometry.iloc[bi])
                       for bi in b_sindex.query(link, predicate="intersects"))

        pts = list(attach.values())
        cx = sum(p[0] for p in pts) / len(pts)
        cy = sum(p[1] for p in pts) / len(pts)
        ordered = sorted(pts, key=lambda p: math.atan2(p[1] - cy, p[0] - cx))
        n_links = 0
        # (a) Straight perimeter links between consecutive entries — the
        # fewest-lines circulation around the space (Kolovou rule 3).
        m = len(ordered)
        consec = ([(i, (i + 1) % m) for i in range(m)] if m > 2
                  else [(0, 1)])
        perim_set = {frozenset(pr) for pr in consec}
        for i, j in consec:
            link = LineString([ordered[i], ordered[j]])
            if link.length < 1.0 or _blocked(link):
                continue
            link_rows.append({"geometry": link, "face_id": len(face_rows),
                              "kind": "perimeter"})
            n_links += 1
        # (a2) Crossing links — every OTHER entry-to-entry chord (the V6
        # all-pairs behaviour). On a crossable open plaza these are the
        # real desire lines; on an uncrossable garden block they are
        # spurious. Geometry cannot tell the two apart (hence review-only),
        # so they are emitted as a SEPARATE `kind` for the analyst to keep
        # or delete — the chord must stay inside the face and clear of
        # buildings to be proposed at all.
        face_keep = face.buffer(1.0)
        for i in range(m):
            for j in range(i + 1, m):
                if frozenset((i, j)) in perim_set:
                    continue
                link = LineString([ordered[i], ordered[j]])
                if link.length < 1.0 or _blocked(link):
                    continue
                if not face_keep.contains(link):
                    continue  # leaves the open space — not a real crossing
                link_rows.append({"geometry": link,
                                  "face_id": len(face_rows), "kind": "crossing"})
                n_links += 1
        # (b) A short connector from each entry, perpendicular onto the
        # nearest street — how the square should join the street network.
        for p in pts:
            ppt = Point(p)
            best = None
            for si in sindex.query(ppt.buffer(15.0), predicate="intersects"):
                lbl = gdf.index[si]
                if lbl in ring_set:
                    continue
                if gdf.loc[lbl, "network_class"] == "walk_only":
                    continue
                gs = geoms.iloc[si]
                d = gs.distance(ppt)
                if 0.5 < d <= 15.0 and (best is None or d < best[0]):
                    best = (d, gs)
            if best is None:
                continue
            foot = best[1].interpolate(best[1].project(ppt))
            conn = LineString([p, (foot.x, foot.y)])
            if _bearing_diff(_bearing_at(best[1], foot),
                             math.atan2(foot.y - p[1], foot.x - p[0])) \
                    < math.radians(55.0):
                continue  # not a perpendicular join — skip
            if _blocked(conn):
                continue
            link_rows.append({"geometry": conn, "face_id": len(face_rows),
                              "kind": "street_connector"})
            n_links += 1
        face_rows.append({"geometry": face, "eq_diameter_m": round(eq_diam, 1),
                          "n_entries": len(attach), "proposed_links": n_links})

    if face_rows:
        review["square_faces"] = gpd.GeoDataFrame(face_rows, geometry="geometry",
                                                  crs=gdf.crs)
        review["square_links"] = gpd.GeoDataFrame(link_rows, geometry="geometry",
                                                  crs=gdf.crs)
    manifest["review"]["squares"] = {
        "faces": len(face_rows), "proposed_links": len(link_rows),
        "elapsed_s": round(time.perf_counter() - t, 1),
    }
    log(f"Squares (review only): {len(face_rows)} candidate spaces, "
        f"{fmt(len(link_rows))} proposed links in {time.perf_counter() - t:.1f}s")


def detect_disconnect_candidates(gdf, unlinks, review: dict, manifest: dict,
                                 reach: float = 25.0):
    """Flag likely disconnections for manual review: a degree-1 endpoint
    lying within `reach` of another line is usually a road that should
    join it, not a genuine cul-de-sac tip. Review layer only."""
    import geopandas as gpd
    from shapely.geometry import Point

    t = time.perf_counter()
    deg = node_degrees(gdf.geometry)
    sindex = gdf.sindex
    unlink_buf = None
    if unlinks is not None and len(unlinks) > 0:
        unlink_buf = unlinks.geometry.union_all().buffer(15.0)
    rows = []
    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty or _grade_separated(row):
            continue
        cs = list(geom.coords)
        for c in (cs[0], cs[-1]):
            if deg.get(_key(c[0], c[1]), 0) != 1:
                continue
            p = Point(c)
            if unlink_buf is not None and unlink_buf.contains(p):
                continue
            best = None
            for j in sindex.query(p.buffer(reach), predicate="intersects"):
                if gdf.index[j] == idx:
                    continue
                d = gdf.geometry.iloc[j].distance(p)
                if d > 0.05 and (best is None or d < best):
                    best = d
            if best is not None and best <= reach:
                rows.append({"geometry": p, "gap_m": round(best, 1),
                             "highway": row.get("highway")})
    if rows:
        review["disconnect_candidates"] = gpd.GeoDataFrame(
            rows, geometry="geometry", crs=gdf.crs)
    manifest["review"]["disconnect_candidates"] = {
        "flagged": len(rows), "elapsed_s": round(time.perf_counter() - t, 1),
    }
    log(f"Disconnect candidates (review only): {fmt(len(rows))} dangling "
        f"ends within {reach:.0f} m of another line "
        f"in {time.perf_counter() - t:.1f}s")


def detect_deletion_candidates(gdf, buildings, review: dict, manifest: dict):
    """Flag likely spurious links for manual deletion: segments running
    through building footprints (excluding tagged building passages) and
    tiny fully isolated fragments. Review layer only — never auto-deleted."""
    import geopandas as gpd

    t = time.perf_counter()
    rows = []
    deg = node_degrees(gdf.geometry)

    if buildings is not None and "network_class" in gdf.columns:
        b_sindex = buildings.sindex
        subset = gdf[gdf["network_class"].isin(["walk_only"]) |
                     (gdf.get("access_class") == "private")]
        for idx, row in subset.iterrows():
            if str(row.get("tunnel", "")).lower() == "building_passage":
                continue
            geom = row.geometry
            if geom is None or geom.is_empty:
                continue
            inter_len = 0.0
            for bi in b_sindex.query(geom, predicate="intersects"):
                try:
                    inter_len += geom.intersection(buildings.geometry.iloc[bi]).length
                except Exception:
                    pass
            if geom.length > 0 and inter_len / geom.length > 0.4:
                rows.append({"geometry": geom, "reason": "crosses_buildings",
                             "share_in_buildings": round(inter_len / geom.length, 2)})

    for idx, row in gdf.iterrows():
        geom = row.geometry
        if geom is None or geom.is_empty or geom.length >= 10.0:
            continue
        c = list(geom.coords)
        ka, kb = _key(c[0][0], c[0][1]), _key(c[-1][0], c[-1][1])
        if deg.get(ka, 0) == 1 and deg.get(kb, 0) == 1:
            rows.append({"geometry": geom, "reason": "isolated_fragment",
                         "share_in_buildings": None})

    if rows:
        review["deletion_candidates"] = gpd.GeoDataFrame(rows, geometry="geometry",
                                                         crs=gdf.crs)
    manifest["review"]["deletion_candidates"] = {
        "flagged": len(rows), "elapsed_s": round(time.perf_counter() - t, 1),
    }
    log(f"Deletion candidates (review only): {fmt(len(rows))} flagged "
        f"in {time.perf_counter() - t:.1f}s")


# ---------------------------------------------------------------------------
# Unlinks — recompute after refinement (geometry has moved)
# ---------------------------------------------------------------------------
def recompute_unlinks(gdf, original=None):
    """Crossing points between segments on different effective layers
    (bridge +1, tunnel -1) are unlinks, not junctions — same logic as
    Phase 1, plus two recoveries the attribute logic alone cannot make:

    - neatnet merges a bridge deck with its approach roads, and the
      `bridge` tag does not always survive the merge. A crossing whose
      attribute layers come out EQUAL is therefore checked against the
      ORIGINAL network: if an original grade-separated segment runs along
      one of the crossing lines at that point, it is an unlink after all.
    - same-layer interior crossings with NO original evidence are returned
      separately as `unresolved` — they are either missing junctions or
      noding errors and belong in the review file, not silently dropped.

    Only interior-to-interior crossings are examined for recovery; shared
    endpoints are ordinary junctions."""
    import geopandas as gpd
    import pandas as pd

    work = gdf.copy()
    work["_layer"] = pd.to_numeric(work.get("layer"), errors="coerce") \
        .fillna(0).astype(int)
    work["_layer"] = work.apply(
        lambda r: r["_layer"] + 1 if _yes(r.get("bridge"))
        else (r["_layer"] - 1 if _yes(r.get("tunnel")) else r["_layer"]), axis=1)
    work = work.reset_index(drop=True)
    sindex = work.sindex

    evid, evid_sindex = None, None
    if original is not None and len(original) > 0:
        ev = original[original.apply(_grade_separated, axis=1)]
        if len(ev) > 0:
            evid = ev.reset_index(drop=True)
            evid_sindex = evid.sindex

    def _has_evidence(pt, ga, gb) -> bool:
        """An original bridge/tunnel segment runs along ga or gb at pt."""
        if evid is None:
            return False
        for ei in evid_sindex.query(pt.buffer(5.0), predicate="intersects"):
            g = evid.geometry.iloc[ei]
            if g.distance(pt) > 5.0:
                continue
            be = _bearing_at(g, pt)
            for go in (ga, gb):
                bo = _bearing_at(go, pt)
                diff = abs((be - bo + math.pi / 2) % math.pi - math.pi / 2)
                if diff < math.radians(30.0):
                    return True
        return False

    pts, unresolved = [], []
    for k, row in work.iterrows():
        geom = row.geometry
        ca = list(geom.coords)
        ends_a = {_key(ca[0][0], ca[0][1]), _key(ca[-1][0], ca[-1][1])}
        for oid in sindex.intersection(geom.bounds):
            if k >= oid:
                continue
            other = work.iloc[oid]
            if not geom.intersects(other.geometry):
                continue
            inter = geom.intersection(other.geometry)
            if inter.is_empty:
                continue
            if inter.geom_type == "Point":
                cand = [inter]
            elif inter.geom_type == "MultiPoint":
                cand = list(inter.geoms)
            else:
                try:
                    cand = [inter.centroid]
                except Exception:
                    cand = []
            oc = list(other.geometry.coords)
            ends_b = {_key(oc[0][0], oc[0][1]), _key(oc[-1][0], oc[-1][1])}
            if row["_layer"] != other["_layer"]:
                # A bridge/boardwalk MEETING a path at a shared node is a
                # connection, not an unlink — only keep points where at
                # least one line is crossed through its interior.
                for pt in cand:
                    pk = _key(pt.x, pt.y)
                    if pk in ends_a and pk in ends_b:
                        continue
                    pts.append(pt)
                continue
            # Equal attribute layers: examine interior crossings only.
            ends = ends_a | ends_b
            for pt in cand:
                if _key(pt.x, pt.y) in ends:
                    continue  # endpoint touch = ordinary junction
                # Two near-parallel lines crossing at grazing angle are a
                # smoothing artefact of twin carriageways on a curve, not a
                # grade separation — a real unlink crosses at a real angle.
                ba = _bearing_at(geom, pt)
                bb = _bearing_at(other.geometry, pt)
                if abs((ba - bb + math.pi / 2) % math.pi - math.pi / 2) \
                        < math.radians(25.0):
                    unresolved.append(pt)
                    continue
                if _has_evidence(pt, geom, other.geometry):
                    pts.append(pt)
                else:
                    unresolved.append(pt)

    def _points_gdf(plist):
        return gpd.GeoDataFrame(geometry=plist, crs=gdf.crs) \
            .drop_duplicates().reset_index(drop=True)

    return _points_gdf(pts), _points_gdf(unresolved)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def run(args: argparse.Namespace) -> int:
    import geopandas as gpd

    t_pipeline = time.perf_counter()
    in_path = Path(args.input)
    if not in_path.exists():
        log(f"!!! ERROR: input not found: {in_path}")
        return 2
    out_dir = Path(args.output) if args.output else in_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    stem = in_path.stem
    base = args.name or (stem[:-len("_simplified")] if stem.endswith("_simplified")
                         else stem)

    rules = [r.strip() for r in args.rules.split(",") if r.strip()]
    if args.merge_dual_carriageways and "dual_carriageways" not in rules:
        rules.append("dual_carriageways")
    bad = [r for r in rules if r not in ALL_RULES]
    if bad:
        log(f"!!! ERROR: unknown rule(s): {', '.join(bad)}. "
            f"Known: {', '.join(ALL_RULES)}")
        return 2

    def _sibling(suffix: str) -> Optional[Path]:
        p = in_path.with_name(f"{base}_{suffix}.gpkg")
        return p if p.exists() else None

    buildings_path = Path(args.buildings) if args.buildings else _sibling("buildings")
    unlinks_path = Path(args.unlinks) if args.unlinks else _sibling("unlinks")

    log("Plan:")
    log(f"  Input        : {in_path.name}")
    log(f"  Rules        : {', '.join(rules)}")
    log(f"  Roundabouts  : {args.roundabout_strategy} "
        f"(star below {args.star_max_diameter} m)")
    log(f"  Buildings    : {buildings_path.name if buildings_path else 'none'}")
    log(f"  Unlinks      : {unlinks_path.name if unlinks_path else 'none'}")
    log(f"  Output       : {out_dir.resolve()}")
    log(f"  File prefix  : {base}")
    log("")

    log(f"Loading {in_path.name} ...")
    gdf = gpd.read_file(in_path)
    if gdf.crs is None or getattr(gdf.crs, "is_geographic", False):
        log("!!! ERROR: input must be in a projected CRS in metres "
            "(run Phase 1 first).")
        return 2
    gdf = gdf.reset_index(drop=True)
    n0, len0 = len(gdf), gdf.length.sum() / 1000
    log(f"Network: {fmt(n0)} segments, {len0:.0f} km (CRS {gdf.crs.to_epsg()})")

    buildings = None
    if buildings_path:
        buildings = gpd.read_file(buildings_path).to_crs(gdf.crs)
        buildings = buildings[buildings.geometry.geom_type.isin(
            ["Polygon", "MultiPolygon"])].reset_index(drop=True)
        log(f"Buildings: {fmt(len(buildings))} footprints")
    unlinks = None
    if unlinks_path:
        unlinks = gpd.read_file(unlinks_path).to_crs(gdf.crs)
        log(f"Unlinks: {fmt(len(unlinks))} Phase 1 crossing points")

    manifest: dict = {
        "input": str(in_path), "rules": {}, "review": {},
        "params": {
            "rules": rules, "junction_tolerance": args.junction_tolerance,
            "gap_tolerance": args.gap_tolerance,
            "roundabout_strategy": args.roundabout_strategy,
            "star_max_diameter": args.star_max_diameter,
            "roundabout_min_diameter": args.roundabout_min_diameter,
            "roundabout_max_diameter": args.roundabout_max_diameter,
            "roundabout_min_circularity": args.roundabout_min_circularity,
            "roundabout_max_radius_cv": args.roundabout_max_radius_cv,
            "parallel_tolerance": args.parallel_tolerance,
            "parallel_protect": args.parallel_protect,
            "dual_tolerance": args.dual_tolerance,
        },
        "started_utc": datetime.now(timezone.utc).isoformat(),
    }
    review: dict = {}
    input_wkb = set(gdf.geometry.to_wkb())

    gdf = cleanup_network(gdf, review, manifest, stage="input")

    if "junctions" in rules:
        gdf = rule_junctions(gdf, args.junction_tolerance, buildings, review,
                             manifest)
        gdf = gdf.reset_index(drop=True)

    faces = None
    if "roundabouts" in rules or not args.no_review:
        log("Polygonising network faces ...")
        t = time.perf_counter()
        faces = detect_faces(gdf)
        log(f"Faces: {fmt(len(faces))} in {time.perf_counter() - t:.1f}s")

    if "roundabouts" in rules:
        gdf = rule_roundabouts(gdf, faces, args, buildings, review, manifest)
        gdf = gdf.reset_index(drop=True)

    protect = [s.strip().lower() for s in args.parallel_protect.split(",")
               if s.strip()]
    if "parallels" in rules:
        gdf = rule_parallels(gdf, args.parallel_tolerance, protect, buildings,
                             review, manifest)
        gdf = gdf.reset_index(drop=True)

    if "dual_carriageways" in rules:
        gdf = rule_dual_carriageways(gdf, args.dual_tolerance, protect,
                                     buildings, review, manifest)
        gdf = gdf.reset_index(drop=True)

    if "gaps" in rules:
        gdf = rule_gaps(gdf, args.gap_tolerance, unlinks, buildings, review,
                        manifest)
        gdf = gdf.reset_index(drop=True)

    if "sliproads" in rules:
        gdf = rule_sliproads(gdf, review, manifest)

    if "smoothing" in rules:
        gdf = rule_smoothing(gdf, buildings, review, manifest)

    if not args.no_review:
        detect_square_candidates(gdf, faces if faces is not None else [],
                                 buildings, review, manifest)
        detect_deletion_candidates(gdf, buildings, review, manifest)
        detect_disconnect_candidates(gdf, unlinks, review, manifest)

    gdf = cleanup_network(gdf, review, manifest, stage="final")

    # ---- Diff vs input ----------------------------------------------------
    out_wkb = gdf.geometry.to_wkb()
    unchanged = out_wkb.isin(input_wkb)
    review["changed_or_added"] = gdf[~unchanged][["geometry"]].copy()

    n1, len1 = len(gdf), gdf.length.sum() / 1000
    manifest["result"] = {
        "segments_in": n0, "segments_out": n1,
        "length_km_in": round(len0, 1), "length_km_out": round(len1, 1),
        "segments_changed_or_added": int((~unchanged).sum()),
        "qa": qa_metrics(gdf, review),
    }
    q = manifest["result"]["qa"]
    log(f"QA: {q['duplicate_groups_exploded']} residual duplicate groups, "
        f"{q['segments_under_0p1m']} segments <0.1 m, "
        f"{q['components']} components (largest "
        f"{q['largest_component_pct']}% by length)")

    # ---- Unlinks (before saving, so unresolved crossings join the review) --
    unlinks_out = None
    if args.detect_unlinks:
        original = None
        original_path = Path(args.original) if args.original \
            else _sibling("original")
        if original_path and original_path.exists():
            log(f"Loading {original_path.name} (grade-separation evidence) ...")
            original = gpd.read_file(original_path).to_crs(gdf.crs)
        else:
            log("No original network found — unlink recovery for merged "
                "bridge tags is OFF (pass --original to enable).")
        log("Recomputing unlinks on the refined network ...")
        t = time.perf_counter()
        unlinks_out, unresolved = recompute_unlinks(gdf, original)
        if len(unresolved) > 0:
            review["unresolved_crossings"] = unresolved
        manifest["rules"]["unlinks"] = {
            "points": int(len(unlinks_out)),
            "unresolved_crossings": int(len(unresolved)),
            "evidence_network": str(original_path) if original is not None else None,
            "elapsed_s": round(time.perf_counter() - t, 1),
        }
        log(f"Unlinks: {fmt(len(unlinks_out))} crossing points, "
            f"{fmt(len(unresolved))} unresolved same-level crossings "
            f"(review layer) in {time.perf_counter() - t:.1f}s")

    # ---- Save --------------------------------------------------------------
    log("")
    log(f"Saving outputs to {out_dir.resolve()} ...")
    refined_path = out_dir / f"{base}_refined.gpkg"
    review_stale = out_dir / f"{base}_refinement_review.gpkg"
    for stale in (refined_path, review_stale,
                  out_dir / f"{base}_refined_unlinks.gpkg"):
        if stale.exists():
            try:
                stale.unlink()  # avoid stale layers from a previous run
            except PermissionError:
                log(f"!!! ERROR: {stale.name} is locked by another program "
                    f"(open in QGIS?). Close it and re-run, or use a "
                    f"different --output folder.")
                return 4
    gdf.to_file(refined_path, driver="GPKG")
    log(f"Saved {refined_path.name} ({fmt(len(gdf))} rows)")
    manifest["outputs"] = {"refined": str(refined_path)}

    review_path = out_dir / f"{base}_refinement_review.gpkg"
    wrote_review = False
    for layer, g in review.items():
        if g is None or len(g) == 0:
            continue
        g.to_file(review_path, driver="GPKG", layer=layer)
        wrote_review = True
        log(f"Saved {review_path.name} :: {layer} ({fmt(len(g))} rows)")
    if wrote_review:
        manifest["outputs"]["review"] = str(review_path)

    if unlinks_out is not None and len(unlinks_out) > 0:
        u_path = out_dir / f"{base}_refined_unlinks.gpkg"
        unlinks_out.to_file(u_path, driver="GPKG")
        manifest["outputs"]["unlinks"] = str(u_path)
        log(f"Saved {u_path.name} ({fmt(len(unlinks_out))} crossing points)")

    manifest["finished_utc"] = datetime.now(timezone.utc).isoformat()
    manifest["total_elapsed_s"] = round(time.perf_counter() - t_pipeline, 1)
    man_path = out_dir / f"{base}_refinement_manifest.json"
    man_path.write_text(json.dumps(manifest, indent=2, default=str),
                        encoding="utf-8")

    log("")
    log(f"=== REFINEMENT COMPLETE in {manifest['total_elapsed_s'] / 60:.1f} min ===")
    log(f"Segments: {fmt(n0)} -> {fmt(n1)}; length {len0:.0f} -> {len1:.0f} km")
    log(f"Outputs in: {out_dir.resolve()}")
    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Phase 2 refinement of a Phase 1 simplified street network.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--input", required=True,
                   help="Phase 1 *_simplified.gpkg to refine.")
    p.add_argument("--output", default=None,
                   help="Output directory (default: alongside the input).")
    p.add_argument("--buildings", default=None,
                   help="Buildings GPKG (default: auto-discover the Phase 1 "
                        "*_buildings.gpkg sibling).")
    p.add_argument("--unlinks", default=None,
                   help="Phase 1 unlinks GPKG (default: auto-discover sibling).")
    p.add_argument("--original", default=None,
                   help="Phase 1 *_original.gpkg (default: auto-discover "
                        "sibling). Used as grade-separation evidence to "
                        "recover unlinks whose bridge tag was lost when "
                        "neatnet merged deck and approach lines.")
    p.add_argument("--rules", default=",".join(DEFAULT_RULES),
                   help="Comma-separated rules to run.")
    p.add_argument("--merge-dual-carriageways", action="store_true",
                   help="Opt in to the experimental wide-tolerance dual-"
                        "carriageway merge (off by default — some regions "
                        "need dual carriageways preserved).")
    p.add_argument("--junction-tolerance", type=float, default=12.0,
                   help="Max length (m) of junction fork edges to contract.")
    p.add_argument("--gap-tolerance", type=float, default=8.0,
                   help="Max gap (m) an undershoot dangle is extended across.")
    p.add_argument("--roundabout-strategy", choices=["hybrid", "star", "chords"],
                   default="hybrid",
                   help="hybrid = star below --star-max-diameter, chords above.")
    p.add_argument("--geometric-roundabouts", action="store_true",
                   help="On inputs without junction tags, collapse geometric "
                        "roundabout candidates instead of only reviewing them. "
                        "Risky: pure-geometry precision measured at 0.16.")
    p.add_argument("--star-max-diameter", type=float, default=40.0,
                   help="Hybrid threshold (m): smaller roundabouts collapse "
                        "to a centroid star, larger to entry-exit chords.")
    p.add_argument("--roundabout-min-diameter", type=float, default=10.0)
    p.add_argument("--roundabout-max-diameter", type=float, default=100.0)
    p.add_argument("--roundabout-min-circularity", type=float, default=0.8,
                   help="4*pi*A/P^2 floor for a face to count as a roundabout "
                        "(a perfect square scores 0.785 — stay above it).")
    p.add_argument("--roundabout-max-radius-cv", type=float, default=0.15,
                   help="Max coefficient of variation of the ring radius. "
                        "Rejects compact blocks that pass the circularity test.")
    p.add_argument("--parallel-tolerance", type=float, default=12.0,
                   help="Max separation (m) for two same-type vehicular lines "
                        "to collapse into one medial line. Pedestrian lines "
                        "are never absorbed.")
    p.add_argument("--parallel-protect", default=PARALLEL_PROTECT_DEFAULT,
                   help="Comma-separated highway classes whose dual/multiple "
                        "lines are kept (their *_link ramps included).")
    p.add_argument("--dual-tolerance", type=float, default=35.0,
                   help="Consolidation tolerance (m) for the opt-in dual-"
                        "carriageway merge.")
    p.add_argument("--detect-unlinks", action="store_true",
                   help="Recompute bridge/tunnel unlink points on the refined "
                        "network (Phase 1 unlinks move when geometry changes).")
    p.add_argument("--no-review", action="store_true",
                   help="Skip the review-layer detectors (squares, deletions).")
    p.add_argument("--name", default=None,
                   help="Override the output filename prefix.")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run(args)
    except KeyboardInterrupt:
        log("!!! Interrupted by user.")
        return 130
    except Exception as e:  # noqa: BLE001 - top-level guard reports cleanly
        log(f"!!! ERROR: {type(e).__name__}: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
