# Brief for researchers: transcribe one board's school capacity table

Ontario has no open dataset of school capacity, so families only see it if someone copies it, carefully, from the
board's own long-term accommodation or capital plan. You are transcribing **one board's** table. Accuracy beats
coverage: leave a school out rather than guess.

Read first: `docs/capacity-sources.md` (where this board's table is) and the Prince Philip record in
`site/board-info/B66150.json` (`schools.456110`), which shows how the site displays it.

Inputs: `SCRATCH\boards-in\<board>.json` (every school with its number, name, city, level and grades).

## What to copy, per school

- `capacity`: the number the plan gives as the building's capacity, and `capacity_label` exactly as the plan
  names it ("On-the-ground capacity (OTG)", "Ministry rated capacity", "Permanent capacity"...). Same label for the
  whole board.
- `enrolment`: the actual enrolment the plan reports, with the year as the plan writes it (e.g. "2024-25" or
  "October 31, 2024"). Only actual figures, not projections.
- `projected`: up to three projected enrolments the table gives (e.g. 5 and 10 years out), with their years.
- `page`: the PDF page number (as your PDF reader counts them, starting at 1) where the row is.
- `name_in_plan`: the school name exactly as the plan prints it.

Do not compute anything (no utilization percentages, no "over capacity" labels of your own). If the plan itself
says a school is over or under capacity, put the plan's words in `plan_note` (short).

Match each row to **exactly one** school in your input file by name and city, checked against level and grades.
Schools that closed, merged or are not yet open go in `unmatched` with the reason. Skip a row you can't read
cleanly (columns misaligned, scanned image) and list it in `unmatched` too. Holding schools, portables and
"pupil places" are not capacity: don't copy them.

Use `pdftotext -layout` (or read the PDF pages directly) and check every number against the page; PDF text
extraction misaligns columns, so read each row as a whole. Never invent a year.

## Output

`SCRATCH\capacity\<board>.json`:

```json
{ "board": "B66044", "source": { "title": "<plan title as printed>", "url": "<PDF url>", "source_date": "<the date the plan gives itself>" },
  "capacity_label": "On-the-ground capacity (OTG)",
  "schools": { "<bsid>": { "name_in_plan": "...", "page": 41, "capacity": 412,
                           "enrolment": { "year": "2024-25", "value": 388 },
                           "projected": [ { "year": "2029-30", "value": 402 } ], "plan_note": "" } },
  "unmatched": [ { "name_in_plan": "...", "reason": "..." } ],
  "doubts": [] }
```

Check the URL returns 200 (`curl -sL -o /dev/null -w "%{http_code}" -A "Mozilla/5.0" "<url>"`). Never work around a
site that refuses automated reading; report it instead. On Windows never pipe a script into `python -`.

Report back in under 10 lines: schools transcribed / rows in the table, unmatched count, doubts.
