"""Hand-kept corrections in sources.py: each says why, and reaches the built data."""
import json
import re

import pytest

from pipeline import config, sources


@pytest.mark.parametrize("board,fix", sorted(sources.BOARD_WEBSITE_FIXES.items()))
def test_board_website_fixes_are_explained(board, fix):
    url, why = fix
    assert re.fullmatch(r"B\d{5}", board)
    assert url.startswith("https://") and " " not in url
    assert "checked 20" in why, "say when the old link was checked"


def test_board_website_fixes_reach_the_board_pages():
    d = config.OUT / "boards"
    if not d.exists():
        pytest.skip("site/data not built yet")
    for board, (url, _why) in sources.BOARD_WEBSITE_FIXES.items():
        p = d / f"{board.lower()}.json"
        if p.exists():
            assert json.loads(p.read_text(encoding="utf-8"))["website"] == url, board


def test_school_link_list_is_well_formed():
    links = json.loads((config.ROOT / "site" / "school-links.json").read_text(encoding="utf-8"))
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", links["checked"])
    for bsid, v in links["schools"].items():
        assert re.fullmatch(r"\d{6}", bsid)
        assert v["status"] in ("dead", "parked", "unrelated") and v["detail"] and v["url"].startswith("http")
