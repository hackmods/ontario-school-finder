#!/usr/bin/env bash
# The definition of done: rebuild everything from a clean download cache and prove it works.
#   1. pipeline end to end from a clean cache -> site/data + pipeline/report.md
#   2. pytest -q pipeline/tests
#   3. generate site/dist and confirm page counts match school, board and FSA counts
#   4. serve site/dist on port 8078, run Playwright tests + screenshots, confirm all 8 exist
#   5. confirm /methodology/ lists every used source with licence and retrieval date
# Options: SKIP_PIPELINE=1 reuses site/data (for quick UI iterations). SLOW=1 also checks source links.
set -euo pipefail
cd "$(dirname "$0")"
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1

if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; elif [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=${PY:-python3}; fi
PORT=8078
START=$(date +%s)
step() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

step "1/5 Pipeline from a clean cache"
if [ "${SKIP_PIPELINE:-}" = "1" ]; then
  echo "SKIP_PIPELINE=1: reusing site/data"
else
  "$PY" -m pipeline.build --clean
fi
test -s pipeline/report.md

step "2/5 Pipeline tests"
"$PY" -m pytest -q pipeline/tests

step "3/5 Generate the site"
"$PY" site/generate.py
"$PY" scripts/check_counts.py

step "4/5 Serve site/dist on :$PORT and run Playwright"
SERVER_PID=""
if curl -fsS "http://127.0.0.1:$PORT/build.json" >/dev/null 2>&1; then
  echo "something already serves :$PORT; checking it is this build"
  diff <(curl -fsS "http://127.0.0.1:$PORT/build.json") site/dist/build.json >/dev/null || { echo "port $PORT is serving a different build; stop it first"; exit 1; }
else
  "$PY" -m http.server "$PORT" --bind 127.0.0.1 --directory site/dist >/dev/null 2>&1 &
  SERVER_PID=$!
  trap '[ -n "$SERVER_PID" ] && kill "$SERVER_PID" 2>/dev/null || true' EXIT
  for _ in $(seq 1 50); do curl -fsS "http://127.0.0.1:$PORT/build.json" >/dev/null 2>&1 && break; sleep 0.2; done
fi
rm -f evidence/*.png
npx playwright test
for f in home-390 search-results-390 school-page-390 school-page-1280 fsa-page-390 compare-1280 map-legend-390 methodology-1280; do
  test -s "evidence/$f.png" || { echo "missing evidence/$f.png"; exit 1; }
done
echo "all 8 screenshots present"

step "5/5 Methodology lists every source"
"$PY" scripts/check_methodology.py

printf '\n\033[1;32mcheck.sh passed in %ss\033[0m\n' "$(( $(date +%s) - START ))"
