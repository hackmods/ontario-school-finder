# Handoff: open items and lessons

State on 2026-11-26: PRs #1–#10 merged, `main` deployed to https://ontarioschoolfinder.ca
(CapRover app `ontario-schools`, build 2026-11-26T08:01:58). No open PRs or branches. There is no
GitHub Actions CI: `./check.sh` on your own machine is the definition of done.

## Open items for the owner

1. **Ask the 7 boards for permission to show their boundaries.** They are live now, labelled as
   shown pending permission. Letter and reply log: [attendance-boundaries.md](attendance-boundaries.md).
   If a board says no, take it down the same day (steps in that file).
2. **FSA check threshold.** Postal code vs. postal-area outline agree for about 95.5% of schools; the
   brief asked for 98%. Accept the calibrated floor or change it ([DECISIONS.md](DECISIONS.md)).
3. **Make the repo public** (owner flips it in GitHub settings). Prepared 2026-11-26:
   - Every blob in all 37 commits, including every PR's commits (GitHub keeps `refs/pull/*`), was scanned for keys,
     tokens, passwords, private keys and personal addresses: none. PR text is clean too. GitHub
     holds no Actions/Dependabot/Codespaces secrets, variables, environments, deploy keys or
     webhooks. `CONTACT_EMAIL` lives only in your Windows user environment.
   - What *will* be public: the owner's name (already on `/about/`), the commit author emails
     (the owner's two addresses, which can't be changed without rewriting history,
     and PR refs keep the old commits anyway), and the server's host name and public IP in
     `deploy.sh` / `scripts/connect-domain.sh` (already public through DNS).
   - Licence: none on purpose (all rights reserved; README "Copyright and reuse", `package.json`
     `UNLICENSED`). Data keeps its source licences; `site/data` and `pipeline/cache` are not in the repo.
   - After going public: turn on secret scanning and push protection, and private vulnerability
     reporting (Settings → Code security). Upload `site/static/img/og.png` as the social preview
     (Settings → General). Optionally set `CORRECTIONS_URL` to the issue chooser so the site's
     corrections page offers GitHub issues as well as email.

## Open engineering items

- **`https://www.` redirects to `http://` apex** (an extra plain-HTTP hop before HTTPS). Fix the
  redirect target in CapRover / `scripts/connect-domain.sh` so `www` goes straight to `https://ontarioschoolfinder.ca`.
- **Boundary layers are named by school year** (for example `Boundaries_Elementary_2026`,
  `2025_2026_...`, `YEAR='2025-2026'`). Each summer, look for each board's new layer, update its
  `url` / `where` in `pipeline/sources.BOUNDARY_LAYERS`, then rebuild (see the cache lesson below).
  Dufferin-Peel's layer is still 2023-24, so its newest schools (St. Sofia, St. Carlo Acutis,
  St. Oscar Romero) have no official area yet.
- **Schools in covered boards still without an official area**: 45 of 695 (650 have one). Mostly holding,
  development and dual-attendance areas, which are left out on purpose. A few are worth a look:
  Hamilton-Wentworth's Dalewood, Westview Middle and Norwood Park aren't in its layer under those
  names. Waterloo has two "Centennial P.S." areas and only one matched. `pipeline/report.md` lists them all.
- **More boards**: Ottawa Catholic SB, the Windsor boards and CS Viamonde have public layers that look old or unclear.
  Confirm with the board before adding. Boards with locator pages only are linked from
  `site/locators.json` (47 boards).
- **Yearly data**: add next year's EQAO Open Data file to `sources.EQAO_OPEN_RESOURCES` (with a
  `label`); the Ministry school file wins once it covers that year. Suspensions stop at 2021-22 and
  nutrition sites are from 2017. Pages say so; recheck the Data Catalogue for newer files.
- **Board service area (#6)** is still "under review" with no files. When it appears, it can replace
  the approximate board areas.

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
