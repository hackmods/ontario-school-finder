"""check.sh step 3: generated page counts must equal the pipeline's school, board and FSA counts."""
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
meta = json.loads((root / "site" / "data" / "meta.json").read_text(encoding="utf-8"))["counts"]
dist = root / "site" / "dist"
pages = {
    "schools": len(list((dist / "school").glob("*/index.html"))),
    "boards": len(list((dist / "board").glob("*/index.html"))),
    "fsas": len(list((dist / "fsa").glob("*/index.html"))),
}
data = {
    "schools": len(list((root / "site" / "data" / "schools").glob("*.json"))),
    "boards": len(list((root / "site" / "data" / "boards").glob("*.json"))),
    "fsas": len(list((root / "site" / "data" / "fsa").glob("*.json"))),
}
ok = True
for k in pages:
    status = "ok" if pages[k] == meta[k] == data[k] else "MISMATCH"
    ok &= status == "ok"
    print(f"{k:8s} pages {pages[k]:5d}  data files {data[k]:5d}  pipeline {meta[k]:5d}  {status}")
for must in ["index.html", "search/index.html", "map/index.html", "compare/index.html", "about/index.html", "methodology/index.html", "data/index.html", "404.html", "sitemap.xml"]:
    if not (dist / must).exists():
        print(f"missing {must}")
        ok = False
sys.exit(0 if ok else 1)
