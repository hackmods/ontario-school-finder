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
