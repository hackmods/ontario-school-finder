"""Family-facing views built from the pipeline output and the hand-checked board records.

Kept apart from generate.py so the rules are small, testable functions:
- `grades_offered` reads the Ministry's grade range ("JK-8") into the grades a school offers;
- `program_badges` is the one program vocabulary used on school pages, board lists and Compare
  (lib.js has the same labels for search results and map popups; a test keeps them in step);
- `BoardInfo` serves the records in site/board-info.json to each school by board, level and program;
- `visit_questions` turns verified facts into questions to ask on a visit. No model, no guessing.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

GRADE_ORDER = ["JK", "K"] + [str(i) for i in range(1, 13)]
GRADE_LABEL = {"JK": "Junior kindergarten", "K": "Senior kindergarten", **{str(i): f"Grade {i}" for i in range(1, 13)}}

# One program vocabulary everywhere (keep in step with PROGRAM_LABELS in site/static/js/lib.js).
PROGRAM_LABELS = {
    "french-language": "French-language school",
    "french-immersion": "French Immersion",
    "extended-french": "Extended French",
    "shsm": "Specialist High Skills Major",
}
PROGRAM_HELP = {
    "french-language": "A school of a French-language board: students learn in French all day. This is French-language education, not French as a second language.",
    "french-immersion": "French as a second language in an English-language school: most subjects taught in French, at least half of the day.",
    "extended-french": "French as a second language in an English-language school: some subjects taught in French, at least a quarter of the day.",
    "shsm": "A bundle of high-school courses, certifications and work experience in one career sector, recorded on the diploma.",
}

# How a missing value is described (never collapse these into "No" or an unexplained dash).
COVERAGE = {
    "reported": "Reported",
    "suppressed": "Withheld to protect privacy",
    "not_applicable": "Not applicable",
    "not_published": "Not published by the source",
    "not_collected": "Not yet collected for this board",
    "match_unresolved": "Source match unresolved",
    "historical": "Historical only",
}


def grades_offered(grade_range: str | None) -> list[str] | None:
    """'JK-8' -> ['JK', 'K', '1', ..., '8']; None when the range is missing or unreadable (unknown, not "none")."""
    if not grade_range:
        return None
    m = re.fullmatch(r"\s*(JK|SK|K|\d{1,2})\s*-\s*(JK|SK|K|\d{1,2})\s*", grade_range.upper())
    if not m:
        return None
    lo, hi = (("K" if g == "SK" else g) for g in m.groups())
    if lo not in GRADE_ORDER or hi not in GRADE_ORDER:
        return None
    i, j = GRADE_ORDER.index(lo), GRADE_ORDER.index(hi)
    return GRADE_ORDER[i:j + 1] if i <= j else None


def grade_span_label(grade_range: str | None) -> str:
    g = grades_offered(grade_range)
    if not g:
        return "Grades not listed in the Ministry's file"
    first = "Junior kindergarten" if g[0] == "JK" else "Senior kindergarten" if g[0] == "K" else f"Grade {g[0]}"
    return f"{first} to Grade {g[-1]}" if g[-1] not in ("JK", "K") else first


def program_badges(s: dict, board_listed: dict | None = None) -> list[dict]:
    """Badges for a school's programs, each with where it came from. board_listed: {program: entry} from board-info."""
    out = []
    if s.get("language") == "French":
        out.append({"key": "french-language", "label": PROGRAM_LABELS["french-language"], "source": "Ministry school list"})
    f = (s.get("programs") or {}).get("fsl") or {}
    bl = board_listed or {}
    if f.get("immersion") or "french-immersion" in bl:
        src = []
        if f.get("immersion"):
            src.append(f"Ministry FSL list {f.get('year')}")
        if "french-immersion" in bl:
            src.append("board's list")
        out.append({"key": "french-immersion", "label": PROGRAM_LABELS["french-immersion"], "source": " and ".join(src),
                    "ministry_missing": "french-immersion" in bl and not f.get("immersion")})
    if f.get("extended"):
        out.append({"key": "extended-french", "label": PROGRAM_LABELS["extended-french"], "source": f"Ministry FSL list {f.get('year')}"})
    sh = (s.get("programs") or {}).get("shsm")
    if sh:
        n = len(sh["sectors"])
        out.append({"key": "shsm", "label": f"SHSM · {n} sector{'' if n == 1 else 's'}", "source": f"Ministry SHSM list {sh.get('year')}"})
    return out


class BoardInfo:
    """site/board-info.json, served per school. Records are inherited from the board, filtered by the
    school's level (and program, for program records), plus anything recorded for the school itself."""

    TOPICS = ["registration", "address_lookup", "program", "transfer", "transportation", "special_education", "seac",
              "accessibility", "newcomer", "planning", "achievement_plan", "involvement", "concerns"]

    def __init__(self, path: Path, today: date | None = None):
        self.raw = json.loads(path.read_text(encoding="utf-8"))
        self.today = today or date.today()
        self.refresh = self.raw.get("refresh_days", {})
        self.boards = self.raw.get("boards", {})
        self.schools = self.raw.get("schools", {})
        self.decisions = self.raw.get("decisions", [])
        self.lists = {k: v for k, v in self.raw.get("school_programs", {}).items() if not k.startswith("_")}

    def stale(self, rec: dict) -> bool:
        """True when a record is older than its lifecycle allows (deadlines go stale faster than rules)."""
        days = self.refresh.get(rec.get("lifecycle", "rules"), 365)
        return (self.today - date.fromisoformat(rec["verified"])).days > days

    def has_board(self, board: str) -> bool:
        return board in self.boards

    def board_listed(self, s: dict) -> dict:
        """{program: {title, url, name_on_list, verified}} for programs the school's board lists it under."""
        out = {}
        lst = self.lists.get(s["board_number"])
        if lst and s["bsid"] in lst["schools"]:
            out[lst["program"]] = {"title": lst["title"], "url": lst["url"], "name_on_list": lst["schools"][s["bsid"]], "verified": lst["verified"]}
        return out

    def for_board(self, board: str) -> dict:
        b = self.boards.get(board)
        if not b:
            return {}
        by_topic: dict[str, list] = {}
        for r in b["records"]:
            by_topic.setdefault(r["topic"], []).append({**r, "stale": self.stale(r)})
        return {"name": b["name"], "short": b.get("short") or b["name"], "topics": by_topic}

    def for_school(self, s: dict, offered: set[str]) -> dict:
        """Records for one school: board records for its level (program records only for programs it offers),
        the school's own records, and board decisions that name it."""
        b = self.boards.get(s["board_number"])
        by_topic: dict[str, list] = {}
        if b:
            for r in b["records"]:
                if s["level"] not in r.get("applies", ["elementary", "secondary"]):
                    continue
                if r.get("program") and r["program"] not in offered:
                    continue
                by_topic.setdefault(r["topic"], []).append({**r, "stale": self.stale(r), "scope": "board"})
        for r in (self.schools.get(s["bsid"]) or {}).get("records", []):
            by_topic.setdefault(r["topic"], []).append({**r, "stale": self.stale(r), "scope": "school"})
        for d in self.decisions:
            if s["bsid"] in d["schools"]:
                by_topic.setdefault(d["topic"], []).append({**d, "stale": self.stale(d), "scope": "school"})
        return {"collected": bool(b), "board_name": b["name"] if b else s["board_name"], "topics": by_topic,
                "checked": self.raw.get("checked")}


def visit_questions(s: dict, *, info: dict, badges: list[dict], offered: list[str] | None, class_status: dict | None,
                    has_childcare_here: bool, sq: list[dict]) -> list[str]:
    """Questions to ask the school or board, built only from facts on the page. Deterministic and short."""
    q = []
    keys = {b["key"] for b in badges}
    topics = info.get("topics", {})
    if offered:
        q.append(f"Which grades will the school offer next year, and is there room in the grade my child is entering? "
                 f"(The Ministry lists {offered[0] if offered[0] not in ('JK', 'K') else 'kindergarten'} to Grade {offered[-1]}.)")
    if "french-immersion" in keys:
        prog = topics.get("program") or []
        entry = next((r.get("facts", {}).get("entry_grades") for r in prog if r.get("facts", {}).get("entry_grades")), None)
        when = f" (the board's entry grade is Grade {entry[0]})" if entry else ""
        q.append(f"How do families apply for French Immersion{when}, when is the registration window, and is there a waitlist?")
        q.append("If my child lives outside this school's area, is transportation provided to the Immersion program?")
    if topics.get("transfer"):
        q.append("If we want a school other than our area school, how do we ask, by when, and who decides?")
    else:
        q.append("Is this the school for our address? How are requests to attend another school handled?")
    if has_childcare_here:
        q.append("How do we register for the child care at the school, and is there before- and after-school care for my child's age?")
    else:
        q.append("Is there before- and after-school care nearby, and how do families register?")
    q.append("How does the school arrange support if my child needs extra help (including an IEP or an IPRC), and who do we speak to first?")
    if any(r.get("kind") in ("decision", "projection", "proposal") for r in topics.get("planning", [])):
        q.append("The board has published plans or decisions that mention this school. What do they mean for my child's grade and program?")
    if class_status and class_status.get("status") == "reported":
        q.append("How many classes combine grades this year, and what is the class size for my child's grade?")
    if any(not b.get("withheld") for b in sq):
        q.append("What does the school do with what students said in EQAO's questionnaire (for example, how prepared they feel for next year)?")
    return q[:8]
