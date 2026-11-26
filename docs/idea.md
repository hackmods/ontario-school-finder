# GOAL 003 — Ontario School Finder (free public service for parents)

## One-line goal
A free, fast, ad-free static website where parents can find Ontario public schools by name, address or postal code (FSA). For every school it shows EQAO results and other public metrics, with trends, context and a link to every original source.

## Principles (these decide every judgment call)
1. **Every number links to its source** and shows its school year. No unsourced figures, ever.
2. **Context, not leaderboards.** Show each school against its board and the province, with multi-year trends. No "top 10" lists and no single 1–10 score.
3. **Honest about gaps.** Suppressed, missing and small-cohort data are labelled clearly, never shown as 0.
4. **Boundaries are approximate unless official.** Every map layer is labelled with what it is, and every school page links to the board's official school locator.
5. **Free forever, private by default.** No accounts, no ads, no tracking cookies, no third-party scripts beyond map tiles.

## Fixed decisions (do NOT ask, do NOT change)
- Two parts: a **Python data pipeline** (`pipeline/`) that downloads, cleans and joins public data into static JSON/GeoJSON, and a **static site** (`site/`) built from that output.
- Site: plain HTML/CSS/vanilla JS, plus Leaflet for maps (the ONLY front-end library). No framework, no build step beyond the Python page generator.
- Pages are pre-generated (one HTML page per school, board and FSA) so every page has a stable, shareable URL and works without JavaScript for the core facts.
- Hosting target: GitHub Pages or Cloudflare Pages ($0). No server, no database at runtime.
- Map tiles: OpenStreetMap-based tiles with proper attribution, following the provider's usage policy.
- Geocoding a typed address (optional feature): client-side call to a free geocoder with attribution and rate limiting. If no free option fits its usage policy, fall back to postal-code FSA lookup only.
- Pipeline: Python 3.11+, pandas, geopandas/shapely, requests. Tests with pytest. Site tests and screenshots with Playwright.

## Data sources (pipeline must record source URL, licence, retrieval date and school year for each)
| # | source | what we use | licence |
|---|--------|-------------|---------|
| 1 | Ontario "School information and student demographics" (data.ontario.ca) | school list, BSID, board, address, grade range, enrolment, Gr 3/6 EQAO, Gr 9 math, OSSLT, demographic context columns | Open Government Licence – Ontario |
| 2 | Ontario "Ontario public school contact information" (data.ontario.ca) | current addresses, phone, website, open/closed status | OGL – Ontario |
| 3 | EQAO Open Agency Data Repository (eqao.com) | newer school-level results than #1, multi-year trends | check terms in pipeline README before publishing; link back on every page |
| 4 | Ontario "School board achievements and progress" (data.ontario.ca) | board-level comparison values (e.g. graduation, Gr 6 reading) | OGL – Ontario |
| 5 | Ontario "Ontario public schools enrolment" / enrolment by grade | enrolment trend | OGL – Ontario |
| 6 | Ontario "Board service area" (data.ontario.ca) | which municipalities each board serves | OGL – Ontario |
| 7 | Statistics Canada 2021 Census FSA Boundary File | FSA polygons | Statistics Canada Open Licence |
| 8 | Statistics Canada 2021 Census subdivision boundary file | municipal polygons to build approximate board coverage from #6 | Statistics Canada Open Licence |
| 9 | Statistics Canada 2021 Census Profile by FSA | area context: children 0–14, households with children, median income, languages | Statistics Canada Open Licence |
| 10 | Ontario "Licensed child care facilities" (data.ontario.ca) | nearby licensed child care | OGL – Ontario |
| 11 | Board-published attendance boundaries (only where a board publishes them openly or gives written permission) | official intake areas | per board; record permission |
Not allowed: scraping or copying third-party rankings (e.g. Fraser Institute), real-estate listings, or any data whose terms forbid redistribution. Linking out to them is fine.

If a dataset's URL or columns have changed, the pipeline must fail loudly with a clear message (expected vs found columns), not guess.

## Data contract — school record (`site/data/schools/<bsid>.json` + `schools-index.json`)
- `bsid`, `name`, `board_number`, `board_name`, `board_type` (public / Catholic), `language` (English / French), `level` (elementary / secondary), `grades`, `address`, `city`, `postal_code`, `fsa`, `lat`, `lon`, `phone`, `website`, `status`
- `programs`: e.g. French Immersion offered (if available in source), otherwise omitted, never guessed
- `enrolment`: `[{year, value, source_id}]`
- `eqao`: `[{year, assessment, subject, pct_at_or_above_standard, board_pct, province_pct, suppressed: bool, small_cohort: bool, source_id}]`
- `context`: demographic context columns from source #1 (with the source's own definitions)
- `sources`: `[{source_id, title, url, licence, retrieved}]`
- Coordinates: use source coordinates if present. Otherwise geocode once in the pipeline, cache results in `pipeline/cache/geocode.json`, and flag `geocoded: true`.

## Boundary layers (each labelled on the map)
1. **FSA areas** (source #7): official StatCan polygons. Label: "Postal code area (first 3 characters)".
2. **Board coverage** (#6 + #8): built by joining service-area municipalities to census subdivision polygons. Label: "Approximate school board area".
3. **Nearest-school areas**: Voronoi polygons per board, language and level. Label: "Nearest school, NOT the official boundary".
4. **Official attendance areas** (#11): only where available. Label: "Official boundary from <board>, <date>".
The map legend must explain all four in plain language.

## Site contract
- `/`: search box (school name, city, postal code) plus "Use my location" (asks permission; never stored). Short plain-language explainer of what EQAO is and isn't.
- `/fsa/<FSA>/`: map of that postal area with all schools in and near it, grouped by board/language/level. Area context from census (#9), with source.
- `/school/<bsid>/`: header facts; map; EQAO chart showing the school vs board vs province over all available years; enrolment trend; context; nearby licensed child care; links to the school website, the board's official school locator and the EQAO school page; a "Sources" section; a "Report a correction" link.
- `/board/<number>/`: board summary, map of its schools, board-level indicators.
- `/compare/?ids=a,b,c`: up to 3 schools side by side (same metrics, same years).
- `/about/`: what this is, who runs it, why it's free, the privacy statement.
- `/methodology/`: every metric explained, how suppression and small cohorts are handled, how approximate boundaries are built, the full source list with licences and dates.
- `/data/`: download the cleaned JSON/CSV with attribution (open data in, open data out).
- Mobile-first, readable at 390px, WCAG AA contrast, keyboard navigable, charts have text tables underneath.
- Every page footer: data last updated date + "Not affiliated with EQAO, the Ministry of Education or any school board."

## Phasing
- **Phase 1 (this goal):** all Ontario public schools from sources 1, 2, 4, 5, 7, 9 and 10; school/FSA/board/compare pages; FSA layer and nearest-school layer province-wide; board coverage layer.
- **Phase 2 (later goal, not this one):** EQAO repository trends (#3) if terms allow republishing; official attendance areas for pilot boards in Niagara (#11).

## Required tests (minimum)
Pipeline:
- each source loader validates expected columns and fails with a clear error when they change
- suppressed and blank values become `null` + `suppressed: true`, never 0
- every school has `bsid`, `name`, `board_number`, `lat`, `lon`, `fsa`
- FSA derived from postal code matches the FSA polygon containing the point for ≥ 98% of schools (report the mismatches)
- every number in the output has a `source_id` that exists in `sources`
- board coverage polygons: every board in source #6 has a polygon
- Voronoi layer: every polygon contains exactly one school
Site (Playwright):
- home search finds a school by partial name, by city, and by FSA
- a school page renders its EQAO chart + text table and a sources section with working source links (HTTP 200 check in a separate, slow test)
- an FSA page shows its map and schools
- compare page works with 2 and 3 schools
- the map legend shows all layer labels
- no console errors; no third-party requests except the map tiles (and the geocoder if enabled)
- at 390px: no horizontal scroll, tap targets ≥ 44px

## Required screenshots (evidence/)
home-390.png, search-results-390.png, school-page-390.png, school-page-1280.png, fsa-page-390.png, compare-1280.png, map-legend-390.png, methodology-1280.png

## Definition of done (the ONLY stop condition)
`./check.sh` exits 0, and it:
1. runs the pipeline end to end from a clean cache and writes `pipeline/report.md` (record counts per source, missing-coordinate count, FSA mismatches, suppressed-value counts)
2. passes `pytest -q pipeline/tests`
3. generates the site into `site/dist/` and confirms page counts match the school, board and FSA counts
4. serves `site/dist/` locally on port 8078, runs the Playwright tests and screenshots, and confirms all 8 screenshots exist
5. confirms `/methodology/` lists every source in the table above that was used, with licence and retrieval date
When check.sh passes and review approves, mark DONE and stop. No new data sources, features or redesigns after DONE.

## Anti-circling rules (enforced by the runner)
- flesh-out: ONE pass; this file is the spec. Max 2 Inbox questions; if unanswered within 10 minutes, use the defaults.
- If a source is unavailable or "under review", skip it, record that in report.md and on /methodology/, and continue. Never invent or estimate replacement data.
- plan: max 10 steps. Suggested order: (1) scaffold + check.sh stub, (2) source registry + download/cache, (3) school loaders + cleaning + tests, (4) geo: coordinates, FSA join, census FSA context, (5) boundary layers, (6) JSON output + report.md, (7) page generator + templates, (8) maps + charts + search, (9) Playwright tests + screenshots, (10) methodology/about/data pages + final check.sh.
- Spec and plan are FROZEN after approval; replan only to unblock, never to add scope.
- Each step: max 3 implement attempts, max 3 debug loops, then replan once, then Inbox + pause.
- Never repeat an identical fix; never weaken a test to pass it.
- Time budget: 45 min per step, 8 hours total.

## Final report must include
Source-by-source record counts and dates, what was skipped and why, check.sh output, all screenshots, total pages generated, known data gaps, and a list of boards whose official attendance boundaries could be requested in Phase 2.
