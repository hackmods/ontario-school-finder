"""Official attendance boundaries: board names match Ministry names, and nothing unmatched is guessed."""
import json

import pytest

from pipeline import boundaries, config, sources
from pipeline.fetch import SchemaChanged


@pytest.mark.parametrize("board_name, ministry_name", [
    ("N.A. MacEachern P.S.", "N A MacEachern Public School"),
    ("St. Mary CES", "St Mary Catholic Elementary School"),
    ("Cayuga DSS", "Cayuga Secondary School"),
    ("Ecole Elementaire Laurier", "École élémentaire Laurier"),
    ("Grand River CVI", "Grand River Collegiate Institute"),
    ("Mt. Hope P.S.", "Mount Hope Public School"),
    ("O'Neill C.V.I.", "O’Neill Collegiate and Vocational Institute"),
])
def test_board_shorthand_matches_ministry_name(board_name, ministry_name):
    assert boundaries.core(board_name) == boundaries.core(ministry_name)


def test_bracketed_notes_and_generic_words_are_ignored():
    assert boundaries.core("Sir John A. Macdonald (Temporary Attendance Area for ELZ)") == boundaries.core("Sir John A Macdonald School")
    assert boundaries.core("St. John") != boundaries.core("St. John Paul II")


def _square(x, y, d=0.02):
    return {"type": "Polygon", "coordinates": [[[x, y], [x + d, y], [x + d, y + d], [x, y + d], [x, y]]]}


@pytest.fixture
def layer(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW", tmp_path / "raw")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "manifest.json")
    (tmp_path / "raw").mkdir()
    lay = {"id": "bdy-test", "board": "B1", "level": "elementary", "label": "Test", "name_field": "NAME",
           "url": "https://example.invalid/FeatureServer/0", "skip": [r"^Holding"]}
    monkeypatch.setattr(sources, "BOUNDARY_LAYERS", [lay])
    feats = [
        {"type": "Feature", "properties": {"NAME": "Alpha P.S."}, "geometry": _square(-80.0, 43.0)},
        {"type": "Feature", "properties": {"NAME": "Alpha P.S."}, "geometry": _square(-79.98, 43.0)},   # second part, same school
        {"type": "Feature", "properties": {"NAME": "Development Area 7"}, "geometry": _square(-79.9, 43.0)},  # one school inside: matched by location
        {"type": "Feature", "properties": {"NAME": "Development Area 9"}, "geometry": _square(-79.5, 43.0)},  # no school inside: left out
        {"type": "Feature", "properties": {"NAME": "Holding Area at Beta"}, "geometry": _square(-79.7, 43.0)},  # skipped by pattern
        {"type": "Feature", "properties": {"NAME": "Gamma P.S."}, "geometry": _square(-79.0, 43.0)},  # name matches, but school is 50 km away
    ]
    (tmp_path / "raw" / "bdy-test.json").write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    (tmp_path / "raw" / "bdy-test-meta.json").write_text(json.dumps({"editingInfo": {"lastEditDate": 1754006400000}}), encoding="utf-8")
    return tmp_path / "raw"


def _school(bsid, name, lon, lat, board="B1", level="elementary"):
    return {"bsid": bsid, "name": name, "board_number": board, "level": level, "lon": lon, "lat": lat}


def test_build_matches_by_name_then_location_and_reports_the_rest(layer):
    schools = [
        _school("1", "Alpha Public School", -79.99, 43.01),
        _school("2", "Delta Public School", -79.89, 43.01),
        _school("3", "Gamma Public School", -79.6, 43.5),
        _school("4", "Alpha Public School", -79.99, 43.01, level="secondary"),  # other level: never a candidate
    ]
    out = boundaries.build(schools, {"B1": "Board One"}, log=lambda *_: None)
    assert set(out["by_school"]) == {"1", "2"}
    assert out["by_school"]["1"]["edited"] == "2025-08"
    assert out["by_school"]["1"]["geometry"]["type"] in ("Polygon", "MultiPolygon")
    rep = out["report"]["bdy-test"]
    assert rep["matched"] == 2 and rep["areas"] == 4
    assert rep["unmatched"] == ["Development Area 9", "Gamma P.S."]
    assert rep["far"] == ["Gamma P.S. -> 3"]
    assert [f["properties"]["id"] for f in out["layers"]["elementary"]] == ["1", "2"]
    assert out["layers"]["secondary"] == []


def test_two_schools_with_one_name_stay_apart_with_split(layer):
    feats = [
        {"type": "Feature", "properties": {"NAME": "St. Joseph CES", "Code": "JOEBR"}, "geometry": _square(-80.0, 43.0)},
        {"type": "Feature", "properties": {"NAME": "St. Joseph CES", "Code": "JOEST"}, "geometry": _square(-79.5, 43.0)},
    ]
    (layer / "bdy-test.json").write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    sources.BOUNDARY_LAYERS[:] = [dict(sources.BOUNDARY_LAYERS[0], split="Code")]
    schools = [_school("1", "St Joseph Separate School", -79.99, 43.01), _school("2", "St Joseph Separate School", -79.49, 43.01)]
    out = boundaries.build(schools, {}, log=lambda *_: None)
    assert set(out["by_school"]) == {"1", "2"}
    assert out["report"]["bdy-test"]["matched"] == 2


def test_split_grade_pair_on_one_site_shares_the_area(layer):
    feats = [{"type": "Feature", "properties": {"NAME": "Frank Panabaker"}, "geometry": _square(-80.0, 43.0)}]
    (layer / "bdy-test.json").write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    schools = [_school("1", "Frank Panabaker North School", -79.99, 43.01),
               _school("2", "Frank Panabaker South Senior Public School", -79.99, 43.011),
               _school("3", "Frank Panabaker East School", -79.0, 43.5)]  # same score, outside the area: blocks the pair
    out = boundaries.build(schools[:2], {}, log=lambda *_: None)
    assert set(out["by_school"]) == {"1", "2"}
    out = boundaries.build(schools, {}, log=lambda *_: None)
    assert out["by_school"] == {} and out["report"]["bdy-test"]["unmatched"] == ["Frank Panabaker"]


def test_build_fails_loudly_when_the_name_field_changes(layer):
    lay = dict(sources.BOUNDARY_LAYERS[0], name_field="SCHOOL")
    sources.BOUNDARY_LAYERS[:] = [lay]
    with pytest.raises(SchemaChanged):
        boundaries.build([_school("1", "Alpha Public School", -79.99, 43.01)], {}, log=lambda *_: None)


def test_every_layer_names_a_board_level_and_field():
    seen = set()
    for lay in sources.BOUNDARY_LAYERS:
        assert lay["id"].startswith("bdy-") and lay["id"] not in seen
        seen.add(lay["id"])
        assert lay["level"] in ("elementary", "secondary")
        assert lay.get("name_field") or lay.get("dissolve")
        assert lay["url"].startswith("https://") and "FeatureServer" in lay["url"]
