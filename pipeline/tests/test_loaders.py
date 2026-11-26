"""Every loader validates its columns and fails with an expected-vs-found message when they change."""
import openpyxl
import pytest

from pipeline import config, fetch, loaders, sources
from pipeline.fetch import SchemaChanged


@pytest.fixture
def raw_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW", tmp_path / "raw")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "manifest.json")
    (tmp_path / "raw").mkdir()
    return tmp_path / "raw"


def write_xlsx(path, header, rows, title="Sheet1"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title
    ws.append(header)
    for r in rows:
        ws.append(r)
    wb.save(path)


def sif_res(**kw):
    return {"id": "sif-test", "year": "2024-25", "eqao_year": "2024-25", "g9": sources.G9_DESTREAMED, "url": "https://example.invalid/x.xlsx", **kw}


def sif_row(header, **vals):
    row = []
    for h in header:
        if h in vals:
            row.append(vals[h])
        elif h.startswith("Percentage"):
            row.append("50%")
        else:
            row.append("x")
    return row


def test_require_columns_message_lists_expected_and_found():
    with pytest.raises(SchemaChanged) as e:
        loaders.require_columns("demo", ["A", "B"], ["A", "C"])
    msg = str(e.value)
    assert "expected" in msg and "found" in msg and "missing" in msg and "C" in msg


def test_sif_loader_reads_a_good_file(raw_dir):
    header = loaders.sif_expected_columns(sources.G9_DESTREAMED)
    row = sif_row(header, **{"School Number": "019186", "School Name": "Test PS", "Enrolment": "295", "Latitude": 46.5, "Longitude": -84.3,
                             "Percentage of Grade 3 Students Achieving the Provincial Standard in Reading": "SP"})
    write_xlsx(raw_dir / "sif-test.xlsx", header, [row])
    out = loaders.load_sif(sif_res())
    rec = out["rows"]["019186"]
    assert rec["eqao"]["g3-reading"] == (None, "SP")
    assert rec["eqao"]["g3-writing"] == (50, None)
    assert rec["enrolment"] == (295, None)


def test_sif_loader_fails_when_a_column_is_renamed(raw_dir):
    header = loaders.sif_expected_columns(sources.G9_DESTREAMED)
    header = [h.replace("Percentage of Grade 6 Students Achieving the Provincial Standard in Reading", "Grade 6 Reading %") for h in header]
    write_xlsx(raw_dir / "sif-test.xlsx", header, [sif_row(header, **{"School Number": "019186"})])
    with pytest.raises(SchemaChanged) as e:
        loaders.load_sif(sif_res())
    assert "Grade 6 Students Achieving the Provincial Standard in Reading" in str(e.value)


def test_sif_loader_rejects_unexpected_values(raw_dir):
    header = loaders.sif_expected_columns(sources.G9_DESTREAMED)
    row = sif_row(header, **{"School Number": "019186", "Enrolment": "295",
                             "Percentage of Grade 3 Students Achieving the Provincial Standard in Reading": "about half"})
    write_xlsx(raw_dir / "sif-test.xlsx", header, [row])
    with pytest.raises(Exception) as e:
        loaders.load_sif(sif_res())
    assert "about half" in str(e.value)


def test_enrolment_loader_needs_exact_columns(raw_dir):
    (raw_dir / "enrol-test.txt").write_text("Board Number|Board Name|School Number|School Name|School Level|School Type|School Language|Students\nB1|X|019186|Y|Elementary|Public|English|155\n", encoding="utf-8")
    with pytest.raises(SchemaChanged):
        loaders.load_enrolment({"id": "enrol-test", "year": "2024-25", "url": "https://example.invalid"})


def test_enrolment_loader_handles_codes_commas_and_totals(raw_dir):
    body = "Board Number|Board Name|School Number|School Name|School Level|School Type|School Language|Enrolment\n" \
           "B1|X|019186|A|Elementary|Public|English|1,336\nB1|X|019187|B|Elementary|Public|English|<10\nB1|X||Total|||| 2,003,237\n"
    (raw_dir / "enrol-test.txt").write_text(body, encoding="utf-8")
    out = loaders.load_enrolment({"id": "enrol-test", "year": "2024-25", "url": "https://example.invalid"})
    assert out["rows"]["019186"] == (1336, None)
    assert out["rows"]["019187"] == (None, "<10")
    assert len(out["rows"]) == 2


def test_contact_loader_validates(raw_dir):
    (raw_dir / "contact-2026-11.txt").write_text("Region|Board Number|School Number\nX|B1|019186\n", encoding="utf-8")
    with pytest.raises(SchemaChanged):
        loaders.load_contact(sources.CONTACT_RESOURCE)


def test_sbpr_loader_validates(raw_dir):
    write_xlsx(raw_dir / "sbpr-test.xlsx", ["Board Number", "Board Name", "Board Language", "Board Type", "Region", "City", "Reading"], [["B1", "X", "English", "Public", "R", "C", 0.5]])
    with pytest.raises(SchemaChanged):
        loaders.load_sbpr({**sources.SBPR_RESOURCES[0], "id": "sbpr-test"})


def test_childcare_loader_validates(raw_dir):
    write_xlsx(raw_dir / "childcare-test.xlsx", ["Licensee Name", "Postal Code"], [["X", "L2S 3A1"]])
    with pytest.raises(SchemaChanged):
        loaders.load_childcare({**sources.CHILDCARE_RESOURCE, "id": "childcare-test"})


def test_download_refuses_html_instead_of_xlsx(monkeypatch, raw_dir):
    class R:
        status_code = 200
        headers = {"content-type": "text/html"}
        content = b"<html>Security Check</html>"

    monkeypatch.setattr(fetch.session(), "get", lambda *a, **k: R())
    with pytest.raises(fetch.SourceUnavailable):
        fetch.download("x", "https://example.invalid/file.xlsx", expect="xlsx")


def test_download_reports_404_as_changed_url(monkeypatch, raw_dir):
    class R:
        status_code = 404
        headers = {}
        content = b""

    monkeypatch.setattr(fetch.session(), "get", lambda *a, **k: R())
    with pytest.raises(fetch.SourceUnavailable) as e:
        fetch.download("y", "https://example.invalid/gone.xlsx", expect="xlsx")
    assert "URL has changed" in str(e.value)
