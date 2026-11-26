# Official attendance boundaries: where they are and what it takes to use them

The brief (#11) allows official attendance boundaries only where a board publishes them under an open
licence or gives written permission. This is the state of play from a search in November 2026.

## Result

No Ontario school board publishes its attendance boundaries under an open licence.

**Status (2026-11-26): published pending permission.** The owner chose to show the seven boards
below now, while asking each one for permission. They are labelled "Official boundary from
<board>, <month year>", credited on every page that uses them, and described on How it works with
a promise to take a board's boundaries down when it asks. Everywhere else the site keeps showing
the approximate "nearest school" areas and links each school page to the board's own locator.

Permission log (fill in as replies arrive; one row per board):

| Board | Asked (date, to whom) | Reply (date, who, scope) |
|---|---|---|
| Waterloo Region DSB | | |
| Hamilton-Wentworth DSB | | |
| Simcoe County DSB | | |
| Grand Erie DSB | | |
| Dufferin-Peel CDSB | | |
| Kawartha Pine Ridge DSB | | |
| Halton CDSB | | |

### Taking a board down

Delete that board's entries from `BOUNDARY_LAYERS` in `pipeline/sources.py`, rebuild
(`python -m pipeline.build`, then `python site/generate.py`) and deploy. Its schools fall back to the
nearest-school estimate, and the Map page and How it works drop the board automatically.

## Boards that publish current boundary layers (no licence stated)

These are public ArcGIS layers on the board's own account, read by `pipeline/boundaries.py` from the
layers in `sources.BOUNDARY_LAYERS`. School IDs are board codes, so the pipeline matches each area to
the Ministry school number (BSID) by board, level and school name, or by the one school of that
board and level inside the area. Unmatched areas (development, holding, dual-attendance) are listed
in `pipeline/report.md` and left out.

| Board | Layers | Layer URL (FeatureServer) | Features | Last edited |
|---|---|---|---|---|
| Waterloo Region DSB | Elementary 2026, Secondary 2026 (with French Immersion flag) | `services1.arcgis.com/xKY66Gy3crN5ZX2F/arcgis/rest/services/Boundaries_Elementary_2026` and `.../Boundaries_Secondary_2026` | 158 / 44 | Aug–Sep 2026 |
| Hamilton-Wentworth DSB | Elementary 2025-26, Secondary 2025 | `services3.arcgis.com/xa1UBgwOXoenQ2Ob/arcgis/rest/services/2025_2026_School_Locations_and_Boundaries_WFL1` and `.../2025_HWDSB_Secondary_Boundaries` | 74 / 12 | Jul–Sep 2025 |
| Simcoe County DSB | Elementary and Secondary 2025-26 | `services.arcgis.com/gV678DkT4msvdr0P/arcgis/rest/services/2025_2026_Elementary_Attendance_Areas` and `..._Secondary_Attendance_Areas` | 146 / 22 | Mar 2025 |
| Grand Erie DSB | Elementary 2025, Secondary 2024-25 (has BSID), French Immersion JK-8 2025 | `services8.arcgis.com/XcIMWbWgADdwHqBM/arcgis/rest/services/Elementary_Boundaries_2025_` (+ secondary and FI layers) | 62 / 12 / 6 | 2024–2025 |
| Dufferin-Peel CDSB | Elementary and Secondary with program, 2023-24 | `services5.arcgis.com/OTdNpvC9YulsqUyQ/arcgis/rest/services/School_Locator_Boundaries_2023_2024_NEW` | 148 | Nov 2024 |
| Kawartha Pine Ridge DSB | Elementary with secondary and French Immersion attributes | `services5.arcgis.com/zWVGGWdq5YnrBtnA/arcgis/rest/services/School_Boundary_July_22` | 88 | Jan 2025 |
| Halton CDSB | Elementary regular track, by school year | `services1.arcgis.com/Z2ZyXpStrYRDJ1cf/arcgis/rest/services/Elementary_Regular_Track_Boundary` | 960 | Feb 2025 |

Not usable as published:

- **Halton DSB**: its layer says it is "intended for exclusive use by Halton District School Board Staff".
- **Lennox and Addington County** (Hastings and Prince Edward DSB, Limestone DSB): its terms of use forbid copying or distribution without written consent.
- **Grey County** (Bluewater DSB, Bruce-Grey CDSB): used under the transportation consortium's 2017 permission, with no redistribution grant, and the data is from 2017.
- **Ottawa Catholic SB, Windsor boards, CS Viamonde**: public layers exist, but they are old or unclear in purpose. Confirm with the board before relying on them.
- Copies held by planning consultants (for example Watson & Associates) are working files, not board publications. Don't use them.

Boards with no public boundary layer (locator or PDF maps only), among others: Toronto DSB, Peel DSB,
Ottawa-Carleton DSB, York Region DSB, Durham DSB, Thames Valley DSB, Upper Grand DSB, Waterloo CDSB,
DSB of Niagara (the brief's pilot), Toronto CDSB.

## Asking a board for permission

Send to the board's planning or communications department, and record the reply (who, date, scope)
in `pipeline/sources.py` before adding the layer.

> Subject: Permission to show your school attendance boundaries on Ontario School Finder
>
> Ontario School Finder (https://ontarioschoolfinder.ca) is a free, ad-free website that helps
> parents find publicly funded schools and understand their public results in context. It has no
> accounts, no tracking and no rankings.
>
> Your board publishes its attendance boundaries as a public map layer:
> <layer URL>. We show these boundaries on the pages for your schools and on our province-wide
> map, and we would like your permission to continue. We:
> - label every boundary "Official boundary from <board>, <month year>", link to your school
>   locator, and tell families to confirm their designated school with the board;
> - refresh the layer when you publish a new school year, and will remove it promptly if you ask;
> - credit the board on every page that shows it and list it on our sources page.
>
> If your board prefers a specific licence (for example an Open Government Licence), we are happy
> to follow its terms.

## How it appears on the site

- School page map: the official area replaces the "nearest school" estimate, drawn solid in orange
  and labelled "Official boundary from <board>, <month year>" (the layer's last-edit date).
- Map page: the "Official boundary from the board" layer shows every matched area for the chosen
  level, and names the boards covered.
- How it works: Map areas item 4 lists the boards, levels, area counts and dates; the sources table
  lists each layer as dataset #11 with its URL and retrieval date.
