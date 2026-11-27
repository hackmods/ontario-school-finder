"""EQAO student questionnaire loader: exact wording from the definitions, withheld values kept, nothing inferred."""
import csv
import io
import zipfile

import openpyxl
import pytest

from pipeline import config, loaders
from pipeline.fetch import SchemaChanged

OPTS3 = {1: "No, I do not agree", 2: "I am not sure", 3: "Yes, I agree", 9: "Response missing"}
G36_QUESTIONS = {  # field stem (with base) -> question text, as EQAO's definitions phrase it
    "R_Interest_LikeRead": ("Reading", "I like to read"),
    "R_Confidence_GoodReader": ("Reading", "I am a good reader"),
    "M_Interest_LikeMath": ("Mathematics", "I like math"),
    "M_Confidence_GoodAtMath": ("Mathematics", "I am good at math"),
    "R_Persevere_KeepTrying": ("Reading", "I keep trying if I make a mistake or if something is difficult"),
    "R_Group_WorkWell": ("Reading", "I work well in a group with other students"),
    # R_Persevere_FeelPrepared deliberately missing: Grade 3 isn't asked it
}


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW", tmp_path / "raw")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "manifest.json")
    (tmp_path / "raw").mkdir()
    return tmp_path / "raw"


def write_defs(path, questions=G36_QUESTIONS, header=("File", "Field Position", "Field Name", "Definition", "G3 File", "G6 File", "Comment")):
    wb = openpyxl.Workbook()
    wb.active.title = "1.Field Descriptions"
    ws = wb.create_sheet("2.Field Descriptions - SQ")
    ws.append(["Table showing Field Definitions"])
    ws.append(list(header))
    for stem, (subject, q) in questions.items():
        for c, opt in OPTS3.items():
            ws.append(["G[3/6]_2026_SQ_1", 1, f"cnt{stem}{c}", f"Number of fully participating students in {subject}, {q}, {opt}", "x", "x", "R-Q1"])
            ws.append(["G[3/6]_2026_SQ_5", 1, f"pct{stem}{c}", f"Percentage of fully participating students in {subject}, {q}, {opt}", "x", "x", "R-Q1"])
    wb.save(path)


ID = ["OrgID", "OrgType", "Language", "Grade", "ApplySuppression", "BoardMident", "BoardName", "SchoolMident", "SchoolName", "FundingType", "Suppressed", "cntSQRespondents"]


def org(oid, otype, board="66150", school="", suppressed="0", lang="en"):
    return {"OrgID": oid, "OrgType": otype, "Language": lang, "Grade": "6", "ApplySuppression": "1", "BoardMident": board, "BoardName": "DSB Niagara",
            "SchoolMident": school, "SchoolName": "x", "FundingType": "1", "Suppressed": suppressed, "cntSQRespondents": "43"}


def counts(stem, c, suppressed=False):
    """cnt columns for one question (split over two CSVs like EQAO's own files)."""
    if suppressed:
        return {f"cnt{stem}{k}": "N/R" for k in (1, 2, 3, 9)}, {f"pct{stem}{k}": "N/R" for k in (1, 2, 3, 9)}
    n = sum(c)
    return ({f"cnt{stem}{k}": str(v) for k, v in zip((1, 2, 3, 9), c)},
            {f"pct{stem}{k}": f"{round(100 * v / n)}%" for k, v in zip((1, 2, 3, 9), c)})


def write_zip(path, rows):
    """rows: list of (id dict, {stem: counts or 'withheld'}). cnt columns go in SQ_1, pct columns in SQ_5."""
    f1, f5 = [], []
    for ident, answers in rows:
        a1, a5 = dict(ident), dict(ident)
        for stem, c in answers.items():
            cnt, pct = counts(stem, c, suppressed=(c == "withheld"))
            a1.update(cnt)
            a5.update(pct)
        f1.append(a1)
        f5.append(a5)
    with zipfile.ZipFile(path, "w") as z:
        for name, recs in (("G6_2026_SQ_1.csv", f1), ("G6_2026_SQ_5.csv", f5)):
            buf = io.StringIO()
            w = csv.DictWriter(buf, fieldnames=list(recs[0]))
            w.writeheader()
            w.writerows(recs)
            z.writestr(f"Grade-6/{name}", buf.getvalue())


RES = {"id": "eqao-sq-test", "year": "2025-26", "kind": "g36", "grade": "6", "url": "https://example.invalid/sq.zip",
       "definitions": "https://example.invalid/defs.xlsx"}
ALL = {stem: (7, 12, 24, 0) for stem in G36_QUESTIONS}


def test_loader_reads_school_board_province_and_keeps_withheld(raw_dir):
    write_defs(raw_dir / "eqao-sq-test-defs.xlsx")
    write_zip(raw_dir / "eqao-sq-test.zip", [
        (org("1", "P", board="", lang="en"), ALL),
        (org("2", "B"), ALL),
        (org("3", "S", school="56110"), ALL),  # leading zero dropped in the file: still school 056110
        (org("4", "S", school="455989", suppressed="1"), {stem: "withheld" for stem in G36_QUESTIONS}),
    ])
    d = loaders.load_eqao_sq(RES)
    assert set(d["schools"]) == {"056110", "455989"}
    assert "B66150" in d["boards"] and "English" in d["province"]
    item = d["schools"]["056110"]["items"]["like_read"]
    assert item["n"] == 43 and item["counts"] == [7, 12, 24, 0]
    assert item["agree_pct"] == 56 and item["agree_derived"] is False  # EQAO's published "Yes, I agree" share
    # withheld: a code, no number, nothing inferred from the board or province
    w = d["schools"]["455989"]
    assert w["withheld"] is True
    assert all(v.get("agree_pct") is None and v["code"] == "N/R" for v in w["items"].values())
    # the exact question wording comes from EQAO's definitions
    assert d["questions"]["keep_trying"]["question"] == "I keep trying if I make a mistake or if something is difficult"
    assert d["questions"]["like_read"]["options"] == list(OPTS3.values())
    # a question this grade isn't asked is recorded as not asked, never filled in
    assert d["not_asked"] == ["feel_prepared"] and "feel_prepared" not in d["questions"]


def test_five_point_scale_adds_somewhat_and_strongly_agree(raw_dir, monkeypatch):
    # Grade 9 / OSSLT: five answers; "agree" = somewhat + strongly, counted from EQAO's numbers and flagged as derived
    monkeypatch.setitem(loaders.SQ_ITEMS, "g9", [("like_math", "", "Interest_LikeMath", "Like math")] * 1
                        + [("good_math", "", "Confidence_GoodAtMath", "x"), ("keep_trying", "", "Persevere_KeepTrying", "x")])
    opts5 = {1: "Strongly disagree", 2: "Somewhat disagree", 3: "Neither agree nor disagree", 4: "Somewhat agree", 5: "Strongly agree", 9: "Response missing"}
    wb = openpyxl.Workbook()
    ws = wb.create_sheet("2.Field Descriptions - SQ")
    ws.append(["File", "Field Position", "Field Name", "Definition", "Question #"])
    stems = ["Interest_LikeMath", "Confidence_GoodAtMath", "Persevere_KeepTrying"]
    for stem in stems:
        for c, o in opts5.items():
            ws.append(["G9_2026_SQ_1", 1, f"cnt{stem}{c}", f"Number of fully participating students, I like it, {o}", "Q05a"])
    wb.save(raw_dir / "eqao-sq-g9t-defs.xlsx")
    rec = org("3", "S", school="123456")
    for stem in stems:
        for c, v in zip((1, 2, 3, 4, 5, 9), (1, 2, 3, 4, 10, 0)):
            rec[f"cnt{stem}{c}"] = str(v)
            rec[f"pct{stem}{c}"] = f"{round(100 * v / 20)}%"
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=list(rec))
    w.writeheader()
    w.writerow(rec)
    with zipfile.ZipFile(raw_dir / "eqao-sq-g9t.zip", "w") as z:
        z.writestr("G9/G9_2026_SQ_1.csv", buf.getvalue())
    d = loaders.load_eqao_sq({**RES, "id": "eqao-sq-g9t", "kind": "g9", "grade": "9"})
    it = d["schools"]["123456"]["items"]["like_math"]
    assert it["agree_n"] == 14 and it["agree_pct"] == 70 and it["agree_derived"] is True
    assert d["questions"]["like_math"]["agree"] == ["Somewhat agree", "Strongly agree"]


def test_changed_question_fails_loudly(raw_dir):
    # the definitions no longer describe a question the data still has: stop, don't guess the wording
    qs = dict(G36_QUESTIONS)
    del qs["R_Interest_LikeRead"]
    write_defs(raw_dir / "eqao-sq-test-defs.xlsx", questions=qs)
    write_zip(raw_dir / "eqao-sq-test.zip", [(org("3", "S", school="456110"), ALL)])
    with pytest.raises(SchemaChanged):
        loaders.load_eqao_sq(RES)


def test_history_only_where_wording_and_answers_match(monkeypatch):
    from pipeline import build, sources
    monkeypatch.setattr(sources, "EQAO_SQ_RESOURCES", [dict(id="cur", kind="g36", grade="6", year="2025-26")])
    monkeypatch.setattr(sources, "EQAO_SQ_HISTORY", [dict(id="h1", kind="g36", grade="6", year="2024-25"),
                                                     dict(id="h2", kind="g36", grade="6", year="2023-24"),
                                                     dict(id="h3", kind="g36", grade="3", year="2024-25")])

    def q(text, opts=("No, I do not agree", "I am not sure", "Yes, I agree", "Response missing")):
        return {"question": text, "options": list(opts), "agree": ["Yes, I agree"]}

    eq = {"cur": {"questions": {"like_read": q("I like to read"), "good_reader": q("I am a good reader")}},
          "h1": {"questions": {"like_read": q("I like to read"), "good_reader": q("I think I am a good reader")}},
          "h2": {"questions": {"like_read": q("I like to read", ("No", "Maybe", "Yes, I agree", "Response missing"))}},
          "h3": {"questions": {"like_read": q("I like to read")}}}  # another grade: never joined
    h = build.questionnaire_history(eq)["cur"]
    assert h["comparable"] == {"like_read": ["h1"], "good_reader": []}
    assert h["excluded"]["good_reader"] == {"2024-25": "worded differently", "2023-24": "not asked that year"}
    assert h["excluded"]["like_read"] == {"2023-24": "different answers"}
