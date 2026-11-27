# Brief for researchers: verify board records against the board's own pages

Another researcher wrote family-facing records about Ontario school boards. Your job is to check them, not to
trust them. Families will act on these (when to register, which grade French Immersion starts, how far a child
walks before a bus), so a wrong record is worse than a missing one.

`SCRATCH` = a working folder outside the repo (researchers write there; a person reviews and merges)

For each board file you are given (`SCRATCH\board-records\<board>.json`), check these records:
- every record with `topic` `program`, `transportation` or `registration`;
- every record with `lifecycle` `dates`;
- every record with `kind` `not_found`;
- the `school_programs` list, if any (spot-check 3 schools against the board's list page).

For each checked record, open its `url` yourself (WebFetch, or `curl -sL -A "Mozilla/5.0"` for PDFs) and compare:
- every number and grade in `summary` and `facts` (`entry_grades`, `walk_km`), every date and deadline;
- whether `kind` is right (a published rule vs a case-by-case process vs a plan);
- for `not_found`: search the board's site (its search box, its site map, the obvious menu pages) for the thing.
  If you find it, that's a finding. If the page couldn't be read (the site blocks automated reading, a list loads by script, a sign-in), the
  record must say so and carry `"unchecked": true` (shown on the site as "Couldn't check: ask the board"):
  a plain `not_found` (shown as "Not published") must never stand in for "we couldn't read it".
- whether the summary says anything the page doesn't (eligibility, guarantees, space, dates from another year).

Don't rewrite records that are right. Don't nitpick style.

## Output

Write `SCRATCH\verify\<board>.json`:

```json
{ "board": "B66095", "checked": 14,
  "findings": [ { "id": "yrdsb-fi", "severity": "wrong|unsupported|misleading|found_it",
                  "problem": "Page says French Immersion starts in Grade 1, record says SK.",
                  "evidence_url": "https://...", "evidence": "short quote or paraphrase from the page",
                  "fix": { "summary": "...corrected summary...", "facts": { "entry_grades": ["1"] }, "kind": "rule",
                           "url": "...", "title": "..." } } ] }
```

`fix` holds only the fields that should change, each a full replacement value, written to the same rules as the
original (plain English, 40 to 600 characters, your own words, no claims about space). For a `not_found` you
disproved, give the full record fields (`kind`, `title`, `url`, `summary`, and `facts`/`lifecycle` if needed).
Every `url` in a fix must return 200 with `curl -sL -o /dev/null -w "%{http_code}" -A "Mozilla/5.0" "<url>"`.

On Windows never pipe a script into `python -` (it hangs); use `node -e` or a script file.

## Report back (under 10 lines)

Per board: records checked, findings by severity, and anything you couldn't check. Don't paste the records.
