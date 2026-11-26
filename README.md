# Ontario School Finder

A free, fast, ad-free website where parents can find Ontario's publicly funded schools by name, city, postal code or street address, and see each school's public results **in context** — next to its board and the province, over several years — with a link to every original source.

- No accounts, ads, tracking cookies or analytics. The only third-party requests are map tiles (OpenFreeMap) and, only when you search an address, the Government of Canada's geolocation service.
- No rankings and no single score. Withheld or missing values are labelled, never shown as 0.
- Every page is pre-generated static HTML, so it is fast, cheap to host, shareable, and the core facts work without JavaScript.

## How it fits together

```
pipeline/   Python: download the public datasets, validate every column, clean, join, build map layers
            -> site/data/*.json + site/data/geo/*.geojson + pipeline/report.md
site/       Python page generator (Jinja templates) + vanilla JS/CSS + self-hosted MapLibre GL
            -> site/dist/ (one page per school, board and postal area)
tests/e2e/  Playwright tests and evidence screenshots
deploy/     nginx config (strict CSP, caching, gzip) for the Docker image
check.sh    the definition of done: clean rebuild + every test + screenshots
```

### Data sources

| # | Source | Used for | Licence |
|---|--------|----------|---------|
| 1 | Ontario *School information and student demographics* (9 files: 2015-16, 2017-18 to 2024-25) | school list, coordinates, EQAO results 2016-17 to 2024-25, student context | OGL – Ontario |
| 2 | Ontario *public school contact information* (Nov 2026) | phone, email, website, open status, opening date | OGL – Ontario |
| 4 | Ontario *School board achievements and progress* (May + Nov 2026 releases) | official board results, credits, graduation | OGL – Ontario |
| 5 | Ontario *public schools enrolment* (2011-12 to 2024-25) | enrolment trend | OGL – Ontario |
| 7 | Statistics Canada 2021 FSA boundary file | postal-area outlines | Statistics Canada Open Licence |
| 9 | Statistics Canada 2021 Census Profile by FSA (Census Profile API) | area context | Statistics Canada Open Licence |
| 10 | Ontario *Licensed child care facilities* (Sept 2026) | child care at each school's address and in each area | OGL – Ontario |
| 12 | Ontario *School enrolment by grade* (2017-18 to 2024-25) | students in each grade | OGL – Ontario |
| 13 | Ontario *Elementary class size* (2007-08 to 2025-26) | class sizes per school, 19 years | OGL – Ontario |

Skipped: #6 *Board service area* (listed as "under review" with no files), #8 census subdivisions (only needed for #6), #3 EQAO repository and #11 board attendance boundaries (Phase 2). Details and retrieval dates are on `/methodology/` and in `pipeline/report.md`.

## Branding

Field Guide is the selected trillium logo. All three retro designs, editable SVG masters, previews and complete web assets are preserved in [branding/](branding/README.md). Use `npm run brand -- --brand field-guide` (or `civic-trillium` / `common-bloom`) to select and regenerate the artwork, then rebuild the site before publishing.

## Run it

Requirements: Python 3.11+ (tested on 3.14), Node 18+ (only for Playwright tests), Git Bash on Windows.

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # .venv/bin/pip on macOS/Linux
npm install                                        # Playwright (uses an installed Chromium)
./check.sh                                         # full clean rebuild + tests + screenshots (~10 min)
```

Quicker loops:

```bash
.venv/Scripts/python -m pipeline.build        # reuse downloaded files in pipeline/cache
.venv/Scripts/python site/generate.py         # rebuild pages only
SKIP_PIPELINE=1 ./check.sh                    # tests + screenshots on the current data
SLOW=1 npx playwright test tests/e2e/links.slow.spec.js   # check external source links
```

Generator settings (environment variables): `SITE_URL`, `CONTACT_EMAIL`, `CORRECTIONS_URL`, `OPERATOR`.
The public contact address is never committed: set `CONTACT_EMAIL` in your own environment (once, e.g. as a Windows user variable)
so every rebuild includes it. To rebuild pages and deploy in one step: `bash scripts/publish.sh`.

## Deploy

The site is a folder of static files. It is served by nginx in a small Docker image on CapRover:

```bash
./check.sh                      # or build without tests
./deploy.sh ontario-schools     # packs site/dist into one archive, builds the nginx image on CapRover
```

Live at **https://ontarioschoolfinder.ca** (CapRover app `ontario-schools`, also reachable at ontario-schools.behind7proxies.com). DNS is on Cloudflare: apex and `www` are A records to the CapRover server, **DNS only** (not proxied) so CapRover can issue Let's Encrypt certificates. To (re)attach the domain, enable HTTPS, redirect `www` and the behind7proxies address to the apex, rebuild canonical URLs and deploy:

```bash
scripts/connect-domain.sh            # defaults: ontarioschoolfinder.ca ontario-schools
```

It also works on any static host (GitHub Pages, Cloudflare Pages) by publishing `site/dist`; copy the headers from `deploy/security-headers.conf`.

## Updating the data

Run the pipeline again. It re-downloads every source, checks every column it reads, and **stops with an expected-vs-found message if a file changes** instead of guessing. New yearly files are added in `pipeline/sources.py` (one line each).

See [docs/DECISIONS.md](docs/DECISIONS.md) for where this build departs from the original brief ([docs/idea.md](docs/idea.md)) and why.
