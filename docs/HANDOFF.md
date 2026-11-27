# Handoff: open items and lessons

State at the end of 2026-11-27: PRs #1–#30 merged. To deploy from the main checkout:

1. `caprover list` should show `captain-01`; if not, `caprover login -u https://captain.behind7proxies.com -n captain-01`
   (asks for the CapRover password; the CLI sign-in expires after a while).
2. `bash scripts/publish.sh` (rebuilds with `CONTACT_EMAIL` from your environment, checks counts, deploys).
3. Check `https://ontarioschoolfinder.ca/build.json` shows the new build time and `/fr/` loads. `caprover deploy`
   can exit 0 after deploying nothing (an expired sign-in, a refused upload), so always check `build.json`.

The built site is about 1.8 GB with the French pages; `deploy.sh` ships it as one `site.tar.xz` of about 55 MB
(as `.tar.gz` it was 316 MB, which CapRover refused with 413). The repo is **public** with no licence (all rights
reserved). There is no GitHub Actions CI: `./check.sh` on your own machine is the definition of done (it
passed on 2026-11-27). The browser suite also runs against production:
`BASE_URL=https://ontarioschoolfinder.ca npx playwright test`.

## Open items for the owner

1. **Ask the 7 boards for permission to show their boundaries.** They are live, labelled as shown
   pending permission. Letter and reply log: [attendance-boundaries.md](attendance-boundaries.md).
   If a board says no, take it down the same day (steps in that file).
2. **FSA check threshold.** Postal code vs. postal-area outline agree for about 95.5% of schools; the
   brief asked for 98%. Accept the calibrated floor or change it ([DECISIONS.md](DECISIONS.md)).
3. **Social preview image**: upload `site/static/img/og.png` in GitHub → Settings → General (web only,
   no API), so links to the repo show the brand instead of a generic card.
4. **Watch the new inbox**: corrections can now arrive as GitHub issues (the *Data correction* form,
   label `data`) as well as email, and security reports through GitHub's private vulnerability reporting.

## Done on 2026-11-26 (for reference)

- Repo made public after a secret scan of every blob in all commits and PR refs (clean). Secret
  scanning, push protection, private vulnerability reporting, Dependabot alerts and security updates
  are on. What is public anyway: the owner's name (on `/about/`), the commit author emails (can't be
  changed without rewriting history), and the server's host name and IP (already in DNS).
- `www` and the CapRover address now go straight to `https://ontarioschoolfinder.ca` in one hop: the
  site's nginx redirects them, and CapRover's own redirect setting (which went to `http://` first) is off.
- Home map follows the search box; school names on every map; corrections through the GitHub issue
  form; every script, data file and the map library are versioned so deploys reach visitors at once;
  MapLibre 6.4.1 (critical XSS fix).
- Full audit of the live site: 33 pages (every page type) at phone, tablet and desktop widths plus dark
  mode, 1,104 internal links, colour contrast, data spot-checks against the source files, headers,
  sitemap and robots. Clean on errors, links, overflow, labels, alt text, contrast (lowest 4.67:1)
  and data. Fixed:
  - 31 Ministry names that repeat a phrase ("Glenwood School School"), now shown once;
  - board pages downloading every board's area (1.7 MB), now only their own (3–30 KB);
  - `/favicon.ico` missing;
  - school descriptions over 160 characters, and long titles;
  - the Data page heading skipping a level;
  - phone polish: the breadcrumb wrapping, the compare search box and the compare tray text cut off,
    and "elementary" in lowercase on Compare;
  - search ignoring letters typed before its script loaded (Compare, slow connections), found by
    running the browser suite against production.

## Family pass (PR #24, 2026-11-26)

What changed and why is in [DECISIONS.md](DECISIONS.md#family-pass-2026-11-26-pr-24). Maintenance:

- **Board information** ([board-info.md](board-info.md)): one file per board in `site/board-info/`, 64 of 72
  district boards plus school authorities, hand-collected and dated 2026-11-26. Registration windows go stale
  fastest (most boards open French Immersion and kindergarten registration between November and February), so
  re-read every board's `program` and `registration` records each November. Records older than their
  `refresh_days` show "may be out of date" on the site, so by late February 2027 the `dates` records will flag
  themselves. Researcher and verifier briefs plus `scripts/board-info-input.mjs` and
  `scripts/check-board-links.mjs` make a refresh repeatable.
- **Board websites**: the Ministry's contact list had dead, parked or hijacked board website links (Bloorview's
  now redirects to an unrelated blog). `sources.BOARD_WEBSITE_FIXES` replaces those, with the reason; drop an
  entry once the Ministry fixes its list. School websites from the same list were not checked.
- **School website links**: the Ministry's list had 773 school links that no longer work (2026-11-26: 717 dead, 52 on GECDSB's old domain that is now parked, 4 hijacked to unrelated sites such as a games-download page). `site/school-links.json` lists them and the site hides those links and says why. Recheck yearly: `node scripts/check-school-links.mjs <out.json>` sorts every link (links a site refuses to answer for scripts are never treated as broken); review anything new by hand before adding it, especially "elsewhere" results, which can be a school's own new site.
- **EQAO questionnaire**: add next year's four ZIPs and field-definition workbooks to
  `sources.EQAO_SQ_RESOURCES` and move the current year into `sources.EQAO_SQ_HISTORY` (its definitions workbook
  is named by the spring: `G36_2026` = 2025-26). Earlier years show only for questions whose wording and answers
  match the latest year exactly (`build.questionnaire_history`; the report lists what was left out and why). The
  loader stops if a latest-year question's wording disappears; check the questionnaire before changing
  `loaders.SQ_ITEMS`.
- **Refreshing the data**: `python -m pipeline.build --refresh` keeps downloaded files and re-downloads only
  those whose publisher changed them (ETag / Last-Modified); `--clean` (what `./check.sh` runs) downloads
  everything again.
- **EQAO eras**: `pipeline/eras.py` holds the 2021-22 break and EQAO's statements. If EQAO ever announces
  another break, add it there; charts, summaries, Compare and the CSV all follow.
- **Class-size ambiguity**: 92 elementary schools share a name with another school in their board, so the Ministry's
  class lists can't be split between them (listed in `pipeline/report.md`). Only the Ministry adding school
  numbers to the class lists would fix this; ask them through the dataset's contact if worth it.

### Backlog status (updated 2026-11-26, PR #26)

1. **Board records for every board: done for 64 of 72 district boards** and the school authorities that publish
   anything (see [board-info.md](board-info.md#coverage-2026-11-26)); about 3,450 of 4,945 schools. **Blocked:**
   Toronto DSB, Toronto Catholic, Peel, Dufferin-Peel Catholic, Ottawa-Carleton, Peterborough Victoria
   Northumberland and Clarington Catholic, Rainbow and CSDC de l'Est ontarien (about 1,480 schools), plus
   John McGivney Children's Centre: their sites refuse automated reading. They need a person reading in a browser
   (the research brief works for a person too), or the boards' permission for a data feed. Never get around a bot
   filter.
2. **DSBN out-of-area procedure**: policy G-23 (elementary to secondary transfers) is still listed by search
   engines, but its policy-site URL returns 404 and DSBN's current policy list (41 policies, rechecked
   2026-11-26) no longer includes it or any transfer policy. Only a 2022 PDF of the old policy survives; don't
   present it as current. No elementary out-of-area procedure is published either. Ask DSBN's planning
   department and record the answer's source.
3. **Questionnaire history: done.** 2022-23 to 2024-25 shown under each school's latest figure where EQAO's
   wording and answers match (they do for every question; "Feel prepared" wasn't asked in 2022-23). 2021-22 left
   out. Ontario-wide figures are steady across the years, so EQAO's method didn't change.
4. **Board achievement plans: linked, not transcribed.** Every collected board has an `achievement_plan`
   record linking its plan; the Ministry's official board figures are already on each board page. Transcribing
   infographic charts would add little and is error-prone.
5. **School-level capacity: not available as data.** The Ministry's capacity dataset (SFIS) is still "under
   review" with no files (checked 2026-11-26). Each board's long-term plan is linked from its `planning` record,
   and [capacity-sources.md](capacity-sources.md) lists where 33 boards publish a per-school capacity table.
   **Transcribed by hand for 26 boards (1,853 schools, 2026-11-27)**, each row rechecked by a second reader; the
   rest of that list is next (PDF extraction misaligns the tables, so read them by hand).
6. **Child care**: blocked. The provincial compliance dataset is still "under review" with no files (rechecked
   2026-11-26); pages link to Ontario's licensed child care search instead.
7. **Conditional downloads: done** (`python -m pipeline.build --refresh`).
8. **French interface: done as a machine translation (2026-11-27).** Every page is built twice, English at `/…`
   and French at `/fr/…`, with an EN/FR switch in the header, the phone menu and the footer. Every French page
   says it was machine-translated and not reviewed, and that English is the reference. Open: a person who reads
   French should review `site/i18n/fr/*.json` and `site/board-info/fr/` (start with the home, school and board
   pages); a build lists any English string still without French in `site/i18n/missing-fr.txt`. How it works:
   [i18n-brief.md](i18n-brief.md).

Reviewed and not worth doing now (2026-11-26):
- **Grade filter on postal-area pages**: a postal-area page lists schools inside the area's outline plus a
  few just outside, while search matches the postal code, so a link to search shows a different list. Search
  already has the grade filter.
- **Grade filter on the Map page**: the level chips cover the common case; search has the grade filter.
- **Badges in the home search suggestions**: too little room. Search results, board lists, postal-area
  lists, map popups and each school's nearby list show them.

## Open engineering items

- **Boundary layers are named by school year** (for example `Boundaries_Elementary_2026`,
  `2025_2026_...`, `YEAR='2025-2026'`). Each summer, look for each board's new layer, update its
  `url` / `where` in `pipeline/sources.BOUNDARY_LAYERS`, then rebuild (see the cache lesson below).
  Dufferin-Peel's layer is still 2023-24, so its newest schools (St. Sofia, St. Carlo Acutis,
  St. Oscar Romero) have no official area yet.
- **Schools in covered boards still without an official area**: 44 of 695 (651 have one). Almost all
  are holding, development and dual-attendance areas, left out on purpose. Hamilton-Wentworth's
  Dalewood, Westview Middle and Norwood Park aren't in its published layer at all (checked); they need
  a newer layer from the board. `pipeline/report.md` lists every unmatched area.
- **More boards**: Ottawa Catholic SB, the Windsor boards and CS Viamonde have public layers that look
  old or unclear. Confirm with the board before adding. Boards with locator pages only are linked from
  `site/locators.json` (47 boards).
- **Yearly data**: add next year's EQAO Open Data file to `sources.EQAO_OPEN_RESOURCES` (with a
  `label`); the Ministry school file wins once it covers that year. Suspensions stop at 2021-22 and
  nutrition sites are from 2017. Pages say so; recheck the Data Catalogue for newer files.
- **Board service area (#6)** is still "under review" with no files. When it appears, it can replace
  the approximate board areas.
- **Dependabot** now opens PRs for vulnerable packages. `maplibre-gl` needs `npm run vendor` and the
  `LIB` path change (see "Map library" below); the Playwright and font packages only affect tests and
  vendored fonts.
- **A full `./check.sh` from a clean download cache** wasn't run this session (it re-downloads every
  source); run it before the next data refresh.

## Lessons (traps that cost time)

### Data and pipeline
- **Read a layer's fields before filtering on them.** Dufferin-Peel's `Program` column lists the
  programs a school *offers*; every row is still that school's own regular area. Filtering
  `Program='N/A'` silently dropped 56 schools. Check that rows don't overlap before you treat them as
  separate areas.
- **Boards name schools differently from the Ministry.** `pipeline/boundaries.py` expands shorthand
  (P.S., CES, CSS, CVI, DHS, St., Mt.), joins initials ("N.A." = "N A"), and ignores generic words
  (including "Separate"). Same-named schools in one board need the layer's `split` field. A
  junior/senior pair on one site (Frank Panabaker North/South) shares one area. "Holding Area at X"
  name-matches X, so a name match must sit within about 3 km of its area. Unmatched areas go to the report; never guess.
- **The raw download cache is keyed by source id, not URL.** `python -m pipeline.build` reuses
  `pipeline/cache/raw/<id>.<ext>` even after you change a layer's `url` or `where`. Delete that file
  and its entry in `pipeline/cache/manifest.json` (or run `./check.sh`, which starts from a clean cache).
- **ArcGIS layers**: query with `outSR=4326&f=geojson`; the layer's own edit date is
  `editingInfo.lastEditDate` from `<layer>?f=json`. Ask the FSA mirror for `maxAllowableOffset`, or
  it sends about 167 MB.
- **Keep map data light**: simplify in metres (EPSG:3347) relative to each area's size. Official
  areas are about 1.4 KB per school page; the province-wide layers are 129 KB + 45 KB gzipped and load only when chosen.
- **New files under `site/data` must be added to the generator's copy list** (`boards-context.json`
  was missing from `site/dist` once). Guard template number formats against `None`.
- **Don't scrape what blocks scripts**: the StatCan download site and the Ministry SIF app both wall
  automated clients. Use the APIs and files noted in DECISIONS.md.

### Map library (MapLibre)
- Since 6.x MapLibre ships ES modules (no more `maplibre-gl-csp.js`). `scripts/vendor.mjs` copies them
  into `site/static/vendor/maplibre/<version>/`, and the library loads its shared chunk and worker from
  that same folder. The version-named folder is what stops a browser from mixing two versions.
- To upgrade: `npm i -D -E maplibre-gl@<version>`, then `npm run vendor` (it removes the old folder),
  then set `LIB` in `site/static/js/maps.js` to the new folder. `site/generate.py` stops the build if
  `LIB` and the vendored folder disagree.
- Modules need a JavaScript content type. nginx gets `mjs` from the Dockerfile `types`, and local tests
  serve the site with `scripts/serve.py`. Python's own `http.server` sends `.mjs` as text/plain, so
  the map silently doesn't load.

### Tooling on Windows
- Shell edits (`node -e`, heredocs) strip `\` and `$`: regexes and template literals came out broken
  three times. Use a real file editor for those.
- Never pipe Python into `python -` from a heredoc: it hangs. Write a script file, and run it with `PYTHONPATH=.`
  from the repo root if it imports `pipeline`.
- Worktrees: copy `site/data` and `pipeline/cache` in, use the main checkout's `.venv`, and make
  `node_modules` a junction. Before `git worktree remove`, run `cmd //c rmdir <worktree>\node_modules` and move the
  shell out of the folder, or the delete fails with "Permission denied".
- Playwright against another port: `BASE_URL=http://127.0.0.1:<port> npx playwright test`.

### Git and PRs
- Squash-merging a PR and deleting its branch auto-closes any PR stacked on that branch. Retarget the
  stacked PR to `main` first.
- `git cherry-pick -X theirs` silently dropped a template global once. After any replay, diff the
  shared lines by hand.

### Deploying
- There is no staging. Deploy only from the main checkout, level with `origin/main`. A stale checkout
  would roll production back.
- **Caching (fixed 2026-11-26).** Before this, only each page's entry script had a `?v=`. The modules it
  imports (`./lib.js`, `./search.js`) and the data it fetched were cached for an hour, and the map
  library for 30 days, so after a deploy returning visitors could run new pages on old code or data.
  Now:
  - every script shares one version (a hash of all scripts plus the vendored map library);
  - `generate.py`'s `version_scripts` writes it into every import and vendor URL;
  - `/data/` fetches go through `lib.js`'s `dataUrl()` with the page's `<html data-v>`;
  - nginx keeps anything with `?v=` for a year and rechecks pages on every visit (`no-cache`, a 304 when unchanged).
  New code that fetches `/data/` or adds a script must keep this: the Playwright test
  "every script, map library, data and picture request is versioned" fails otherwise.
- Test the real nginx config locally before changing it: run `nginx:1.27-alpine` in Docker with
  `deploy/nginx.conf`, `deploy/security-headers.conf` and `site/dist` mounted (and an empty
  `default.conf`), then `nginx -t`, `curl -I` the headers, and run Playwright against it.
- `CONTACT_EMAIL` is a Windows *user* environment variable. A shell started before it was set doesn't
  see it, and the agent's Git Bash didn't. Without it, the site silently ships with no contact address. Read it with
  `powershell -NoProfile -c "[Environment]::GetEnvironmentVariable('CONTACT_EMAIL','User')"` and pass
  it to `site/generate.py` (or use `scripts/publish.sh`).
- Before building in the main checkout, copy any new raw cache files from your worktree
  (`pipeline/cache/raw/bdy-*` for boundaries) or let the pipeline download them.
- After `./deploy.sh ontario-schools` the old container answers for about 20 seconds. Check
  `/build.json` again before calling it a failure.
- The build rewrites `pipeline/report.md` (timestamps). Restore it afterwards so the main checkout stays clean.

### UI
- The header overflowed at 921–1000 px after the logo change. Below 1080 px the search box becomes a
  nav icon; below 820 px the nav becomes a menu.
- "Use my location" error 1 means the OS, browser or in-app browser blocked it as often as a real
  "no". The message offers the postal-code search instead.
- Long chart series are drawn twice (phone and wide); exactly one is visible, picked by chart width.
