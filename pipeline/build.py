"""Run the whole pipeline: download, clean, join, and write ``site/data`` plus ``pipeline/report.md``.

    python -m pipeline.build            # use whatever is already cached
    python -m pipeline.build --clean    # delete downloaded files first (geocode cache is kept)
    python -m pipeline.build --refresh  # keep downloads, re-download only files their publisher changed
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import statistics
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone

from . import boundaries, config, eras, fetch, geo, loaders, parse, report, sources
from .fetch import SourceUnavailable

LEVELS = {"Elementary": "elementary", "Secondary": "secondary"}
REGULAR_SPECIAL = {"Not applicable", "Junior High School"}
BOARD_KIND = {"Public": "public", "Catholic": "catholic"}


def log(msg: str) -> None:
    print(f"[pipeline {datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def eqao_school_url(bsid: str) -> str:
    return f"https://www.eqao.com/results/?orgType=S&mident={bsid}&lang=en"


def ministry_profile_url(bsid: str, level: str) -> str:
    page = "schoolProfileSec.asp" if level == "secondary" else "schoolProfileElm.asp"
    return f"https://www.app.edu.gov.on.ca/eng/sift/{page}?SCH_NUMBER={bsid}"


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def system_of(school_type: str | None, language: str | None) -> str:
    kind = BOARD_KIND.get(school_type or "")
    lang = (language or "").lower()
    if kind and lang in ("english", "french"):
        return f"{lang}-{kind}"
    return "other"


SYSTEM_LABEL = {
    "english-public": "English public",
    "english-catholic": "English Catholic",
    "french-public": "French public",
    "french-catholic": "French Catholic",
    "other": "Provincial or other",
}


def fmt_postal(p: str | None) -> str | None:
    return f"{p[:3]} {p[3:]}" if p else None


def phone(v) -> str | None:
    s = parse.clean_text(v)
    return s if s and re.search(r"\d{3}.*\d{4}", s) else None


def date_open(v) -> str | None:
    s = parse.clean_text(v)
    if not s:
        return None
    m = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", s)
    if m:
        d, mo, y = m.groups()
        return f"{y}-{int(mo):02d}-{int(d):02d}"
    return None


# ---------------------------------------------------------------------------
# Geocoding fallback (only for schools without source coordinates)
# ---------------------------------------------------------------------------

GEOCODER = "https://www.geolocator.api.geo.ca/geolocation/en/locate"


def geocode(address: str, city: str | None, postal: str | None) -> dict | None:
    cache = {}
    if config.GEOCODE_CACHE.exists():
        cache = json.loads(config.GEOCODE_CACHE.read_text(encoding="utf-8"))
    key = f"{address}|{city}|{postal}"
    if key in cache:
        return cache[key]
    q = ", ".join(x for x in [address, city, "Ontario"] if x)
    time.sleep(1.1)  # stay well under the service's fair use (one request per second)
    try:
        js = fetch.get_json(GEOCODER, params={"q": q})
    except SourceUnavailable:
        return None
    hit = None
    for r in js if isinstance(js, list) else []:
        title = r.get("title", "")
        if "Ontario" not in title and not (postal and title.startswith(postal[:3])):
            continue
        lon, lat = r["geometry"]["coordinates"][:2]
        hit = {"lat": round(lat, 6), "lon": round(lon, 6), "match": title, "precision": r.get("qualifier", "")}
        break
    cache[key] = hit
    config.GEOCODE_CACHE.parent.mkdir(parents=True, exist_ok=True)
    config.GEOCODE_CACHE.write_text(json.dumps(cache, indent=1, sort_keys=True), encoding="utf-8")
    return hit


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def median(vals):
    return round(statistics.median(vals), 1) if vals else None


def questionnaire_history(eqao_sq: dict) -> dict:
    """For each latest-year questionnaire, the earlier years (newest first) that asked each question with exactly the
    same wording and the same answers, and why the others are left out. Nothing is compared across a wording change."""
    out = {}
    for res in sources.EQAO_SQ_RESOURCES:
        cur = eqao_sq[res["id"]]["questions"]
        comparable: dict[str, list[str]] = {k: [] for k in cur}
        excluded: dict[str, dict[str, str]] = {}
        for h in sorted((r for r in sources.EQAO_SQ_HISTORY if r["kind"] == res["kind"] and r["grade"] == res["grade"]),
                        key=lambda r: r["year"], reverse=True):
            old = eqao_sq[h["id"]]["questions"]
            for k, q in cur.items():
                o = old.get(k)
                why = ("not asked that year" if not o else "worded differently" if o["question"] != q["question"]
                       else "different answers" if o["options"] != q["options"] or o["agree"] != q["agree"] else None)
                if why:
                    excluded.setdefault(k, {})[h["year"]] = why
                else:
                    comparable[k].append(h["id"])
        out[res["id"]] = {"comparable": comparable, "excluded": excluded}
    return out


def build(clean: bool = False) -> dict:
    t0 = time.time()
    if clean and config.RAW.exists():
        shutil.rmtree(config.RAW)
        if config.MANIFEST.exists():
            config.MANIFEST.unlink()
        log("cleared downloaded files (geocode cache kept)")
    rep = report.Report()

    # ---------------- load every source ----------------
    sif = {}
    for res in sources.SIF_RESOURCES:
        log(f"loading {res['id']}")
        sif[res["id"]] = loaders.load_sif(res)
        rep.count(res["id"], sif[res["id"]]["stats"]["schools"], "schools")
        rep.suppressed[res["id"]] = {k: v for k, v in sif[res["id"]]["stats"].items() if k.startswith(("eqao_", "context_code_"))}
    latest_res = sources.SIF_RESOURCES[0]
    latest = sif[latest_res["id"]]["rows"]

    log("loading contact list")
    contact = loaders.load_contact(sources.CONTACT_RESOURCE)
    rep.count(sources.CONTACT_RESOURCE["id"], len(contact["rows"]), "schools and sites")

    sbpr = {}
    for res in sources.SBPR_RESOURCES:
        log(f"loading {res['id']}")
        sbpr[res["id"]] = loaders.load_sbpr(res)
        rep.count(res["id"], sbpr[res["id"]]["stats"]["boards"], "boards")
        rep.suppressed[res["id"]] = {k: v for k, v in sbpr[res["id"]]["stats"].items() if k.startswith("code_")}

    enrol = {}
    for res in sources.ENROL_RESOURCES:
        log(f"loading {res['id']}")
        enrol[res["id"]] = loaders.load_enrolment(res)
        rep.count(res["id"], enrol[res["id"]]["stats"]["schools"], "schools")
        rep.suppressed[res["id"]] = {k: v for k, v in enrol[res["id"]]["stats"].items() if k.startswith("code_")}

    egrade = {}
    for res in sources.ENROL_GRADE_RESOURCES:
        log(f"loading {res['id']}")
        egrade[res["id"]] = loaders.load_grade_enrolment(res)
        rep.count(res["id"], egrade[res["id"]]["stats"]["schools"], "schools with enrolment by grade")
    csize = {}
    for res in sources.CLASS_SIZE_RESOURCES:
        log(f"loading {res['id']} (class lists)")
        csize[res["id"]] = loaders.load_class_size(res)
        rep.count(res["id"], csize[res["id"]]["stats"]["school_years"], "school-years of elementary class lists")
    log(f"loading {sources.FSL_RESOURCE['id']} (French programs)")
    fsl = loaders.load_fsl(sources.FSL_RESOURCE)
    rep.count(sources.FSL_RESOURCE["id"], fsl["stats"]["schools"], "English-language schools with French program flags")
    log(f"loading {sources.SHSM_RESOURCE['id']} (Specialist High Skills Majors)")
    shsm = loaders.load_shsm(sources.SHSM_RESOURCE)
    rep.count(sources.SHSM_RESOURCE["id"], shsm["stats"]["programs"], f"SHSM programs at {shsm['stats']['schools']} schools")
    eqao_open = {}
    for res in sources.EQAO_OPEN_RESOURCES:
        log(f"loading {res['id']} (EQAO open data)")
        eqao_open[res["id"]] = loaders.load_eqao_open(res)
        rep.count(res["id"], eqao_open[res["id"]]["stats"]["schools"], "schools in EQAO's file")
        rep.suppressed[res["id"]] = {k: v for k, v in eqao_open[res["id"]]["stats"].items() if k.startswith("code_")}
    eqao_sq = {}
    for res in sources.EQAO_SQ_RESOURCES:
        log(f"loading {res['id']} (EQAO student questionnaire)")
        eqao_sq[res["id"]] = loaders.load_eqao_sq(res)
        rep.count(res["id"], eqao_sq[res["id"]]["stats"]["schools"], "schools in EQAO's questionnaire file")
        rep.suppressed[res["id"]] = {k: v for k, v in eqao_sq[res["id"]]["stats"].items() if k.startswith("code_")}
    for res in sources.EQAO_SQ_HISTORY:
        log(f"loading {res['id']} (EQAO student questionnaire, earlier year)")
        eqao_sq[res["id"]] = loaders.load_eqao_sq(res, strict=False)
        rep.count(res["id"], eqao_sq[res["id"]]["stats"]["schools"], "schools in EQAO's questionnaire file")
    sq_history = questionnaire_history(eqao_sq)
    sq_year = {r["id"]: r["year"] for r in sources.EQAO_SQ_RESOURCES + sources.EQAO_SQ_HISTORY}
    log("loading board context (suspensions, expulsions, spending, French enrolment)")
    susp = loaders.load_board_rates(sources.SUSPENSION_RESOURCE, what="suspension")
    expul = loaders.load_board_rates(sources.EXPULSION_RESOURCE, what="expulsion")
    finance = loaders.load_finance(sources.FINANCE_RESOURCE)
    fsl_enrol = loaders.load_fsl_enrolment(sources.FSL_ENROL_RESOURCE)
    rep.count(sources.SUSPENSION_RESOURCE["id"], susp["stats"]["boards"], "boards with suspension rates")
    rep.count(sources.FINANCE_RESOURCE["id"], finance["stats"]["boards"], "boards with 2024-25 spending")
    spend_median = median([v["per_student"] for v in finance["boards"].values()])  # the middle board in Ontario
    rep.count(sources.FSL_ENROL_RESOURCE["id"], fsl_enrol["stats"]["boards"], "boards with French program enrolment")
    log("loading EarlyON centres and Student Nutrition Program sites")
    earlyon = loaders.load_earlyon(sources.EARLYON_RESOURCE)
    nutrition = loaders.load_nutrition(sources.NUTRITION_RESOURCE)
    rep.count(sources.EARLYON_RESOURCE["id"], earlyon["stats"]["sites"], "EarlyON sites")
    rep.count(sources.NUTRITION_RESOURCE["id"], nutrition["stats"]["schools"], "schools on the 2017 Student Nutrition Program list")
    eo_by_fsa = defaultdict(list)
    for x in earlyon["rows"]:
        if x["fsa"]:
            eo_by_fsa[x["fsa"]].append(x)

    log("loading child care")
    childcare = loaders.load_childcare(sources.CHILDCARE_RESOURCE)
    rep.count(sources.CHILDCARE_RESOURCE["id"], len(childcare["rows"]), f"active licensed sites (snapshot {childcare['snapshot']})")

    log("loading FSA boundaries")
    fsa_gdf, fsa_via = loaders.load_fsa_boundaries()
    rep.count(sources.FSA_RESOURCE["id"], len(fsa_gdf), "Ontario FSA polygons")
    if fsa_via != "official":
        rep.note(f"FSA boundaries: Statistics Canada's download site blocked automated access ({fsa_via.split('(', 1)[-1].rstrip(')')}). "
                 f"Used Esri Canada's open republication of the same 2021 file: {sources.FSA_RESOURCE['mirror_landing']}")
    fsa_codes = sorted(fsa_gdf["fsa"])

    log("loading census profile (Statistics Canada API)")
    census = loaders.load_census(fsa_codes)
    rep.count(sources.CENSUS_RESOURCE["id"], census["stats"]["fsas_with_census"], f"FSAs with census figures (of {len(fsa_codes)})")

    for key, ds in sources.DATASETS.items():
        if ds["status"] != "used":
            rep.skip(key, ds)

    # ---------------- build school records ----------------
    log("building school records")
    schools: list[dict] = []
    excluded: list[dict] = []
    coord_fallback = Counter()
    for bsid, r in latest.items():
        c = contact["rows"].get(bsid)
        name = parse.tidy_school_name(parse.clean_text(r["School Name"]))
        level = LEVELS.get(parse.clean_text(r["School Level"]) or "", None)
        language = parse.clean_text(r["School Language"])
        stype = parse.clean_text(r["School Type"])
        special = parse.clean_text(r["School Special Condition Code"])
        postal = parse.norm_postal(r["Postal Code"])
        lat, lon = r["Latitude"], r["Longitude"]
        coord_source, geocoded, precision = latest_res["id"], False, None
        if not isinstance(lat, (int, float)) or not isinstance(lon, (int, float)):
            lat = lon = None
            for res in sources.SIF_RESOURCES[1:]:
                old = sif[res["id"]]["rows"].get(bsid)
                if old and isinstance(old["Latitude"], (int, float)) and isinstance(old["Longitude"], (int, float)):
                    lat, lon, coord_source = old["Latitude"], old["Longitude"], res["id"]
                    coord_fallback["earlier_year"] += 1
                    break
        if lat is None:
            street = parse.clean_text(r["Street"]) or (parse.clean_text(c["Street"]) if c else None)
            city = parse.clean_text(r["City"]) or (parse.clean_text(c["City"]) if c else None)
            if street:
                hit = geocode(street, city, postal)
                if hit:
                    lat, lon, geocoded, precision, coord_source = hit["lat"], hit["lon"], True, hit["precision"], "geocoder"
                    coord_fallback["geocoded"] += 1
        if lat is None or not (41.5 < float(lat) < 57.5 and -95.5 < float(lon) < -74.0):
            excluded.append({"bsid": bsid, "name": name, "reason": "no usable location in any source year and no geocoder match"})
            continue
        if not level:
            excluded.append({"bsid": bsid, "name": name, "reason": f"unknown school level {r['School Level']!r}"})
            continue
        board_number = parse.clean_text(r["Board Number"])
        rec = {
            "bsid": bsid,
            "name": name,
            "board_number": board_number,
            "board_name": parse.clean_text(r["Board Name"]),
            "board_type": stype,
            "system": system_of(stype, language),
            "language": language,
            "level": level,
            "grades": parse.clean_text(r["Grade Range"]),
            "special": None if special in (None, "Not applicable") else special,
            "address": parse.clean_text(r["Street"]),
            "suite": parse.clean_text(r["Building Suite"]),
            "po_box": parse.clean_text(r["P.O. Box"]),
            "city": parse.clean_text(r["City"]),
            "municipality": parse.clean_text(r["Municipality"]),
            "postal_code": fmt_postal(postal),
            "fsa": parse.fsa_of(postal),
            "lat": round(float(lat), 6),
            "lon": round(float(lon), 6),
            "coord_source": coord_source,
            "geocoded": geocoded,
            "geocode_precision": precision,
            "phone": phone(c["Phone"]) if c else phone(r["Phone Number"]),
            "email": parse.clean_text(c["Email"]) if c else None,
            "website": parse.clean_url(c["Website"]) if c and parse.clean_text(c["Website"]) else parse.clean_url(r["School Website"]),
            "board_website": (sources.BOARD_WEBSITE_FIXES.get(board_number) or [None])[0]
            or (parse.clean_url(c["Board Website"]) if c and parse.clean_text(c["Board Website"]) else parse.clean_url(r["Board Website"])),
            "region": parse.clean_text(c["Region"]) if c else None,
            "date_open": date_open(c["Date Open"]) if c else None,
            "status": "open" if c else "not-in-contact-list",
            "contact_source": sources.CONTACT_RESOURCE["id"] if c else latest_res["id"],
            "regular": (special or "Not applicable") in REGULAR_SPECIAL,
        }
        schools.append(rec)
    rep.missing_coords = {"from_earlier_years": coord_fallback["earlier_year"], "geocoded": coord_fallback["geocoded"], "excluded": excluded}
    by_id = {s["bsid"]: s for s in schools}
    log(f"{len(schools)} schools ({len(excluded)} excluded)")

    # ---------------- geography ----------------
    log("geography: FSA join")
    pts = geo.points_gdf(schools)
    poly_fsa = geo.fsa_containing(pts, fsa_gdf)

    # Some source coordinates are plainly wrong (a Kitchener school plotted in Woodstock).
    # When a school's point is more than 1 km outside the postal area of its own postal code,
    # look its street address up; use that location only if it lands inside the right postal
    # area (two independent signals agreeing). Every moved school is flagged and reported.
    fsa_proj_full = geo.to_projected(fsa_gdf).set_index("fsa")
    pts_proj = geo.to_projected(pts)
    relocated = []
    for s, pt in zip(schools, pts_proj.geometry):
        pf = poly_fsa.get(s["bsid"])
        if not s["fsa"] or pf == s["fsa"] or s["fsa"] not in fsa_proj_full.index or s["geocoded"]:
            continue
        off_m = fsa_proj_full.loc[s["fsa"]].geometry.distance(pt)
        if off_m < 1000 or not s["address"]:
            continue
        hit = geocode(s["address"], s["city"], s["postal_code"].replace(" ", "") if s["postal_code"] else None)
        if not hit or not re.search(r"POSITION|ADDRESS", hit.get("precision") or ""):
            continue
        cand = geo.points_gdf([{"bsid": s["bsid"], "lat": hit["lat"], "lon": hit["lon"]}])
        if geo.fsa_containing(cand, fsa_gdf).get(s["bsid"]) != s["fsa"]:
            continue
        relocated.append({"bsid": s["bsid"], "name": s["name"], "off_km": round(off_m / 1000, 1), "from": [s["lat"], s["lon"]], "to": [hit["lat"], hit["lon"]], "match": hit["match"]})
        s.update(lat=hit["lat"], lon=hit["lon"], geocoded=True, geocode_precision=hit["precision"], coord_source="geocoder",
                 coord_note=f"The Ministry's coordinates for this school were {round(off_m / 1000, 1)} km outside its postal area, so it is placed by its street address instead.")
        poly_fsa[s["bsid"]] = s["fsa"]
    rep.relocated = relocated
    mismatches = []
    for s in schools:
        pf = poly_fsa.get(s["bsid"])
        s["fsa_polygon"] = pf
        if s["fsa"] is None:
            s["fsa"] = pf
            s["fsa_from"] = "polygon"
        else:
            s["fsa_from"] = "postal_code"
            if pf != s["fsa"]:
                mismatches.append({"bsid": s["bsid"], "name": s["name"], "postal_fsa": s["fsa"], "polygon_fsa": pf})
    rep.fsa_mismatches = mismatches
    rep.fsa_checked = sum(1 for s in schools if s["fsa_from"] == "postal_code")
    no_fsa = [s for s in schools if not s["fsa"]]
    for s in no_fsa:
        excluded.append({"bsid": s["bsid"], "name": s["name"], "reason": "no postal code and location outside every FSA"})
    schools = [s for s in schools if s["fsa"]]
    by_id = {s["bsid"]: s for s in schools}

    log("geography: layers (FSA, nearest-school, board areas)")
    geo_dir = config.OUT / "geo"
    if config.OUT.exists():
        shutil.rmtree(config.OUT)
    geo_dir.mkdir(parents=True, exist_ok=True)
    # A nearest-school area only makes sense for a school families attend by neighbourhood. Leave out
    # special-purpose schools (s["regular"]) and English-language elementary schools the Ministry lists as
    # offering French Immersion but neither Core nor Extended French: Core French is required in Grades 4-8
    # of the regular English program, so such a school is almost certainly an Immersion centre families
    # choose for the program. Its page says why no area is drawn; nothing is inferred about eligibility.
    for s in schools:
        s["immersion_only"], s["proximity_area"] = proximity_area(s, fsl["rows"].get(s["bsid"]))
    layer_input = [s for s in schools if s["proximity_area"] == "drawn"]
    rep.proximity = Counter(s["proximity_area"] for s in schools)
    layers = geo.build_layers(layer_input, fsa_gdf, geo_dir, log=log)
    rep.layers = layers["stats"]
    all_proj = geo.to_projected(geo.points_gdf(schools))
    all_proj["x"] = all_proj.geometry.x
    all_proj["y"] = all_proj.geometry.y
    nearby = geo.nearest_by_level(schools, all_proj, config.NEARBY_COUNT)
    fsa_schools = geo.schools_near_fsa(layers["fsa_proj"], all_proj, config.NEAR_FSA_METRES)

    # ---------------- EQAO with board + province medians ----------------
    log("EQAO: series and medians")
    eqao_rows = defaultdict(list)  # (assessment, year, board) -> values
    prov_rows = defaultdict(list)  # (assessment, year, language) -> values
    sif_eqao = [res for res in sources.SIF_RESOURCES if res["eqao_year"]]
    for res in sif_eqao:
        for bsid, r in sif[res["id"]]["rows"].items():
            bn = parse.clean_text(r["Board Number"])
            lang = parse.clean_text(r["School Language"])
            for aid, (v, code) in r["eqao"].items():
                if v is not None:
                    eqao_rows[(aid, res["eqao_year"], bn)].append(v)
                    prov_rows[(aid, res["eqao_year"], lang)].append(v)
    # EQAO's own open data for years the Ministry's school file doesn't have yet (same measure:
    # checked school by school against SIF 2024-25). Board and language come from the school list.
    sif_years = {res["eqao_year"] for res in sif_eqao}
    open_eqao = [res for res in sources.EQAO_OPEN_RESOURCES if res["year"] not in sif_years]
    for res in open_eqao:
        for bsid, r in eqao_open[res["id"]]["rows"].items():
            mine = by_id.get(bsid)
            bn = mine["board_number"] if mine else r["board"]
            lang = mine["language"] if mine else r["language"]
            for aid, rec in r["results"].items():
                if rec["v"] is not None:
                    eqao_rows[(aid, res["year"], bn)].append(rec["v"])
                    prov_rows[(aid, res["year"], lang)].append(rec["v"])
    # every EQAO year on the site, newest first, with the source of each assessment's figure
    def _open_source(year):
        by_grade = {r["grade"]: r["id"] for r in open_eqao if r["year"] == year}
        return lambda aid: by_grade.get(loaders.ASSESSMENTS[aid]["grade"].replace("Grade ", ""))
    eqao_years_all = [(y, _open_source(y)) for y in sorted({r["year"] for r in open_eqao}, reverse=True)]
    eqao_years_all += [(res["eqao_year"], (lambda aid, i=res["id"]: i)) for res in sif_eqao]
    rep.eqao_open = {res["id"]: {"schools": len(eqao_open[res["id"]]["rows"]),
                                 "matched": sum(1 for b in eqao_open[res["id"]]["rows"] if b in by_id)} for res in open_eqao}
    board_median = {k: (median(v), len(v)) for k, v in eqao_rows.items() if len(v) >= 3}
    prov_median = {k: (median(v), len(v)) for k, v in prov_rows.items()}

    for s in schools:
        series = []
        for res in open_eqao:  # newest years first, like the SIF loop below
            r = eqao_open[res["id"]]["rows"].get(s["bsid"])
            for aid, rec in (r["results"] if r else {}).items():
                bm = board_median.get((aid, res["year"], s["board_number"]))
                pm = prov_median.get((aid, res["year"], s["language"]))
                a = loaders.ASSESSMENTS[aid]
                series.append({
                    "year": res["year"], "assessment": aid, "grade": a["grade"], "subject": a["subject"],
                    "pct_at_or_above_standard": rec["v"],
                    "board_median": bm[0] if bm else None, "board_n": bm[1] if bm else None,
                    "province_median": pm[0] if pm else None, "province_n": pm[1] if pm else None,
                    **parse.flags(rec["code"]), "source_id": res["id"], "era": eras.era_of(aid, res["year"]),
                    # the extra detail EQAO publishes: share at levels 4, 3, 2, 1 and how many took part
                    "levels": rec["levels"], "participation": rec["participation"],
                })
        for res in sif_eqao:
            r = sif[res["id"]]["rows"].get(s["bsid"])
            if not r:
                continue
            for aid, (v, code) in r["eqao"].items():
                if code in ("NA", "BLANK"):
                    continue  # the school has no students in that grade: nothing to show
                bm = board_median.get((aid, res["eqao_year"], s["board_number"]))
                pm = prov_median.get((aid, res["eqao_year"], s["language"]))
                a = loaders.ASSESSMENTS[aid]
                series.append({
                    "year": res["eqao_year"], "assessment": aid, "grade": a["grade"], "subject": a["subject"],
                    "pct_at_or_above_standard": v,
                    "board_median": bm[0] if bm else None, "board_n": bm[1] if bm else None,
                    "province_median": pm[0] if pm else None, "province_n": pm[1] if pm else None,
                    **parse.flags(code), "source_id": res["id"], "era": eras.era_of(aid, res["eqao_year"]),
                })
        s["eqao"] = series

    # ---------------- enrolment ----------------
    for s in schools:
        e = []
        for res in reversed(sources.ENROL_RESOURCES):
            hit = enrol[res["id"]]["rows"].get(s["bsid"])
            if hit is None:
                continue
            v, code = hit
            e.append({"year": res["year"], "value": v, **parse.flags(code), "source_id": res["id"]})
        s["enrolment"] = e

    # ---------------- context (latest SIF year) ----------------
    for s in schools:
        r = latest[s["bsid"]]
        items = []
        for key, label, _col, definition in loaders.SIF_CONTEXT_COLS:
            c = r["context"][key]
            items.append({"key": key, "label": label, "definition": definition, "value": c["value"],
                          **{k: v for k, v in c.items() if k != "value"}})
        s["context"] = {"year": latest_res["year"], "source_id": latest_res["id"], "items": items}

    # ---------------- child care ----------------
    cc_by_key = defaultdict(list)
    cc_by_fsa = defaultdict(list)
    for cc in childcare["rows"]:
        if cc["postal_code"] and cc["street_number"]:
            cc_by_key[(cc["postal_code"], cc["street_number"])].append(cc)
        if cc["fsa"]:
            cc_by_fsa[cc["fsa"]].append(cc)
    cc_at_school = 0
    for s in schools:
        num = re.match(r"\s*(\d+)", s["address"] or "")
        key = (s["postal_code"].replace(" ", "") if s["postal_code"] else None, num.group(1) if num else None)
        at = cc_by_key.get(key, []) if all(key) else []
        if at:
            cc_at_school += 1
        s["childcare"] = {
            "at_address": [{k: cc[k] for k in ("name", "type", "options", "language", "address", "city", "postal_code", "licence")} for cc in at],
            "in_fsa_count": len(cc_by_fsa.get(s["fsa"], [])),
            "source_id": sources.CHILDCARE_RESOURCE["id"],
            "snapshot": childcare["snapshot"],
        }
    rep.childcare_at_school = cc_at_school

    # ---------------- enrolment by grade ----------------
    for s in schools:
        series = []
        for res in reversed(sources.ENROL_GRADE_RESOURCES):
            hit = egrade[res["id"]]["rows"].get(s["bsid"])
            if hit:
                series.append({"year": res["year"], "grades": hit["grades"], "codes": hit["codes"], "source_id": res["id"]})
        s["grade_enrolment"] = series

    # ---------------- programs: French as a second language, SHSM (joined on school number) ----------------
    fr, sr = sources.FSL_RESOURCE, sources.SHSM_RESOURCE
    for s in schools:
        f = fsl["rows"].get(s["bsid"])
        sh = shsm["rows"].get(s["bsid"])
        meals = nutrition["rows"].get(s["bsid"])
        s["programs"] = {
            "fsl": {**f, "year": fr["year"], "source_id": fr["id"]} if f else None,
            "shsm": {"year": sr["year"], "source_id": sr["id"], "sectors": sh} if sh else None,
            "nutrition": {"meals": meals, "year": sources.NUTRITION_RESOURCE["year"], "source_id": sources.NUTRITION_RESOURCE["id"]} if meals else None,
        }
        s["earlyon_in_fsa"] = len(eo_by_fsa.get(s["fsa"], []))
    known = {s["bsid"] for s in schools}
    rep.programs = {
        "fsl_matched": sum(1 for s in schools if s["programs"]["fsl"]),
        "fsl_unmatched": sorted(set(fsl["rows"]) - known),
        "shsm_matched": sum(1 for s in schools if s["programs"]["shsm"]),
        "shsm_unmatched": sorted(set(shsm["rows"]) - known),
    }

    # ---------------- class sizes (matched by board + school name) ----------------
    log("class sizes: matching class lists to schools by name")
    name_index = defaultdict(set)
    for res in sources.SIF_RESOURCES:  # every name a school has used since 2015-16
        for bsid, r in sif[res["id"]]["rows"].items():
            if bsid in by_id and r["School Name"]:
                name_index[school_key(r["School Name"])].add(bsid)
                name_index[school_key(parse.tidy_school_name(r["School Name"]))].add(bsid)  # "Glenwood School School" as "Glenwood School"
    cm = match_class_lists([(res["id"], csize[res["id"]]["rows"]) for res in sources.CLASS_SIZE_RESOURCES], name_index, by_id)
    cs_by_school, cs_ambiguous, cs_ambiguous_years = cm["by_school"], cm["ambiguous"], cm["ambiguous_years"]
    matched, unmatched, ambiguous = cm["matched"], cm["unmatched"], cm["ambiguous_rows"]
    for s in schools:
        rows = sorted(cs_by_school.get(s["bsid"], []), key=lambda r: r["year"])
        # two files can cover one year only if a school appears twice under one name; keep the first
        seen, keep = set(), []
        for r in rows:
            if r["year"] not in seen:
                seen.add(r["year"])
                keep.append(r)
        s["class_size"] = keep
        # why a page has (or hasn't) class sizes, in words a parent can act on
        s["class_size_status"] = class_size_status(s, keep, cs_ambiguous, cs_ambiguous_years)
    rep.class_size = {"matched": matched, "ambiguous": ambiguous, "unmatched_by_year": dict(sorted(unmatched.items())),
                      "schools_with_class_sizes": sum(1 for s in schools if s["class_size"]),
                      "by_status": dict(Counter(s["class_size_status"]["status"] for s in schools)),
                      "unresolved": sorted(({"bsid": s["bsid"], "name": s["name"], "board": s["board_name"], "others": s["class_size_status"]["others"]}
                                            for s in schools if s["class_size_status"]["status"] == "match_unresolved"), key=lambda x: (x["board"], x["name"]))}

    # class size medians (board and province) per year, for comparison lines
    cs_board, cs_prov = defaultdict(list), defaultdict(list)
    for s in schools:
        for r in s["class_size"]:
            if r["primary_avg"] is not None:
                cs_board[(s["board_number"], r["year"])].append(r["primary_avg"])
                cs_prov[(s["language"], r["year"])].append(r["primary_avg"])
    for s in schools:
        for r in s["class_size"]:
            bm = cs_board.get((s["board_number"], r["year"]), [])
            pm = cs_prov.get((s["language"], r["year"]), [])
            r["primary_board_median"] = median(bm) if len(bm) >= 3 else None
            r["primary_province_median"] = median(pm) if pm else None

    # ---------------- nearby ----------------
    for s in schools:
        s["nearby"] = [{"bsid": n["bsid"], "km": n["km"], "name": by_id[n["bsid"]]["name"], "level": by_id[n["bsid"]]["level"],
                        "language": by_id[n["bsid"]]["language"], "board_name": by_id[n["bsid"]]["board_name"],
                        "system": by_id[n["bsid"]]["system"]} for n in nearby.get(s["bsid"], [])]

    for s in schools:
        s["nearest_area"] = layers["cells"].get(s["bsid"])

    # ---------------- EQAO student questionnaire (school, its whole board, Ontario: kept apart) ----------------
    sq_report = {}
    for res in sources.EQAO_SQ_RESOURCES:
        d = eqao_sq[res["id"]]
        sq_report[res["id"]] = {"schools": len(d["schools"]), "matched": sum(1 for b in d["schools"] if b in by_id),
                                "withheld": sum(1 for b, o in d["schools"].items() if b in by_id and o["withheld"])}
    for s in schools:
        blocks = []
        for res in sources.EQAO_SQ_RESOURCES:
            d = eqao_sq[res["id"]]
            org = d["schools"].get(s["bsid"])
            if not org:
                continue
            board = d["boards"].get(s["board_number"])
            prov = d["province"].get(s["language"])
            items = []
            used_history = set()
            for key, q in d["questions"].items():
                mine = org["items"].get(key, {"code": "N/D", **parse.flags("N/D")})
                # earlier years of the same question (same wording and answers), newest first; different students each year
                hist = []
                for hid in sq_history[res["id"]]["comparable"].get(key, []):
                    h = eqao_sq[hid]
                    ho = h["schools"].get(s["bsid"])
                    if not ho:
                        continue
                    hv = ho["items"].get(key, {"code": "N/D"})
                    hist.append({"year": sq_year[hid], "source_id": hid, "agree_pct": hv.get("agree_pct"), "n": hv.get("n"), "code": hv.get("code"),
                                 "board_pct": h["boards"].get(s["board_number"], {}).get("items", {}).get(key, {}).get("agree_pct"),
                                 "province_pct": h["province"].get(s["language"], {}).get("items", {}).get(key, {}).get("agree_pct")})
                    used_history.add(hid)
                items.append({"key": key, **mine,
                              "board_pct": (board or {}).get("items", {}).get(key, {}).get("agree_pct"),
                              "province_pct": (prov or {}).get("items", {}).get(key, {}).get("agree_pct"),
                              "history": hist})
            blocks.append({"assessment": res["kind"], "grade": res["grade"], "year": res["year"], "source_id": res["id"],
                           "withheld": org["withheld"], "respondents": org["respondents"], "items": items,
                           "history_sources": sorted(used_history, reverse=True)})
        s["student_experience"] = blocks
    rep.eqao_sq = sq_report
    rep.eqao_sq_history = sq_history

    # ---------------- official attendance boundaries (boards' public map layers) ----------------
    log("official attendance boundaries")
    official = boundaries.build(schools, {s["board_number"]: s["board_name"] for s in schools}, log=log)
    for s in schools:
        o = official["by_school"].get(s["bsid"])
        lay = next((x for x in sources.BOUNDARY_LAYERS if o and x["id"] == o["layer"]), {})
        s["official_area"] = {"geometry": o["geometry"], "edited": o["edited"], "source_id": o["layer"],
                              "effective": lay.get("effective"), "effective_note": lay.get("effective_note")} if o else None
    for lvl, feats in official["layers"].items():
        geo.write_geojson(geo_dir / f"official-{lvl}.geojson", feats)
    rep.boundaries = official["report"]

    # ---------------- links + sources per school ----------------
    manifest = {res["id"]: fetch.manifest_entry(res["id"]) for res in sources.all_resources()}
    src_table = build_sources_table(manifest)
    src_ids = set(src_table)
    for s in schools:
        s["links"] = {
            "eqao": eqao_school_url(s["bsid"]),
            "ministry_profile": ministry_profile_url(s["bsid"], s["level"]),
            "find_your_school": "https://www.ontario.ca/page/find-your-school",
        }
        used = {s["coord_source"], s["contact_source"], s["context"]["source_id"], s["childcare"]["source_id"]}
        used |= {e["source_id"] for e in s["eqao"]} | {e["source_id"] for e in s["enrolment"]}
        used |= {e["source_id"] for e in s["grade_enrolment"]} | {e["source_id"] for e in s["class_size"]}
        used |= {p["source_id"] for p in s["programs"].values() if p}
        used |= {b["source_id"] for b in s["student_experience"]} | {h for b in s["student_experience"] for h in b.get("history_sources", [])}
        if s["official_area"]:
            used.add(s["official_area"]["source_id"])
        if s["earlyon_in_fsa"]:
            used.add(sources.EARLYON_RESOURCE["id"])
        used.discard("geocoder")
        s["sources"] = [src_table[i] for i in sorted(used) if i in src_ids]

    # ---------------- boards ----------------
    log("boards")
    boards: dict[str, dict] = {}
    for s in schools:
        b = boards.setdefault(s["board_number"], {
            "number": s["board_number"], "name": s["board_name"], "slug": slug(s["board_number"]),
            "website": s["board_website"], "systems": Counter(), "languages": Counter(), "levels": Counter(),
            "schools": [], "regions": Counter(),
        })
        b["systems"][s["system"]] += 1
        b["languages"][s["language"]] += 1
        b["levels"][s["level"]] += 1
        if s["region"]:
            b["regions"][s["region"]] += 1
        b["schools"].append(s["bsid"])
    latest_enrol = sources.ENROL_RESOURCES[0]["id"]
    for bn, b in boards.items():
        b["system"] = b["systems"].most_common(1)[0][0]
        b["system_label"] = SYSTEM_LABEL[b["system"]]
        b["language"] = b["languages"].most_common(1)[0][0]
        b["region"] = b["regions"].most_common(1)[0][0] if b["regions"] else None
        vals = [enrol[latest_enrol]["rows"].get(x) for x in b["schools"]]
        b["enrolment_total"] = {"value": sum(v for v, c in (x for x in vals if x) if v is not None),
                                "schools_counted": sum(1 for x in vals if x and x[0] is not None),
                                "schools_suppressed": sum(1 for x in vals if x and x[0] is None),
                                "year": sources.ENROL_RESOURCES[0]["year"], "source_id": latest_enrol}
        # ---- board context: spending, suspensions/expulsions, French program enrolment ----
        fin = finance["boards"].get(bn)
        sus = susp["boards"].get(bn, {})
        exp = expul["boards"].get(bn, {})
        fe = fsl_enrol["boards"].get(bn)
        enrol_year_total = b["enrolment_total"]["value"] if b["enrolment_total"]["year"] == sources.FSL_ENROL_RESOURCE["year"] else None
        b["context"] = {
            "spending": {**fin, "year": sources.FINANCE_RESOURCE["year"], "source_id": sources.FINANCE_RESOURCE["id"],
                         "ontario_median": spend_median} if fin else None,
            "safe": {
                "series": [{"year": y, "rate": sus.get(y, {}).get("rate"), "rate_code": sus.get(y, {}).get("rate_code"),
                            "count": sus.get(y, {}).get("count"), "count_code": sus.get(y, {}).get("count_code"),
                            "expelled": exp.get(y, {}).get("count"), "expelled_code": exp.get(y, {}).get("count_code"),
                            "province_rate": susp["province"].get(y, {}).get("rate")} for y in susp["years"] if y in sus],
                "source_ids": [sources.SUSPENSION_RESOURCE["id"], sources.EXPULSION_RESOURCE["id"]],
            } if sus else None,
            "fsl_enrolment": {**fe, "year": sources.FSL_ENROL_RESOURCE["year"], "source_id": sources.FSL_ENROL_RESOURCE["id"],
                              "immersion_share": round(100 * fe["immersion"] / enrol_year_total, 1) if enrol_year_total else None} if fe else None,
        }
        b["indicators"] = []
        for res in sources.SBPR_RESOURCES:
            row = sbpr[res["id"]]["rows"].get(bn)
            if row:
                b.setdefault("sbpr_city", row["city"])
                for key, v in row["indicators"].items():
                    b["indicators"].append({"key": key, "label": loaders.SBPR_LABELS[key], **v, "source_id": res["id"]})
        b["class_size_medians"] = [{"year": y, "primary_median": median(v), "n": len(v), "province_median": median(cs_prov.get((b["language"], y), []))}
                                   for (bn2, y), v in sorted(cs_board.items()) if bn2 == bn and len(v) >= 3]
        b["eqao_medians"] = []
        for year, src_of in eqao_years_all:
            for aid in loaders.ASSESSMENTS:
                bm = board_median.get((aid, year, bn))
                if bm:
                    pm = prov_median.get((aid, year, b["language"]))
                    b["eqao_medians"].append({"assessment": aid, "year": year, "board_median": bm[0], "board_n": bm[1],
                                              "province_median": pm[0] if pm else None, "province_n": pm[1] if pm else None,
                                              "source_id": src_of(aid), "era": eras.era_of(aid, year)})
        b["area"] = rep.layers["boards"].get(bn)
        b["levels"] = dict(b["levels"])
        b["systems"] = dict(b["systems"])
        b["languages"] = dict(b["languages"])
        b["regions"] = dict(b["regions"])
        used = {s for s in [latest_enrol] + [i["source_id"] for i in b["indicators"]] + [m["source_id"] for m in b["eqao_medians"]]}
        used.add(latest_res["id"])
        ctx = b["context"]
        for part in ("spending", "fsl_enrolment"):
            if ctx[part]:
                used.add(ctx[part]["source_id"])
        if ctx["safe"]:
            used |= set(ctx["safe"]["source_ids"])
        b["sources"] = [src_table[i] for i in sorted(used) if i in src_ids]
    rep.count("boards", len(boards), "boards with at least one school")
    missing_area = [bn for bn, b in boards.items() if b["system"] != "other" and any(by_id[x]["regular"] for x in b["schools"]) and not b["area"]]
    rep.boards_without_area = missing_area

    # ---------------- FSAs ----------------
    log("FSAs")
    fsas: dict[str, dict] = {}
    all_fsa = sorted(set(fsa_codes) | {s["fsa"] for s in schools})
    for f in all_fsa:
        inside = sorted(set(fsa_schools.get(f, {}).get("in", [])) | {s["bsid"] for s in schools if s["fsa"] == f})
        near = [b for b in fsa_schools.get(f, {}).get("near", []) if b not in inside]
        cities = Counter(by_id[b]["city"] for b in inside if by_id[b]["city"])
        cc = cc_by_fsa.get(f, [])
        fsas[f] = {
            "fsa": f, "in": inside, "near": near,
            "place": cities.most_common(1)[0][0] if cities else None,
            "census": census["rows"].get(f), "census_source": sources.CENSUS_RESOURCE["id"] if f in census["rows"] else None,
            "boundary": layers["fsa_detail"].get(f), "boundary_source": sources.FSA_RESOURCE["id"] if f in layers["fsa_detail"] else None,
            "childcare": {"count": len(cc), "source_id": sources.CHILDCARE_RESOURCE["id"],
                          "sites": [{k: x[k] for k in ("name", "type", "language", "address", "city", "postal_code")} for x in cc]},
            "rural": f[1] == "0",
            "earlyon": {"count": len(eo_by_fsa.get(f, [])), "source_id": sources.EARLYON_RESOURCE["id"],
                        "sites": [{k: x[k] for k in ("name", "address", "city", "postal_code")} for x in eo_by_fsa.get(f, [])]},
        }
        if not inside and not near:
            # nothing within the buffer (large rural FSAs at the edge): list the closest schools to the area's centre
            if f in layers["fsa_detail"]:
                import shapely.geometry as sg
                c = sg.shape(layers["fsa_detail"][f]).representative_point()
                dists = sorted(schools, key=lambda s: (s["lat"] - c.y) ** 2 + ((s["lon"] - c.x) * 0.7) ** 2)[:8]
                fsas[f]["closest"] = [s["bsid"] for s in dists]
        used = [x for x in (fsas[f]["census_source"], fsas[f]["boundary_source"], sources.CHILDCARE_RESOURCE["id"], latest_res["id"],
                            sources.EARLYON_RESOURCE["id"] if fsas[f]["earlyon"]["count"] else None) if x]
        fsas[f]["sources"] = [src_table[i] for i in used if i in src_ids]
    rep.count("fsas", len(fsas), "postal areas (FSAs) with a page")

    # ---------------- write outputs ----------------
    log("writing site/data")
    sq_meta = {}
    for res in sources.EQAO_SQ_RESOURCES:
        sq_meta[res["id"]] = {"kind": res["kind"], "grade": res["grade"], "year": res["year"],
                              "questions": list(eqao_sq[res["id"]]["questions"].values()),
                              "history": sq_history[res["id"]]}
    write_outputs(schools, boards, fsas, src_table, census, rep, [y for y, _ in eqao_years_all], prov_median, sq_meta)
    rep.elapsed = round(time.time() - t0)
    rep.write(config.REPORT, schools=schools, boards=boards, fsas=fsas, sources_table=src_table)
    log(f"done in {rep.elapsed}s: {len(schools)} schools, {len(boards)} boards, {len(fsas)} FSAs")
    return {"schools": len(schools), "boards": len(boards), "fsas": len(fsas)}


GENERIC_SCHOOL_WORDS = {"school", "public", "ps", "catholic", "cs", "ces", "elementary", "separate", "ecole", "elementaire", "catholique",
                        "publique", "the", "of", "and", "de", "du", "des", "la", "le", "l", "d", "sr", "jr"}
GENERIC_BOARD_WORDS = {"district", "school", "board", "dsb", "cdsb", "catholic", "public", "conseil", "scolaire", "catholique", "public",
                       "de", "du", "des", "la", "le", "l", "d", "csd", "csdc", "csc", "cscd", "cs", "the", "of", "and", "separate",
                       "roman", "rcssb", "rcss", "dssb", "authority", "sa", "isolate", "area", "boards", "des", "ecoles", "publiques"}


def _tokens(name: str) -> list[str]:
    import unicodedata
    t = unicodedata.normalize("NFD", name or "")
    t = "".join(ch for ch in t if unicodedata.category(ch) != "Mn").lower()
    t = re.sub(r"\b(saint|sainte|ste|st)\b\.?", "st", t)
    return re.findall(r"[a-z0-9]+", t)


def school_key(name: str) -> str:
    return " ".join(w for w in _tokens(name) if w not in GENERIC_SCHOOL_WORDS)


def board_key(name: str) -> tuple:
    toks = _tokens(name)
    catholic = any(w in ("catholic", "catholique", "cdsb", "csc", "cscd", "csdc", "separate", "rcssb", "rcss") for w in toks)
    return (frozenset(w for w in toks if w not in GENERIC_BOARD_WORDS), catholic)


def match_class_lists(files: list[tuple[str, dict]], name_index: dict, by_id: dict) -> dict:
    """Match the Ministry's class lists, which name schools but don't number them, to school numbers.

    A class-list row matches a school when its school name (any name the school has used, normalised)
    and its board both agree, and exactly one school fits. The lists are of elementary classes (JK to
    Grade 8), so a school number whose grade range has none of those grades (a 9-12 school the Ministry
    splits from its 7-8 twin of the same name) can't own the row; a missing grade range doesn't rule a
    school out. When two or more schools still fit, the row can't be split between them, so it is skipped
    and both are recorded as ambiguous (with each other and the years affected). Nothing is guessed from
    enrolment or class mix.
    """
    by_school, ambiguous, ambiguous_years = defaultdict(list), defaultdict(set), defaultdict(set)
    matched, unmatched, ambiguous_rows = 0, Counter(), 0
    for source_id, rows in files:
        for (year, board, school), a in rows.items():
            cands = name_index.get(school_key(school), set())
            bk = board_key(board)
            hits = [b for b in cands if board_key(by_id[b]["board_name"]) == bk and may_have_elementary_classes(by_id[b].get("grades"))]
            if len(hits) != 1:
                if len(hits) > 1:
                    ambiguous_rows += 1
                    for b in hits:
                        ambiguous[b] |= set(hits) - {b}
                        ambiguous_years[b].add(year)
                else:
                    unmatched[year] += 1
                continue
            matched += 1
            by_school[hits[0]].append(class_size_row(year, a, source_id))
    return {"by_school": by_school, "ambiguous": ambiguous, "ambiguous_years": ambiguous_years,
            "matched": matched, "unmatched": unmatched, "ambiguous_rows": ambiguous_rows}


ELEMENTARY_GRADES = {"JK", "K", "SK", "1", "2", "3", "4", "5", "6", "7", "8"}


def may_have_elementary_classes(grade_range: str | None) -> bool:
    """False only when the school's published grade range has no grade from JK to 8 (e.g. "9-12")."""
    m = re.fullmatch(r"\s*(JK|SK|K|\d{1,2})\s*-\s*(JK|SK|K|\d{1,2})\s*", (grade_range or "").upper())
    if not m:
        return True  # unknown range: don't rule the school out
    lo = m.group(1)
    return lo in ELEMENTARY_GRADES and (not lo.isdigit() or int(lo) <= 8)


def class_size_status(s: dict, kept: list, ambiguous: dict, ambiguous_years: dict) -> dict:
    """Why a school page has (or hasn't) class sizes, in words a parent can act on."""
    if kept:  # includes the odd secondary school with Grade 7-8 classes in the elementary lists
        st = {"status": "reported"}
        if s["bsid"] in ambiguous:  # matched in some years, but a same-named school blocks others
            st["unresolved_years"] = sorted(ambiguous_years[s["bsid"]] - {r["year"] for r in kept})
        return st
    if s["bsid"] in ambiguous:
        return {"status": "match_unresolved", "others": sorted(ambiguous[s["bsid"]]), "years": sorted(ambiguous_years[s["bsid"]])}
    if s["level"] != "elementary":
        return {"status": "not_applicable"}
    return {"status": "not_listed"}


def proximity_area(s: dict, fsl_row: dict | None) -> tuple[bool, str]:
    """(immersion_only, why) for the nearest-school area: "drawn", or why it isn't.

    An English-language elementary school the Ministry lists as offering French Immersion but neither
    Core nor Extended French is almost certainly an Immersion school (Core French is required in Grades
    4-8 of the regular English program), which families choose for the program, not by neighbourhood.
    """
    f = fsl_row or {}
    imm_only = bool(f.get("immersion") and not f.get("core") and not f.get("extended")
                    and s["level"] == "elementary" and s["language"] == "English")
    if s["system"] == "other":
        return imm_only, "other_system"
    if not s["regular"]:
        return imm_only, "not_regular"
    if imm_only:
        return imm_only, "immersion_only"
    return imm_only, "drawn"


def class_size_row(year: str, a: dict, source_id: str) -> dict:
    """Per-school figures computed from the Ministry's class list (one row per class)."""
    def avg(v):
        return round(sum(v) / len(v), 1) if v else None
    complete = year >= "2014-15"  # earlier files list only primary (JK to Grade 3) classes
    p = a["primary"]
    return {
        "year": year, "source_id": source_id, "complete": complete,
        "classes": a["classes"] if complete else None,
        "avg_all": round(a["students"] / a["classes"], 1) if complete and a["classes"] else None,
        "primary_classes": len(p), "primary_avg": avg(p),
        "primary_le20_pct": round(100 * sum(1 for x in p if x <= 20) / len(p)) if p else None,
        "primary_max": max(p) if p else None,
        "kinder_avg": avg(a["kinder"]), "junior_avg": avg(a["junior"]) if complete else None,
        "combined_classes": a["combined"],
    }


def build_sources_table(manifest: dict) -> dict:
    table = {}
    for res in sources.all_resources():
        ds = sources.DATASETS[res["dataset"]]
        m = manifest.get(res["id"], {})
        retrieved = (m.get("retrieved") or "")[:10] or None
        # show the file we actually read (the mirror, when the official FSA file was blocked)
        url = (m.get("url") or res["url"]) if res["dataset"] == "fsa_boundary" else res["url"]
        table[res["id"]] = {
            "source_id": res["id"], "dataset": res["dataset"], "brief_no": ds["brief_no"],
            "title": ds["title"] + (f" ({res.get('label') or res['year']})" if (res.get("label") or res.get("year")) else ""),
            "publisher": ds["publisher"], "url": url, "landing": ds["landing"],
            "licence": ds["licence"][0], "licence_url": ds["licence"][1], "licence_status": ds["licence_status"], "retrieved": retrieved,
            # "year" is the period the file describes (reference period); "retrieved" is only when we downloaded it
            "year": res.get("year"), "release": res.get("release"), "historical": bool(ds.get("historical")),
            "note": res.get("note", "") + (f" {m['note']}" if m.get("note") else ""),
            "downloaded": bool(m),
        }
    return table


def write_outputs(schools, boards, fsas, src_table, census, rep, eqao_years, prov_median, sq_meta=None) -> None:
    out = config.OUT
    (out / "schools").mkdir(parents=True, exist_ok=True)
    (out / "boards").mkdir(parents=True, exist_ok=True)
    (out / "fsa").mkdir(parents=True, exist_ok=True)
    (out / "downloads").mkdir(parents=True, exist_ok=True)

    def dump(path, obj):
        path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    for s in schools:
        dump(out / "schools" / f"{s['bsid']}.json", s)
    for bn, b in boards.items():
        dump(out / "boards" / f"{b['slug']}.json", b)
    for f, rec in fsas.items():
        dump(out / "fsa" / f"{f}.json", rec)

    # compact search index: short keys keep it small
    idx = [{
        "id": s["bsid"], "n": s["name"], "c": s["city"], "f": s["fsa"], "b": s["board_number"], "bn": s["board_name"],
        "l": "E" if s["level"] == "elementary" else "S", "g": s["grades"], "lang": (s["language"] or "")[:1],
        "sys": s["system"], "x": round(s["lon"], 5), "y": round(s["lat"], 5), "sp": s["special"] or None,
        # programs, for search filters: French Immersion / Extended French offered, number of SHSM sectors
        "fi": 1 if (s["programs"]["fsl"] or {}).get("immersion") else None,
        "ef": 1 if (s["programs"]["fsl"] or {}).get("extended") else None,
        "sh": len(s["programs"]["shsm"]["sectors"]) if s["programs"]["shsm"] else None,
    } for s in sorted(schools, key=lambda s: s["name"])]
    for r in idx:  # program flags only where true: most schools have none, so don't ship thousands of nulls
        for k in ("fi", "ef", "sh"):
            if r[k] is None:
                del r[k]
    dump(out / "schools-index.json", idx)
    # one small file with each board's headline context, for the compare tool (instead of loading
    # every board's full page data): spending per student, latest suspension rate, Immersion share
    bctx = {}
    for bn, b in boards.items():
        c = b.get("context") or {}
        sp, sf, fe = c.get("spending"), c.get("safe"), c.get("fsl_enrolment")
        last = next((r for r in reversed(sf["series"]) if r["rate"] is not None), None) if sf else None
        row = {"sp": sp["per_student"] if sp else None, "sr": last["rate"] if last else None, "sry": last["year"] if last else None,
               "srp": last["province_rate"] if last else None, "fi": fe["immersion_share"] if fe else None}
        if any(v is not None for v in row.values()):
            bctx[bn] = row
    spend_med = next((b["context"]["spending"]["ontario_median"] for b in boards.values() if (b.get("context") or {}).get("spending")), None)
    dump(out / "boards-context.json", {
        "spending_year": sources.FINANCE_RESOURCE["year"], "spending_median": spend_med,
        "fsl_year": sources.FSL_ENROL_RESOURCE["year"], "boards": bctx,
    })
    dump(out / "boards-index.json", [{"n": b["number"], "name": b["name"], "slug": b["slug"], "sys": b["system"], "count": len(b["schools"])}
                                    for b in sorted(boards.values(), key=lambda b: b["name"])])
    dump(out / "fsa-index.json", [{"f": f, "p": r["place"], "count": len(r["in"])} for f, r in sorted(fsas.items())])
    dump(out / "sources.json", src_table)
    retrieved = sorted(x["retrieved"] for x in src_table.values() if x["retrieved"])
    meta = {
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "data_updated": retrieved[-1] if retrieved else None,
        "counts": {"schools": len(schools), "boards": len(boards), "fsas": len(fsas)},
        "eqao_years": list(reversed(eqao_years)),
        "latest_eqao_year": eqao_years[0],
        "latest_sif": sources.SIF_RESOURCES[0]["id"],
        # boards whose official attendance areas are on the site (map legend, How it works)
        "official_boundaries": [{"board": r["board"], "level": r["level"], "edited": r["edited"], "areas": r["matched"], "source_id": lid}
                                for lid, r in rep.boundaries.items() if r["matched"]],
        "assessments": loaders.ASSESSMENTS,
        "eqao_eras": eras.meta(),
        "student_questionnaire": sq_meta or {},
        "licence_status": sources.LICENCE_STATUS,
        "context_fields": [{"key": k, "label": lab, "definition": d} for k, lab, _c, d in loaders.SIF_CONTEXT_COLS],
        "census_fields": [{"key": k, "label": lab, "unit": u} for k, _c, _s, lab, u in sources.CENSUS_FIELDS],
        "codes": {k: {x: v[x] for x in ("label", "explain")} for k, v in parse.CODES.items()},
        "datasets": {k: {x: v[x] for x in ("brief_no", "title", "publisher", "landing", "used_for", "status", "licence_status", "cadence")}
                     | {"licence": v["licence"][0], "licence_url": v["licence"][1], "historical": bool(v.get("historical"))}
                     for k, v in sources.DATASETS.items()},
        "references": sources.REFERENCES,
        "systems": SYSTEM_LABEL,
        "layers": rep.layers,
        "province_medians": [{"assessment": a, "year": y, "language": l, "median": m, "n": n} for (a, y, l), (m, n) in sorted(prov_median.items())],
        "skipped": rep.skipped,
        "notes": rep.notes,
        "fsa_check": {"checked": rep.fsa_checked, "mismatches": len(rep.fsa_mismatches)},
    }
    dump(out / "meta.json", meta)

    # downloads (CSV) ----------------------------------------------------------
    d = out / "downloads"
    with open(d / "schools.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        cols = ["bsid", "name", "board_number", "board_name", "board_type", "language", "level", "grades", "special", "address",
                "city", "postal_code", "fsa", "lat", "lon", "geocoded", "phone", "email", "website", "status", "date_open"]
        # program flags come from their own files (FSL list, SHSM list, the 2017 nutrition list): see programs_source_ids
        extra = ["french_immersion", "extended_french", "core_french", "fsl_list_year", "shsm_sectors",
                 "nutrition_program_historical", "class_size_status", "nearest_school_area"]
        w.writerow(cols + ["source_id"] + extra + ["programs_source_ids"])
        yn = {True: "yes", False: "no", None: ""}
        for s in schools:
            f, sh, nu = s["programs"]["fsl"], s["programs"]["shsm"], s["programs"]["nutrition"]
            w.writerow([s.get(c) for c in cols] + [s["contact_source"]] + [
                yn[f["immersion"]] if f else "", yn[f["extended"]] if f else "", yn[f["core"]] if f else "", f["year"] if f else "",
                "; ".join(x["sector"] for x in sh["sectors"]) if sh else "",
                f"historically listed ({nu['year']}): {', '.join(nu['meals'])}; current availability unverified" if nu else "",
                s["class_size_status"]["status"], s["proximity_area"],
                " ".join(p["source_id"] for p in s["programs"].values() if p)])
    with open(d / "eqao.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        # era: "current" (2021-22 on, EQAO's new trend line) or "paper" (2016-17 to 2018-19, reference only).
        # Never compute a change between rows of different eras.
        w.writerow(["bsid", "name", "year", "era", "assessment", "grade", "subject", "pct_at_or_above_standard", "suppressed", "small_cohort", "code",
                    "board_median", "board_n", "province_median", "province_n", "source_id"])
        for s in schools:
            for e in s["eqao"]:
                w.writerow([s["bsid"], s["name"], e["year"], e["era"], e["assessment"], e["grade"], e["subject"], e["pct_at_or_above_standard"],
                            e["suppressed"], e["small_cohort"], e.get("code"), e["board_median"], e["board_n"], e["province_median"],
                            e["province_n"], e["source_id"]])
    with open(d / "student-experience.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        qtext = {(sid, q["key"]): q["question"] for sid, m in (sq_meta or {}).items() for q in m["questions"]}
        w.writerow(["bsid", "name", "year", "grade", "question_key", "question", "students", "agree_pct", "agree_pct_derived",
                    "missing_pct", "code", "board_agree_pct", "province_agree_pct", "source_id"])
        for s in schools:
            for b in s["student_experience"]:
                for it in b["items"]:
                    w.writerow([s["bsid"], s["name"], b["year"], b["grade"], it["key"], qtext.get((b["source_id"], it["key"]), ""),
                                it.get("n"), it.get("agree_pct"), it.get("agree_derived"), it.get("missing_pct"), it.get("code"),
                                it.get("board_pct"), it.get("province_pct"), b["source_id"]])
                    for h in it.get("history", []):  # earlier years: same question, same answers, different students
                        w.writerow([s["bsid"], s["name"], h["year"], b["grade"], it["key"], qtext.get((b["source_id"], it["key"]), ""),
                                    h.get("n"), h.get("agree_pct"), it.get("agree_derived"), None, h.get("code"),
                                    h.get("board_pct"), h.get("province_pct"), h["source_id"]])
    with open(d / "enrolment.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["bsid", "name", "year", "enrolment", "suppressed", "code", "source_id"])
        for s in schools:
            for e in s["enrolment"]:
                w.writerow([s["bsid"], s["name"], e["year"], e["value"], e["suppressed"], e.get("code"), e["source_id"]])
    with open(d / "fsa-census.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        keys = [k for k, *_ in sources.CENSUS_FIELDS]
        w.writerow(["fsa"] + keys + ["source_id"])
        for f, rec in sorted(fsas.items()):
            if rec["census"]:
                w.writerow([f] + [rec["census"].get(k) for k in keys] + [sources.CENSUS_RESOURCE["id"]])
    with open(d / "sources.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        # year = the period the file describes; retrieved = when this site downloaded it (not how current it is)
        w.writerow(["source_id", "title", "publisher", "url", "licence", "licence_url", "licence_status", "retrieved", "year", "release", "historical"])
        for x in src_table.values():
            w.writerow([x["source_id"], x["title"], x["publisher"], x["url"], x["licence"], x["licence_url"], x["licence_status"], x["retrieved"],
                        x["year"], x["release"] or "", "yes" if x["historical"] else ""])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--clean", action="store_true", help="delete downloaded files first (keeps the geocode cache)")
    ap.add_argument("--refresh", action="store_true",
                    help="keep downloaded files but ask each publisher whether its file changed; replace only those that did")
    args = ap.parse_args(argv)
    if args.clean and args.refresh:
        ap.error("--clean already downloads everything again; use one or the other")
    fetch.REVALIDATE = args.refresh
    try:
        build(clean=args.clean)
    except (fetch.SchemaChanged, SourceUnavailable, parse.UnknownToken) as e:
        print(f"\nPIPELINE FAILED: {e}\n", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
