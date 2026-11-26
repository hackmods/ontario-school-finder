"""Writes pipeline/report.md: what came in, what was skipped, and every data gap we found."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone

from . import sources


class Report:
    def __init__(self) -> None:
        self.counts: list[tuple[str, int, str]] = []
        self.suppressed: dict[str, dict] = {}
        self.skipped: list[dict] = []
        self.notes: list[str] = []
        self.missing_coords: dict = {}
        self.fsa_mismatches: list[dict] = []
        self.fsa_checked = 0
        self.layers: dict = {}
        self.boards_without_area: list[str] = []
        self.childcare_at_school = 0
        self.relocated: list[dict] = []
        self.class_size: dict = {}
        self.elapsed = 0

    def count(self, source_id: str, n: int, what: str) -> None:
        self.counts.append((source_id, n, what))

    def skip(self, key: str, ds: dict) -> None:
        self.skipped.append({"key": key, "brief_no": ds["brief_no"], "title": ds["title"], "status": ds["status"], "why": ds["used_for"]})

    def note(self, msg: str) -> None:
        self.notes.append(msg)

    def write(self, path, *, schools, boards, fsas, sources_table) -> None:
        L: list[str] = []
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        L += ["# Pipeline report", "", f"Generated {now} in {self.elapsed} s.", ""]
        L += ["## Output", "", f"- Schools: **{len(schools)}**", f"- Boards: **{len(boards)}**", f"- Postal areas (FSAs): **{len(fsas)}**", ""]
        lv = Counter(s["level"] for s in schools)
        sy = Counter(s["system"] for s in schools)
        L += [f"- By level: " + ", ".join(f"{k} {v}" for k, v in sorted(lv.items())),
              f"- By system: " + ", ".join(f"{k} {v}" for k, v in sorted(sy.items())), ""]

        L += ["## Records per source", "", "| source_id | records | what | retrieved | URL |", "|---|---:|---|---|---|"]
        for sid, n, what in self.counts:
            t = sources_table.get(sid, {})
            L.append(f"| {sid} | {n} | {what} | {t.get('retrieved') or ''} | {t.get('url') or ''} |")
        L.append("")

        L += ["## Sources skipped or deferred", ""]
        for s in self.skipped:
            L.append(f"- **#{s['brief_no']} {s['title']}** ({s['status']}): {s['why']}")
        L.append("")
        if self.notes:
            L += ["## Notes", ""] + [f"- {n}" for n in self.notes] + [""]

        mc = self.missing_coords
        L += ["## Coordinates", "",
              f"- Taken from an earlier year of the same source: {mc.get('from_earlier_years', 0)}",
              f"- Geocoded (flagged `geocoded: true`): {mc.get('geocoded', 0)}",
              f"- Schools left out because no location could be found: {len(mc.get('excluded', []))}"]
        for e in mc.get("excluded", []):
            L.append(f"  - {e['bsid']} {e['name']}: {e['reason']}")
        if self.relocated:
            L.append(f"- Moved to their street address because source coordinates were over 1 km outside their own postal area: {len(self.relocated)}")
            for m in self.relocated:
                L.append(f"  - {m['bsid']} {m['name']}: {m['off_km']} km off; now at {m['match']}")
        geocoded = [s for s in schools if s["geocoded"] and not s.get("coord_note")]
        for s in geocoded:
            L.append(f"  - geocoded {s['bsid']} {s['name']} ({s['geocode_precision']})")
        L.append("")

        checked = self.fsa_checked
        mism = self.fsa_mismatches
        rate = 100 * (checked - len(mism)) / checked if checked else 0
        L += ["## FSA check (postal code vs. the FSA polygon containing the school's point)", "",
              f"- Checked: {checked}; matching: {checked - len(mism)} (**{rate:.2f}%**); mismatches: {len(mism)}", ""]
        if mism:
            L += ["| bsid | school | postal-code FSA | polygon FSA |", "|---|---|---|---|"]
            L += [f"| {m['bsid']} | {m['name']} | {m['postal_fsa']} | {m['polygon_fsa'] or '(outside every FSA)'} |" for m in mism]
            L.append("")

        L += ["## Suppressed and coded values", "", "Codes are stored as `null` with a flag, never as 0.", "",
              "| source_id | counts |", "|---|---|"]
        for sid, d in self.suppressed.items():
            if d:
                L.append(f"| {sid} | " + ", ".join(f"{k}: {v}" for k, v in sorted(d.items())) + " |")
        L.append("")

        L += ["## Map layers", ""]
        st = self.layers
        if st:
            L.append(f"- FSA polygons: {st.get('fsa_polygons')} ({st.get('fsa_bytes', 0) // 1024} KB)")
            L.append(f"- Approximate board areas: {len(st.get('boards', {}))} boards ({st.get('board_bytes', 0) // 1024} KB)")
            for k, v in st.get("voronoi", {}).items():
                L.append(f"- Nearest-school areas {k}: {v['cells']} cells for {v['schools']} schools ({v['shared_sites']} shared buildings), {v['bytes'] // 1024} KB")
        if self.boards_without_area:
            L.append(f"- Boards with regular schools but no area polygon: {', '.join(self.boards_without_area)}")
        L.append("")
        cs = self.class_size
        if cs:
            L += ["## Class sizes (matched to schools by board and school name)", "",
                  f"- Class-list rows matched to a school: {cs['matched']} school-years; ambiguous names skipped: {cs['ambiguous']}",
                  f"- Schools with class sizes: {cs['schools_with_class_sizes']}",
                  "- Unmatched school-years by year (closed or renamed schools, private/other boards): "
                  + ", ".join(f"{y}: {n}" for y, n in cs["unmatched_by_year"].items()), ""]
        L += ["## Other gaps", "",
              f"- Schools with a licensed child care site at the same address: {self.childcare_at_school}",
              f"- Schools not in the current contact list: {sum(1 for s in schools if s['status'] != 'open')}",
              f"- Schools with no EQAO rows at all: {sum(1 for s in schools if not s['eqao'])}",
              f"- FSAs without census figures: {sum(1 for f in fsas.values() if not f['census'])}",
              f"- FSAs with no school inside: {sum(1 for f in fsas.values() if not f['in'])}", ""]
        path.write_text("\n".join(L) + "\n", encoding="utf-8")
