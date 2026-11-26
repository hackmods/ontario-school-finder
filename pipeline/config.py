"""Paths and shared settings for the data pipeline."""
from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PIPELINE = ROOT / "pipeline"
CACHE = Path(os.environ.get("OSF_CACHE", PIPELINE / "cache"))
RAW = CACHE / "raw"
MANIFEST = CACHE / "manifest.json"
GEOCODE_CACHE = CACHE / "geocode.json"
OUT = ROOT / "site" / "data"
REPORT = PIPELINE / "report.md"

# Honest, identifiable user agent. We never pretend to be a browser.
USER_AGENT = "ontario-school-finder-pipeline/1.0 (open-data rebuild; +https://github.com/hackmods/ontario-school-finder)"
TIMEOUT = 120

# Map projection used for distances, Voronoi cells and dissolves (Statistics Canada Lambert).
PROJECTED_CRS = "EPSG:3347"
GEO_CRS = "EPSG:4326"

# How far outside an FSA we still list a school as "near" it on the FSA page.
NEAR_FSA_METRES = 1500
# Number of nearby schools listed on each school page (same level).
NEARBY_COUNT = 6
