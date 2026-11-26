"""Static site generator: site/data (pipeline output) + templates -> site/dist.

    python site/generate.py

Environment (all optional):
    SITE_URL         canonical origin, default https://ontarioschoolfinder.ca
    CONTACT_EMAIL    shown on /corrections/ when set
    CORRECTIONS_URL  a public form or issue tracker for corrections
    OPERATOR         one sentence for /about/ "Who runs it"
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
from collections import Counter, defaultdict
from datetime import date, datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import charts  # noqa: E402

DATA = HERE / "data"
DIST = HERE / "dist"
STATIC = HERE / "static"
SITE_URL = os.environ.get("SITE_URL", "https://ontarioschoolfinder.ca").rstrip("/")
CONTACT_EMAIL = os.environ.get("CONTACT_EMAIL", "").strip()
CORRECTIONS_URL = os.environ.get("CORRECTIONS_URL", "").strip()
OPERATOR = os.environ.get("OPERATOR", "").strip() or "Ontario School Finder is an independent, volunteer-run project built for Ontario families."

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


class Assets:
    """Content-hashed URLs for static files so browsers can cache them for a year."""

    def __init__(self, root: Path):
        self.root = root
        self.cache: dict[str, str] = {}

    def __call__(self, rel: str) -> str:
        if rel not in self.cache:
            h = hashlib.sha256((self.root / rel).read_bytes()).hexdigest()[:10]
            self.cache[rel] = f"/static/{rel}?v={h}"
        return self.cache[rel]


def pct(v) -> str:
    return "—" if v is None else f"{v:g}%"


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
        self.env.globals.update(
            asset=self.assets, meta=self.meta, site_url=SITE_URL, pct=pct,
            code_text=lambda c: codes.get(c, {}).get("explain", "") if c else "",
        )
        self.pages = 0
        svg, w, h = hero_svg(self.index)
        self.hero = {"svg": svg, "w": w, "h": h}
        self.context_medians()
        self.official_by_board = self._official()

    # ------------------------------------------------------------------
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
        official = self.official_by_board.get(s["board_number"], {})
        for aid in ASSESSMENT_ORDER:
            rows = sorted(by_a.get(aid, []), key=lambda r: r["year"])
            if not rows:
                continue
            a = self.meta["assessments"][aid]
            yrs = [y for y in years_all if any(r["year"] == y for r in rows)]
            if aid.startswith("g9-math-a"):
                yrs = [y for y in years_all if y <= "2018-19"]
            elif aid == "g9-math":
                yrs = [y for y in years_all if y >= "2021-22"]
            last = rows[-1]
            summary = self.summary_sentence(s, a, last)
            off = None
            key = {"g6-reading": "g6_reading", "osslt": "osslt"}.get(aid)
            if key and key in official:
                yr = max(official[key])
                off = {"year": yr, "value": official[key][yr]["value"], "source_id": official[key][yr]["source_id"]}
            results.append({
                "id": aid, "grade": a["grade"], "subject": a["subject"], "rows": rows, "summary": summary, "official": off,
                "svg": charts.eqao_chart(rows, yrs, title=f"{a['grade']} {a['subject']}: this school, board median and Ontario median by year"),
                "codes": sorted({r["code"] for r in rows if r.get("code")}),
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
        neighbours = [self.schools[n["bsid"]] for n in s["nearby"] if n["bsid"] in self.schools]
        map_data = {
            "center": [s["lon"], s["lat"]],
            "school": {"id": s["bsid"], "n": s["name"], "sys": s["system"], "x": s["lon"], "y": s["lat"]},
            "nearby": [{"id": n["bsid"], "n": n["name"], "sys": n["system"], "x": n["lon"], "y": n["lat"], "g": n["grades"]} for n in neighbours],
            "area": s.get("nearest_area"),
        }
        addr = ", ".join(x for x in [s["address"], s["suite"], s["city"], "ON", s["postal_code"]] if x)
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
        desc = f"{s['name']} in {s['city'] or 'Ontario'} ({s['board_name']}): {s['level']} school, grades {s['grades']}. "
        if latest_eqao:
            desc += f"EQAO results {min(e['year'] for e in s['eqao'])} to {latest_eqao} next to the board and Ontario, enrolment and sources."
        else:
            desc += "Enrolment, student context, nearby schools and child care, with sources."
        self.render(f"school/{s['bsid']}/index.html", "school.html",
                    title=f"{s['name']} — {s['city'] or s['board_name']}", description=desc, page_kind="school", map=True,
                    s=s, results=results, system_label=sys_label, address_line=addr,
                    contact_label=self.sources.get("contact-2026-11", {}).get("year", "current"),
                    enrol_latest=enrol_latest, enrol_change=enrol_change,
                    enrol_svg=charts.bar_chart(enrol, title=f"Enrolment at {s['name']} by school year"),
                    latest_eqao=latest_eqao, eqao_span=f"{min(e['year'] for e in s['eqao'])} to {latest_eqao}" if latest_eqao else "",
                    context_rows=context_rows, childcare_date=human_date(s["childcare"]["snapshot"]),
                    map_json=json.dumps(map_data, separators=(",", ":")).replace("</", "<\\/"),
                    jsonld=json.dumps({k: v for k, v in jsonld.items() if v}, ensure_ascii=False).replace("</", "<\\/"))

    def summary_sentence(self, s, a, last) -> str:
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
        return "".join(parts)

    # ------------------------------------------------------------------
    def board_page(self, b: dict) -> None:
        schools = sorted((self.schools[x] for x in b["schools"] if x in self.schools), key=lambda s: s["name"])
        rows = []
        for s in schools:
            e = s["enrolment"][-1] if s["enrolment"] else None
            rows.append({"bsid": s["bsid"], "name": s["name"], "level": s["level"], "grades": s["grades"], "city": s["city"],
                         "special": s["special"], "enrol": e["value"] if e and e["year"] == b["enrolment_total"]["year"] else None})
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
        for aid in ASSESSMENT_ORDER:
            rws = sorted(med.get(aid, []), key=lambda r: r["year"])
            if not rws:
                continue
            a = self.meta["assessments"][aid]
            yrs = [y for y in years_all if any(r["year"] == y for r in rws)]
            medians.append({"grade": a["grade"], "subject": a["subject"], "rows": rws,
                            "svg": charts.eqao_chart(rws, yrs, title=f"{a['grade']} {a['subject']}: board median and Ontario median", main_key="board_median", main_label="Board median")})
        # chart helper draws board_median dashed too; blank it so only the two lines show
        for m in medians:
            m["svg"] = m["svg"].replace('class="s-board"', 'class="s-board" style="display:none"').replace('class="p-board"', 'class="p-board" style="display:none"')
        types = {"english-public": "English-language public district school board", "english-catholic": "English-language Catholic district school board",
                 "french-public": "French-language public district school board", "french-catholic": "French-language Catholic district school board",
                 "other": "Provincial school, hospital school or school authority"}
        b = {**b, "full_type": types[b["system"]]}
        map_data = {"schools": [{"id": s["bsid"], "n": s["name"], "sys": s["system"], "x": s["lon"], "y": s["lat"], "l": "E" if s["level"] == "elementary" else "S", "g": s["grades"]} for s in schools],
                    "board": b["number"], "system": b["system"]}
        self.render(f"board/{b['number']}/index.html", "board.html", title=b["name"], page_kind="board", map=True,
                    description=f"{b['name']}: {len(schools)} schools, official board results, EQAO medians across its schools and a map, with sources.",
                    b=b, schools=rows, indicators=indicators, indicator_releases=releases, headline=headline, medians=medians,
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
            groups[(s["system"], s["level"])].append({"bsid": bsid, "name": s["name"], "board_name": s["board_name"], "grades": s["grades"], "inside": inside})
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
                pts.append({"id": bsid, "n": s["name"], "sys": s["system"], "x": s["lon"], "y": s["lat"], "in": inside, "g": s["grades"], "l": "E" if s["level"] == "elementary" else "S"})
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
                    description="Map of every Ontario public school with postal areas, approximate board areas and nearest-school areas, each clearly labelled.")
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
                    datasets=ds, codes=[(k, v) for k, v in self.meta["codes"].items() if k != "BLANK"], fsa_check_rate=f"{rate:.1f}%",
                    description="Sources, licences, definitions, how withheld values are handled and how map areas are drawn.")
        self.render("about/index.html", "about.html", title="About", page_kind="about", operator=OPERATOR,
                    description="Why Ontario School Finder exists, who runs it, why it's free and how it protects your privacy.")
        self.render("corrections/index.html", "corrections.html", title="Report a correction", page_kind="corrections",
                    contact_email=CONTACT_EMAIL, corrections_url=CORRECTIONS_URL)
        downloads = []
        for name, title, desc in [
            ("schools.csv", "Schools", "One row per school: board, level, grades, address, coordinates, contact, status."),
            ("eqao.csv", "EQAO results", "Every school, assessment and year, with codes, board and Ontario medians."),
            ("enrolment.csv", "Enrolment", "Every school and year from 2011-12."),
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


def hero_svg(index: list[dict]) -> tuple[str, int, int]:
    """Dot map of every school in southern Ontario, drawn from the data.

    Written to /static/img/hero-map.svg (cached by browsers) instead of inlined: ~4,000
    dots would otherwise add ~250 KB to every home page load. Colours are mid-tones that
    read on both the light and the dark card; the legend lives in HTML so it follows the theme.
    """
    import math
    minx, maxx, miny, maxy = -83.3, -74.3, 41.9, 46.4
    kx = math.cos(math.radians((miny + maxy) / 2))  # equirectangular correction
    w = 440
    h = round(w * (maxy - miny) / ((maxx - minx) * kx))
    colors = {"english-public": "#1f8fb0", "english-catholic": "#9a5cc0", "french-public": "#d0682f", "french-catholic": "#4c9a44", "other": "#8a8f98"}
    groups: dict[str, list[str]] = {}
    for r in index:
        if not (minx <= r["x"] <= maxx and miny <= r["y"] <= maxy):
            continue
        px = (r["x"] - minx) / (maxx - minx) * w
        py = h - (r["y"] - miny) / (maxy - miny) * h
        groups.setdefault(r["sys"], []).append(f'<circle cx="{px:.0f}" cy="{py:.0f}" r="1.9"/>')
    body = "".join(f'<g fill="{colors.get(k, "#8a8f98")}">{"".join(v)}</g>' for k, v in groups.items())
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}"><g opacity=".92">{body}</g></svg>', w, h)


def copy_static_and_data() -> None:
    shutil.copytree(STATIC, DIST / "static", dirs_exist_ok=True)
    out = DIST / "data"
    out.mkdir(parents=True, exist_ok=True)
    for name in ["schools-index.json", "boards-index.json", "fsa-index.json", "meta.json", "sources.json"]:
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
        if p.is_file() and p.suffix in (".css", ".js", ".json", ".geojson", ".svg", ".xml", ".csv", ".md", ".webmanifest"):
            if p.stat().st_size < 8192 or "/data/schools/" in p.as_posix() or "/data/fsa/" in p.as_posix() or "/data/boards/" in p.as_posix():
                continue
            data = p.read_bytes()
            (p.parent / (p.name + ".gz")).write_bytes(gzip.compress(data, compresslevel=6, mtime=0))
            n += 1
    return n


def main() -> int:
    t0 = time.time()
    if not (DATA / "meta.json").exists():
        print("site/data is missing: run `python -m pipeline.build` first", file=sys.stderr)
        return 2
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    site = Site()
    for s in site.schools.values():
        site.school_page(s)
    for b in site.boards.values():
        site.board_page(b)
    for f in site.fsas.values():
        site.fsa_page(f)
    site.index_pages()
    copy_static_and_data()
    site.extras()
    (DIST / "static" / "img" / "hero-map.svg").write_text(site.hero["svg"], encoding="utf-8")
    gz = precompress()
    counts = {"school": len(list((DIST / "school").glob("*/index.html"))), "board": len(list((DIST / "board").glob("*/index.html"))),
              "fsa": len(list((DIST / "fsa").glob("*/index.html")))}
    (DIST / "build.json").write_text(json.dumps({"built": datetime.now().isoformat(timespec="seconds"), "pages": site.pages, **counts}), encoding="utf-8")
    print(f"generated {site.pages} pages ({counts}) and {gz} gzip files in {time.time() - t0:.1f}s -> {DIST}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
