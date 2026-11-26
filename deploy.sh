#!/usr/bin/env bash
# Ships the prebuilt static site to a CapRover app. The app is always named outright.
#   ./deploy.sh ontario-schools
#   MACHINE=other ./deploy.sh <app>
# Build first: ./check.sh (full pipeline + tests) or `python -m pipeline.build && python site/generate.py`.
set -euo pipefail
cd "$(dirname "$0")"
MACHINE="${MACHINE:-captain-01}"
APP="${1:-}"
if [ -z "$APP" ]; then echo "usage: ./deploy.sh <caprover-app-name>"; exit 1; fi
if [ ! -f site/dist/build.json ]; then echo "site/dist is not built yet"; exit 1; fi
rm -f deploy.tar site.tar.gz
# GNU tar exits 1 when a file's timestamp changes mid-read (Windows virus scanning right after a
# rebuild); the archive is still complete, so only a real error (2) stops the deploy.
tar --warning=no-file-changed -czf site.tar.gz -C site/dist . || [ $? -eq 1 ]
tar -cf deploy.tar captain-definition Dockerfile deploy/nginx.conf deploy/security-headers.conf site.tar.gz
ls -lh deploy.tar
caprover deploy -n "$MACHINE" -a "$APP" -t ./deploy.tar
rm -f deploy.tar site.tar.gz
