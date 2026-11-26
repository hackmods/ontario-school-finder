# Handoff: open items and lessons

State at the end of 2026-11-26: PRs #1–#19 merged (Dependabot's #14 closed as superseded by #18),
`main` deployed to https://ontarioschoolfinder.ca (CapRover app `ontario-schools`). The repo is
**public** with no licence (all rights reserved). No open PRs or branches. There is no GitHub Actions
CI: `./check.sh` on your own machine is the definition of done (it passed on 2026-11-26).

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
