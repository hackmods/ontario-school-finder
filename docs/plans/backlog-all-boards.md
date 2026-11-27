# Backlog for all boards (2026-11-26)

Owner asked: "finish the full backlog for all boards" (after #25 went live). Working branch
`feat/backlog-all-boards`. This file survives context resets; tick items as they land.

## Items and decisions
1. **Board records for every board** (HANDOFF backlog 1). Move `site/board-info.json` to one file per
   board in `site/board-info/` (`_meta.json` + `<B>.json`), so boards refresh independently. Research
   the other 70 district school boards and 12 school authorities with worker subagents, 2 boards each;
   workers write `scratchpad/board-records/<B>.json` in the final format. I merge after:
   - automated checks: schema tests, every url and related url returns 200, ids unique, all 13 topics
     covered (or `not_found`), program-list bsids belong to the board;
   - adversarial pass: re-read the pages behind `program`, `transportation`, `dates` and `not_found`
     records and correct anything that doesn't match.
2. **Questionnaire history** (backlog 3): EQAO open data has 2021-22 to 2024-25 ZIPs and definitions.
   Add 2022-23 to 2024-25 only where wording and answer scale match; 2021-22 left out (EQAO says its
   CSVs differ from its dashboards).
3. **Achievement plans** (backlog 4): each board's plan linked as an `achievement_plan` record; the
   Ministry's official board figures are already on board pages. No transcription of infographics.
4. **School capacity** (backlog 5): the Ministry's SFIS dataset (capacity by school) is still
   `under_review` with 0 resources (checked 2026-11-26), so no province-wide data; each board's long-term
   accommodation plan is linked as a `planning` record. Per-school transcription not done.
5. **Child care** (backlog 6): recheck the compliance dataset; blocked if still under review.
6. **Conditional downloads** (backlog 7): ETag / If-Modified-Since in `pipeline/fetch.py`.
7. **French interface** (backlog 8) and **DSBN out-of-area** (backlog 2): blocked on a human (a reviewed
   translation; DSBN's answer). Not done.

## Status
- [ ] board-info per-board files + loader + tests
- [ ] worker waves (boards) -> merge -> checks -> adversarial pass
- [ ] questionnaire history
- [ ] conditional downloads
- [ ] docs (board-info.md, HANDOFF, README, DECISIONS, methodology coverage)
- [ ] check.sh, draft PR, owner OK, merge + deploy
