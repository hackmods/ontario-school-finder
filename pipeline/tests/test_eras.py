"""EQAO assessment eras: no trend, chart line or "change since" may cross the 2021-22 break."""
import sys
import types
from pathlib import Path

from pipeline import eras

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "site"))
import generate  # noqa: E402


def test_era_boundaries():
    assert eras.era_of("g6-math", "2018-19") == "paper"
    assert eras.era_of("g6-math", "2016-17") == "paper"
    assert eras.era_of("g6-math", "2021-22") == "current"
    assert eras.era_of("osslt", "2025-26") == "current"
    # Grade 9 academic/applied were separate courses: always the earlier era, whatever the year label
    assert eras.era_of("g9-math-academic", "2021-22") == "paper"
    assert eras.era_of("g9-math-applied", "2017-18") == "paper"
    assert not eras.same_era("g3-reading", "2018-19", "2021-22")
    assert eras.same_era("g3-reading", "2021-22", "2025-26")


def test_era_meta_cites_eqao():
    m = eras.meta()
    assert m["current_from"] == "2021-22"
    assert m["evidence"] and all(e["url"].startswith("https://www.eqao.com/") for e in m["evidence"])


def row(year, v, era):
    return {"year": year, "pct_at_or_above_standard": v, "board_median": None, "province_median": None, "era": era}


def summary(rows):
    fake = types.SimpleNamespace(meta={"codes": {}})
    a = {"grade": "Grade 6", "subject": "Mathematics"}
    return generate.Site.summary_sentence(fake, {}, a, rows[-1], rows)


def test_summary_never_measures_change_across_eras():
    # the review's example: a "Down 14 points since 2016-17" sentence must not come back
    rows = [row("2016-17", 79, "paper"), row("2018-19", 70, "paper"), row("2021-22", 64, "current"), row("2025-26", 65, "current")]
    text = summary(rows)
    assert "2016-17" not in text and "2018-19" not in text
    assert "1 point higher than in 2021-22" in text
    assert "different group of students" in text


def test_summary_with_one_current_year_has_no_change():
    text = summary([row("2018-19", 70, "paper"), row("2025-26", 65, "current")])
    assert "higher" not in text and "lower" not in text and "since" not in text


def test_summary_of_suppressed_latest_year_keeps_the_code():
    fake = types.SimpleNamespace(meta={"codes": {"N/R": {"explain": "Not reported."}}})
    last = {"year": "2025-26", "pct_at_or_above_standard": None, "code": "N/R", "era": "current"}
    text = generate.Site.summary_sentence(fake, {}, {"grade": "Grade 3", "subject": "Reading"}, last, [last])
    assert "N/R" in text and "%" not in text
