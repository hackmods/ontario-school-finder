"""Official school attendance boundaries that boards publish as public map layers (brief #11).

Each layer in ``sources.BOUNDARY_LAYERS`` is read from the board's own ArcGIS service, its
areas are grouped by school name, and each group is matched to a Ministry school number by
name within the board and level (falling back to "the one school of that board and level whose
location is inside the area"). Anything that can't be matched is reported, never guessed.
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from urllib.parse import quote

import geopandas as gpd
import shapely
from shapely.geometry import Point, mapping, shape

from . import config, fetch, geo, sources

# Board shorthand -> words, so "N.A. MacEachern P.S." and "N A MacEachern Public School" compare equal.
_ABBREV = {
    "ps": "public school", "es": "elementary school", "ss": "secondary school", "ces": "catholic elementary school",
    "css": "catholic secondary school", "ci": "collegiate institute", "cvi": "collegiate vocational institute",
    "dhs": "district high school", "dss": "district secondary school", "hs": "high school", "jr": "junior", "sr": "senior",
    "st": "saint", "ste": "sainte", "mt": "mount", "pss": "public school", "ecole": "ecole",
}
# Words that say what kind of school it is, not which one.
_GENERIC = {
    "public", "school", "schools", "elementary", "secondary", "catholic", "high", "collegiate", "institute", "district",
    "junior", "senior", "and", "of", "the", "vocational", "intermediate", "composite", "middle", "academy", "centre",
    "center", "temporary", "attendance", "area", "for", "french", "immersion", "boundary", "s", "c", "v", "separate",
}


def tokens(name: str) -> list[str]:
    s = "".join(c for c in unicodedata.normalize("NFKD", name or "") if not unicodedata.combining(c)).lower()
    s = re.sub(r"\(.*?\)", " ", s)              # "(Temporary Attendance Area for ELZ)"
    s = re.sub(r"[.’']", "", s)            # "P.S." -> "ps", "O'Neill" -> "oneill"
    s = re.sub(r"[^a-z0-9]+", " ", s)
    s = re.sub(r"\b([a-z]) (?=[a-z]\b)", r"\1", s)  # initials: "n a macdonald" -> "na macdonald", like "N.A."
    out = []
    for w in s.split():
        out.extend(_ABBREV.get(w, w).split())
    return out


def core(name: str) -> frozenset:
    t = tokens(name)
    c = [w for w in t if w not in _GENERIC]
    return frozenset(c or t)


def _score(a: frozenset, b: frozenset) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def _query_url(layer: dict) -> str:
    where = quote(layer.get("where") or "1=1", safe="")
    return f"{layer['url']}/query?where={where}&outFields=*&outSR=4326&f=geojson"


def _last_edit(layer: dict) -> str | None:
    """The layer's own last-edit date, from its service description."""
    path = fetch.download(f"{layer['id']}-meta", f"{layer['url']}?f=json", expect="json")
    meta = json.loads(path.read_text(encoding="utf-8"))
    ms = (meta.get("editingInfo") or {}).get("lastEditDate") or (meta.get("editingInfo") or {}).get("dataLastEditDate")
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m") if ms else None


def _layer_areas(layer: dict) -> tuple[dict[tuple[str, str], list], int]:
    """(name, part) -> [shapely geometries] for one layer, grouped by the name field (or ``dissolve``)
    and, where two schools share a name, by the layer's ``split`` field."""
    path = fetch.download(layer["id"], _query_url(layer), expect="json")
    gj = json.loads(path.read_text(encoding="utf-8"))
    if "features" not in gj:
        raise fetch.SourceUnavailable(f"{layer['id']}: the layer query returned no features ({str(gj)[:200]}).")
    field = layer.get("dissolve") or layer["name_field"]
    groups = defaultdict(list)
    for f in gj["features"]:
        props, g = f.get("properties") or {}, f.get("geometry")
        if field not in props:
            raise fetch.SchemaChanged(f"{layer['id']}: field '{field}' is missing (found {sorted(props)[:12]}).")
        name = (props.get(field) or "").strip()
        if not g or not name or any(re.search(p, name, re.I) for p in layer.get("skip", [])):
            continue
        part = str(props.get(layer["split"]) or "").strip() if layer.get("split") else ""
        groups[(name, part)].append(shapely.make_valid(shape(g)))
    return groups, len(gj["features"])


def build(schools: list[dict], board_names: dict[str, str], log=print) -> dict:
    """Return {'by_school': {bsid: {...}}, 'layers': {elementary|secondary: [features]}, 'report': {...}}."""
    pool = defaultdict(list)  # (board, level) -> [(bsid, name core tokens, point)]
    for s in schools:
        pool[(s["board_number"], s["level"])].append((s["bsid"], core(s["name"]), Point(s["lon"], s["lat"])))
    by_school, report = {}, {}
    for layer in sources.BOUNDARY_LAYERS:
        groups, n_features = _layer_areas(layer)
        edited = _last_edit(layer)
        cands = pool.get((layer["board"], layer["level"]), [])
        matched, unmatched, far = 0, [], []
        for (name, _part), geoms in groups.items():
            area = geo.polygonal(shapely.make_valid(shapely.union_all(geoms)))
            if area.is_empty:
                continue
            want = core(name)
            scored = sorted(((_score(want, c), b) for b, c, _p in cands), reverse=True)
            top = scored[0][0] if scored else 0.0
            tied = [b for sc, b in scored if sc == top] if top >= 0.5 else []
            inside = [b for b, _c, p in cands if area.contains(p)]
            picks = []
            if len(tied) == 1:
                # a name match must sit in or near its area (about 3 km): guards "St. John" vs "St. John Paul II"
                pt = next(p for b, _c, p in cands if b == tied[0])
                if area.buffer(0.03).contains(pt):
                    picks = tied
                else:
                    far.append(f"{name} -> {tied[0]}")
            elif tied and set(tied) <= set(inside):
                picks = tied  # one area for a split-grade pair on one site ("Frank Panabaker North" and "South")
            elif len(inside) == 1:
                picks = inside
            if not picks:
                unmatched.append(name)
                continue
            for pick in picks:
                prev = by_school.get(pick)
                mine = geo.polygonal(shapely.union_all([prev["_area"], area])) if prev and prev["layer"] == layer["id"] else area
                by_school[pick] = {"_area": mine, "layer": layer["id"], "board": layer["board"], "level": layer["level"], "edited": edited}
            matched += 1
        report[layer["id"]] = {"features": n_features, "areas": len(groups), "matched": matched, "unmatched": sorted(unmatched), "far": far,
                               "board": board_names.get(layer["board"], layer["board"]), "level": layer["level"], "edited": edited}
        log(f"  official boundaries: {layer['id']}: {matched} of {len(groups)} areas matched to schools")

    # simplify in metres: school pages get 8 m, or coarser for big rural areas (about 1/400 of the
    # area's width) so one school page stays light; the province-wide map layer gets 25 m or coarser
    ids = list(by_school)
    if not ids:
        return {"by_school": {}, "layers": {"elementary": [], "secondary": []}, "report": report}
    gs = gpd.GeoSeries([by_school[i]["_area"] for i in ids], crs=config.GEO_CRS).to_crs(config.PROJECTED_CRS)
    width = gs.area.pow(0.5)
    fine = gpd.GeoSeries([g.simplify(max(8.0, w / 400)) for g, w in zip(gs, width)], crs=config.PROJECTED_CRS).to_crs(config.GEO_CRS)
    coarse = gpd.GeoSeries([g.simplify(max(25.0, w / 150)) for g, w in zip(gs, width)], crs=config.PROJECTED_CRS).to_crs(config.GEO_CRS)
    layers = {"elementary": [], "secondary": []}
    for i, g_fine, g_coarse in zip(ids, fine, coarse):
        rec = by_school[i]
        rec["geometry"] = mapping(geo.round_coords(geo.polygonal(shapely.make_valid(g_fine))))
        layers[rec["level"]].append(geo.feature(geo.round_coords(geo.polygonal(shapely.make_valid(g_coarse))),
                                                {"id": i, "b": rec["board"], "d": rec["edited"]}))
        del rec["_area"]
    return {"by_school": by_school, "layers": layers, "report": report}
