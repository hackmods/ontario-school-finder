# Brief for researchers: hand-checked family records for Ontario school boards

You are researching official school board web pages for **Ontario School Finder** (ontarioschoolfinder.ca), a free,
ad-free site that helps families understand Ontario schools and take next steps. Every school page shows its board's
records in "Attendance and registration", "Supports" and "Plans and involvement". Families act on these, so accuracy
beats coverage: a clear `not_found` is better than a guess.

Read before starting (do not edit anything in the repo):
- `docs/board-info.md`: the rules and fields. Follow them exactly.
- `site/board-info/B66150.json` (DSB Niagara) and `B67156.json`
  (Niagara Catholic): finished examples of the output. Match their tone, length and structure.
- Your board's input file: `SCRATCH\boards-in\<board>.json` (made with
  `node scripts/board-info-input.mjs <board> SCRATCH\boards-in`). It has the board's website, the address-lookup link we
  already have (`locator`, may be marked `unverified`), and every school with its number (`bsid`), name, city, level,
  grade range and the Ministry's French program flags.

`SCRATCH` = a working folder outside the repo (researchers write there; a person reviews and merges)

## Output

Write one file per board: `SCRATCH\board-records\<board number>.json`, e.g. `B66052.json` (not the id prefix),
UTF-8, 2-space indent. If the board's site refuses automated reading altogether (403, Cloudflare challenge),
**write no file**: report it as blocked. Never write placeholder records. The shape:

```json
{
  "board": "B66052",
  "name": "Toronto District School Board",
  "short": "TDSB",
  "checked": "YYYY-MM-DD",
  "records": [ { ...record... } ],
  "school_programs": [ { ...list... } ],
  "decisions": [ { ...decision... } ],
  "notes": { "capacity": "", "unmatched_list_names": [], "blocked": [], "doubts": [] }
}
```

- `name`: the board's official name as its site writes it. `short`: the short name families use (e.g. "TDSB",
  "Peel DSB", "CS Viamonde").
- `checked` and every `verified`: today's date from `date +%F`.
- `school_programs` and `decisions` are optional; leave the key out if you have none.
- `notes` is for the reviewer and is removed before publishing:
  - `capacity`: one sentence on whether the board's long-term accommodation plan has a table of school capacity
    (OTG) and enrolment by school, and where (URL + page). Don't transcribe it.
  - `unmatched_list_names`: names on a board program list you could not match to exactly one school.
  - `blocked`: URLs that refused automated reading (403, CAPTCHA, JavaScript wall). Do not work around a wall.
  - `doubts`: anything you were unsure about.

### Record fields

`id` (prefix given in your task, then a short slug: `tdsb-register`), `topic`, `kind`, `applies`
(`["elementary","secondary"]` or one), `lifecycle` (`dates` when the record gives a deadline or registration
window; `rules`, `plans`, `contacts` otherwise), `title` (the page's own title; add " (PDF)" for PDFs), `url`,
`summary` (40 to 600 characters, plain English, your own words), optional `facts`, `related` (list of
`{title, url}`), `source_date` (the date the document gives itself, as written), `verified`. Program records also
have `program`.

Topics: every district school board needs at least one record for **each** of these 13 topics; use
`"kind": "not_found"` with a summary saying what you looked for and what to do instead (ask the board) when the
board doesn't publish it.

| topic | what to find | usual kind |
|---|---|---|
| `registration` | how to register (online/at the school), documents, kindergarten registration timing, eligibility (Catholic boards: who may attend elementary vs secondary, as the board states it; French-language boards: admission of children of rights holders and the admission committee for others) | process |
| `address_lookup` | the board's own "which school serves my address" tool or the transportation consortium's | rule |
| `program` | French Immersion entry: entry grade(s), how and when to apply, lottery/waitlist, transportation to the program. One record per distinct entry point (early, middle, late), `program: "french-immersion"`, `facts.entry_grades` with grade codes `JK`, `K` (senior kindergarten), `1`..`12`. Extended French gets its own record with `program: "extended-french"`. A secondary record if the board describes continuing Immersion in high school (`applies: ["secondary"]`). French-language boards: no Immersion; record the board's support for students still learning French (ALF / PANA / accueil) or `not_found`. A board with no French Immersion at all: `not_found` saying the board doesn't list one. | rule / process |
| `transfer` | asking to attend a school other than your area school (out-of-area, optional attendance, school of choice), and applications to specialized secondary programs if handled board-wide | process |
| `transportation` | the board's or consortium's eligibility rules; put the walk distances in `facts.walk_km` as `{"JK and SK": 0.8, "Grades 1 to 8": 1.6, "Grades 9 to 12": 3.2}` using the board's own grade groupings and km numbers; say if courtesy seats or program transportation exist | rule |
| `special_education` | the board's Special Education Plan and how IEPs/IPRCs work there | rule |
| `seac` | the Special Education Advisory Committee page | rule |
| `accessibility` | the multi-year accessibility plan | rule / plan |
| `newcomer` | welcome / assessment centre, English (or French) language learner reception | rule / process |
| `planning` | long-term accommodation or capital plan, pupil accommodation reviews; say in the summary that projections are forecasts and capacity is building space, not open seats | plan |
| `achievement_plan` | the board's improvement / achievement plan (multi-year strategic plan only if no achievement plan exists) | plan |
| `involvement` | Parent Involvement Committee, school councils (1 or 2 records) | rule |
| `concerns` | how to raise a concern (school first, then superintendent, then trustee/board) | process |

### Board program lists (`school_programs`)

Only when the board publishes an explicit list of its French Immersion (or Extended French) schools:

```json
{ "program": "french-immersion", "title": "<page title>", "url": "<page>", "verified": "YYYY-MM-DD",
  "schools": { "<bsid>": "<name as the board lists it> (<city>)" } }
```

Match each listed school to exactly one school in your input file by name **and** city, checked against its grade
range and level. If a name could match two schools, or none, leave it out and put it in `notes.unmatched_list_names`.
No fuzzy guessing. It is fine, and useful, when the board's list and the Ministry's flags disagree; don't "fix" either.

### Decisions (optional, max 3)

Only an **approved** board decision (with its date) that changes attendance boundaries or programs for named
schools from 2026-27 on, found on the board's planning pages. Shape as in `B67156.json` (`decided`, `schools`
as bsids from your input, `match` explaining how you matched names). Skip if unsure.

## Rules

- Read the page before you write the record (WebFetch, or `curl -sL` for PDFs and pages WebFetch can't read).
  Search results and snippets are not sources. Prefer the board's HTML page over a PDF when both exist.
- Summarise; don't copy. Never claim a school has space or that a child is eligible. Never fill in forms or use
  sign-in systems. Keep board, school and province apart.
- Board pages in French: read them in French, write the summary in English, keep the French `title`.
- URLs must be `https://` and must return 200: check each `url` and `related` url with
  `curl -sL -o /dev/null -w "%{http_code}" -A "Mozilla/5.0" "<url>"`. Use the final URL after redirects when it
  is stable. If a page only works in a browser, list it in `notes.blocked` and say so in `doubts`.
- Dates in summaries must come from the page (e.g. "Kindergarten registration opens in January" only if the
  page says so). If a page shows a past school year's dates, say what it says and that the board updates it yearly.
- Don't spend more than ~30 page reads per board. When the board's site has a search, use it.
- On Windows never pipe a script into `python -` or `python3 -` (it hangs). Use `node -e` or write a script file.
- Validate your file before finishing:
  `node -e "const j=JSON.parse(require('fs').readFileSync(process.argv[1],'utf8'));const T=['registration','address_lookup','program','transfer','transportation','special_education','seac','accessibility','newcomer','planning','achievement_plan','involvement','concerns'];const have=new Set(j.records.map(r=>r.topic));console.log(j.board,j.records.length,'records; missing:',T.filter(t=>!have.has(t)).join(',')||'none');for(const r of j.records){if(r.summary.length<40||r.summary.length>600)console.log('summary length',r.id)}" <file>`

## Report back (keep it short, under 15 lines)

For each board: file path, number of records, topics recorded as `not_found`, program-list schools matched /
listed, anything blocked, and your doubts. Do not paste the records.
