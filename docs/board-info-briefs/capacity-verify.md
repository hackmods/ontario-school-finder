# Brief for verifiers: check a board's transcribed capacity table

Someone transcribed a board's school capacity table into `SCRATCH\capacity\<board>.json` (see
`docs/board-info-briefs/capacity.md` for the format). Check it against the board's own PDF; don't trust it.

1. Open the PDF in `source.url`. Pick at least 12 schools spread across different pages (first, middle and last
   pages of the table, elementary and secondary), plus every school with a `plan_note` and every row named in
   `doubts`.
2. For each, read the row on the PDF page (render the page or use `pdftotext -layout`/`-raw`; read the whole row,
   since columns misalign) and compare `capacity`, `enrolment` (value and year), every `projected` value and
   year, and that `name_in_plan` matches the school number it was matched to (check the name and city in
   `SCRATCH\boards-in\<board>.json`).
3. Check `capacity_label` is what the plan calls the figure, and that no projected figure was copied as actual
   enrolment.

Write `SCRATCH\capacity-verify\<board>.json`:
```json
{ "board": "B66044", "checked": 14, "errors": [ { "bsid": "...", "field": "capacity|enrolment|projected|match|label",
  "recorded": "...", "pdf": "...", "page": 41, "fix": <replacement value, or null to drop the school> } ],
  "notes": [] }
```
Report back in under 6 lines: schools checked, errors found, and whether the error rate suggests the whole file
needs re-reading. On Windows never pipe a script into `python -`.
