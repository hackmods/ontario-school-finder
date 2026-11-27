"""Downloads: a refresh asks the publisher whether a file changed, keeps it when it didn't, and never swaps good
data for an error or a block page. ``retrieved`` only moves when the bytes do."""
import pytest

from pipeline import config, fetch

URL = "https://example.invalid/file.csv"


class Resp:
    def __init__(self, status, content=b"", headers=None):
        self.status_code, self.content, self.headers = status, content, headers or {}


class Session:
    def __init__(self, *resps):
        self.resps, self.calls = list(resps), []

    def get(self, url, timeout=None, headers=None):
        self.calls.append(headers or {})
        return self.resps.pop(0)


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "RAW", tmp_path / "raw")
    monkeypatch.setattr(config, "MANIFEST", tmp_path / "manifest.json")
    monkeypatch.setattr(fetch, "REVALIDATE", False)
    monkeypatch.setattr(fetch, "_revalidated", set())
    clock = iter(f"2026-11-{d:02d}T00:00:00Z" for d in range(1, 29))
    monkeypatch.setattr(fetch, "_now", lambda: next(clock))
    return monkeypatch


def first_download(cache, *later):
    s = Session(Resp(200, b"a,b\n1,2\n", {"ETag": '"v1"', "Last-Modified": "Mon, 02 Nov 2026 10:00:00 GMT", "content-type": "text/csv"}), *later)
    cache.setattr(fetch, "session", lambda: s)
    path = fetch.download("src", URL, expect="csv")
    return s, path, fetch.manifest_entry("src")


def test_plain_run_never_asks_again(cache):
    s, path, _ = first_download(cache)
    fetch.download("src", URL, expect="csv")
    assert len(s.calls) == 1


def test_refresh_keeps_an_unchanged_file(cache):
    s, path, before = first_download(cache, Resp(304))
    cache.setattr(fetch, "REVALIDATE", True)
    fetch.download("src", URL, expect="csv")
    fetch.download("src", URL, expect="csv")  # once per run
    assert len(s.calls) == 2
    assert s.calls[1] == {"If-None-Match": '"v1"', "If-Modified-Since": "Mon, 02 Nov 2026 10:00:00 GMT"}
    after = fetch.manifest_entry("src")
    assert after["retrieved"] == before["retrieved"] and after["checked"] > before["checked"]
    assert path.read_bytes() == b"a,b\n1,2\n"


def test_refresh_replaces_a_changed_file(cache):
    s, path, before = first_download(cache, Resp(200, b"a,b\n1,3\n", {"ETag": '"v2"', "content-type": "text/csv"}))
    cache.setattr(fetch, "REVALIDATE", True)
    fetch.download("src", URL, expect="csv")
    after = fetch.manifest_entry("src")
    assert path.read_bytes() == b"a,b\n1,3\n" and after["etag"] == '"v2"' and after["retrieved"] > before["retrieved"]


def test_same_bytes_without_validators_keep_their_date(cache):
    s, path, before = first_download(cache, Resp(200, b"a,b\n1,2\n", {"content-type": "text/csv"}))
    cache.setattr(fetch, "REVALIDATE", True)
    fetch.download("src", URL, expect="csv")
    assert fetch.manifest_entry("src")["retrieved"] == before["retrieved"]


@pytest.mark.parametrize("resp", [Resp(503), Resp(403), Resp(200, b"<html>Security check</html>", {"content-type": "text/html"})])
def test_errors_and_block_pages_never_replace_good_data(cache, resp):
    s, path, before = first_download(cache, resp)
    cache.setattr(fetch, "REVALIDATE", True)
    assert fetch.download("src", URL, expect="csv") == path
    assert path.read_bytes() == b"a,b\n1,2\n" and fetch.manifest_entry("src")["retrieved"] == before["retrieved"]


def test_a_failed_build_leaves_the_previous_data(tmp_path, monkeypatch):
    from pipeline import build
    final = tmp_path / "data"
    (final / "schools").mkdir(parents=True)
    (final / "schools" / "x.json").write_text("old", encoding="utf-8")
    monkeypatch.setattr(config, "OUT", final)

    def boom(clean=False):
        (config.OUT / "schools").mkdir(parents=True)
        (config.OUT / "schools" / "x.json").write_text("half-written", encoding="utf-8")
        raise RuntimeError("source changed")

    monkeypatch.setattr(build, "_build", boom)
    with pytest.raises(RuntimeError):
        build.build()
    assert (final / "schools" / "x.json").read_text(encoding="utf-8") == "old"
    assert config.OUT == final

    def ok(clean=False):
        (config.OUT / "schools").mkdir(parents=True)
        (config.OUT / "schools" / "x.json").write_text("new", encoding="utf-8")
        return {"schools": 1}

    monkeypatch.setattr(build, "_build", ok)
    assert build.build() == {"schools": 1}
    assert (final / "schools" / "x.json").read_text(encoding="utf-8") == "new"
    assert not (tmp_path / "data.building").exists() and not (tmp_path / "data.old").exists()
