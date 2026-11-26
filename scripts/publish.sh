#!/usr/bin/env bash
# Rebuild the pages from the current site/data and deploy them.
# The public contact address comes from your environment, so it never lives in the repo:
#   CONTACT_EMAIL=you@example.org bash scripts/publish.sh
# (or set CONTACT_EMAIL once in your user environment and just run bash scripts/publish.sh)
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; else PY=.venv/bin/python; fi
if [ -z "${CONTACT_EMAIL:-}" ]; then echo "Note: CONTACT_EMAIL is not set, so the site will show no contact address."; fi
PYTHONIOENCODING=utf-8 "$PY" site/generate.py
"$PY" scripts/check_counts.py
./deploy.sh "${APP:-ontario-schools}"
echo "Published. Contact address on the site: ${CONTACT_EMAIL:-none}"
