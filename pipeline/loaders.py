"""Loaders: one per source. Each validates its columns and fails loudly when they change."""
from __future__ import annotations

import csv
import io
import json
import re
import time
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


def sif_expected_columns(g9: str, eqao_only: bool = False) -> list[str]:
    cols = list(SIF_INFO_COLS) + ([] if eqao_only else [c[2] for c in SIF_CONTEXT_COLS])
    cols += [c for _, _, _, c, layout in EQAO_COLS if layout in (None, g9)]
    return cols


def load_sif(res: dict) -> dict:
    """Load one School Information file. Returns {'rows': {bsid: {...}}, 'stats': {...}}."""
    path = fetch.download(res["id"], res["url"], expect="xlsx")
    title, header, body = read_xlsx(path)
    if res.get("sheet_must_contain") and res["sheet_must_contain"] not in title:
        raise SchemaChanged(f"{res['id']}: sheet '{title}' does not name EQAO year {res['sheet_must_contain']} — the file may have been replaced.")
    require_columns(res["id"], header, sif_expected_columns(res["g9"], res.get("eqao_only", False)))
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
        for key, _label, col, _d in ([] if res.get("eqao_only") else SIF_CONTEXT_COLS):
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
            for attempt in range(4):
                js = fetch.get_json(res["mirror"] + "/query", params={
                    "where": "PRUID='35'", "outFields": "CFSAUID,PRUID", "outSR": "4326", "f": "geojson",
                    # ~10 m generalization on the server: plenty for web maps and point-in-polygon checks
                    "maxAllowableOffset": "0.0001", "geometryPrecision": "5",
                    "resultOffset": offset, "resultRecordCount": page, "orderByFields": "CFSAUID",
                })
                # The service has a per-minute quota for large-geometry queries (shared, it seems: a clean
                # rebuild hit it on 2026-11-26 with ~13 requests). It says "Retry after 60 sec": do that.
                if (js.get("error") or {}).get("code") == 429 and attempt < 3:
                    time.sleep(65)
                    continue
                break
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


# ---------------------------------------------------------------------------
# 12. School enrolment by grade (one file per year)
# ---------------------------------------------------------------------------

GRADE_KEYS = ["JK", "K"] + [f"G{i}" for i in range(1, 13)]


def grade_key(header: str) -> str | None:
    h = header.lower()
    if re.match(r"^(junior kindergarten|jk)\b", h):
        return "JK"
    if re.match(r"^(kindergarten|senior kindergarten|sk|k)\b", h):
        return "K"
    m = re.match(r"^(grade|gr\.?)\s*(\d{1,2})\b", h)
    return f"G{int(m.group(2))}" if m and 1 <= int(m.group(2)) <= 12 else None


def load_grade_enrolment(res: dict) -> dict:
    fmt = res.get("fmt", "txt")
    path = fetch.download(res["id"], res["url"], expect=fmt)
    if fmt == "xlsx":
        _t, header, body = read_xlsx(path)
        body = [["" if v is None else v for v in r] for r in body]
    else:
        header, body = read_pipe_txt(path)
    header = [h or "" for h in header]
    require_columns(res["id"], header, ["School Number"])
    gcols = {}
    for i, h in enumerate(header):
        k = grade_key(h)
        if k and k not in gcols:
            gcols[k] = i
    if set(gcols) != set(GRADE_KEYS):
        raise SchemaChanged(f"{res['id']}: expected grade columns JK, K, Grade 1-12; found {sorted(gcols)} in {header}")
    si = header.index("School Number")
    out, stats = {}, Counter()
    for r in body:
        if si >= len(r):
            continue
        bsid = school_number(r[si])
        if not bsid or not re.fullmatch(r"[0-9A-Z]{6}", bsid):
            stats["skipped_rows"] += 1
            continue
        grades, codes = {}, {}
        for k, i in gcols.items():
            raw = r[i] if i < len(r) else None
            v, code = parse.parse_count(raw, context=f"{res['id']} {bsid} {k}")
            if code == "BLANK":
                continue  # grade not offered
            grades[k] = v
            if code:
                codes[k] = code
                stats[f"code_{code}"] += 1
        if grades:
            out[bsid] = {"grades": grades, "codes": codes}
    stats["schools"] = len(out)
    return {"rows": out, "stats": dict(stats)}


# ---------------------------------------------------------------------------
# 13. Elementary class size (one row per class; keyed by board and school NAME)
# ---------------------------------------------------------------------------

CS_COLS = {
    "year": r"^(schoolyear|academic year)$",
    "board": r"^(boardname|board_long_name)$",
    "school": r"^(schoolname|school_long_name)$",
    "JK": r"^jk$", "K": r"^k$", "G1": r"^g1$", "G2": r"^g2$", "G3": r"^g3$",
    "G48": r"^(g4to8|gr4to8|g4g8)$",
}


def _cs_year(v) -> str:
    s = str(v).strip()
    m = re.match(r"^(\d{4})-(\d{2,4})$", s)
    if not m:
        raise SchemaChanged(f"class size: unreadable school year {v!r}")
    return f"{m.group(1)}-{m.group(2)[-2:]}"


def load_class_size(res: dict) -> dict:
    """Aggregate class lists into per-school, per-year figures (keys are board + school names)."""
    path = fetch.download(res["id"], res["url"], expect="xlsx")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    agg: dict[tuple, dict] = {}
    stats = Counter()
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        try:
            header = [norm_header(h).lower() if h is not None else "" for h in next(rows)]
        except StopIteration:
            continue
        idx = {}
        for key, pat in CS_COLS.items():
            hits = [i for i, h in enumerate(header) if re.match(pat, h)]
            if hits:
                idx[key] = hits[0]
        if "year" not in idx:
            stats["sheets_skipped_other_language"] += 1  # the French copy of the same data
            continue
        missing = [k for k in CS_COLS if k not in idx]
        if missing:
            raise SchemaChanged(f"{res['id']} sheet {ws.title!r}: class size columns missing {missing}; found {header}")
        for r in rows:
            if r is None or r[idx["school"]] in (None, ""):
                continue
            counts = {}
            bad = False
            for k in ("JK", "K", "G1", "G2", "G3", "G48"):
                v = r[idx[k]]
                if v in (None, ""):
                    v = 0
                if isinstance(v, str):
                    if v.strip().isdigit():
                        v = int(v.strip())
                    else:
                        bad = True
                        break
                counts[k] = int(v)
            if bad:
                stats["classes_with_withheld_counts"] += 1
                continue
            size = sum(counts.values())
            if size <= 0:
                continue
            year = _cs_year(r[idx["year"]])
            key = (year, str(r[idx["board"]]).strip(), str(r[idx["school"]]).strip())
            a = agg.setdefault(key, {"classes": 0, "students": 0, "primary": [], "kinder": [], "junior": [], "combined": 0})
            a["classes"] += 1
            a["students"] += size
            groups = {"k": counts["JK"] + counts["K"] > 0, "p": counts["G1"] + counts["G2"] + counts["G3"] > 0, "j": counts["G48"] > 0}
            if sum(groups.values()) > 1:
                a["combined"] += 1
            elif groups["p"]:
                a["primary"].append(size)
            elif groups["k"]:
                a["kinder"].append(size)
            else:
                a["junior"].append(size)
            stats[f"classes_{year}"] += 1
    wb.close()
    stats["school_years"] = len(agg)
    return {"rows": agg, "stats": dict(stats)}


# ---------------------------------------------------------------------------
# 14. French as a Second Language program offerings
# ---------------------------------------------------------------------------
FSL_COLS = ["Board Number", "School Number", "School Name", "FSL Core", "FSL Extended", "FSL Immersion"]
FSL_FLAGS = (("core", "FSL Core"), ("extended", "FSL Extended"), ("immersion", "FSL Immersion"))


def load_fsl(res: dict) -> dict:
    """bsid -> {core, extended, immersion} (True/False). English-language boards only."""
    path = fetch.download(res["id"], res["url"], expect="txt")
    header, body = read_pipe_txt(path)
    require_columns(res["id"], header, FSL_COLS)
    idx = {h: i for i, h in enumerate(header)}
    rows, stats = {}, Counter()
    for r in body:
        bsid = school_number(r[idx["School Number"]])
        if not bsid:
            stats["no_school_number"] += 1
            continue
        flags = {}
        for key, col in FSL_FLAGS:
            v = (r[idx[col]] or "").strip().upper()
            if v not in ("YES", "NO"):
                raise SchemaChanged(f"{res['id']}: '{col}' should be YES or NO, found {v!r} for school {bsid}.")
            flags[key] = v == "YES"
            stats[f"{key}_yes"] += flags[key]
        rows[bsid] = flags
    stats["schools"] = len(rows)
    return {"rows": rows, "stats": dict(stats)}


# ---------------------------------------------------------------------------
# 15. Specialist High Skills Major programs
# ---------------------------------------------------------------------------
SHSM_COLS = ["Board_Name", "Sector", "School_Name", "MIDENT", "Language"]


def load_shsm(res: dict) -> dict:
    """bsid -> [{sector, years, language}] where ``years`` is how many years the program has run."""
    path = fetch.download(res["id"], res["url"], expect="csv")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    table = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    header = [norm_header(h) for h in table[0]]
    age_col = next((h for h in header if h.startswith("Age_of_Program")), None)
    require_columns(res["id"], header, SHSM_COLS + [age_col or "Age_of_Program_in_<school year>"])
    idx = {h: i for i, h in enumerate(header)}
    rows, stats = {}, Counter()
    for r in table[1:]:
        bsid = school_number(r[idx["MIDENT"]])
        sector = parse.clean_text(r[idx["Sector"]])
        if not bsid or not sector:
            stats["incomplete_rows"] += 1
            continue
        age = (r[idx[age_col]] or "").strip()
        rows.setdefault(bsid, []).append({
            "sector": sector,
            "years": int(age) if age.isdigit() else None,
            "language": parse.clean_text(r[idx["Language"]]),
        })
        stats["programs"] += 1
    for progs in rows.values():
        progs.sort(key=lambda p: p["sector"])
    stats["schools"] = len(rows)
    return {"rows": rows, "stats": dict(stats)}


# ---------------------------------------------------------------------------
# 3. EQAO open data (achievement results, one ZIP per assessment and year)
# ---------------------------------------------------------------------------
EQAO_OD_ID = ["OrgType", "Language", "BoardMident", "SchoolMident", "SchoolName", "Suppressed"]
EQAO_SUBJECTS = (("R", "reading", "Read"), ("W", "writing", "Write"), ("M", "math", "Math"))
EQAO_LANG = {"en": "English", "fr": "French"}


def _level_pct(v: str | None):
    """Level shares: '45%' -> 45, '<1 %' -> '<1' (shown as written), codes -> None."""
    s = (v or "").strip().replace(" ", "")
    if s.startswith("<1"):
        return "<1"
    m = re.fullmatch(r"(\d+(?:\.\d+)?)%", s)
    return (int(float(m.group(1))) if float(m.group(1)).is_integer() else float(m.group(1))) if m else None


def load_eqao_open(res: dict) -> dict:
    """bsid -> {board, language, results: {assessment: {v, code, levels, participation}}}.

    ``v`` is the share of students at or above the provincial standard (levels 3 and 4; for the
    OSSLT, first-time eligible students who were successful), the same figure the Ministry's
    school file publishes. Codes (N/R, N/D and the French S. R. / A/D) are kept, never 0.
    """
    path = fetch.download(res["id"], res["url"], expect="zip")
    with zipfile.ZipFile(path) as z:
        name = next((n for n in z.namelist() if n.endswith(res["member"])), None)
        if not name:
            raise SchemaChanged(f"{res['id']}: {res['member']} not found in the ZIP (found {z.namelist()}).")
        text = z.read(name).decode("utf-8-sig")
    table = list(csv.reader(io.StringIO(text)))
    header = [norm_header(h) for h in table[0]]
    kind = res["kind"]
    if kind == "g36":
        specs = [(f"g{res['grade']}-{sub}", f"pctOverall{k}_L34", [f"pctOverall{k}_L{n}" for n in (4, 3, 2, 1)], f"pctFullyParticipating_{p}")
                 for k, sub, p in EQAO_SUBJECTS]
    elif kind == "g9":
        specs = [("g9-math", "pctOverallM_L34", [f"pctOverallM_L{n}" for n in (4, 3, 2, 1)], "pctFullyParticipating")]
    elif kind == "osslt":
        specs = [("osslt", "pctSuccessful", None, "pctFullyParticipating")]
    else:  # pragma: no cover
        raise ValueError(kind)
    expected = list(EQAO_OD_ID) + [c for _a, v, lv, p in specs for c in [v, p, *(lv or [])]]
    require_columns(res["id"], header, expected + (["Eligibility"] if kind == "osslt" else []))
    idx = {h: i for i, h in enumerate(header)}
    rows, stats = {}, Counter()
    for r in table[1:]:
        if len(r) < len(header) or r[idx["OrgType"]] != "S":
            continue
        if kind == "osslt" and r[idx["Eligibility"]].strip() != "1":
            continue  # first-time eligible students only, as in the Ministry's file
        bsid = school_number(r[idx["SchoolMident"]])
        if not bsid:
            continue
        results = {}
        for aid, vcol, lcols, pcol in specs:
            v, code = parse.parse_pct(r[idx[vcol]], context=f"{res['id']} {bsid} {vcol}")
            if code == "BLANK":
                continue
            results[aid] = {
                "v": v, "code": code,
                "levels": [_level_pct(r[idx[c]]) for c in lcols] if (lcols and v is not None) else None,
                "participation": _level_pct(r[idx[pcol]]) if v is not None else None,
            }
            stats["values" if v is not None else f"code_{code}"] += 1
        bn = r[idx["BoardMident"]].strip()
        rows[bsid] = {"board": f"B{bn}" if bn and bn.isdigit() else bn or None,
                      "language": EQAO_LANG.get(r[idx["Language"]].strip().lower()), "results": results}
    stats["schools"] = len(rows)
    return {"rows": rows, "stats": dict(stats)}


# ---------------------------------------------------------------------------
# 21. EQAO student questionnaire results (one ZIP of several CSVs per assessment and year)
# ---------------------------------------------------------------------------
# A small, deliberate set of questions (key, field stem, plain label). The exact wording and the answer
# choices are read from EQAO's field definitions every run, never typed here. Grades 3 and 6 report the
# same answers against three bases (students who fully took part in reading, writing or math); we use
# the math base for math questions and the reading base for the rest. Grade 9 (math) and the OSSLT
# (literacy, first-time eligible students) have one base. Home language and home technology questions
# are left out on purpose: they describe families, not the school.
SQ_ITEMS = {
    "g36": [("like_read", "R", "Interest_LikeRead", "Like to read"),
            ("good_reader", "R", "Confidence_GoodReader", "See themselves as good readers"),
            ("like_math", "M", "Interest_LikeMath", "Like math"),
            ("good_math", "M", "Confidence_GoodAtMath", "See themselves as good at math"),
            ("keep_trying", "R", "Persevere_KeepTrying", "Keep trying when something is difficult"),
            ("feel_prepared", "R", "Persevere_FeelPrepared", "Feel prepared for next year"),
            ("group_work", "R", "Group_WorkWell", "Work well in a group")],
    "g9": [("like_math", "", "Interest_LikeMath", "Like math"),
           ("good_math", "", "Confidence_GoodAtMath", "See themselves as good at math"),
           ("keep_trying", "", "Persevere_KeepTrying", "Keep trying when something is difficult"),
           ("feel_prepared", "", "Persevere_FeelPrepared", "Feel prepared for next semester or year"),
           ("group_work", "", "Group_WorkWell", "Work well in a group")],
    "osslt": [("like_read", "", "Interest_LikeRead", "Like to read"),
              ("good_reader", "", "Confidence_GoodReader", "See themselves as good readers"),
              ("keep_trying", "", "Persevere_KeepTrying", "Keep trying when something is difficult"),
              ("feel_prepared", "", "Persevere_FeelPrepared", "Feel prepared for next semester or year"),
              ("group_work", "", "Group_WorkWell", "Work well in a group")],
}
SQ_BASE_LABEL = {"R": "who fully took part in the reading assessment", "M": "who fully took part in the math assessment",
                 "": "who fully took part in the assessment"}
SQ_SCALES = {"g36": (1, 2, 3), "g9": (1, 2, 3, 4, 5), "osslt": (1, 2, 3, 4, 5)}
SQ_AGREE = {"g36": (3,), "g9": (4, 5), "osslt": (4, 5)}  # "Yes, I agree" / "Somewhat" + "Strongly agree"


def _sq_field(base: str, stem: str) -> str:
    return f"{base}_{stem}" if base else stem


def load_eqao_sq_definitions(res: dict, items: list | None = None, strict: bool = True) -> dict:
    """field stem -> {question, options: {category: label}} from EQAO's field-definitions workbook.
    strict=False (earlier years): a question missing from the definitions is left out instead of stopping the build."""
    path = fetch.download(res["id"] + "-defs", res["definitions"], expect="xlsx")
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = next((w for w in wb.worksheets if "SQ" in w.title), None)
    if ws is None:
        raise SchemaChanged(f"{res['id']}: no questionnaire sheet in the field definitions ({[w.title for w in wb.worksheets]})")
    name_col = def_col = None
    defs: dict[str, str] = {}
    for r in ws.iter_rows(values_only=True):
        cells = [norm_header(x) if x is not None else "" for x in r]
        if name_col is None:
            label = next((x for x in ("Definition", "Description") if x in cells), None)  # the OSSLT workbook says "Description"
            if "Field Name" in cells and label:
                name_col, def_col = cells.index("Field Name"), cells.index(label)
            continue
        if len(cells) > def_col and cells[name_col].startswith("cnt"):
            defs[cells[name_col]] = cells[def_col]
    wb.close()
    out = {}
    for _key, base, stem, _label in (items if items is not None else SQ_ITEMS[res["kind"]]):
        field = _sq_field(base, stem)
        cats = {int(m.group(1)): d for f, d in defs.items() if (m := re.fullmatch(rf"cnt{re.escape(field)}(\d)", f))}
        if not cats or 9 not in cats:
            if not strict:
                continue
            raise SchemaChanged(f"{res['id']}: question {field!r} is not in EQAO's field definitions any more; check the questionnaire")
        texts = [cats[c] for c in sorted(cats)]
        common = texts[0]
        for t in texts[1:]:
            while not t.startswith(common):
                common = common[:-1]
        cut = common[: common.rfind(", ") + 2]  # "Number of fully participating students in Reading, I like to read, "
        question = cut.rstrip(", ").split(", ", 1)[1] if ", " in cut.rstrip(", ") else cut
        out[field] = {"question": question.strip(), "options": {c: cats[c][len(cut):].strip() for c in sorted(cats)}}
    return out


def _sq_int(v: str):
    s = (v or "").strip()
    return int(s) if s.isdigit() else None


def load_eqao_sq(res: dict, strict: bool = True) -> dict:
    """Student questionnaire answers for the questions in SQ_ITEMS, for schools, boards and Ontario.

    Returns {"schools": {bsid: org}, "boards": {"B66150": org}, "province": {"English": org, "French": org},
    "questions": {key: {...}}, "stats": {...}}. Each org has, per question, the count and EQAO's published
    percentage for every answer (including "Response missing"), the number of students (the sum of every
    answer, EQAO's denominator) and, when EQAO withholds the figures, the code it shows instead (N/R,
    S. R., N/D) and no numbers. Nothing is filled in or inferred.
    """
    kind = res["kind"]
    path = fetch.download(res["id"], res["url"], expect="zip")
    merged: dict[tuple, dict] = {}
    with zipfile.ZipFile(path) as z:
        members = [n for n in z.namelist() if n.lower().endswith(".csv") and (kind != "osslt" or "_FTE_" in n)]
        if not members:
            raise SchemaChanged(f"{res['id']}: no questionnaire CSVs in the ZIP ({z.namelist()})")
        for name in members:
            raw = z.read(name)
            try:
                text = raw.decode("utf-8-sig")
            except UnicodeDecodeError:  # some earlier years were saved as Windows-1252 (accented French names)
                text = raw.decode("cp1252")
            rd = csv.DictReader(io.StringIO(text))
            for r in rd:
                if "Eligibility" in r and (r["Eligibility"] or "").strip() not in ("1", ""):
                    continue
                # the OSSLT files have no OrgID: board and school numbers identify every row
                key = (r["OrgType"], r.get("OrgID") or "", r["BoardMident"], r["SchoolMident"], r["Language"], r.get("Administration") or "")
                merged.setdefault(key, {}).update(r)
    scale, agree = SQ_SCALES[kind], SQ_AGREE[kind]
    columns = set().union(*(r.keys() for r in merged.values()))
    # Grades 3 and 6 share one questionnaire design, but not every question is asked in both grades
    # (Grade 3 isn't asked about feeling prepared for next year). A question is used when its answers
    # are in the file; the ones that aren't are recorded, never filled in.
    asked = [it for it in SQ_ITEMS[kind] if f"cnt{_sq_field(it[1], it[2])}1" in columns]
    not_asked = [it[0] for it in SQ_ITEMS[kind] if it not in asked]
    if len(asked) < 3:
        raise SchemaChanged(f"{res['id']}: only {len(asked)} of the expected questions are in the file; check the questionnaire")
    needed = [f"{p}{_sq_field(b, st)}{c}" for _k, b, st, _l in asked for c in (*scale, 9) for p in ("cnt", "pct")]
    require_columns(res["id"], sorted(columns), ["OrgType", "Language", "BoardMident", "SchoolMident", "Suppressed"] + needed)
    defs = load_eqao_sq_definitions(res, asked, strict=strict)
    if not strict:  # earlier years: only questions both in the file and in that year's definitions
        asked = [it for it in asked if _sq_field(it[1], it[2]) in defs]
    out = {"schools": {}, "boards": {}, "province": {}, "stats": Counter(), "not_asked": not_asked}
    for (otype, _oid, _bn, _sn, lang, _adm), r in merged.items():
        withheld = (r.get("Suppressed") or "").strip() == "1"
        items = {}
        for key, base, stem, _label in asked:
            field = _sq_field(base, stem)
            counts = [_sq_int(r.get(f"cnt{field}{c}")) for c in (*scale, 9)]
            raw_pct = [r.get(f"pct{field}{c}") for c in (*scale, 9)]
            if withheld or any(c is None for c in counts):
                # the code EQAO printed (N/R, S. R., N/D, A/D); a cell missing from every file reads as "no data"
                codes = [parse.code_of(v) for v in [r.get(f"cnt{field}{scale[0]}"), *raw_pct]]
                code = next((c for c in codes if c and c != "BLANK"), None) or ("N/R" if withheld else "N/D")
                items[key] = {"code": code, **parse.flags(code)}
                out["stats"][f"code_{code}"] += 1
                continue
            n = sum(counts)
            if n == 0:
                items[key] = {"code": "N/D", **parse.flags("N/D")}
                continue
            pct = [_level_pct(v) for v in raw_pct]
            agree_n = sum(counts[scale.index(c)] for c in agree)
            items[key] = {
                "n": n, "counts": counts, "pct": pct,
                # one published percentage for a 3-point scale; two categories added up (from the counts) for a 5-point one
                "agree_pct": pct[scale.index(agree[0])] if len(agree) == 1 else round(100 * agree_n / n),
                "agree_n": agree_n, "agree_derived": len(agree) > 1,
                "missing_pct": pct[-1],
            }
            out["stats"]["values"] += 1
        org = {"withheld": withheld, "respondents": _sq_int(r.get("cntSQRespondents")), "items": items}
        lang_name = EQAO_LANG.get((lang or "").strip().lower())
        if otype == "S":
            bsid = school_number(r["SchoolMident"])
            if bsid:
                out["schools"][bsid] = org
        elif otype == "B":
            bn = (r["BoardMident"] or "").strip()
            out["boards"][f"B{bn}" if bn.isdigit() else bn] = org
        elif otype == "P" and lang_name:
            out["province"][lang_name] = org
    out["questions"] = {}
    for key, base, stem, label in asked:
        d = defs[_sq_field(base, stem)]
        out["questions"][key] = {"key": key, "label": label, "question": d["question"], "base": SQ_BASE_LABEL[base],
                                 "options": [d["options"][c] for c in (*scale, 9)], "agree": [d["options"][c] for c in agree],
                                 "field": _sq_field(base, stem)}
    out["stats"]["schools"] = len(out["schools"])
    out["stats"] = dict(out["stats"])
    return out


# ---------------------------------------------------------------------------
# 16. Suspension and expulsion rates by board (one wide sheet: two columns per school year)
# ---------------------------------------------------------------------------
def _rate_pct(v, context: str):
    """Rates are 0-1 fractions in these files; codes (<10, blank) are kept."""
    if v is None or (isinstance(v, str) and not v.strip()):
        return None, "BLANK"
    if isinstance(v, (int, float)):
        if not 0 <= v <= 1:
            raise SchemaChanged(f"{context}: rate {v!r} is not a 0-1 fraction")
        return round(v * 100, 2), None
    return parse.parse_pct(v, context=context, numeric="fraction")


def load_board_rates(res: dict, *, what: str) -> dict:
    """{'boards': {Bnumber: {year: {count, count_code, rate, rate_code}}}, 'province': {...}, 'years': [...]}."""
    path = fetch.download(res["id"], res["url"], expect="xlsx")
    _t, header, body = read_xlsx(path)
    require_columns(res["id"], header, ["Board Number", "Board Name"])
    years = []
    for h in header:
        m = re.match(r"^(\d{4})-(\d{4}) .*Rate$", h or "")
        if m:
            years.append(f"{m.group(1)}-{m.group(2)[2:]}")
    if not years:
        raise SchemaChanged(f"{res['id']}: no '<year> ... Rate' columns found (found {header[:6]}).")
    idx = {h: i for i, h in enumerate(header) if h}
    noun = "Suspended" if what == "suspension" else "Expelled"
    out, province = {}, {}
    for r in body:
        bn, name = r[idx["Board Number"]], parse.clean_text(r[idx["Board Name"]])
        series = {}
        for y in years:
            full = f"{y[:4]}-{int(y[:4]) + 1}"
            count_col = next((h for h in idx if h.startswith(full) and noun in h), None)
            rate_col = next((h for h in idx if h.startswith(full) and h.endswith("Rate")), None)
            if not count_col or not rate_col:
                raise SchemaChanged(f"{res['id']}: missing the {full} count or rate column.")
            c, cc = parse.parse_count(r[idx[count_col]], context=f"{res['id']} {bn} {count_col}")
            v, vc = _rate_pct(r[idx[rate_col]], f"{res['id']} {bn} {rate_col}")
            if cc == "BLANK" and vc == "BLANK":
                continue
            series[y] = {"count": c, "count_code": cc, "rate": v, "rate_code": vc}
        if bn:
            out[str(bn).strip()] = series
        elif name and "ontario" in name.lower():
            province = series
    if not province:
        raise SchemaChanged(f"{res['id']}: the 'Province of Ontario' total row is missing.")
    return {"boards": out, "province": province, "years": years, "stats": {"boards": len(out)}}


# ---------------------------------------------------------------------------
# 17. Board financial statements (EFIS): spending per student
# ---------------------------------------------------------------------------
EFIS_CELLS = {
    "total": "SC10_00529C",           # Sch. 10 total expenses
    "instruction": "SC10_00573C",     # classroom teachers, assistants, supplies, principals, guidance...
    "administration": "SC10_00579C",  # trustees, director, board administration
    "transportation": "SC10_00585C",  # student transportation
    "accommodation": "SC10_00596C",   # school operations, maintenance, renewal, amortization of buildings
    "ade": "SC13_00165C",             # Sch. 13-3 total day-school average daily enrolment
}


def load_finance(res: dict) -> dict:
    path = fetch.download(res["id"], res["url"], expect="csv")
    text = path.read_bytes().decode("utf-8-sig")
    reader = csv.reader(io.StringIO(text))
    header = [norm_header(h) for h in next(reader)]
    require_columns(res["id"], header, ["Cell Name:", "Area:", "Year:"])
    board_cols = header[8:]
    unknown = [b for b in board_cols if b and b not in sources.EFIS_BOARDS]
    if unknown:
        raise SchemaChanged(f"{res['id']}: board columns not in sources.EFIS_BOARDS: {unknown}. Map them to Ministry board numbers.")
    wanted = {v: k for k, v in EFIS_CELLS.items()}
    found = {}
    for r in reader:
        if r and r[0] in wanted:
            found[wanted[r[0]]] = r[8:]
    missing = sorted(set(EFIS_CELLS) - set(found))
    if missing:
        raise SchemaChanged(f"{res['id']}: cells {[EFIS_CELLS[m] for m in missing]} not found; the EFIS layout changed (check the Cell Name Reference Book).")
    boards = {}
    for i, name in enumerate(board_cols):
        if not name:
            continue

        def num(key, i=i):
            v = (found[key][i] or "").replace(",", "").strip()
            try:
                return float(v)
            except ValueError:
                return None
        ade, total = num("ade"), num("total")
        if not ade or not total:
            continue
        parts = {k: num(k) for k in ("instruction", "administration", "transportation", "accommodation")}
        other = total - sum(v for v in parts.values() if v)
        boards[sources.EFIS_BOARDS[name]] = {
            "ade": round(ade), "total": round(total), "per_student": round(total / ade),
            "parts": {**{k: round(v / ade) for k, v in parts.items() if v is not None}, "other": round(other / ade)},
        }
    return {"boards": boards, "stats": {"boards": len(boards)}}


# ---------------------------------------------------------------------------
# 18. French as a Second Language enrolment by board
# ---------------------------------------------------------------------------
FSL_ENROL_COLS = ["Board Number", "Board Name", "FSL-Core Total", "FSL-Extended Total", "FSL-Immersion Total", "Overall Total"]


def load_fsl_enrolment(res: dict) -> dict:
    path = fetch.download(res["id"], res["url"], expect="txt")
    header, body = read_pipe_txt(path)
    require_columns(res["id"], header, FSL_ENROL_COLS)
    idx = {h: i for i, h in enumerate(header)}
    out = {}
    for r in body:
        bn = (r[idx["Board Number"]] or "").strip()
        if not re.fullmatch(r"B\d{5}", bn):
            continue  # totals and notes

        def n(col, r=r, bn=bn):
            v, code = parse.parse_count(r[idx[col]], context=f"{res['id']} {bn} {col}")
            return 0 if code == "BLANK" else v
        out[bn] = {"core": n("FSL-Core Total"), "extended": n("FSL-Extended Total"), "immersion": n("FSL-Immersion Total"), "total": n("Overall Total")}
    return {"boards": out, "stats": {"boards": len(out)}}


# ---------------------------------------------------------------------------
# 19. EarlyON Child and Family Centres
# ---------------------------------------------------------------------------
EARLYON_COLS = ["Service System Managers", "Name of Location", "Street Address", "Postal Code", "Municipality/City/Town"]


def load_earlyon(res: dict) -> dict:
    path = fetch.download(res["id"], res["url"], expect="xlsx")
    _t, header, body = read_xlsx(path)
    require_columns(res["id"], header, EARLYON_COLS)
    idx = {h: i for i, h in enumerate(header) if h}
    rows = []
    for r in body:
        name = parse.clean_text(r[idx["Name of Location"]])
        postal = parse.norm_postal(r[idx["Postal Code"]])
        if not name:
            continue
        rows.append({"name": name, "address": parse.clean_text(r[idx["Street Address"]]),
                     "city": parse.clean_text(r[idx["Municipality/City/Town"]]),
                     "postal_code": postal, "fsa": parse.fsa_of(postal)})
    return {"rows": rows, "stats": {"sites": len(rows), "no_postal": sum(1 for x in rows if not x["fsa"])}}


# ---------------------------------------------------------------------------
# 20. Student Nutrition Program sites (December 2017)
# ---------------------------------------------------------------------------
NUTRITION_COLS = ["School_Name", "School_ID", "Breakfast", "Lunch", "Snack"]
MEALS = ["Breakfast", "Lunch", "Snack"]


def load_nutrition(res: dict) -> dict:
    path = fetch.download(res["id"], res["url"], expect="csv")
    raw = path.read_bytes()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw.decode("cp1252")
    table = [r for r in csv.reader(io.StringIO(text)) if any(c.strip() for c in r)]
    header = [norm_header(h) for h in table[0]]
    require_columns(res["id"], header, NUTRITION_COLS)
    idx = {h: i for i, h in enumerate(header)}
    out, stats = {}, Counter()
    for r in table[1:]:
        bsid = school_number(r[idx["School_ID"]])
        if not bsid or not bsid.isdigit():
            stats["no_school_number"] += 1
            continue
        meals = [m for m in MEALS if (r[idx[m]] or "").strip().lower() in ("yes", "y", "oui")]
        if meals:
            out[bsid] = sorted(set(out.get(bsid, [])) | set(meals), key=MEALS.index)
    stats["schools"] = len(out)
    return {"rows": out, "stats": dict(stats)}
