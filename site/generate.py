"""Static site generator: site/data (pipeline output) + templates -> site/dist.

    python site/generate.py

Environment (all optional):
    SITE_URL         canonical origin, default https://ontarioschoolfinder.ca
    CONTACT_EMAIL    contact address shown on /about/, /corrections/ and in the footer (set it in your environment)
    CORRECTIONS_URL  a public form or issue tracker for corrections, default the repo's "Data correction" issue form
    REPO_URL         the public source repository, linked in the footer
    OPERATOR         who runs the site, for /about/ "Who runs it"
    SUPPORT_URL      optional tip jar, linked from the footer and /about/#support; default Buy Me a Coffee, "off" hides it
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import shutil
import statistics
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charts  # noqa: E402
import family  # noqa: E402


SERIES_RE = re.compile(r"^(.*?)\s*\(([^()]*)\)$")


def source_series(sources: list[dict]) -> list[dict]:
    """Sources grouped by publisher, then by dataset. A dataset published once a year (enrolment
    2011-12 ... 2024-25) becomes one row with a link per year instead of fourteen near-identical rows."""
    pubs: dict[str, dict] = {}
    for src in sources:
        m = SERIES_RE.match(src["title"])
        stem, label = (m.group(1), m.group(2)) if m else (src["title"], "")
        p = pubs.setdefault(src["publisher"], {"publisher": src["publisher"], "sets": {}, "licences": {}})
        p["licences"][src["licence"]] = src.get("licence_url")
        p["sets"].setdefault(stem, []).append({**src, "label": label})
    out = []
    for p in sorted(pubs.values(), key=lambda p: p["publisher"]):
        sets = []
        for stem, items in p["sets"].items():
            items = sorted(items, key=lambda x: x["label"])
            retrieved = {x.get("retrieved") for x in items}
            sets.append({"stem": stem, "items": items, "retrieved": retrieved.pop() if len(retrieved) == 1 else None})
        sets.sort(key=lambda s: (len(s["items"]) > 1, s["stem"]))  # single files first, then yearly series
        lic = list(p["licences"].items())
        out.append({"publisher": p["publisher"], "licence": lic[0] if len(lic) == 1 else None, "sets": sets})
    return out


def plain(text: str) -> str:
    """Accent-free, case-free sort key: "École Sainte-Anne" sorts with the E schools."""
    return "".join(c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)).casefold()


DATA = HERE / "data"
DIST = HERE / "dist"
STATIC = HERE / "static"
SITE_URL = os.environ.get("SITE_URL", "https://ontarioschoolfinder.ca").rstrip("/")
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "").strip()  # set by the site owner; never stored in the repo
REPO_URL = (os.environ.get("REPO_URL", "").strip() or "https://github.com/hackmods/ontario-school-finder").rstrip("/")
# GitHub issue form; corrections.js adds the school's page and a title when the visitor came from a school
CORRECTIONS_URL = os.environ.get("CORRECTIONS_URL", "").strip() or f"{REPO_URL}/issues/new?template=data-correction.yml"
# An optional tip jar: a plain link (no widget, no third-party script), so the privacy promise holds
_support = os.environ.get("SUPPORT_URL", "").strip()
SUPPORT_URL = "" if _support.lower() == "off" else (_support or "https://buymeacoffee.com/ryanmorris")
OPERATOR = os.environ.get("OPERATOR", "").strip() or "Ontario School Finder is built and run by Ryan Morris, independently, for Ontario families."

ASSESSMENT_ORDER = ["g3-reading", "g3-writing", "g3-math", "g6-reading", "g6-writing", "g6-math", "g9-math", "g9-math-academic", "g9-math-applied", "osslt"]
SYSTEM_ORDER = ["english-public", "english-catholic", "french-public", "french-catholic", "other"]
REGION_LABEL = {"K": "Eastern Ontario", "L": "Central Ontario", "M": "Toronto", "N": "Southwestern Ontario", "P": "Northern Ontario"}
SBPR_ROWS = ["g6_reading", "g6_reading_change", "osslt", "osslt_change", "credits_g10", "credits_g10_change", "credits_g11", "credits_g11_change",
             "grad_4yr", "grad_4yr_change", "grad_5yr", "grad_5yr_change"]


def load(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))


def human_date(iso: str | None) -> str:
    if not iso:
        return "unknown"
    d = date.fromisoformat(iso[:10])
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def clip(text: str, limit: int) -> str:
    """Shorten to at most `limit` characters at a word boundary, ending with an ellipsis."""
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rsplit(" ", 1)[0].rstrip(" ,.;:—-")
    return cut + "…"


def short_hash(*parts: bytes) -> str:
    h = hashlib.sha256()
    for p in parts:
        h.update(p)
    return h.hexdigest()[:10]


class Assets:
    """Versioned URLs (?v=) for static files, which nginx lets browsers keep for a year.

    Scripts are ES modules that import each other, so they all share one version: a hash of every
    script and the vendored map library. The import specifiers inside them get the same ?v= at
    copy time (`version_scripts`), so a deploy that changes any script changes every script URL and
    no browser can pair a new page with an old cached module.
    """

    def __init__(self, root: Path):
        self.root = root
        self.cache: dict[str, str] = {}
        code = sorted(p for p in [*(root / "js").glob("*.js"), *(root / "vendor").rglob("*")] if p.is_file())
        self.js_v = short_hash(*(p.relative_to(root).as_posix().encode() + p.read_bytes() for p in code))

    def __call__(self, rel: str) -> str:
        if rel not in self.cache:
            h = self.js_v if rel.startswith("js/") else short_hash((self.root / rel).read_bytes())
            self.cache[rel] = f"/static/{rel}?v={h}"
        return self.cache[rel]


# `from "./x.js"`, `import "./x.js"`, `import("./x.js")`, and the vendored map library's URLs in maps.js
_IMPORT_RE = re.compile(r"""((?:\bfrom|\bimport)\s*\(?\s*)(["'])(\./[\w.-]+\.js)\2""")
_VENDOR_RE = re.compile(r"""(["'])(/static/vendor/[^"'?]+)\1""")


def maplibre_dir() -> str:
    """The vendored MapLibre folder, `vendor/maplibre/<version>` (scripts/vendor.mjs keeps exactly one),
    checked against the path site/static/js/maps.js loads so an upgrade can't ship half done."""
    root = STATIC / "vendor" / "maplibre"
    found = sorted(d.name for d in root.iterdir() if d.is_dir()) if root.exists() else []
    if len(found) != 1:
        raise SystemExit(f"expected one MapLibre version in {root}, found {found or 'none'}: run `npm run vendor`")
    rel = f"vendor/maplibre/{found[0]}"
    if f"/static/{rel}/maplibre-gl.mjs" not in (STATIC / "js" / "maps.js").read_text(encoding="utf-8"):
        raise SystemExit(f"site/static/js/maps.js doesn't load /static/{rel}/maplibre-gl.mjs: update LIB there")
    return rel


def version_scripts(js_dir: Path, v: str) -> int:
    """Give every relative import and vendor URL in the copied scripts the build's script version."""
    n = 0
    for p in js_dir.glob("*.js"):
        src = p.read_text(encoding="utf-8")
        out, k1 = _IMPORT_RE.subn(lambda m: f"{m[1]}{m[2]}{m[3]}?v={v}{m[2]}", src)
        for m in _VENDOR_RE.finditer(out):
            if not (js_dir.parent / m[2].removeprefix("/static/")).is_file():
                raise SystemExit(f"{p.name} refers to {m[2]}, which isn't in site/static")
        out, k2 = _VENDOR_RE.subn(lambda m: f"{m[1]}{m[2]}?v={v}{m[1]}", out)
        if k1 or k2:
            p.write_text(out, encoding="utf-8")
            n += k1 + k2
    return n


def pct(v) -> str:
    if v is None:
        return "—"
    return f"{v}%" if isinstance(v, str) else f"{v:g}%"  # EQAO prints shares under 0.5% as "<1%"


def median(vals):
    vals = [v for v in vals if v is not None]
    return round(statistics.median(vals), 1) if vals else None


class Site:
    def __init__(self):
        t0 = time.time()
        self.meta = load(DATA / "meta.json")
        self.meta["data_updated_human"] = human_date(self.meta.get("data_updated"))
        self.sources = load(DATA / "sources.json")
        self.index = load(DATA / "schools-index.json")
        self.boards_index = load(DATA / "boards-index.json")
        self.fsa_index = load(DATA / "fsa-index.json")
        self.schools = {p.stem: load(p) for p in (DATA / "schools").glob("*.json")}
        self.boards = {p.stem: load(p) for p in (DATA / "boards").glob("*.json")}
        self.fsas = {p.stem: load(p) for p in (DATA / "fsa").glob("*.json")}
        print(f"loaded {len(self.schools)} schools, {len(self.boards)} boards, {len(self.fsas)} FSAs in {time.time() - t0:.1f}s")
        self.assets = Assets(STATIC)
        self.env = Environment(loader=FileSystemLoader(HERE / "templates"), autoescape=select_autoescape(["html"]),
                               trim_blocks=True, lstrip_blocks=True)
        codes = self.meta["codes"]
        loc = load(HERE / "locators.json")  # hand-checked links to each board's "which school serves my address" page
        self.env.globals.update(
            asset=self.assets, meta=self.meta, site_url=SITE_URL, pct=pct, contact_email=CONTACT_EMAIL, source_series=source_series, repo_url=REPO_URL, support_url=SUPPORT_URL,
            code_text=lambda c: codes.get(c, {}).get("explain", "") if c else "",
            locators=loc["boards"], locators_checked=loc["checked"], maplibre_dir=maplibre_dir(),
        )
        self.env.filters["month_year"] = lambda ym: datetime.strptime(ym, "%Y-%m").strftime("%B %Y") if ym else ""
        self.pages = 0
        svg, w, h = hero_svg(self.index)
        # bounds and colours go to the page too, so home.js can light up search matches on the same picture
        self.hero = {"svg": svg, "w": w, "h": h, "bounds": HERO_BOUNDS, "colors": HERO_COLORS,
                     "src": f"/static/img/hero-map.svg?v={short_hash(svg.encode())}"}
        self.context_medians()
        # Data the scripts fetch (/data/...) is versioned by the pipeline run plus what this generator
        # derives from it, and stamped on every page as <html data-v> for lib.js's dataUrl().
        self.ctx_json = self.context_json()
        self.env.globals["data_v"] = short_hash((DATA / "meta.json").read_bytes(), self.ctx_json.encode(), (HERE / "board-info.json").read_bytes())
        self.official_by_board = self._official()
        # hand-checked board records (registration, programs, transfers, supports, planning), inherited by schools
        self.info = family.BoardInfo(HERE / "board-info.json")
        self.env.globals.update(program_help=family.PROGRAM_HELP, coverage=family.COVERAGE, grade_label=family.GRADE_LABEL,
                                board_info_checked=self.info.raw.get("checked"))

    # ------------------------------------------------------------------
    def context_json(self) -> str:
        """/data/context-medians.json: board and province medians of each student-context measure, for Compare."""
        ctx = {"board": defaultdict(dict), "province": defaultdict(dict)}
        for (bn, key), v in self.ctx_board.items():
            ctx["board"][bn][key] = v
        for (lang, key), v in self.ctx_prov.items():
            ctx["province"][lang][key] = v
        return json.dumps(ctx, separators=(",", ":"))

    def context_medians(self):
        board_vals, prov_vals = defaultdict(list), defaultdict(list)
        for s in self.schools.values():
            for it in s["context"]["items"]:
                if it["value"] is not None:
                    board_vals[(s["board_number"], it["key"])].append(it["value"])
                    prov_vals[(s["language"], it["key"])].append(it["value"])
        self.ctx_board = {k: median(v) for k, v in board_vals.items() if len(v) >= 3}
        self.ctx_prov = {k: median(v) for k, v in prov_vals.items()}

    def _official(self):
        out = {}
        for bn, b in self.boards.items():
            d = {}
            for i in b["indicators"]:
                if i["key"] in ("g6_reading", "osslt") and i["value"] is not None:
                    d.setdefault(i["key"], {})[i["year"]] = i
            out[b["number"]] = d
        return out

    # ------------------------------------------------------------------
    def render(self, rel: str, template: str, **ctx) -> None:
        ctx.setdefault("path", "/" + rel.replace("index.html", ""))
        ctx.setdefault("description", "Find Ontario public schools by name, city or postal code. EQAO results in context, with a source for every number.")
        html = self.env.get_template(template).render(**ctx)
        if "<pre" not in html:
            html = re.sub(r"\n[ \t]+", "\n", html)  # drop template indentation (≈30% smaller pages)
        html = re.sub(r"\n\s*\n+", "\n", html)
        out = DIST / rel
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        self.pages += 1

    # ------------------------------------------------------------------
    def school_page(self, s: dict) -> None:
        years_all = self.meta["eqao_years"]
        by_a = defaultdict(list)
        for e in s["eqao"]:
            by_a[e["assessment"]].append(e)
        results = []
        historical = []  # paper-era results (2016-17 to 2018-19): kept, shown apart, never joined to the current trend
        official = self.official_by_board.get(s["board_number"], {})
        current_years = [y for y in years_all if y >= self.meta["eqao_eras"]["current_from"]]
        for aid in ASSESSMENT_ORDER:
            all_rows = sorted(by_a.get(aid, []), key=lambda r: r["year"])
            if not all_rows:
                continue
            a = self.meta["assessments"][aid]
            paper = [r for r in all_rows if r.get("era") == "paper"]
            rows = [r for r in all_rows if r.get("era") != "paper"]
            if paper:
                historical.append({"id": aid, "grade": a["grade"], "subject": a["subject"], "rows": paper,
                                   "codes": sorted({r["code"] for r in paper if r.get("code")})})
            if not rows:
                continue  # Grade 9 academic/applied: historical only
            yrs = [y for y in current_years if any(r["year"] == y for r in rows)] or [r["year"] for r in rows]
            last = rows[-1]
            summary = self.summary_sentence(s, a, last, rows)
            off = None
            key = {"g6-reading": "g6_reading", "osslt": "osslt"}.get(aid)
            if key and key in official:
                yr = max(official[key])
                off = {"year": yr, "value": official[key][yr]["value"], "source_id": official[key][yr]["source_id"]}
            # EQAO's open data adds the level split and participation for its years (shown under the chart)
            detail = None
            if last.get("levels") or last.get("participation") is not None:
                lv = last.get("levels") or []
                detail = {"year": last["year"], "participation": last.get("participation"),
                          "levels": [{"n": 4 - i, "v": v, "w": (v if isinstance(v, (int, float)) else 0.5)} for i, v in enumerate(lv) if v is not None]}
            results.append({
                "id": aid, "grade": a["grade"], "subject": a["subject"], "rows": rows, "summary": summary, "official": off, "detail": detail,
                "svg": charts.eqao_chart(rows, yrs, gap=False,
                                         title=f"{a['grade']} {a['subject']}: this school, board median and Ontario median by year, {yrs[0]} to {yrs[-1]}"),
                "codes": sorted({r["code"] for r in rows if r.get("code")}),
                "paper_years": [r["year"] for r in paper],
            })
        enrol = s["enrolment"]
        enrol_latest = enrol[-1] if enrol else None
        enrol_change = None
        vals = [e for e in enrol if e["value"] is not None]
        if len(vals) >= 2 and enrol_latest and enrol_latest["value"] is not None:
            past = next((e for e in reversed(vals) if e["year"][:4] <= str(int(enrol_latest["year"][:4]) - 5)), vals[0])
            if past is not enrol_latest:
                d = enrol_latest["value"] - past["value"]
                enrol_change = f"{'+' if d >= 0 else '−'}{abs(d):,} since {past['year']}"
        context_rows = []
        for it in s["context"]["items"]:
            context_rows.append({**it, "board_median": self.ctx_board.get((s["board_number"], it["key"])),
                                 "province_median": self.ctx_prov.get((s["language"], it["key"]))})
        cs = s.get("class_size") or []
        cs_view = None
        if cs:
            cyears = [r["year"] for r in cs]
            latest_cs = cs[-1]
            cs_view = {
                "latest": latest_cs, "first": cs[0]["year"],
                "svg": charts.wide_line_chart(cs, cyears, title=f"Average Grades 1 to 3 class size at {s['name']}, board median and Ontario median by year",
                                              main_key="primary_avg", board_key="primary_board_median", prov_key="primary_province_median",
                                              ymax=30, unit="", gap=False),
            }
        ge = s.get("grade_enrolment") or []
        grade_view = None
        if ge:
            order = ["JK", "K"] + [f"G{i}" for i in range(1, 13)]
            used = [g for g in order if any(g in r["grades"] for r in ge)]
            grade_view = {"years": [r["year"] for r in ge][-5:], "rows": [], "latest": ge[-1]}
            for g in used:
                label = "Junior kindergarten" if g == "JK" else "Kindergarten" if g == "K" else f"Grade {g[1:]}"
                cells = []
                for r in ge[-5:]:
                    if g not in r["grades"]:
                        cells.append({"v": None, "code": None})
                    else:
                        cells.append({"v": r["grades"][g], "code": r["codes"].get(g)})
                grade_view["rows"].append({"label": label, "cells": cells})
        neighbours = [self.schools[n["bsid"]] for n in s["nearby"] if n["bsid"] in self.schools]
        # the nearby list shows each school's programs, so a family can see which nearby school offers Immersion
        nearby_badges = {n["bsid"]: family.program_badges(n, self.info.board_listed(n)) for n in neighbours}
        map_data = {
            "center": [s["lon"], s["lat"]],
            "school": {"id": s["bsid"], "n": s["name"], "sys": s["system"], "x": s["lon"], "y": s["lat"]},
            "nearby": [{"id": n["bsid"], "n": n["name"], "sys": n["system"], "x": n["lon"], "y": n["lat"], "g": n["grades"], **self.pt_flags(n)} for n in neighbours],
            # the board's own attendance area when it publishes one, else the nearest-school estimate
            "area": (s.get("official_area") or {}).get("geometry") or s.get("nearest_area"),
            "area_kind": "official" if s.get("official_area") else "nearest",
        }
        official_label = official_when = None
        if s.get("official_area"):
            oa = s["official_area"]
            ed = oa.get("edited")
            when = datetime.strptime(ed, "%Y-%m").strftime("%B %Y") if ed else None
            official_label = f"Official boundary from {s['board_name']}" + (f", for {oa['effective']}" if oa.get("effective") else f", edited {when}" if when else "")
            # the school year a layer says it is for is not the same thing as when its map was last edited
            official_when = {"effective": oa.get("effective"), "effective_note": oa.get("effective_note"), "edited": when}
        addr = ", ".join(x for x in [s["address"], s["suite"], s["city"], "ON", s["postal_code"]] if x)
        family_view = self.family_view(s, results=results)
        jsonld = {
            "@context": "https://schema.org", "@type": "School" if s["level"] == "elementary" else "HighSchool",
            "name": s["name"], "url": f"{SITE_URL}/school/{s['bsid']}/", "telephone": s["phone"],
            "address": {"@type": "PostalAddress", "streetAddress": s["address"], "addressLocality": s["city"], "addressRegion": "ON",
                        "postalCode": s["postal_code"], "addressCountry": "CA"},
            "geo": {"@type": "GeoCoordinates", "latitude": s["lat"], "longitude": s["lon"]},
            "parentOrganization": {"@type": "Organization", "name": s["board_name"]},
        }
        if s["level"] == "elementary":
            jsonld["@type"] = "ElementarySchool"
        if s["website"]:
            jsonld["sameAs"] = s["website"]
        sys_label = self.meta["systems"][s["system"]]
        latest_eqao = max((e["year"] for e in s["eqao"]), default=None)
        desc = f"{s['name']}, {s['city'] or 'Ontario'}: {s['level']} school ({s['grades']}), {s['board_name']}. "
        if latest_eqao:
            desc += f"EQAO {min(e['year'] for e in s['eqao'])} to {latest_eqao} with board and Ontario medians, enrolment and sources."
        else:
            desc += "Enrolment, student context, nearby schools and child care, with sources."
        desc = clip(desc, 160)  # search results cut descriptions at about 160 characters
        self.render(f"school/{s['bsid']}/index.html", "school.html",
                    title=f"{s['name']} — {s['city'] or s['board_name']}", description=desc, page_kind="school", map=True,
                    s=s, results=results, historical=historical, system_label=sys_label, address_line=addr, official_label=official_label,
                    official_when=official_when, fv=family_view, nearby_badges=nearby_badges,
                    contact_label=self.sources.get("contact-2026-11", {}).get("year", "current"),
                    enrol_latest=enrol_latest, enrol_change=enrol_change,
                    enrol_svg=charts.wide_bar_chart(enrol, title=f"Enrolment at {s['name']} by school year"),
                    latest_eqao=latest_eqao, eqao_span=f"{min(e['year'] for e in s['eqao'])} to {latest_eqao}" if latest_eqao else "",
                    context_rows=context_rows, childcare_date=human_date(s["childcare"]["snapshot"]), cs_view=cs_view, grade_view=grade_view,
                    map_json=json.dumps(map_data, separators=(",", ":")).replace("</", "<\\/"),
                    jsonld=json.dumps({k: v for k, v in jsonld.items() if v}, ensure_ascii=False).replace("</", "<\\/"))

    def family_view(self, s: dict, *, results: list) -> dict:
        """Everything a family needs to act on: grades, programs, the board's sourced records, student
        experience, coverage states for missing sections, and questions to ask."""
        offered = family.grades_offered(s.get("grades"))
        listed = self.info.board_listed(s)
        badges = family.program_badges(s, listed)
        keys = {b["key"] for b in badges}
        info = self.info.for_school(s, keys)
        sq = self.sq_view(s)
        cs = s.get("class_size_status") or {}
        cs_text = None
        if cs.get("status") == "match_unresolved":
            names = [self.schools[b]["name"] + (f" ({self.schools[b]['city']})" if self.schools[b].get("city") else "") for b in cs["others"] if b in self.schools]
            cs_text = (f"The Ministry's class lists name schools rather than numbering them, and {s['board_name']} has another school with this "
                       f"same name ({', '.join(names)}). The lists can't tell the two apart, so we show no class sizes for either rather than guess.")
        elif cs.get("status") == "not_listed":
            cs_text = "This school is not in the Ministry's elementary class lists under any name it has used since 2015-16."
        prox = s.get("proximity_area")
        prox_text = None
        if not s.get("official_area"):
            if prox == "immersion_only":
                prox_text = ("No nearest-school area is drawn for this school. The Ministry lists it as offering French Immersion but neither Core nor "
                             "Extended French, so it is most likely a French Immersion school that families choose for the program, not a "
                             "neighbourhood school. Who can attend is set by the board's program rules.")
            elif prox == "not_regular":
                prox_text = f"No nearest-school area is drawn for {(s.get('special') or 'special-purpose').lower()} schools: families don't attend them by neighbourhood."
            elif prox == "other_system":
                prox_text = "No nearest-school area is drawn for provincial and other special schools."
        questions = family.visit_questions(s, info=info, badges=badges, offered=offered, class_status=cs,
                                           has_childcare_here=bool(s["childcare"]["at_address"]), sq=s.get("student_experience") or [])
        return {"offered": offered, "grade_span": family.grade_span_label(s.get("grades")), "badges": badges, "listed": listed,
                "opened": family.opened_label(s.get("date_open")),
                "info": info, "sq": sq, "cs_status": cs, "cs_text": cs_text, "prox_text": prox_text, "questions": questions,
                "locator": self.env.globals["locators"].get(s["board_number"])}

    def sq_view(self, s: dict) -> list[dict]:
        out = []
        for b in s.get("student_experience") or []:
            m = self.meta["student_questionnaire"].get(b["source_id"])
            if not m:
                continue
            qs = {q["key"]: q for q in m["questions"]}
            five = len(qs[next(iter(qs))]["options"]) > 4
            grade = {"3": "Grade 3", "6": "Grade 6", "9": "Grade 9", "10": "Grade 10 (OSSLT)"}[b["grade"]]
            items = []
            for it in b["items"]:
                q = qs.get(it["key"])
                if not q:
                    continue
                dist = None
                if it.get("pct"):
                    dist = [{"label": lab, "pct": p, "n": n} for lab, p, n in zip(q["options"], it["pct"], it["counts"])]
                items.append({**it, "label": q["label"], "question": q["question"], "base": q["base"], "agree": q["agree"], "dist": dist})
            out.append({"grade": grade, "year": b["year"], "source_id": b["source_id"], "withheld": b["withheld"],
                        "respondents": b["respondents"], "five_point": five, "rows": items})
        return out

    def pt_flags(self, s: dict) -> dict:
        """Program flags for a map point, the same short keys as the search index (popups show badges from them)."""
        f = (s.get("programs") or {}).get("fsl") or {}
        sh = (s.get("programs") or {}).get("shsm")
        out = {"lang": (s.get("language") or "")[:1], "fi": 1 if f.get("immersion") else 0, "ef": 1 if f.get("extended") else 0,
               "sh": len(sh["sectors"]) if sh else 0, "fb": 1 if "french-immersion" in self.info.board_listed(s) else 0}
        return {k: v for k, v in out.items() if v}

    def board_records(self, board: str) -> dict:
        return self.info.for_board(board)

    def index_with_board_lists(self) -> int:
        """Add board-listed programs to the search index the browser loads (/data/schools-index.json):
        fb = the school's board lists it as a French Immersion school (shown even when the Ministry's
        preliminary FSL list doesn't flag it, so search, maps and the school page agree)."""
        p = DIST / "data" / "schools-index.json"
        idx = load(p)
        n = 0
        for r in idx:
            s = self.schools.get(r["id"])
            if s and "french-immersion" in self.info.board_listed(s):
                r["fb"] = 1
                n += 1
        p.write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        # Compare reads each school's JSON: give it the same practical facts the school page shows
        # (grades offered, program badges incl. the board's own lists, address lookup, registration page,
        # Immersion entry grade), so the two never disagree.
        for s in self.schools.values():
            listed = self.info.board_listed(s)
            badges = family.program_badges(s, listed)
            info = self.info.for_school(s, {b["key"] for b in badges})
            T = info["topics"]
            reg = next((r for r in T.get("registration", [])), None)
            fi_entry = next((r["facts"]["entry_grades"] for r in T.get("program", []) if r.get("program") == "french-immersion"
                             and (r.get("facts") or {}).get("entry_grades")), None)
            loc = next((r for r in T.get("address_lookup", [])), None) or self.env.globals["locators"].get(s["board_number"])
            s_out = {**s, "family": {
                "grades_offered": family.grades_offered(s.get("grades")), "grade_span": family.grade_span_label(s.get("grades")),
                "badges": badges, "listed": listed, "info_collected": info["collected"], "checked": info["checked"],
                "locator": {"url": loc["url"], "title": loc.get("title") or "Check your address"} if loc else None,
                "register": {"url": reg["url"], "title": reg["title"]} if reg else None,
                "fi_entry": fi_entry, "opened": family.opened_label(s.get("date_open")),
                "fi_page": next(({"url": r["url"], "title": r["title"]} for r in T.get("program", []) if r.get("program") == "french-immersion"), None),
                "transfer": next(({"url": r["url"], "title": r["title"], "kind": r["kind"]} for r in T.get("transfer", [])), None),
            }}
            (DIST / "data" / "schools" / f"{s['bsid']}.json").write_text(json.dumps(s_out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        return n

    def summary_sentence(self, s, a, last, rows=()) -> str:
        subj = a["subject"].lower()
        who = f"{a['grade']} students"
        if a["grade"] == "Grade 10":
            what = "passed the literacy test on their first try"
        else:
            what = f"met the provincial standard in {subj}"
        v = last["pct_at_or_above_standard"]
        yr = last["year"]
        if v is None:
            code = last.get("code") or ""
            expl = self.meta["codes"].get(code, {}).get("explain", "No value published.")
            return f"<b>{yr}:</b> no result shown ({code}). {expl}"
        parts = [f"In <b>{yr}</b>, <b>{v:g}%</b> of {who} {what}."]
        cmp = []
        if last.get("board_median") is not None:
            cmp.append(f"board median {last['board_median']:g}%")
        if last.get("province_median") is not None:
            cmp.append(f"Ontario median {last['province_median']:g}%")
        if cmp:
            txt = ", ".join(cmp)
            parts.append(" " + txt[0].upper() + txt[1:] + ".")
        # A change is only stated within one assessment era (EQAO's current trend line starts in 2021-22),
        # and it compares different groups of students, not the same children's progress.
        era = last.get("era")
        pts = [r for r in rows if r["pct_at_or_above_standard"] is not None and r.get("era") == era]
        if era == "current" and len(pts) >= 2 and pts[0]["year"] != pts[-1]["year"]:
            d = round(pts[-1]["pct_at_or_above_standard"] - pts[0]["pct_at_or_above_standard"], 1)
            unit = "point" if abs(d) == 1 else "points"
            how = f"{abs(d):g} {unit} {'higher' if d > 0 else 'lower'} than" if d else "the same as"
            parts.append(f" That is {how} in {pts[0]['year']} (a different group of students).")
        return "".join(parts)

    # ------------------------------------------------------------------
    def board_page(self, b: dict) -> None:
        schools = sorted((self.schools[x] for x in b["schools"] if x in self.schools), key=lambda s: plain(s["name"]))
        rows = []
        for s in schools:
            e = s["enrolment"][-1] if s["enrolment"] else None
            rows.append({"bsid": s["bsid"], "name": s["name"], "level": s["level"], "grades": s["grades"], "city": s["city"],
                         "special": s["special"], "enrol": e["value"] if e and e["year"] == b["enrolment_total"]["year"] else None,
                         "fi": bool(((s.get("programs") or {}).get("fsl") or {}).get("immersion")) or "french-immersion" in self.info.board_listed(s),
                         "badges": family.program_badges(s, self.info.board_listed(s))})
        school_groups = []  # A-Z groups for the school list; "École" files under E
        for r in rows:
            first = plain(r["name"])[:1].upper()
            letter = first if first.isalpha() else "#"
            if not school_groups or school_groups[-1]["letter"] != letter:
                school_groups.append({"letter": letter, "schools": []})
            school_groups[-1]["schools"].append(r)
        releases = []
        for i in b["indicators"]:
            if i["source_id"] not in [r["source_id"] for r in releases]:
                releases.append({"source_id": i["source_id"], "label": self.sources.get(i["source_id"], {}).get("note", "").split(":")[0] or i["source_id"]})
        for r in releases:
            r["label"] = {"sbpr-2026-11": "Nov 2026 release", "sbpr-2026-05": "May 2026 release"}.get(r["source_id"], r["source_id"])
        by_key = defaultdict(dict)
        for i in b["indicators"]:
            yl = f"cohort {i['cohort']}" if i.get("cohort") else i["year"]
            by_key[i["key"]][i["source_id"]] = {**i, "year_label": yl}
        indicators = []
        labels = {}
        for i in b["indicators"]:
            labels[i["key"]] = i["label"]
        for k in SBPR_ROWS:
            if k in by_key:
                indicators.append({"label": labels[k], "change": k.endswith("_change"), "cells": [by_key[k].get(r["source_id"]) for r in releases]})
        headline = []
        if releases:
            first = releases[0]["source_id"]
            for k, lab in (("g6_reading", "Grade 6 reading"), ("osslt", "OSSLT pass, first try"), ("grad_5yr", "5-year graduation")):
                c = by_key.get(k, {}).get(first)
                if c:
                    headline.append({"label": lab, "value": c["value"], "code": c.get("code"), "year_label": c["year_label"]})
        years_all = self.meta["eqao_years"]
        med = defaultdict(list)
        for m in b["eqao_medians"]:
            med[m["assessment"]].append(m)
        medians = []
        medians_paper = []  # 2016-17 to 2018-19: a different test, listed apart and never joined to the current lines
        for aid in ASSESSMENT_ORDER:
            all_rws = sorted(med.get(aid, []), key=lambda r: r["year"])
            if not all_rws:
                continue
            a = self.meta["assessments"][aid]
            paper = [r for r in all_rws if r.get("era") == "paper"]
            rws = [r for r in all_rws if r.get("era") != "paper"]
            if paper:
                medians_paper.append({"grade": a["grade"], "subject": a["subject"], "rows": paper})
            if not rws:
                continue
            yrs = [y for y in years_all if any(r["year"] == y for r in rws)]
            medians.append({"grade": a["grade"], "subject": a["subject"], "rows": rws,
                            "svg": charts.eqao_chart(rws, yrs, gap=False, title=f"{a['grade']} {a['subject']}: board median and Ontario median, {yrs[0]} to {yrs[-1]}", main_key="board_median", main_label="Board median")})
        # chart helper draws board_median dashed too; blank it so only the two lines show
        for m in medians:
            m["svg"] = m["svg"].replace('class="s-board"', 'class="s-board" style="display:none"').replace('class="p-board"', 'class="p-board" style="display:none"')
        types = {"english-public": "English-language public district school board", "english-catholic": "English-language Catholic district school board",
                 "french-public": "French-language public district school board", "french-catholic": "French-language Catholic district school board",
                 "other": "Provincial school, hospital school or school authority"}
        b = {**b, "full_type": types[b["system"]]}
        csm = b.get("class_size_medians") or []
        cs_board = None
        if csm:
            rows_cs = [{"year": r["year"], "board_median": r["primary_median"], "province_median": r["province_median"], "board_n": r["n"]} for r in csm]
            cs_board = {"rows": rows_cs, "svg": charts.wide_line_chart(rows_cs, [r["year"] for r in rows_cs], title="Average Grades 1 to 3 class size: median school in the board and in Ontario",
                                                                      main_key="board_median", board_key="_none", prov_key="province_median", ymax=30, unit="", gap=False)}
        # board context: suspension trend chart (board vs Ontario) and spending split
        ctx = b.get("context") or {}
        safe = ctx.get("safe")
        safe_view = None
        if safe and any(r["rate"] is not None for r in safe["series"]):
            sr = [{"year": r["year"], "board_median": r["rate"], "province_median": r["province_rate"], "code": r["rate_code"]} for r in safe["series"]]
            top = max([r["rate"] or 0 for r in safe["series"]] + [r["province_rate"] or 0 for r in safe["series"]])
            ymax = max(2, int(top) + (2 if top < 10 else 4))
            safe_view = {"rows": safe["series"], "last": next(r for r in reversed(safe["series"]) if r["rate"] is not None),
                         "svg": charts.wide_line_chart(sr, [r["year"] for r in sr], title=f"Share of {b['name']} students suspended each year, with Ontario",
                                                       main_key="board_median", main_label=b["name"], board_key="_none", prov_key="province_median",
                                                       ymax=ymax, unit="%", gap=False)}
        spend = ctx.get("spending")
        spend_view = None
        if spend:
            parts = [("instruction", "Classroom", "teachers, assistants, supplies, principals, guidance"),
                     ("accommodation", "Buildings", "running, repairing and renewing schools"),
                     ("transportation", "Transportation", "school buses"),
                     ("administration", "Administration", "trustees, director, board offices"),
                     ("other", "Other", "everything else")]
            spend_view = {**spend, "parts": [{"key": k, "label": l, "what": w, "v": spend["parts"].get(k, 0),
                                              "pct": round(100 * spend["parts"].get(k, 0) / spend["per_student"])} for k, l, w in parts if spend["parts"].get(k, 0) > 0]}
        map_data = {"schools": [{"id": s["bsid"], "n": s["name"], "sys": s["system"], "x": s["lon"], "y": s["lat"], "l": "E" if s["level"] == "elementary" else "S", "g": s["grades"], **self.pt_flags(s)} for s in schools],
                    "board": b["number"], "system": b["system"]}
        self.render(f"board/{b['number']}/index.html", "board.html", title=b["name"], page_kind="board", map=True,
                    description=f"{b['name']}: {len(schools)} schools, official board results, EQAO medians across its schools and a map, with sources.",
                    safe_view=safe_view, spend_view=spend_view, fsl_enrol=ctx.get("fsl_enrolment"),
                    b=b, schools=rows, school_groups=school_groups, cs_board=cs_board, indicators=indicators, indicator_releases=releases, headline=headline, medians=medians, medians_paper=medians_paper, board_info=self.board_records(b["number"]),
                    map_json=json.dumps(map_data, separators=(",", ":")).replace("</", "<\\/"))

    # ------------------------------------------------------------------
    def fsa_page(self, f: dict) -> None:
        ids = [(x, True) for x in f["in"]] + [(x, False) for x in f["near"]] + [(x, False) for x in f.get("closest", [])]
        groups = defaultdict(list)
        seen = set()
        for bsid, inside in ids:
            if bsid in seen or bsid not in self.schools:
                continue
            seen.add(bsid)
            s = self.schools[bsid]
            groups[(s["system"], s["level"])].append({"bsid": bsid, "name": s["name"], "board_name": s["board_name"], "grades": s["grades"], "inside": inside,
                                                   "badges": family.program_badges(s, self.info.board_listed(s))})
        glist = []
        for system in SYSTEM_ORDER:
            for level in ("elementary", "secondary"):
                items = sorted(groups.get((system, level), []), key=lambda x: (not x["inside"], x["name"]))
                if items:
                    glist.append({"system": system, "system_label": self.meta["systems"][system], "level": level, "entries": items})
        c = f["census"] or {}
        fields = {x["key"]: x for x in self.meta["census_fields"]}

        def fmt(key):
            v = c.get(key)
            if v is None:
                return "—"
            unit = fields[key]["unit"]
            if unit == "pct":
                return f"{v:g}%"
            if unit == "dollars":
                return f"${v:,.0f}"
            if unit == "count":
                return f"{v:,}"
            return f"{v:,.1f}"
        kpis = []
        if c:
            kpis = [
                {"label": "Population, 2021", "value": fmt("population"), "d": f"{fmt('density_per_km2')} per km²"},
                {"label": "Children 0–14", "value": fmt("children_0_14"), "d": f"{fmt('children_0_14_pct')} of residents"},
                {"label": "Households: couples with children", "value": fmt("couple_hh_children_pct"), "d": f"One-parent: {fmt('one_parent_hh_pct')}"},
                {"label": "Median household income (2020)", "value": fmt("median_household_income"), "d": "Before tax"},
                {"label": "Children 0–17 in low income", "value": fmt("low_income_0_17_pct"), "d": "LIM-AT, 2020"},
                {"label": "Non-official language at home", "value": fmt("home_other_pct"), "d": f"French at home: {fmt('home_french_pct')}"},
            ]
        census_rows = [{"label": x["label"], "value": fmt(x["key"])} for x in self.meta["census_fields"]] if c else []
        pts = []
        for bsid, inside in ids:
            if bsid in self.schools:
                s = self.schools[bsid]
                pts.append({"id": bsid, "n": s["name"], "sys": s["system"], "x": s["lon"], "y": s["lat"], "in": inside, "g": s["grades"], "l": "E" if s["level"] == "elementary" else "S", **self.pt_flags(s)})
        map_data = {"fsa": f["fsa"], "boundary": f["boundary"], "schools": pts}
        place = f" ({f['place']})" if f["place"] else ""
        self.render(f"fsa/{f['fsa']}/index.html", "fsa.html", title=f"Schools in postal area {f['fsa']}{place}", page_kind="fsa", map=True,
                    description=f"Public schools in and near Ontario postal area {f['fsa']}{place}, grouped by board and level, with 2021 Census context and licensed child care.",
                    f=f, groups=glist, census_kpis=kpis, census_rows=census_rows, near_km=1.5,
                    childcare_date=human_date(next(iter(self.schools.values()))["childcare"]["snapshot"]),
                    map_json=json.dumps(map_data, separators=(",", ":")).replace("</", "<\\/"))

    # ------------------------------------------------------------------
    def index_pages(self) -> None:
        self.render("index.html", "home.html", title="Ontario School Finder — find a school, see the facts in context", home=True, page_kind="home",
                    og_title="Ontario School Finder", hero=self.hero)
        groups = []
        for system in SYSTEM_ORDER:
            bs = [b for b in self.boards_index if b["sys"] == system]
            if bs:
                groups.append({"system": system, "label": self.meta["systems"][system], "boards": [{"number": b["n"], "name": b["name"], "count": b["count"]} for b in bs]})
        self.render("boards/index.html", "boards.html", title="School boards", page_kind="boards", groups=groups,
                    description="All Ontario school boards and school authorities, grouped by English/French and public/Catholic.")
        areas = defaultdict(list)
        for a in self.fsa_index:
            areas[a["f"][0]].append({"fsa": a["f"], "place": a["p"], "count": a["count"]})
        self.render("areas/index.html", "areas.html", title="Postal areas", page_kind="areas",
                    groups=[{"letter": k, "label": REGION_LABEL.get(k, ""), "entries": v} for k, v in sorted(areas.items())],
                    description="Every Ontario forward sortation area (first three characters of a postal code) with its schools.")
        self.render("search/index.html", "search.html", title="Search", page_kind="search")
        self.render("compare/index.html", "compare.html", title="Compare schools", page_kind="compare")
        self.render("map/index.html", "map.html", title="Map", page_kind="map", map=True,
                    systems=[(k, self.meta["systems"][k]) for k in SYSTEM_ORDER],
                    description="Map of every Ontario public school with postal areas, approximate board areas, nearest-school areas and the official attendance areas boards publish, each clearly labelled.")
        ds = []
        files = defaultdict(list)
        for x in self.sources.values():
            files[x["dataset"]].append(x)
        for key, d in sorted(self.meta["datasets"].items(), key=lambda kv: kv[1]["brief_no"]):
            fl = files.get(key, [])
            retrieved = sorted(f["retrieved"] for f in fl if f.get("retrieved"))
            ds.append({**d, "key": key, "files": fl, "retrieved": retrieved[-1] if retrieved else None})
        rate = 100 * (self.meta["fsa_check"]["checked"] - self.meta["fsa_check"]["mismatches"]) / max(1, self.meta["fsa_check"]["checked"])
        self.render("methodology/index.html", "methodology.html", title="How it works", page_kind="methodology",
                    datasets=ds, licence_counts=sorted(Counter(d["licence_status"] for d in ds if d["status"] == "used").items(), key=lambda kv: (kv[0] != "open", kv[0])), codes=[(k, v) for k, v in self.meta["codes"].items() if k != "BLANK"], fsa_check_rate=f"{rate:.1f}%",
                    description="Sources, licences, definitions, how withheld values are handled and how map areas are drawn.")
        self.render("about/index.html", "about.html", title="About", page_kind="about", operator=OPERATOR, contact_email=CONTACT_EMAIL,
                    description="Why Ontario School Finder exists, who runs it, why it's free and how it protects your privacy.")
        self.render("corrections/index.html", "corrections.html", title="Report a correction", page_kind="corrections",
                    contact_email=CONTACT_EMAIL, corrections_url=CORRECTIONS_URL)
        downloads = []
        for name, title, desc in [
            ("schools.csv", "Schools", "One row per school: board, level, grades, address, coordinates, contact, status."),
            ("eqao.csv", "EQAO results", "Every school, assessment and year, with codes, board and Ontario medians."),
            ("enrolment.csv", "Enrolment", "Every school and year from 2011-12."),
            ("student-experience.csv", "Student experience", "EQAO questionnaire answers by school, with the whole board and Ontario, latest year."),
            ("fsa-census.csv", "Postal-area census", "2021 Census figures for every Ontario FSA."),
            ("sources.csv", "Sources", "Every source file with URL, licence and retrieval date."),
        ]:
            p = DATA / "downloads" / name
            downloads.append({"href": f"/data/downloads/{name}", "title": title, "desc": desc, "size": f"{p.stat().st_size / 1e6:.1f} MB" if p.stat().st_size > 1e5 else f"{p.stat().st_size // 1024} KB"})
        self.render("data/index.html", "data.html", title="Download the data", page_kind="data", downloads=downloads,
                    description="Download Ontario school data as CSV and JSON with a source id on every row.")
        self.render("404.html", "404.html", title="Page not found", page_kind="404", path="/404.html")

    # ------------------------------------------------------------------
    def extras(self) -> None:
        urls = ["/", "/search/", "/map/", "/boards/", "/areas/", "/compare/", "/methodology/", "/about/", "/data/"]
        urls += [f"/board/{b['number']}/" for b in self.boards.values()]
        urls += [f"/fsa/{f}/" for f in self.fsas]
        urls += [f"/school/{s}/" for s in self.schools]
        lastmod = (self.meta.get("data_updated") or "")[:10]
        sm = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        sm += [f"<url><loc>{SITE_URL}{u}</loc><lastmod>{lastmod}</lastmod></url>" for u in urls]
        sm.append("</urlset>")
        (DIST / "sitemap.xml").write_text("\n".join(sm), encoding="utf-8")
        (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {SITE_URL}/sitemap.xml\n", encoding="utf-8")
        shutil.copy2(STATIC / "favicon.ico", DIST / "favicon.ico")  # browsers and crawlers still ask for /favicon.ico
        manifest = {
            "name": "Ontario School Finder", "short_name": "School Finder", "start_url": "/?source=app", "scope": "/",
            "display": "standalone", "background_color": "#f6f5f1", "theme_color": "#0b5d4f",
            "description": "Find Ontario public schools and see their public results in context.",
            "icons": [{"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
                      {"src": "/static/img/icon-512.png", "sizes": "512x512", "type": "image/png"},
                      {"src": "/static/img/icon-maskable-512.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"},
                      {"src": "/static/img/icon.svg", "sizes": "any", "type": "image/svg+xml"}],
        }
        (DIST / "manifest.webmanifest").write_text(json.dumps(manifest, indent=1), encoding="utf-8")
        (DIST / "healthz").write_text("ok\n", encoding="utf-8")


HERO_BOUNDS = (-83.3, -74.3, 41.9, 46.4)  # min lon, max lon, min lat, max lat: southern Ontario
HERO_COLORS = {"english-public": "#1f8fb0", "english-catholic": "#9a5cc0", "french-public": "#d0682f", "french-catholic": "#4c9a44", "other": "#8a8f98"}


def hero_svg(index: list[dict]) -> tuple[str, int, int]:
    """Dot map of every school in southern Ontario, drawn from the data.

    Written to /static/img/hero-map.svg (cached by browsers) instead of inlined: ~4,000
    dots would otherwise add ~250 KB to every home page load. Colours are mid-tones that
    read on both the light and the dark card; the legend lives in HTML so it follows the theme.
    """
    import math
    minx, maxx, miny, maxy = HERO_BOUNDS
    kx = math.cos(math.radians((miny + maxy) / 2))  # equirectangular correction
    w = 440
    h = round(w * (maxy - miny) / ((maxx - minx) * kx))
    colors = HERO_COLORS
    groups: dict[str, list[str]] = {}
    for r in index:
        if not (minx <= r["x"] <= maxx and miny <= r["y"] <= maxy):
            continue
        px = (r["x"] - minx) / (maxx - minx) * w
        py = h - (r["y"] - miny) / (maxy - miny) * h
        groups.setdefault(r["sys"], []).append(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="1.9"/>')
    body = "".join(f'<g fill="{colors.get(k, "#8a8f98")}">{"".join(v)}</g>' for k, v in groups.items())
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><g opacity=".92">{body}</g></svg>', w, h)


def split_board_areas() -> int:
    """One small area file per board (data/geo/board/<number>.geojson) for the board pages, which used
    to download every board's area (1.7 MB) to draw one. The Map page still uses boards.geojson."""
    by_board = defaultdict(list)
    for f in load(DATA / "geo" / "boards.geojson")["features"]:
        by_board[f["properties"]["board"]].append(f)
    out = DIST / "data" / "geo" / "board"
    out.mkdir(parents=True, exist_ok=True)
    for board, feats in by_board.items():
        (out / f"{board}.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}, separators=(",", ":")), encoding="utf-8")
    return len(by_board)


def copy_static_and_data() -> None:
    shutil.copytree(STATIC, DIST / "static", dirs_exist_ok=True)
    out = DIST / "data"
    out.mkdir(parents=True, exist_ok=True)
    for name in ["schools-index.json", "boards-index.json", "boards-context.json", "fsa-index.json", "meta.json", "sources.json"]:
        shutil.copy2(DATA / name, out / name)
    for sub in ["geo", "downloads", "schools", "boards", "fsa"]:
        shutil.copytree(DATA / sub, out / sub, dirs_exist_ok=True)
    report = HERE.parent / "pipeline" / "report.md"
    if report.exists():
        shutil.copy2(report, out / "report.md")


def precompress() -> int:
    n = 0
    for p in DIST.rglob("*"):
        # HTML is compressed on the fly by nginx; precompress the big shared assets only
        if p.is_file() and p.suffix in (".css", ".js", ".mjs", ".json", ".geojson", ".svg", ".xml", ".csv", ".md", ".webmanifest"):
            if p.stat().st_size < 8192 or "/data/schools/" in p.as_posix() or "/data/fsa/" in p.as_posix() or "/data/boards/" in p.as_posix():
                continue
            data = p.read_bytes()
            (p.parent / (p.name + ".gz")).write_bytes(gzip.compress(data, compresslevel=6, mtime=0))
            n += 1
    return n


def clear_dir(d: Path) -> None:
    """Empty the output folder but keep it (Windows refuses to delete a folder a local preview server is serving)."""
    d.mkdir(parents=True, exist_ok=True)
    for child in d.iterdir():
        for attempt in range(8):
            try:
                if child.is_dir():
                    shutil.rmtree(child)
                else:
                    child.unlink()
                break
            except OSError:  # file locks / "directory not empty" while Windows indexing or scanning catches up
                if attempt == 7:
                    raise
                time.sleep(1 + attempt)


def main() -> int:
    t0 = time.time()
    if not (DATA / "meta.json").exists():
        print("site/data is missing: run `python -m pipeline.build` first", file=sys.stderr)
        return 2
    clear_dir(DIST)
    site = Site()
    for s in site.schools.values():
        site.school_page(s)
    for b in site.boards.values():
        site.board_page(b)
    for f in site.fsas.values():
        site.fsa_page(f)
    site.index_pages()
    copy_static_and_data()
    site.index_with_board_lists()
    split_board_areas()
    if not version_scripts(DIST / "static" / "js", site.assets.js_v):
        raise SystemExit("version_scripts found no imports to version: check _IMPORT_RE against site/static/js")
    site.extras()
    (DIST / "static" / "img" / "hero-map.svg").write_text(site.hero["svg"], encoding="utf-8")
    (DIST / "data" / "context-medians.json").write_text(site.ctx_json, encoding="utf-8")
    gz = precompress()
    counts = {"school": len(list((DIST / "school").glob("*/index.html"))), "board": len(list((DIST / "board").glob("*/index.html"))),
              "fsa": len(list((DIST / "fsa").glob("*/index.html")))}
    (DIST / "build.json").write_text(json.dumps({"built": datetime.now().isoformat(timespec="seconds"), "pages": site.pages, **counts}), encoding="utf-8")
    print(f"generated {site.pages} pages ({counts}) and {gz} gzip files in {time.time() - t0:.1f}s -> {DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
