"""Class lists matched by name, and nearest-school areas: ambiguous or program-only schools are never guessed."""
from collections import defaultdict

from pipeline import build


def school(bsid, name, board="DSB Niagara", level="elementary", **kw):
    return {"bsid": bsid, "name": name, "board_name": board, "level": level, **kw}


def index(schools, extra_names=()):
    idx = defaultdict(set)
    for s in schools:
        idx[build.school_key(s["name"])].add(s["bsid"])
    for bsid, name in extra_names:
        idx[build.school_key(name)].add(bsid)
    return idx


CLASS = {"classes": 2, "students": 40, "primary": [20, 20], "kinder": [], "junior": [], "combined": 0}


def test_same_name_in_one_board_is_unresolved_for_both():
    # Prince Philip: two DSB Niagara schools with one name; the class list can't tell them apart
    a, b = school("456110", "Prince Philip Public School"), school("455989", "Prince Philip Public School")
    by_id = {s["bsid"]: s for s in (a, b)}
    rows = {("2025-26", "DSB Niagara", "Prince Philip Public School"): CLASS}
    m = build.match_class_lists([("classsize-x", rows)], index([a, b]), by_id)
    assert not m["by_school"]
    assert m["ambiguous"]["456110"] == {"455989"} and m["ambiguous"]["455989"] == {"456110"}
    st = build.class_size_status(a, [], m["ambiguous"], m["ambiguous_years"])
    assert st == {"status": "match_unresolved", "others": ["455989"], "years": ["2025-26"]}


def test_a_9_12_school_number_cant_own_elementary_classes():
    # the Ministry splits some 7-12 schools into a 9-12 and a 7-8 school number with the same name
    hi = school("893803", "Bayside Secondary School", grades="9-12", level="secondary")
    el = school("893804", "Bayside Secondary School", grades="7-8")
    unknown = school("893805", "Bayside Secondary School", grades=None)
    rows = {("2025-26", "DSB Niagara", "Bayside Secondary School"): CLASS}
    m = build.match_class_lists([("x", rows)], index([hi, el]), {s["bsid"]: s for s in (hi, el)})
    assert list(m["by_school"]) == ["893804"] and not m["ambiguous"]
    # a school with no published grade range isn't ruled out: still ambiguous, never guessed
    m2 = build.match_class_lists([("x", rows)], index([el, unknown]), {s["bsid"]: s for s in (el, unknown)})
    assert not m2["by_school"] and m2["ambiguous"]["893804"] == {"893805"}
    assert build.may_have_elementary_classes("JK-8") and build.may_have_elementary_classes("7-12")
    assert not build.may_have_elementary_classes("9-12") and not build.may_have_elementary_classes("11-12")


def test_same_name_in_different_boards_still_matches():
    a = school("1", "St Mary Catholic School", board="Niagara CDSB")
    b = school("2", "St Mary Catholic School", board="Toronto CDSB")
    by_id = {"1": a, "2": b}
    rows = {("2025-26", "Niagara Catholic District School Board", "St. Mary Catholic School"): CLASS}
    m = build.match_class_lists([("x", rows)], index([a, b]), by_id)
    assert list(m["by_school"]) == ["1"] and not m["ambiguous"]


def test_former_name_matches_and_unknown_name_is_counted_not_guessed():
    a = school("3", "Harriet Tubman Public School")
    by_id = {"3": a}
    rows = {("2018-19", "DSB Niagara", "Old Name Public School"): CLASS, ("2018-19", "DSB Niagara", "No Such School"): CLASS}
    m = build.match_class_lists([("x", rows)], index([a], extra_names=[("3", "Old Name Public School")]), by_id)
    assert list(m["by_school"]) == ["3"] and m["unmatched"]["2018-19"] == 1


def test_status_for_secondary_and_unlisted():
    assert build.class_size_status(school("9", "X", level="secondary"), [], {}, {}) == {"status": "not_applicable"}
    assert build.class_size_status(school("8", "Y"), [], {}, {}) == {"status": "not_listed"}
    kept = [{"year": "2025-26"}]
    st = build.class_size_status(school("7", "Z"), kept, {"7": {"6"}}, {"7": {"2024-25", "2025-26"}})
    assert st == {"status": "reported", "unresolved_years": ["2024-25"]}


def area_school(**kw):
    return {"level": "elementary", "language": "English", "system": "english-public", "regular": True, **kw}


def test_immersion_only_school_gets_no_nearest_school_area():
    assert build.proximity_area(area_school(), {"immersion": True, "core": False, "extended": False}) == (True, "immersion_only")
    # dual-track (Core French too): a neighbourhood school, area drawn
    assert build.proximity_area(area_school(), {"immersion": True, "core": True, "extended": False}) == (False, "drawn")
    assert build.proximity_area(area_school(), None) == (False, "drawn")
    # secondary schools aren't judged by Core French
    assert build.proximity_area(area_school(level="secondary"), {"immersion": True, "core": False, "extended": False}) == (False, "drawn")
    assert build.proximity_area(area_school(regular=False), None) == (False, "not_regular")
    assert build.proximity_area(area_school(system="other"), None) == (False, "other_system")
