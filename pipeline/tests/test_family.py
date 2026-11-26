"""Family-facing rules: grades offered, one program vocabulary, board records inherited by schools, and
the hand-checked site/board-info.json itself."""
import json
import re
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "site"))
import family  # noqa: E402

INFO = ROOT / "site" / "board-info.json"


@pytest.mark.parametrize("rng,expect", [
    ("JK-8", ["JK", "K", "1", "2", "3", "4", "5", "6", "7", "8"]),
    ("1-8", ["1", "2", "3", "4", "5", "6", "7", "8"]),  # an Immersion school with no kindergarten
    ("9-12", ["9", "10", "11", "12"]),
    ("K-8", ["K", "1", "2", "3", "4", "5", "6", "7", "8"]),
    ("7-8", ["7", "8"]),
    ("SK-3", ["K", "1", "2", "3"]),
])
def test_grades_offered(rng, expect):
    assert family.grades_offered(rng) == expect


@pytest.mark.parametrize("rng", [None, "", "Grades vary", "8-1"])
def test_unknown_grades_are_unknown_not_none(rng):
    assert family.grades_offered(rng) is None
    assert "not listed" in family.grade_span_label(rng)


def test_opened_label_does_not_pretend_1969_is_an_opening_date():
    assert family.opened_label("1969-09-01") == "1969 or earlier"
    assert family.opened_label("2016-09-06") == "2016"
    assert family.opened_label(None) is None


def school(**kw):
    return {"bsid": "456110", "board_number": "B66150", "board_name": "DSB Niagara", "level": "elementary", "language": "English",
            "programs": {"fsl": None, "shsm": None}, **kw}


def test_program_vocabulary_keeps_french_language_and_immersion_apart():
    fr = family.program_badges(school(language="French"))
    assert [b["key"] for b in fr] == ["french-language"]
    fi = family.program_badges(school(programs={"fsl": {"immersion": True, "extended": False, "core": False, "year": "2024-25"}, "shsm": None}))
    assert [b["label"] for b in fi] == ["French Immersion"] and "Ministry FSL list" in fi[0]["source"]


def test_board_list_counts_when_the_ministry_list_misses_a_school():
    # DSBN lists Bridgeview as a French Immersion school; the Ministry's preliminary list doesn't
    b = family.program_badges(school(programs={"fsl": {"immersion": False, "extended": False, "core": True, "year": "2024-25"}, "shsm": None}),
                              {"french-immersion": {"url": "https://example.invalid"}})
    assert b[0]["key"] == "french-immersion" and b[0]["ministry_missing"] is True and b[0]["source"] == "board's list"


def test_program_labels_match_the_browser_copy():
    js = (ROOT / "site" / "static" / "js" / "lib.js").read_text(encoding="utf-8")
    block = re.search(r"export const PROGRAM_LABELS = \{(.*?)\};", js, re.S).group(1)
    pairs = dict(re.findall(r'"?([\w-]+)"?:\s*"([^"]+)"', block))
    assert pairs == family.PROGRAM_LABELS


@pytest.fixture(scope="module")
def info():
    return family.BoardInfo(INFO, today=date(2026, 11, 27))


def test_records_are_inherited_by_level_and_program(info):
    elem_fi = info.for_school(school(), {"french-immersion"})
    topics = elem_fi["topics"]
    assert elem_fi["collected"] is True
    assert [r["id"] for r in topics["program"]] == ["dsbn-fi"]  # the elementary FI record, not the secondary one
    assert any(r["id"] == "dsbn-ltap-prince-philip-nf" and r["scope"] == "school" for r in topics["planning"])
    plain = info.for_school({**school(), "bsid": "000001"}, set())
    assert "program" not in plain["topics"]  # no program records for a school that doesn't offer the program
    sec = info.for_school({**school(), "bsid": "890200", "level": "secondary"}, {"french-immersion"})
    assert [r["id"] for r in sec["topics"]["program"]] == ["dsbn-fi-secondary"]
    other = info.for_school({**school(), "bsid": "000002", "board_number": "B99999"}, set())
    assert other["collected"] is False and other["topics"] == {}


def test_approved_decision_reaches_the_schools_it_names(info):
    s = {**school(), "bsid": "694304", "board_number": "B67156", "board_name": "Niagara CDSB"}
    plan = info.for_school(s, set())["topics"]["planning"]
    d = next(r for r in plan if r["kind"] == "decision")
    assert d["decided"] == "2026-06-16" and d["scope"] == "school"


def test_dates_go_stale_before_rules(info):
    assert info.stale({"verified": "2026-06-01", "lifecycle": "dates"}) is True
    assert info.stale({"verified": "2026-06-01", "lifecycle": "rules"}) is False


KINDS = {"rule", "process", "decision", "proposal", "projection", "plan", "not_found"}


def all_records(raw):
    for b in raw["boards"].values():
        yield from b["records"]
    for s in raw["schools"].values():
        yield from s["records"]
    yield from raw["decisions"]


def test_board_info_schema():
    raw = json.loads(INFO.read_text(encoding="utf-8"))
    ids = set()
    for r in all_records(raw):
        assert r["id"] not in ids, f"duplicate id {r['id']}"
        ids.add(r["id"])
        assert r["topic"] in family.BoardInfo.TOPICS, r["id"]
        assert r["kind"] in KINDS, r["id"]
        assert r["url"].startswith("https://"), r["id"]
        assert date.fromisoformat(r["verified"]) <= date.today(), r["id"]
        assert 40 <= len(r["summary"]) <= 600, f"{r['id']}: summary should be a few plain sentences"
        assert r.get("lifecycle", "rules") in raw["refresh_days"], r["id"]
        for x in r.get("related", []):
            assert x["url"].startswith("https://") and x["title"], r["id"]
        for lv in r.get("applies", []):
            assert lv in ("elementary", "secondary"), r["id"]
    for d in raw["decisions"]:
        assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", d["decided"]) and d["schools"] and d["match"]
    for board, lst in ((k, v) for k, v in raw["school_programs"].items() if not k.startswith("_")):
        assert board in raw["boards"] and lst["url"].startswith("https://") and lst["schools"]
        assert all(re.fullmatch(r"\d{6}", b) for b in lst["schools"])


def test_board_info_schools_exist_in_the_data():
    data = ROOT / "site" / "data" / "schools"
    if not data.exists():
        pytest.skip("site/data not built yet")
    raw = json.loads(INFO.read_text(encoding="utf-8"))
    named = set(raw["schools"]) | {b for d in raw["decisions"] for b in d["schools"]}
    named |= {b for k, v in raw["school_programs"].items() if not k.startswith("_") for b in v["schools"]}
    for bsid in named:
        p = data / f"{bsid}.json"
        assert p.exists(), f"board-info.json names school {bsid}, which isn't in the data"


def test_visit_questions_are_built_from_page_facts(info):
    s = {**school(), "childcare": {"at_address": [{"name": "x"}]}}
    badges = family.program_badges({**s, "programs": {"fsl": {"immersion": True, "core": False, "extended": False, "year": "2024-25"}, "shsm": None}})
    qs = family.visit_questions(s, info=info.for_school(s, {"french-immersion"}), badges=badges, offered=["1", "2", "8"],
                                class_status={"status": "match_unresolved"}, has_childcare_here=True, sq=[])
    text = " ".join(qs)
    assert "Grade 1" in text and "French Immersion" in text and "child care at the school" in text
    assert len(qs) <= 8
