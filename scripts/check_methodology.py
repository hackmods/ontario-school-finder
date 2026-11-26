"""check.sh step 5: /methodology/ must list every source from the brief's table that was used,
with its licence and retrieval date (and say why the others were skipped)."""
import html
import json
import re
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
meta = json.loads((root / "site" / "data" / "meta.json").read_text(encoding="utf-8"))
sources = json.loads((root / "site" / "data" / "sources.json").read_text(encoding="utf-8"))
page = (root / "site" / "dist" / "methodology" / "index.html").read_text(encoding="utf-8")
table = page[page.index('id="sources"'):]
rows = re.findall(r'<tr id="dataset-([a-z_]+)">(.*?)</tr>', table, flags=re.S)
by_key = {k: html.unescape(re.sub(r"<[^>]+>", " ", v)) for k, v in rows}

ok = True
for key, d in sorted(meta["datasets"].items(), key=lambda kv: kv[1]["brief_no"]):
    row = by_key.get(key)
    problems = []
    if row is None:
        problems.append("not listed")
    else:
        if d["title"] not in row:
            problems.append("title missing")
        if d["licence"].split(" (")[0] not in row:
            problems.append("licence missing")
        if d["status"] == "used":
            dates = [s["retrieved"] for s in sources.values() if s["dataset"] == key and s["retrieved"]]
            if not dates or max(dates) not in row:
                problems.append("retrieval date missing")
        elif "Skipped" not in row and "Later" not in row:
            problems.append("status missing")
    ok &= not problems
    print(f"#{d['brief_no']:>2} {d['status']:8s} {d['title'][:60]:60s} {'ok' if not problems else ', '.join(problems)}")
sys.exit(0 if ok else 1)
