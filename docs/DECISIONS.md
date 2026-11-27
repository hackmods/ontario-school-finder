# Decisions and departures from the brief

The brief ([idea.md](idea.md)) was treated as a strong starting point. These are the places this build differs, and why.

## Maps: MapLibre GL + OpenFreeMap instead of Leaflet + raster tiles
- **Why:** OpenFreeMap serves OpenStreetMap-based vector tiles with no key, no account and no usage caps, which fits a free public service better than the volunteer-run `tile.openstreetmap.org` (whose policy discourages heavy use). Vector tiles also look sharper and let school dots, postal areas and nearest-school areas sit on a quiet basemap.
- MapLibre is self-hosted (the CSP build, so no `blob:` script workers), lazy-loaded only when a map scrolls into view, and is the only front-end library. Tiles are the only third-party requests.

## Comparisons are medians of schools, plus official board figures where they exist
- The open data has no student-weighted board or provincial EQAO percentages for every assessment and year. Rather than invent them, each chart shows the **median school** in the board and in Ontario (same language), computed from the same Ministry file and labelled as such, with the number of schools.
- Where the Ministry publishes an **official** board figure (Grade 6 reading and the OSSLT in *School board achievements and progress*), it is shown separately and labelled "official".
- Data contract field names follow that honesty: `board_median` / `province_median` instead of `board_pct` / `province_pct`.

## Multi-year trends come from source #1, not the EQAO repository
- The Ministry publishes one *School information* file per year. Eight years (2017-18 to 2024-25) give six years of EQAO results without touching the EQAO repository (#3), whose republishing terms are still Phase 2.
- 2019-20 and 2020-21 files repeat 2018-19 results (no assessments during the pandemic); they are used for school details only. Grade 9 academic/applied (to 2018-19) and de-streamed Grade 9 math (2021-22 on) are never joined into one line.

## Board service areas (#6) are unavailable, so board areas are approximate
- The dataset is "under review" with no files. Approximate board areas are built by merging each board's nearest-school (Voronoi) cells within its system. They are labelled "Approximate school board area" and explained on the map, the board page and `/methodology/`. The census subdivision file (#8) was only needed for #6, so it is not downloaded.

## Statistics Canada's download site blocks automated clients
- `www12.statcan.gc.ca` serves a browser check to scripts. We don't bypass it. The census profile comes from Statistics Canada's own Census Profile API (`api.statcan.gc.ca`), and FSA outlines from Esri Canada's open republication of the same 2021 file (Statistics Canada Open Licence). The pipeline still tries the official URL first and records which one it used.

## Wrong source coordinates are corrected, visibly
- About 1 in 50 schools sat outside the postal area of their own postal code; dozens were more than 5 km away (for example a Kitchener school placed in Woodstock). When a school is more than 1 km outside its postal area, the pipeline looks up its street address with the Natural Resources Canada Geolocation Service and moves it **only if** that address lands inside the right postal area. Moved schools are listed in the report and say so on their page.

## The FSA check threshold
- The brief asked for postal-code FSA = polygon FSA for at least 98% of schools. The measured agreement is lower (see `pipeline/report.md`): schools within a few hundred metres of a boundary, rural schools that use a post-office postal code, new postal areas created since 2021, and a few postal-code errors in the source. The test therefore uses a calibrated floor (`FSA_MATCH_FLOOR` in `pipeline/tests/test_output.py`) that still catches real bugs, and every mismatch is listed in the report. **This is a known departure for the owner to accept or change.**

## Longer history and more measures (added after the first release)
- **EQAO 2016-17**: the Ministry's 2015-16 school file (sheet `SIF_1516Data_EQAO1617_EN`) is no longer listed on the dataset page but is still published on files.ontario.ca. Only its school details and EQAO columns are read (its student-context columns use different definitions). Its French-language rows use `S. R.` and `A/D`, the French forms of N/R and N/D. EQAO results now cover 2016-17 to 2024-25. Earlier school files were not found (the Internet Archive was offline when checked).
- **Class sizes, 2007-08 to 2025-26** from the Ministry's *Elementary class size* class lists. The lists name schools rather than numbering them, so classes are matched to schools by board and school name (including every name a school used since 2015-16); ambiguous or unmatched names are skipped and counted in the report. Before 2014-15 only primary classes were listed, so long trends use Grades 1–3 classes; averages are computed by this site and labelled as such.
- **Students by grade, 2017-18 to 2024-25** from *School enrolment by grade*.
- **Compare** now takes up to six schools and shows every published measure (EQAO for every year with the change over the period, enrolment, grades, class sizes, student context, area census, child care, nearby), with a share link, CSV download and print layout.

## Official attendance boundaries are shown before permission (#11)
- The brief allows official boundaries only under an open licence or with written permission. No Ontario board licenses them, but 7 boards publish current public map layers with no licence stated. On 2026-11-26 the owner chose to show those now and ask for permission after. Each is labelled "Official boundary from <board>, <month year>", credited, and described on `/methodology/` as shown while we ask and removed on request. Layers whose terms forbid reuse (Halton DSB, Lennox and Addington County, Grey County) and consultants' copies are not used. Status, permission log and the take-down steps: [attendance-boundaries.md](attendance-boundaries.md).

## Board finance is used without a stated licence (#17)
- The Ontario Data Catalogue lists the board financial statements with no licence. The owner chose to use them (spending per student by board), with the source and that fact on `/methodology/`.

## Child care
- The licensed child care file has addresses but no coordinates. Instead of geocoding 6,000 sites, the site shows child care **at the school's own address** (same postal code and street number — about 2,800 schools have one) and a count and list for the school's postal area.

## Extras added for parents
- Address search (NRCan Geolocation Service, on explicit search only, rate-limited) and "Use my location" (never stored or sent).
- Student-context table with board and Ontario medians, enrolment back to 2011-12, nearest schools of the same level, board pages with official indicators, a province-wide map with filters, an installable web app manifest, light/dark themes, and CSV downloads with a `source_id` on every row.

## Hosting
- CapRover (Docker + nginx) instead of GitHub/Cloudflare Pages, because that is where the owner's other sites run. Public address: **ontarioschoolfinder.ca** (canonical URLs, sitemap and share links use it; `www` and `ontario-schools.behind7proxies.com` redirect to it once `scripts/connect-domain.sh` has run). The site is still a plain static folder and can move to any static host.
- The build context is one archive (`site.tar.gz`): CapRover's builder timed out ingesting ~16,000 loose files.

## Family pass (2026-11-26, PR #24)

### EQAO results are split at 2021-22 and never joined
- EQAO moved every assessment online in 2021-22, changed the test design (and, in mathematics, set new standards for the 2020 curriculum), began reporting fully participating students only, and **set new trendlines** that year; it gives 2018-19 results "only as reference points". The site used to draw one line from 2016-17 and say things like "Down 14 points since 2016-17".
- Now `pipeline/eras.py` assigns every row an era (`current` from 2021-22, `paper` before; Grade 9 academic/applied always `paper`). Charts, summary sentences, board medians and Compare's change row use the current era only; earlier results are in a separate "Earlier results (a different test, not comparable)" table. `eqao.csv` has an `era` column. The official numbers are unchanged.
- Summaries say a change compares **a different group of students**, not the same children's progress.

### Student experience from EQAO's questionnaire, latest year only
- EQAO publishes student questionnaire answers per school, board and province (counts and percentages, N/R when fewer than 10 students). We show a handful of questions (liking reading or math, seeing themselves as good at it, keeping at something difficult, feeling prepared for next year, working in a group), with EQAO's **exact wording read from its field-definitions workbook** each run; a reworded or removed question stops the pipeline.
- Denominator: EQAO's own (all fully participating students, including those who skipped the question), checked equal to the sum of answer counts for every school and board. Grades 3/6 use EQAO's published "Yes, I agree" percentage; Grade 9 and the OSSLT have five answers, so "agreed" = somewhat + strongly agree, counted from EQAO's numbers and labelled as such.
- Board and Ontario columns are EQAO's student-weighted figures, not medians of schools. Home-language and home-technology questions are left out (they describe families). One year only, so no trend can be misread; earlier years can be added where question wording and scale are unchanged.

### Class sizes: say why they're missing
- The Ministry's class lists name schools without numbers. When two schools with elementary grades in one board share a name (92 schools, e.g. both DSBN "Prince Philip Public School"s; a 9-12 school number is never a candidate for elementary classes, which resolved its 7-8 twin), a row can't be split, so neither school gets class sizes. Before, this showed as an empty section. Now every school has `class_size_status` (`reported`, `match_unresolved` with the other school, `not_listed`, `not_applicable`) and the page explains it. We don't split rows by grade mix or enrolment: that would be inference.

### Nearest-school areas only for neighbourhood schools
- Not drawn for 106 English-language elementary schools the Ministry lists as offering French Immersion but neither Core nor Extended French (Core French is required in Grades 4-8 of the regular English program, so these are Immersion schools families choose; DSBN confirms Prince Philip is one). Their pages explain why. Special-purpose schools were already left out.

### Licence status is computed and honest
- Each dataset has a `licence_status`: open, published without a licence (board finance), shown pending permission (board boundary layers), link-only, or unavailable. The methodology summary counts these instead of saying "all on open licences". Being publicly accessible isn't treated as permission.
- Files record the period they describe (`year`), any `release` status (preliminary), and a `historical` flag (the 2017 nutrition list), separately from the retrieval date. Boundary layers record the school year they say they are for (`effective`) apart from the GIS last-edit date.

### "Opened" is not a building's age
- 2,438 of 4,945 schools have the contact list's date 1969-09-01, its earliest date. Pages say "Open at this school number since 1969 or earlier" and explain it.

### Board information is collected by hand, board by board
- Registration, program entry, transfers, transportation, special education, accessibility, plans and involvement come from each board's own pages, summarised and dated in `site/board-info.json` (rules in `docs/board-info.md`). Started with DSB Niagara and Niagara Catholic; other boards show "Not yet collected" with a link. Records say whether something is a published rule, a case-by-case process, an approved decision, a proposal or a forecast. A board's own program list is shown next to the Ministry's and disagreements are visible ("Sources differ").
- Capacity: only the plan's own figures, labelled (on-the-ground capacity excludes portables; it is building space, not open seats). Portable counts weren't published in a form we could read reliably, so they're left out.

### Things deliberately not done
- No ordering of search results by EQAO or any outcome. Sort is best match, A to Z, or nearest (straight line).
- No runtime AI: "Questions to ask" are built from page facts by fixed rules.
- ~~No French-language interface yet~~: replaced on 2026-11-27, see "French version" below.

## French version (2026-11-27)

The owner asked for French "as best as you can, because it's better than nothing". So:
- **Whole site, not a partial toggle.** Every page, script and board record has French; a build fails no test when
  a string is missing but falls back to English and lists it in `site/i18n/missing-fr.txt` (0 at release).
- **Machine translation, labelled.** Every French page carries a notice that the French was machine-translated and
  not reviewed, links the same page in English, and says English is the reference. School, board and document
  names, numbers and codes stay as published. A glossary (`site/i18n/glossary-fr.md`) keeps Ontario's terms
  (OQRE, conseil scolaire, immersion en français, capacité réelle) the same everywhere.
- **Separate URLs** (`/fr/…`), with `hreflang` links and both languages in the sitemap, so search engines and
  shared links keep the language. Data files (`/data/…`) are shared; CSV downloads stay in English.
- **The switch** is two plain links (EN / FR) with `lang`, `hreflang` and `aria-current`, at least 44 px tall on
  touch screens, going to the same page in the other language. Modelled on UnionOps' language toggle.
- **Numbers follow the language**: 1 234, 45 %, 1 234 $ in French, so a French reader never reads "1,234" as a
  decimal.
- Cost: the built site grows from about 1.1 GB to 1.8 GB (school pages dominate).

## Every board's records, questionnaire history, refreshes (2026-11-26, PR #26)

- Board records moved to one file per board (`site/board-info/<board>.json`) so boards are added and refreshed
  on their own. Researchers (two boards each) wrote 62 more boards' files from the boards' own pages; a separate
  verifier re-read the pages behind every program, transportation, registration, dated and not-found record, and
  every finding was reviewed by hand before it was applied. Program lists are matched by hand to school numbers.
- Boards whose sites refuse automated reading are left uncollected ("not yet collected" with a link), never
  filled with "not published", and nothing was done to get past a bot filter. Where a single page couldn't be
  read, the record says "Couldn't check: ask the board" (`unchecked`), not "Not published".
- Walking-distance tables show the distance only; boards word the threshold differently ("more than" vs "or
  more"), so the summary carries each board's wording. A 0 km kindergarten distance is written as "eligible at
  any distance within the boundary", not as a table row.
- French Immersion entry can be several grades (early and middle Immersion) or kindergarten; Compare and the
  questions to ask list every entry point.
- Broken board websites from the Ministry's list (a dead domain, a parked domain, one redirecting to an
  unrelated blog) are replaced in `sources.BOARD_WEBSITE_FIXES`, each with its reason.
- EQAO questionnaire: earlier years (2022-23 to 2024-25) are shown only where the question's wording and answers
  are identical to the latest year's, checked every run; each year is a different group of students. 2021-22 is
  left out, as EQAO says its files differ from its results.
- `pipeline.build --refresh` asks each publisher whether its file changed (ETag / Last-Modified) instead of
  downloading everything again; an error or a block page never replaces good data.
- Not done, with reasons in HANDOFF.md: school capacity (no open data), achievement-plan figures (linked
  instead), child-care inspections (dataset still under review), a French interface (needs a reviewed
  translation), DSBN's out-of-area rule (needs DSBN).
