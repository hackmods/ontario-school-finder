"""Serve site/dist locally with the content types nginx uses (ES modules need a JavaScript type).

    python scripts/serve.py [port] [directory]      # defaults: 8078, site/dist

Python's own `http.server` sends `.mjs` as text/plain on some systems, and browsers refuse to run
a module served that way, so the map (MapLibre 6 is an ES module) would not load in tests.
"""
from __future__ import annotations

import functools
import http.server
import sys
from pathlib import Path


class Handler(http.server.SimpleHTTPRequestHandler):
    extensions_map = {
        **http.server.SimpleHTTPRequestHandler.extensions_map,
        ".js": "text/javascript",
        ".mjs": "text/javascript",
        ".json": "application/json",
        ".geojson": "application/geo+json",
        ".webmanifest": "application/manifest+json",
        ".svg": "image/svg+xml",
        ".md": "text/markdown; charset=utf-8",
        ".csv": "text/csv; charset=utf-8",
    }

    def log_message(self, *args) -> None:  # quiet: tests make thousands of requests
        pass


def main() -> None:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8078
    root = sys.argv[2] if len(sys.argv) > 2 else str(Path(__file__).resolve().parent.parent / "site" / "dist")
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), functools.partial(Handler, directory=root))
    print(f"serving {root} on http://127.0.0.1:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
