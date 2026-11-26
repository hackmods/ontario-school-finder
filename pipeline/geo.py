"""Geography: FSA joins, the Ontario outline, nearest-school (Voronoi) areas and approximate board areas.

Ontario's shoreline is very detailed (tens of thousands of islands), so every heavy
operation works on a generalized copy, and clipping uses a quadtree of small pieces.
"""
from __future__ import annotations

import json
from collections import defaultdict

import geopandas as gpd
import numpy as np
import shapely
from shapely import STRtree
from shapely.geometry import MultiPoint, Point, box, mapping
from shapely.prepared import prep

from . import config


def to_projected(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gdf.to_crs(config.PROJECTED_CRS)


def polygonal(g):
    """Keep only the polygon parts of a geometry (GEOS can leave stray lines after overlays)."""
    if g is None or g.is_empty:
        return shapely.Polygon()
    if g.geom_type in ("Polygon", "MultiPolygon"):
        return g
    if g.geom_type == "GeometryCollection":
        polys = [x for x in shapely.get_parts(g) if x.geom_type in ("Polygon", "MultiPolygon")]
        return shapely.union_all(polys) if polys else shapely.Polygon()
    return shapely.Polygon()


def generalize(g, tolerance_m: float, min_part_m2: float = 0.0):
    """Drop island parts smaller than ``min_part_m2``, then simplify each remaining part.

    Northern FSAs have ~5,000 islands each; dropping islets first and simplifying parts
    one by one is thousands of times faster than a topology-preserving pass on the whole.
    """
    if g is None or g.is_empty:
        return shapely.Polygon()
    parts = np.asarray(shapely.get_parts(polygonal(g)))
    if len(parts) == 0:
        return shapely.Polygon()
    areas = shapely.area(parts)
    keep = parts[areas >= min_part_m2] if min_part_m2 else parts
    if len(keep) == 0:
        keep = parts[[int(np.argmax(areas))]]
    simp = shapely.make_valid(shapely.simplify(keep, tolerance_m, preserve_topology=False))
    polys = []
    for p in simp:
        polys.extend(x for x in shapely.get_parts(polygonal(p)) if x.geom_type == "Polygon" and not x.is_empty)
    if not polys:
        return polygonal(shapely.make_valid(keep[int(np.argmax(shapely.area(keep)))]))
    return polys[0] if len(polys) == 1 else shapely.MultiPolygon(polys)


def ontario_outline(fsa_proj: gpd.GeoDataFrame):
    geoms = [generalize(g, 150, 1_000_000) for g in fsa_proj.geometry.values]
    return polygonal(shapely.make_valid(shapely.union_all(geoms)))


def quadtree(geom, max_coords: int = 2500, depth: int = 0) -> list:
    """Split a big polygon into small pieces so clipping only touches what it needs."""
    if geom.is_empty:
        return []
    if shapely.get_num_coordinates(geom) <= max_coords or depth >= 12:
        return [geom]
    minx, miny, maxx, maxy = geom.bounds
    mx, my = (minx + maxx) / 2, (miny + maxy) / 2
    out = []
    for b in (box(minx, miny, mx, my), box(mx, miny, maxx, my), box(minx, my, mx, maxy), box(mx, my, maxx, maxy)):
        out += quadtree(polygonal(geom.intersection(b)), max_coords, depth + 1)
    return out


class Clipper:
    def __init__(self, outline):
        self.outline = outline
        self.pieces = quadtree(outline)
        self.tree = STRtree(self.pieces)
        self.prepared = [prep(p) for p in self.pieces]

    def clip(self, geom):
        idx = self.tree.query(geom)
        if len(idx) == 0:
            return shapely.Polygon()
        if len(idx) == 1 and self.prepared[idx[0]].contains(geom):
            return geom
        parts = [polygonal(geom.intersection(self.pieces[i])) for i in idx]
        return polygonal(shapely.make_valid(shapely.union_all([p for p in parts if not p.is_empty]))) if parts else shapely.Polygon()


def points_gdf(records: list[dict]) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"bsid": [r["bsid"] for r in records]},
        geometry=[Point(r["lon"], r["lat"]) for r in records],
        crs=config.GEO_CRS,
    )


def fsa_containing(points: gpd.GeoDataFrame, fsa: gpd.GeoDataFrame) -> dict[str, str | None]:
    joined = gpd.sjoin(points, fsa[["fsa", "geometry"]], how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    return {b: (f if isinstance(f, str) else None) for b, f in zip(joined["bsid"], joined["fsa"])}


def round_coords(geom, nd: int = 5):
    """Round coordinates for smaller files (display only; no topology work)."""
    if geom is None or geom.is_empty:
        return geom
    return shapely.transform(geom, lambda c: np.round(c, nd))


def feature(geom, props: dict) -> dict:
    return {"type": "Feature", "properties": props, "geometry": mapping(geom)}


def write_geojson(path, features: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":"))
    path.write_text(text, encoding="utf-8")
    return len(text)


def colocated_sites(df: gpd.GeoDataFrame) -> list[dict]:
    """Group schools that share the same point (shared buildings) into one site."""
    sites: dict[tuple, dict] = {}
    for row in df.itertuples():
        k = (round(row.x, 1), round(row.y, 1))
        s = sites.setdefault(k, {"x": row.x, "y": row.y, "bsids": [], "boards": []})
        s["bsids"].append(row.bsid)
        s["boards"].append(row.board_number)
    return list(sites.values())


def voronoi_cells(sites: list[dict], clipper: Clipper):
    """One clipped Voronoi cell per site, in the same order as ``sites``."""
    if len(sites) == 1:
        return [clipper.outline]
    pts = MultiPoint([(s["x"], s["y"]) for s in sites])
    env = clipper.outline.envelope.buffer(50_000)
    regions = shapely.voronoi_polygons(pts, extend_to=env, ordered=True)
    cells = list(shapely.get_parts(regions))
    if len(cells) != len(sites):
        raise RuntimeError(f"Voronoi returned {len(cells)} cells for {len(sites)} sites")
    out = []
    for s, c in zip(sites, cells):
        clipped = clipper.clip(c)
        p = Point(s["x"], s["y"])
        # A school on an island or at the shoreline can sit just outside the generalized
        # outline; keep a small disc around it so its own cell still holds it.
        if clipped.is_empty or not clipped.buffer(1).contains(p):
            clipped = polygonal(shapely.make_valid(shapely.union_all([clipped, p.buffer(250).intersection(c)])))
        out.append(clipped)
    return out


def build_layers(schools: list[dict], fsa_gdf: gpd.GeoDataFrame, out_dir, log=print) -> dict:
    """Write the province-wide map layers and return stats for the report and tests."""
    stats: dict = {}
    fsa_proj = to_projected(fsa_gdf)

    # 1) FSA areas -------------------------------------------------------------
    log("  FSA layer")
    prov = [generalize(g, 120, 200_000) for g in fsa_proj.geometry.values]
    detail = [generalize(g, 20, 5_000) for g in fsa_proj.geometry.values]
    prov_ll = gpd.GeoSeries(prov, crs=config.PROJECTED_CRS).to_crs(config.GEO_CRS)
    det_ll = gpd.GeoSeries(detail, crs=config.PROJECTED_CRS).to_crs(config.GEO_CRS)
    feats = [feature(round_coords(g, 4), {"fsa": f}) for f, g in zip(fsa_proj["fsa"], prov_ll)]
    stats["fsa_bytes"] = write_geojson(out_dir / "fsa.geojson", feats)
    stats["fsa_polygons"] = len(feats)
    fsa_detail = {f: mapping(round_coords(g, 5)) for f, g in zip(fsa_proj["fsa"], det_ll)}
    fsa_simple_proj = gpd.GeoDataFrame({"fsa": fsa_proj["fsa"].values}, geometry=detail, crs=config.PROJECTED_CRS)

    log("  Ontario outline")
    outline = ontario_outline(fsa_proj)
    clipper = Clipper(outline)
    stats["outline_pieces"] = len(clipper.pieces)

    df = gpd.GeoDataFrame(
        {
            "bsid": [s["bsid"] for s in schools],
            "board_number": [s["board_number"] for s in schools],
            "system": [s["system"] for s in schools],
            "level": [s["level"] for s in schools],
        },
        geometry=[Point(s["lon"], s["lat"]) for s in schools],
        crs=config.GEO_CRS,
    ).to_crs(config.PROJECTED_CRS)
    df["x"] = df.geometry.x
    df["y"] = df.geometry.y

    # 2) Nearest-school areas per system + level ------------------------------
    stats["voronoi"] = {}
    cells_by_bsid: dict[str, dict] = {}
    for (system, level), grp in df.groupby(["system", "level"]):
        log(f"  nearest-school areas: {system} {level} ({len(grp)})")
        sites = colocated_sites(grp)
        raw_cells = voronoi_cells(sites, clipper)
        cells = []
        for s, c in zip(sites, raw_cells):
            g = generalize(c, 60)
            p = Point(s["x"], s["y"])
            # simplification can shave a shoreline school out of its own cell: keep a disc around it
            if not g.buffer(-15).contains(p):
                g = polygonal(shapely.make_valid(shapely.union_all([g, p.buffer(250).intersection(c)])))
            cells.append(g)
        cg = gpd.GeoSeries(cells, crs=config.PROJECTED_CRS).to_crs(config.GEO_CRS)
        feats = [feature(round_coords(g, 4), {"bsids": s["bsids"], "board": s["boards"][0]}) for s, g in zip(sites, cg)]
        for s, g in zip(sites, cg):
            for b in s["bsids"]:
                cells_by_bsid[b] = mapping(round_coords(g, 5))
        name = f"nearest-{system}-{level}.geojson".lower()
        size = write_geojson(out_dir / name, feats)
        stats["voronoi"][f"{system}|{level}"] = {"file": name, "cells": len(feats), "schools": len(grp),
                                                  "shared_sites": sum(1 for s in sites if len(s["bsids"]) > 1), "bytes": size}

    # 3) Approximate board areas: nearest-school cells of a system, merged by board --
    board_feats = []
    stats["boards"] = {}
    for system, grp in df.groupby("system"):
        log(f"  board areas: {system}")
        sites = colocated_sites(grp)
        cells = voronoi_cells(sites, clipper)
        by_board = defaultdict(list)
        for s, c in zip(sites, cells):
            by_board[s["boards"][0]].append(c)
        for b, parts in by_board.items():
            merged = generalize(shapely.union_all(parts), 300, 2_000_000)
            g = gpd.GeoSeries([merged], crs=config.PROJECTED_CRS).to_crs(config.GEO_CRS).iloc[0]
            board_feats.append(feature(round_coords(g, 4), {"board": b, "system": system}))
            stats["boards"][b] = {"system": system, "area_km2": round(merged.area / 1e6)}
    stats["board_bytes"] = write_geojson(out_dir / "boards.geojson", board_feats)

    o = gpd.GeoSeries([generalize(outline, 1500, 50_000_000)], crs=config.PROJECTED_CRS).to_crs(config.GEO_CRS).iloc[0]
    write_geojson(out_dir / "ontario.geojson", [feature(round_coords(o, 3), {"name": "Ontario"})])
    return {"stats": stats, "fsa_detail": fsa_detail, "outline": outline, "fsa_proj": fsa_simple_proj, "cells": cells_by_bsid}


def nearest_by_level(schools: list[dict], df_proj: gpd.GeoDataFrame, k: int) -> dict[str, list[dict]]:
    """For each school, the k nearest other schools of the same level (straight-line distance)."""
    from scipy.spatial import cKDTree

    out: dict[str, list[dict]] = {}
    pos = {b: (x, y) for b, x, y in zip(df_proj["bsid"], df_proj["x"], df_proj["y"])}
    by_level = defaultdict(list)
    for s in schools:
        by_level[s["level"]].append(s["bsid"])
    for level, ids in by_level.items():
        xy = np.array([pos[b] for b in ids])
        tree = cKDTree(xy)
        kk = min(k + 1, len(ids))
        dist, ind = tree.query(xy, k=kk)
        for i, b in enumerate(ids):
            lst = []
            for d, j in zip(np.atleast_1d(dist[i]), np.atleast_1d(ind[i])):
                if ids[j] == b:
                    continue
                lst.append({"bsid": ids[j], "km": round(float(d) / 1000, 1)})
            out[b] = lst[:k]
    return out


def schools_near_fsa(fsa_proj: gpd.GeoDataFrame, df_proj: gpd.GeoDataFrame, metres: float) -> dict[str, dict]:
    """Schools inside each FSA and schools within ``metres`` of its edge."""
    inside = gpd.sjoin(df_proj[["bsid", "geometry"]], fsa_proj[["fsa", "geometry"]], how="inner", predicate="within")
    res: dict[str, dict] = {f: {"in": [], "near": []} for f in fsa_proj["fsa"]}
    for b, f in zip(inside["bsid"], inside["fsa"]):
        res[f]["in"].append(b)
    buf = gpd.GeoDataFrame({"fsa": fsa_proj["fsa"].values}, geometry=fsa_proj.geometry.simplify(200).buffer(metres, resolution=4), crs=config.PROJECTED_CRS)
    near = gpd.sjoin(df_proj[["bsid", "geometry"]], buf, how="inner", predicate="within")
    for b, f in zip(near["bsid"], near["fsa"]):
        if b not in res[f]["in"]:
            res[f]["near"].append(b)
    return res
