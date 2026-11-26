"""Loaders: one per source. Each validates its columns and fails loudly when they change."""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from collections import Counter
from datetime import date, datetime
from pathlib import Path

import openpyxl

from . import config, fetch, parse, sources
from .fetch import SchemaChanged, SourceUnavailable

# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def require_columns(source_id: str, found: list[str], expected: list[str], *, exact: bool = False) -> None:
    found_clean = [norm_header(h) for h in found if h is not None and str(h).strip()]
    exp_clean = [norm_header(h) for h in expected]
    missing = [e for e in exp_clean if e not in found_clean]
    extra = [f for f in found_clean if f not in exp_clean]
    if missing or (exact and extra):
        raise SchemaChanged(
            f"{source_id}: columns changed.\n  expected: {exp_clean}\n  found:    {found_clean}\n"
            f"  missing:  {missing}\n  unexpected: {extra}\n"
            "Update pipeline/loaders.py after checking the dataset's documentation."
        )


def norm_header(h) -> str:
    return re.sub(r"\s+", " ", str(h).replace("\xa0", " ")).strip()


def read_xlsx(path: Path) -> tuple[str, list[str], list[tuple]]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = ws.iter_rows(values_only=True)
    header = [norm_header(h) if h is not None else None for h in next(rows)]
    body = [r for r in rows]
    title = ws.title
    wb.close()
    return title, header, body


def read_pipe_txt(path: Path) -> tuple[list[str], list[list[str]]]:
    raw = path.read_bytes()
    for enc in ("utf-8-sig", "cp1252"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:  # pragma: no cover
        raise SchemaChanged(f"{path.name}: unknown text encoding")
    reader = csv.reader(io.StringIO(text), delimiter="|", quoting=csv.QUOTE_NONE)
    rows = [r for r in reader if any(c.strip() for c in r)]
    return [norm_header(h) for h in rows[0]], rows[1:]


def school_number(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return str(int(v)).zfill(6)
    s = str(v).strip()
    if not s:
        return None
    return s.zfill(6) if s.isdigit() else s.upper()


# ---------------------------------------------------------------------------
# 1. School information and student demographics (one file per school year)
# ---------------------------------------------------------------------------

SIF_INFO_COLS = [
    "Board Number", "Board Name", "Board Type", "School Number", "School Name", "School Type",
    "School Special Condition Code", "School Level", "School Language", "Grade Range", "Building Suite",
    "P.O. Box", "Street", "Municipality", "City", "Province", "Postal Code", "Phone Number", "Fax Number",
    "School Website", "Board Website", "Enrolment", "Latitude", "Longitude",
]

# key, label, source column, definition (shown on the site)
SIF_CONTEXT_COLS = [
    ("first_lang_not_english", "First language is not English", "Percentage of Students Whose First Language Is Not English",
     "Share of students whose first language is not English."),
    ("first_lang_not_french", "First language is not French", "Percentage of Students Whose First Language Is Not French",
     "Share of students whose first language is not French."),
    ("new_non_english", "New to Canada from a non-English-speaking country", "Percentage of Students Who Are New to Canada from a Non-English Speaking Country",
     "Share of students who arrived in Canada in the last few years from a country where English is not a main language."),
    ("new_non_french", "New to Canada from a non-French-speaking country", "Percentage of Students Who Are New to Canada from a Non-French Speaking Country",
     "Share of students who arrived in Canada in the last few years from a country where French is not a main language."),
    ("special_ed", "Receiving special education services", "Percentage of Students Receiving Special Education Services",
     "Share of students receiving special education programs or services."),
    ("gifted", "Identified as gifted", "Percentage of Students Identified as Gifted",
     "Share of students formally identified as gifted by an Identification, Placement and Review Committee."),
    ("low_income", "School-aged children in low-income households", "Percentage of School-Aged Children Who Live in Low-Income Households",
     "Estimated share of school-aged children in the school's area who live in low-income households (Statistics Canada census data matched to student addresses)."),
    ("parents_no_degree", "Parents with no degree, diploma or certificate", "Percentage of Students Whose Parents Have No Degree, Diploma or Certificate",
     "Estimated share of students whose parents have no degree, diploma or certificate (Statistics Canada census data matched to student addresses)."),
]

# assessment id, grade label, subject label, column, which Grade 9 layout it belongs to
EQAO_COLS = [
    ("g3-reading", "Grade 3", "Reading", "Percentage of Grade 3 Students Achieving the Provincial Standard in Reading", None),
    ("g3-writing", "Grade 3", "Writing", "Percentage of Grade 3 Students Achieving the Provincial Standard in Writing", None),
    ("g3-math", "Grade 3", "Mathematics", "Percentage of Grade 3 Students Achieving the Provincial Standard in Mathematics", None),
    ("g6-reading", "Grade 6", "Reading", "Percentage of Grade 6 Students Achieving the Provincial Standard in Reading", None),
    ("g6-writing", "Grade 6", "Writing", "Percentage of Grade 6 Students Achieving the Provincial Standard in Writing", None),
    ("g6-math", "Grade 6", "Mathematics", "Percentage of Grade 6 Students Achieving the Provincial Standard in Mathematics", None),
    ("g9-math", "Grade 9", "Mathematics", "Percentage of Grade 9 Students Achieving the Provincial Standard in Mathematics", sources.G9_DESTREAMED),
    ("g9-math-academic", "Grade 9", "Academic mathematics", "Percentage of Grade 9 Students Achieving the Provincial Standard in Academic Mathematics", sources.G9_STREAMED),
    ("g9-math-applied", "Grade 9", "Applied mathematics", "Percentage of Grade 9 Students Achieving the Provincial Standard in Applied Mathematics", sources.G9_STREAMED),
    ("osslt", "Grade 10", "Literacy (OSSLT)", "Percentage of Students That Passed the Grade 10 OSSLT on Their First Attempt", None),
]

ASSESSMENTS = {a: {"id": a, "grade": g, "subject": s} for a, g, s, _, _ in EQAO_COLS}


def sif_expected_columns(g9: str) -> list[str]:
    cols = list(SIF_INFO_COLS) + [c[2] for c in SIF_CONTEXT_COLS]
    cols += [c for _, _, _, c, layout in EQAO_COLS if layout in (None, g9)]
    return cols


def load_sif(res: dict) -> dict:
    """Load one School Information file. Returns {'rows': {bsid: {...}}, 'stats': {...}}."""
    path = fetch.download(res["id"], res["url"], expect="xlsx")
    title, header, body = read_xlsx(path)
    if res.get("sheet_must_contain") and res["sheet_must_contain"] not in title:
        raise SchemaChanged(f"{res['id']}: sheet '{title}' does not name EQAO year {res['sheet_must_contain']} — the file may have been replaced.")
    require_columns(res["id"], header, sif_expected_columns(res["g9"]))
    idx = {h: i for i, h in enumerate(header) if h}
    rows: dict[str, dict] = {}
    stats = Counter()
    for r in body:
        bsid = school_number(r[idx["School Number"]])
        if not bsid:
            stats["rows_without_school_number"] += 1
            continue
        if bsid in rows:
            raise SchemaChanged(f"{res['id']}: school number {bsid} appears twice")

        def g(col):
            return r[idx[col]]

        rec = {"bsid": bsid}
        for col in SIF_INFO_COLS:
            rec[col] = g(col)
        ctx = {}
        for key, _label, col, _d in SIF_CONTEXT_COLS:
            v, code = parse.parse_pct(g(col), context=f"{res['id']} {bsid} {col}", numeric=res.get("context_numeric"))
            ctx[key] = {"value": v, **parse.flags(code)}
            if code:
                stats[f"context_code_{code}"] += 1
        rec["context"] = ctx
        eq = {}
        if res["eqao_year"]:
            for aid, _g, _s, col, layout in EQAO_COLS:
                if layout not in (None, res["g9"]):
                    continue
                v, code = parse.parse_pct(g(col), context=f"{res['id']} {bsid} {col}", numeric="fraction")
                eq[aid] = (v, code)
                stats[f"eqao_{code or 'value'}"] += 1
        rec["eqao"] = eq
        e, ecode = parse.parse_count(g("Enrolment"), context=f"{res['id']} {bsid} Enrolment")
        rec["enrolment"] = (e, ecode)
        rows[bsid] = rec
    stats["schools"] = len(rows)
    return {"rows": rows, "stats": dict(stats), "sheet": title}


# ---------------------------------------------------------------------------
# 2. Contact list
# ---------------------------------------------------------------------------

CONTACT_COLS = [
    "Region", "Board Number", "Board Name", "Board Type", "Board Language", "School Number", "School Name",
    "School Level", "School Language", "School Type", "School Special Conditions", "Suite", "PO Box", "Street",
    "City", "Province", "Postal Code", "Phone", "Fax", "Grade Range", "Date Open", "Email", "Website", "Board Website",
]


def load_contact(res: dict) -> dict:
    path = fetch.download(res["id"], res["url"], expect="txt")
    header, body = read_pipe_txt(path)
    require_columns(res["id"], header, CONTACT_COLS)
    out = {}
    for r in body:
        if len(r) != len(header):
            raise SchemaChanged(f"{res['id']}: a row has {len(r)} fields, header has {len(header)}")
        d = dict(zip(header, r))
        bsid = school_number(d["School Number"])
        if bsid:
            out[bsid] = d
    return {"rows": out, "stats": {"rows": len(out)}}


# ---------------------------------------------------------------------------
# 4. School board achievements and progress
# ---------------------------------------------------------------------------

SBPR_FIXED = ["Board Number", "Board Name", "Board Language", "Board Type", "Region", "City"]
SBPR_PATTERNS = [
    # key, regex for header, label, year field in resource
    ("g6_reading", r"^Grade 6 EQAO Reading Results$", "Grade 6 students meeting the provincial reading standard", "eqao_year"),
    ("g6_reading_change", r"^Progress in Grade 6 EQAO Reading Results$", "Change in Grade 6 reading (percentage points)", "eqao_year"),
    ("osslt", r"^Grade 10 OSSLT Results$", "Students passing the Grade 10 literacy test (OSSLT) on their first try", "eqao_year"),
    ("osslt_change", r"^Progress in Grade 10 OSSLT Results$", "Change in OSSLT (percentage points)", "eqao_year"),
    ("credits_g10", r"^Credit Accumulation by the end of Grade 10$", "Students with 16+ credits by the end of Grade 10", "credits_year"),
    ("credits_g10_change", r"^Progress in Credit Accumulation by the end of Grade 10$", "Change in Grade 10 credit accumulation", "credits_year"),
    ("credits_g11", r"^Credit Accumulation by the end of Grade 11$", "Students with 23+ credits by the end of Grade 11", "credits_year"),
    ("credits_g11_change", r"^Progress in Credit Accumulation by the end of Grade 11$", "Change in Grade 11 credit accumulation", "credits_year"),
    ("grad_4yr", r"^Four Year Graduation Rate (\d{4}-\d{4}) Grade 9 Cohort$", "Four-year graduation rate", "grad_year"),
    ("grad_4yr_change", r"^Progress in Four Year Graduation Rate (\d{4}-\d{4}) Grade 9 Cohort$", "Change in four-year graduation rate", "grad_year"),
    ("grad_5yr", r"^Five Year Graduation Rate (\d{4}-\d{4}) Grade 9 Cohort$", "Five-year graduation rate", "grad_year"),
    ("grad_5yr_change", r"^Progress in Five Year Graduation Rate (\d{4}-\d{4}) Grade 9 Cohort$", "Change in five-year graduation rate", "grad_year"),
]

SBPR_LABELS = {k: lab for k, _, lab, _ in SBPR_PATTERNS}


def load_sbpr(res: dict) -> dict:
    path = fetch.download(res["id"], res["url"], expect="xlsx")
    _title, header, body = read_xlsx(path)
    require_columns(res["id"], header, SBPR_FIXED)
    colmap, cohorts = {}, {}
    for key, pat, _lab, _yf in SBPR_PATTERNS:
        hits = [(i, h) for i, h in enumerate(header) if h and re.match(pat, h)]
        if len(hits) != 1:
            raise SchemaChanged(f"{res['id']}: expected one column matching /{pat}/, found {[h for _, h in hits]} in {header}")
        colmap[key] = hits[0][0]
        m = re.match(pat, hits[0][1])
        if m and m.groups():
            cohorts[key] = m.group(1)
    idx = {h: i for i, h in enumerate(header) if h}
    boards = {}
    stats = Counter()
    for r in body:
        bn = r[idx["Board Number"]]
        if not bn:
            continue
        bn = str(bn).strip()
        vals = {}
        for key, _pat, _lab, yf in SBPR_PATTERNS:
            v, code = parse.parse_fraction(r[colmap[key]], context=f"{res['id']} {bn} {key}", digits=1)
            vals[key] = {"value": v, "year": res[yf], "cohort": cohorts.get(key), **parse.flags(code)}
            stats[f"code_{code}" if code else "values"] += 1
        boards[bn] = {
            "name": r[idx["Board Name"]], "language": r[idx["Board Language"]], "type": r[idx["Board Type"]],
            "region": r[idx["Region"]], "city": r[idx["City"]], "indicators": vals,
        }
    stats["boards"] = len(boards)
    return {"rows": boards, "stats": dict(stats), "cohorts": cohorts}


# ---------------------------------------------------------------------------
# 5. Enrolment by school (one file per year)
# ---------------------------------------------------------------------------

ENROL_COLS = ["Board Number", "Board Name", "School Number", "School Name", "School Level", "School Type", "School Language", "Enrolment"]


def load_enrolment(res: dict) -> dict:
    path = fetch.download(res["id"], res["url"], expect="txt")
    header, body = read_pipe_txt(path)
    require_columns(res["id"], header, ENROL_COLS, exact=True)
    out, stats = {}, Counter()
    for r in body:
        d = dict(zip(header, r))
        bsid = school_number(d.get("School Number"))
        if not bsid or not re.fullmatch(r"[0-9A-Z]{6}", bsid):
            stats["skipped_rows"] += 1  # totals / notes rows
            continue
        v, code = parse.parse_count(d["Enrolment"], context=f"{res['id']} {bsid}")
        out[bsid] = (v, code)
        stats[f"code_{code}" if code else "values"] += 1
    stats["schools"] = len(out)
    return {"rows": out, "stats": dict(stats)}


# ---------------------------------------------------------------------------
# 10. Licensed child care
# ---------------------------------------------------------------------------

CHILDCARE_COLS = [
    "Report Snapshot Date", "Licensee Name", "Program Type Desc", "Region Display Name", "CMSM / DSSAB Name",
    "Child Care Site Name", "Licence Number", "Program Option", "Original Issue Date", "Licence Status",
    "Closure or Termination Date", "Language of Service Desc", "Street Number", "Street Name", "Street Type",
    "City", "Province", "Postal Code",
]


def load_childcare(res: dict) -> dict:
    path = fetch.download(res["id"], res["url"], expect="xlsx")
    _t, header, body = read_xlsx(path)
    require_columns(res["id"], header, CHILDCARE_COLS)
    idx = {h: i for i, h in enumerate(header) if h}
    out, stats = [], Counter()
    for r in body:
        def g(c):
            return r[idx[c]]
        status = parse.clean_text(g("Licence Status"))
        stats[f"status_{status}"] += 1
        if status != "Active":
            continue
        postal = parse.norm_postal(g("Postal Code"))
        num = parse.clean_text(g("Street Number"))
        street = " ".join(x for x in [parse.clean_text(g("Street Name")), parse.clean_text(g("Street Type"))] if x)
        out.append({
            "name": parse.clean_text(g("Child Care Site Name")),
            "licensee": parse.clean_text(g("Licensee Name")),
            "type": parse.clean_text(g("Program Type Desc")),
            "options": parse.clean_text(g("Program Option")),
            "language": parse.clean_text(g("Language of Service Desc")),
            "licence": parse.clean_text(g("Licence Number")),
            "street_number": num,
            "address": " ".join(x for x in [num, street] if x) or None,
            "city": parse.clean_text(g("City")),
            "postal_code": postal,
            "fsa": parse.fsa_of(postal),
        })
    snap = next((r[idx["Report Snapshot Date"]] for r in body if r[idx["Report Snapshot Date"]]), None)
    stats["active"] = len(out)
    return {"rows": out, "stats": dict(stats), "snapshot": snap.date().isoformat() if isinstance(snap, datetime) else str(snap)}


# ---------------------------------------------------------------------------
# 7. FSA boundaries
# ---------------------------------------------------------------------------


def load_fsa_boundaries():
    """Return a GeoDataFrame of Ontario FSAs (EPSG:4326) plus a note on where it came from."""
    import geopandas as gpd

    res = sources.FSA_RESOURCE
    try:
        path = fetch.download(res["id"], res["url"], expect="zip")
        gdf = gpd.read_file(f"zip://{path}")
        require_columns(res["id"], list(gdf.columns), ["CFSAUID", "PRUID"])
        gdf = gdf[gdf["PRUID"].astype(str) == "35"].to_crs(config.GEO_CRS)
        via = "official"
    except SourceUnavailable as e:
        gdf = _fsa_from_mirror(res)
        via = f"mirror ({e})"
    gdf = gdf[["CFSAUID", "geometry"]].rename(columns={"CFSAUID": "fsa"})
    gdf["fsa"] = gdf["fsa"].astype(str).str.upper()
    if not gdf["fsa"].str.fullmatch(r"[KLMNP]\d[A-Z]").all():
        raise SchemaChanged("fsa-boundary-2021: Ontario FSA codes did not all look like K/L/M/N/P + digit + letter")
    return gdf.reset_index(drop=True), via


def _fsa_from_mirror(res: dict):
    import geopandas as gpd

    raw = config.RAW / "fsa-boundary-2021.mirror.geojson"
    if not raw.exists():
        meta = fetch.get_json(res["mirror"], params={"f": "json"})
        names = [f["name"] for f in meta.get("fields", [])]
        require_columns(res["id"] + " (mirror)", names, ["CFSAUID", "PRUID"])
        feats = []
        offset = 0
        page = 40
        expected = fetch.get_json(res["mirror"] + "/query", params={"where": "PRUID='35'", "returnCountOnly": "true", "f": "json"}).get("count")
        while True:
            js = fetch.get_json(res["mirror"] + "/query", params={
                "where": "PRUID='35'", "outFields": "CFSAUID,PRUID", "outSR": "4326", "f": "geojson",
                # ~10 m generalization on the server: plenty for web maps and point-in-polygon checks
                "maxAllowableOffset": "0.0001", "geometryPrecision": "5",
                "resultOffset": offset, "resultRecordCount": page, "orderByFields": "CFSAUID",
            })
            if "error" in js:
                raise SourceUnavailable(f"fsa-boundary-2021 mirror query failed: {js['error']}")
            got = js.get("features", [])
            feats.extend(got)
            if not got or offset + len(got) >= (expected or 0):
                break
            offset += len(got)
        if expected and len(feats) != expected:
            raise SourceUnavailable(f"fsa-boundary-2021 mirror: got {len(feats)} of {expected} Ontario FSAs")
        if len(feats) < 500:
            raise SourceUnavailable(f"fsa-boundary-2021 mirror returned only {len(feats)} Ontario FSAs")
        raw.write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
        fetch.record(res["id"], url=res["mirror"], path=raw, note=f"Official file blocked for automated download; read from {res['mirror_landing']}")
    gdf = gpd.read_file(raw)
    return gdf.set_crs(config.GEO_CRS, allow_override=True)


# ---------------------------------------------------------------------------
# 9. Census profile by FSA (Statistics Canada Census Profile SDMX API)
# ---------------------------------------------------------------------------


def load_census(fsas: list[str]) -> dict:
    res = sources.CENSUS_RESOURCE
    cache = config.RAW / "census-2021-fsa.json"
    chars = sorted({c for _, c, _, _, _ in sources.CENSUS_FIELDS}, key=int)
    if cache.exists():
        table = json.loads(cache.read_text(encoding="utf-8"))
    else:
        table = {}
        batch = 40
        for i in range(0, len(fsas), batch):
            chunk = fsas[i:i + batch]
            key = "A5.{}.1.{}.1+4".format("+".join("2021A0011" + f for f in chunk), "+".join(chars))
            text = fetch.get_text(res["api"] + key, headers={"Accept": "application/vnd.sdmx.data+csv;version=1.0.0"})
            reader = csv.DictReader(io.StringIO(text))
            need = ["REF_AREA", "CHARACTERISTIC", "STATISTIC", "OBS_VALUE", "ALT_GEO_CODE"]
            require_columns(res["id"], reader.fieldnames or [], need)
            for row in reader:
                f = row["ALT_GEO_CODE"]
                table.setdefault(f, {})[f"{row['CHARACTERISTIC']}:{row['STATISTIC']}"] = row["OBS_VALUE"]
        cache.write_text(json.dumps(table), encoding="utf-8")
        fetch.record(res["id"], url=res["url"], path=cache)
    out = {}
    for f in fsas:
        vals = table.get(f)
        if not vals:
            continue
        rec = {}
        for key, char, stat, _label, unit in sources.CENSUS_FIELDS:
            raw = vals.get(f"{char}:{stat}")
            if raw in (None, ""):
                rec[key] = None
            else:
                x = float(raw)
                rec[key] = int(x) if unit in ("count", "dollars") else round(x, 1)
        out[f] = rec
    return {"rows": out, "stats": {"fsas_with_census": len(out), "fsas_requested": len(fsas)}}
