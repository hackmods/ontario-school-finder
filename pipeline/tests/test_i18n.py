"""French catalogue: fragments parse, keep every placeholder and tag, and agree with each other."""
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "site"))
import i18n  # noqa: E402

FRAGMENTS = sorted((ROOT / "site" / "i18n" / "fr").glob("*.json"))
PLACE = re.compile(r"\{(\w+)\}")
TAG = re.compile(r"</?([a-z]+)\b")


def entries(p):
    return {k: v for k, v in json.loads(p.read_text(encoding="utf-8")).items() if not k.startswith("_")}


@pytest.mark.parametrize("path", FRAGMENTS, ids=lambda p: p.stem)
def test_fragment_keeps_placeholders_and_tags(path):
    for en, fr in entries(path).items():
        assert isinstance(fr, str) and fr.strip(), f"{path.name}: empty French for {en!r}"
        assert sorted(PLACE.findall(en)) == sorted(PLACE.findall(fr)), f"{path.name}: placeholders differ in {en!r}"
        assert sorted(TAG.findall(en)) == sorted(TAG.findall(fr)), f"{path.name}: tags differ in {en!r}"


def test_fragments_agree_with_each_other():
    seen = {}
    for p in FRAGMENTS:
        for en, fr in entries(p).items():
            if en in seen and seen[en][1] != fr:
                pytest.fail(f"{en!r}: {seen[en][0]} says {seen[en][1]!r}, {p.name} says {fr!r}")
            seen[en] = (p.name, fr)


def test_links_and_fallback():
    lang = i18n.Lang("fr")
    assert lang.url("/school/123/") == "/fr/school/123/"
    assert lang.url("/data/x.json") == "/data/x.json" and lang.url("https://x.ca/") == "https://x.ca/"
    assert lang.other("/fr/school/123/") == "/school/123/" and lang.other("/fr/") == "/"
    assert i18n.Lang("en").other("/school/123/") == "/fr/school/123/"
    assert lang("a string nobody translated") == "a string nobody translated" and "a string nobody translated" in lang.missing
    assert str(lang.html("<b>{x}</b>", x="<i>")) == "<b>&lt;i&gt;</b>"  # arguments are escaped, our markup isn't


def test_every_board_record_has_french():
    """Each record shown on a school or board page has a French summary (hand-translated, or generated for capacity)."""
    folder = ROOT / "site" / "board-info"
    missing = []
    for p in sorted(folder.glob("B*.json")):
        b = json.loads(p.read_text(encoding="utf-8"))
        fr = {}
        for q in (folder / "fr" / p.name, folder / "fr" / "capacity" / p.name):
            if q.exists():
                fr.update(json.loads(q.read_text(encoding="utf-8")))
        recs = b["records"] + b.get("decisions", []) + [r for s in b.get("schools", {}).values() for r in s["records"]]
        missing += [f"{p.stem}:{r['id']}" for r in recs if not (fr.get(r["id"]) or {}).get("summary")]
    assert not missing, f"{len(missing)} records without French, e.g. {missing[:5]}"


@pytest.mark.parametrize("lang,n,pct,money", [("en", "1,234", "4.5%", "$12,346"), ("fr", "1 234", "4,5 %", "12 346 $")])
def test_numbers_follow_the_language(lang, n, pct, money):
    i18n.use(lang)
    try:
        assert i18n.num(1234) == n and i18n.pct(4.5) == pct and i18n.money(12345.6) == money
        assert i18n.pct("<1").startswith("<1") and i18n.num(None) == ""
    finally:
        i18n.use("en")


def test_plan_dates_follow_the_language():
    import generate  # noqa: E402 (site/ is on the path above)
    try:
        i18n.use("fr")
        assert generate.date_text("October 31, 2023") == "31 octobre 2023"
        assert generate.date_text("September 1, 2025") == "1er septembre 2025"
        assert generate.date_text("June 2024") == "juin 2024" and generate.date_text("2024-25") == "2024-25"
        assert generate.date_text("current") == "actuel (sans date)"
        assert generate.grades_text("JK-8") == "M-8" and generate.grades_text("SK-3") == "JE-3"
        i18n.use("en")
        assert generate.date_text("October 31, 2023") == "October 31, 2023" and generate.grades_text("JK-8") == "JK-8"
    finally:
        i18n.use("en")
