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
rm -f deploy.tar site.tar.gz site.tar.xz
# xz, not gzip: the ~11,000 pages repeat the same templates, which xz's large window finds across files
# (1.8 GB of pages: 316 MB as .tar.gz, over CapRover's upload limit; about 55 MB as .tar.xz).
# GNU tar exits 1 when a file's timestamp changes mid-read (Windows virus scanning right after a
# rebuild); the archive is still complete, so only a real error (2) stops the deploy.
{ tar --warning=no-file-changed -cf - -C site/dist . || [ $? -eq 1 ]; } | xz -9 -T0 > site.tar.xz
tar -cf deploy.tar captain-definition Dockerfile deploy/nginx.conf deploy/security-headers.conf site.tar.xz
ls -lh deploy.tar
caprover deploy -n "$MACHINE" -a "$APP" -t ./deploy.tar
rm -f deploy.tar site.tar.xz
# caprover can exit 0 even when it deployed nothing (an expired sign-in, an upload refused): check the live
# build instead of trusting the exit code
BUILT=$(sed -n 's/.*"built": *"\([^"]*\)".*/\1/p' site/dist/build.json)
echo "Uploaded the build from $BUILT. Check the live site's /build.json shows that time before calling it done."
