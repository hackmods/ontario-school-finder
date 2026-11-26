#!/usr/bin/env bash
# Ships the prebuilt static site to a CapRover app. The app is always named outright.
#   ./deploy.sh ontario-schools
#   MACHINE=other ./deploy.sh <app>
# Build first: ./check.sh (full pipeline + tests) or `python -m pipeline.build && python site/generate.py`.
set -euo pipefail
cd "$(dirname "$0")"
MACHINE="${MACHINE:-behind7proxies}"
APP="${1:-}"
if [ -z "$APP" ]; then echo "usage: ./deploy.sh <caprover-app-name>"; exit 1; fi
if [ ! -f site/dist/build.json ]; then echo "site/dist is not built yet"; exit 1; fi
rm -f deploy.tar site.tar.gz
tar -czf site.tar.gz -C site/dist .
tar -cf deploy.tar captain-definition Dockerfile deploy/nginx.conf deploy/security-headers.conf site.tar.gz
ls -lh deploy.tar
caprover deploy -n "$MACHINE" -a "$APP" -t ./deploy.tar
rm -f deploy.tar site.tar.gz
