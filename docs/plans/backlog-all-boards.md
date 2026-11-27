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
- [x] board-info per-board files + loader + tests (commit 446ea4c)
- [ ] worker waves. Scratchpad (session temp): brief-board-records.md, boards-in/<B>.json, board-records/<B>.json,
      check-board.mjs (checks; --install copies passing files without notes), brief-verify.md, verify/<B>.json,
      blocked-boards.txt. Wave 1 Toronto/Peel/Ottawa/Waterloo/York/London/Durham; wave 2 Halton/Hamilton/Simcoe/
      UCDSB/KPR/Upper Grand/Grand Erie; wave 3 Essex/Lambton/Limestone/HPE+Renfrew/Bluewater/Avon/TLDSB+NN;
      wave 4 north (Rainbow+Sudbury C, Algoma+Huron-Superior, Lakehead+TBC, KP+Kenora C, Rainy River+Northwest C,
      Superior-Greenstone+Superior North C, DSB1+Northeastern C); wave 5 RCCDSB+NPSC, French boards (Viamonde+
      MonAvenir, CEPEO+CECCE, CSDCEO+Providence, Nouvel-Ontario+CSPGNO, Grandes Rivieres+CSPNE, Franco-Nord+Aurores);
      wave 6 school authorities.
- Blocked (no file, site refuses automated reading): TDSB, TCDSB, Peel DSB, Dufferin-Peel CDSB, OCDSB, PVNCCDSB,
  Rainbow DSB (list: scratchpad/blocked-boards.txt). Never spoof a browser to get past a bot filter (the safety
  classifier refused it, correctly).
- Installed in site/board-info (verified): OCSB, WRDSB, WCDSB, DDSB, DCDSB, TVDSB, LDCSB, YRDSB, YCDSB, KPRDSB.
- Verify running (8 agents) for 33 boards; research still running: Rainy River+NW C, DSB1+NE C, RCCDSB+NPSC,
  6 French pairs, authorities. Then verify those, apply-verify.mjs (review, --apply), check-board.mjs --install.
- Owner (2026-11-26): deploy at most once an hour (server almost out of disk); nav Compare count spacing fixed
  (140bfff).
- [ ] verify pass (brief-verify.md) on program/transportation/registration/dates/not_found records -> apply fixes
- [x] questionnaire history (ec96c03), pipeline rebuilt; Ontario-wide figures stable across years
- [x] conditional downloads (e300bb4)
- [ ] docs (board-info.md done; HANDOFF, README, DECISIONS, methodology coverage)
- [ ] check.sh, draft PR, owner OK, merge + deploy
