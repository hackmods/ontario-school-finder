"""EQAO assessment eras: which school years can sit on one trend line.

EQAO changed every assessment in 2021-22: online delivery, a new assessment model (a linear test
design for literacy, a multi-stage adaptive design for mathematics), new mathematics standards for the
2020 curriculum, and results reported for fully participating students only. EQAO "set new trendlines"
in 2021-22 and gives 2018-19 results "only as reference points". So:

- the **current** era starts in 2021-22 and is the only one a trend, a "change since" or a chart line
  may use;
- the **paper** era (2016-17 to 2018-19 on this site) is kept, shown apart, and never joined to it;
- Grade 9 academic and applied mathematics were separate courses that no longer exist: always paper era.

This is a versioned definition: change ``ERA_DEFINITION_VERSION`` if the rule changes, and keep the
evidence links current.
"""
from __future__ import annotations

ERA_DEFINITION_VERSION = "2026-11-26"
CURRENT_FROM = "2021-22"

ERAS = {
    "current": {
        "label": "2021-22 onward",
        "title": "Current EQAO assessments",
        "explain": "Online assessments with a new design and, in mathematics, new standards for the 2020 curriculum. "
                   "EQAO started new trend lines in 2021-22, and since then reports results for fully participating students only.",
    },
    "paper": {
        "label": "2016-17 to 2018-19",
        "title": "Earlier paper-based assessments",
        "explain": "Paper tests with a different design and, in mathematics, a different curriculum and standards. "
                   "EQAO gives these years only as reference points, not as part of the current trend.",
    },
}

# Official statements this rule rests on (read 2026-11-26).
EVIDENCE = [
    ("EQAO, Highlights of the provincial results 2022-2023, Grade 6: new trendlines set in 2021-2022",
     "https://www.eqao.com/wp-content/uploads/2023/08/highlights-provincial-results-2023-g6.pdf"),
    ("EQAO, Highlights of the provincial results 2021-2022, Grade 3: 2018-2019 results provided only as reference points",
     "https://www.eqao.com/wp-content/uploads/2022/10/highlights-provincial-results-grade3-2022.pdf"),
    ("EQAO, Annual report 2022-2023: new mathematics standards set in 2022; 2021-2022 results established new baselines",
     "https://www.eqao.com/wp-content/uploads/2023/11/annual-report-2022-2023.pdf"),
    ("EQAO, Highlights of the provincial results 2023-2024, Grade 9: new trendlines and new baselines",
     "https://www.eqao.com/wp-content/uploads/2024/09/highlights-provincial-results-2024-g9.pdf"),
    ("EQAO, Highlights of the provincial results 2023-2024, OSSLT: online delivery and linear test design from 2021-2022",
     "https://www.eqao.com/wp-content/uploads/2024/09/highlights-provincial-results-2024-osslt.pdf"),
]

PAPER_ONLY = {"g9-math-academic", "g9-math-applied"}


def era_of(assessment: str, year: str) -> str:
    """'current' or 'paper' for one assessment and school year ("2024-25")."""
    if assessment in PAPER_ONLY:
        return "paper"
    return "current" if year >= CURRENT_FROM else "paper"


def same_era(assessment: str, a: str, b: str) -> bool:
    return era_of(assessment, a) == era_of(assessment, b)


def meta() -> dict:
    return {"version": ERA_DEFINITION_VERSION, "current_from": CURRENT_FROM, "eras": ERAS,
            "evidence": [{"title": t, "url": u} for t, u in EVIDENCE], "paper_only": sorted(PAPER_ONLY)}
