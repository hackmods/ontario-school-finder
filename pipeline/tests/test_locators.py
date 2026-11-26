"""site/locators.json: hand-checked links to each board's "which school serves my address" page."""
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
LOC = json.loads((ROOT / "site" / "locators.json").read_text(encoding="utf-8"))
BOARDS = ROOT / "site" / "data" / "boards-index.json"


def test_every_entry_has_a_known_kind_and_a_web_url():
    assert LOC["checked"]
    for number, e in LOC["boards"].items():
        assert number.startswith("B") and number[1:].isdigit(), number
        assert e["kind"] in {"board", "consortium", "maps"}, (number, e["kind"])
        assert e["url"].startswith(("https://", "http://")), (number, e["url"])
        assert set(e) <= {"kind", "url", "unverified"}, (number, sorted(e))


@pytest.mark.skipif(not BOARDS.exists(), reason="site/data not built")
def test_every_board_number_is_a_real_board():
    known = {b["n"] for b in json.loads(BOARDS.read_text(encoding="utf-8"))}
    unknown = sorted(set(LOC["boards"]) - known)
    assert not unknown, f"locators.json has board numbers not in the Ministry list: {unknown}"
