# Board information (`site/board-info/`)

Practical, sourced information families need to act: how to register, which school serves an address,
program entry (French Immersion), asking for another school, transportation rules, special education,
accessibility, newcomer support, board plans and how to take part. It is collected **by hand** from each
board's own pages, summarised in plain words, and inherited by every school page of that board.

One file per board: `site/board-info/<board number>.json` (e.g. `B66150.json`), plus `_meta.json` (the
refresh rules). A board with no file shows "Not yet collected for this board" and a link to the board, never a
guess. Coverage and the boards that couldn't be collected are listed in [HANDOFF.md](HANDOFF.md).

## Rules

- **Read the page before you write the record.** Every `url` must be a page or document you fetched and
  read on the board's own site (or its transportation consortium). Search-engine snippets don't count.
- **Summarise, don't copy.** A few plain sentences in `summary`; no long quotations of policy text.
- **Say what kind of fact it is** (`kind`):
  - `rule`: a published rule that applies to everyone it describes (walk distances, entry grade);
  - `process`: how to ask, where the answer is decided case by case (registration, out-of-area requests);
  - `decision`: approved by the board (with `decided`);
  - `proposal`: a recommendation not yet decided; `projection`: figures from a plan that include forecasts;
    `plan`: a board plan as a whole;
  - `not_found`: we looked and the board doesn't publish it. Say so; don't leave a gap that reads as "no".
- **Never claim a school has space**, never automate a sign-in or eligibility system, never collect family
  information. Link to official forms instead of recreating them.
- **Keep board, school and province apart.** Board plans (accommodation, achievement) are board-wide; a
  record for one school goes under `schools.<bsid>`; an approved decision naming schools goes in `decisions`.
- **Match schools by hand**, by name and city checked against the grade range, and say how in `match`
  (decisions) or the `school_programs._about` note. Don't use fuzzy matching on its own.
- **Programs a board lists itself** (`school_programs`) are shown next to the Ministry's FSL list. When they
  disagree (DSBN lists Bridgeview as an Immersion school; the Ministry's preliminary list doesn't), the page
  shows both and says "Sources differ".

## Fields

| field | meaning |
|---|---|
| `id` | stable key, unique across the file |
| `topic` | `registration`, `address_lookup`, `program`, `transfer`, `transportation`, `special_education`, `seac`, `accessibility`, `newcomer`, `planning`, `achievement_plan`, `involvement`, `concerns` |
| `kind` | see above |
| `applies` | levels it applies to: `elementary`, `secondary` |
| `program` | for program records: only shown to schools that offer the program (`french-immersion`) |
| `lifecycle` | `dates` (registration windows, deadlines), `rules`, `plans`, `contacts`: how fast it goes stale |
| `title`, `url` | the board's own page or document |
| `summary` | plain words |
| `facts` | structured facts used on pages: `entry_grades` (grade codes `JK`, `K` = senior kindergarten, `1` to `12`; list every entry point, e.g. early and middle Immersion), `walk_km` (the board's own grade groups and distances), `capacity_otg`, `enrolment`, `projected` |
| `related` | further official links |
| `source_date` | the date the document gives itself (e.g. "Latest review September 8, 2026") |
| `verified` | the day you read it (ISO date) |

`refresh_days` sets when a record is flagged "may be out of date: check the board's page" on the site:
90 days for `dates`, 180 for `contacts`, 365 for `rules` and `plans`.

## Refreshing

1. For each record, open its `url` (and `related` links). If it still says the same, update `verified`.
2. If it changed, rewrite `summary`/`facts` from the page, and update `verified` and `source_date`.
3. Each winter, check the French Immersion pages for the next registration window (both Niagara boards
   register for Grade 1 Immersion in January).
4. Run `pytest pipeline/tests/test_family.py` (schema, dates, every named school exists) and rebuild.

A quick reachability check of every link: `node -e` or `curl -s -o /dev/null -w "%{http_code}"` over the
URLs; every one returned 200 on 2026-11-26.

## A board file

```json
{ "board": "B66150", "name": "District School Board of Niagara", "short": "DSB Niagara", "checked": "2026-11-26",
  "records": [ ... ],
  "schools": { "<bsid>": { "records": [ ... ] } },
  "decisions": [ { ..., "decided": "2026-06-16", "schools": ["<bsid>"], "match": "how names were matched" } ],
  "school_programs": [ { "program": "french-immersion", "title": "...", "url": "...", "verified": "...", "schools": { "<bsid>": "name on the list (city)" } } ] }
```

Every record id in a file starts with the same prefix (`dsbn-`), unique to the board. `schools`, `decisions`
and `school_programs` are optional, and every school they name must belong to the board (the tests check).
District school boards need at least one record for each of the 13 topics (`not_found` when the board doesn't
publish it); school authorities (hospital and treatment-centre schools, isolate boards, provincial schools) only
what applies to them.

**A site that blocks automated reading** (Cloudflare challenge, 403) is not a board that publishes nothing: leave
that board without a file rather than write `not_found` records, and list it in HANDOFF.md for a person to read.

## Adding a board

Copy one board's file to `site/board-info/<board number>.json`, change `board`, `name`, `short` and the id prefix, then read that board's pages for each topic. Start with registration, the address
lookup, program entry, out-of-area requests and transportation (the "Attendance and registration" panel),
then special education, SEAC, accessibility, newcomer support, plans and involvement. Never guess: use
`not_found` when you looked and the board doesn't publish it.
