"""Turning source cells into numbers without ever inventing a value.

Rule: a code (suppressed, not reported, not applicable, no data) or a blank becomes
``value = None`` plus a flag explaining why. Nothing is ever turned into 0.
"""
from __future__ import annotations

import math
import re

# Codes used in the Ministry's School Information and Student Demographics files.
CODES = {
    "SP": {
        "code": "SP",
        "label": "Suppressed",
        "suppressed": True,
        "small_cohort": True,
        "explain": "Withheld by the Ministry to protect student privacy (the school population is too small to report).",
    },
    "N/R": {
        "code": "N/R",
        "label": "Not reported",
        "suppressed": True,
        "small_cohort": True,
        "explain": "Not reported. EQAO does not report results when so few students took part that individuals could be identified.",
    },
    "N/D": {
        "code": "N/D",
        "label": "No data",
        "suppressed": False,
        "small_cohort": False,
        "explain": "No data: the school did not have EQAO results for this assessment that year.",
    },
    "NA": {
        "code": "NA",
        "label": "Not applicable",
        "suppressed": False,
        "small_cohort": False,
        "explain": "Not applicable: the school does not offer this grade, or the measure does not apply.",
    },
    "N/A": {
        "code": "N/A",
        "label": "Not applicable",
        "suppressed": False,
        "small_cohort": False,
        "explain": "Not applicable or not available in the source.",
    },
    "-": {
        "code": "-",
        "label": "Not available",
        "suppressed": False,
        "small_cohort": False,
        "explain": "Shown as a dash in the source (no value published).",
    },
    "<10": {
        "code": "<10",
        "label": "Fewer than 10",
        "suppressed": True,
        "small_cohort": True,
        "explain": "Fewer than 10 students; the exact number is withheld to protect privacy.",
    },
    "BLANK": {
        "code": "BLANK",
        "label": "Blank",
        "suppressed": False,
        "small_cohort": False,
        "explain": "The source cell is empty.",
    },
}

_PCT = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*%\s*$")
_NUM = re.compile(r"^\s*(-?\d{1,3}(?:,\d{3})+|-?\d+)(?:\.(\d+))?\s*$")


class UnknownToken(ValueError):
    pass


def _blank(v) -> bool:
    return v is None or (isinstance(v, float) and math.isnan(v)) or (isinstance(v, str) and v.strip() == "")


def code_of(v) -> str | None:
    """Return the source code for a non-numeric cell, or None if the cell holds a number."""
    if _blank(v):
        return "BLANK"
    if isinstance(v, str):
        s = v.strip().upper().replace(" ", "")
        for key in CODES:
            if s == key.replace(" ", ""):
                return key
    return None


ANOMALIES: list[str] = []


def parse_pct(v, *, context: str = "", numeric: str | None = None) -> tuple[float | None, str | None]:
    """Parse a percentage cell.

    Text like ``'94%'`` / ``'94 %'`` is always accepted. Bare numbers (``94``, ``'94'``,
    ``0.94``) are only accepted when the caller says how that file stores them:

    - ``numeric="whole"``: whole-number percentages 0-100 (older demographic columns)
    - ``numeric="fraction"``: 0-1 fractions (EQAO cells in some years, everything in 2023-24)

    Without a mode a bare number fails loudly, so a silent format change cannot slip in.
    Returns ``(value, code)``; exactly one of them is not None.
    """
    c = code_of(v)
    if c:
        return None, c
    if isinstance(v, bool):
        raise UnknownToken(f"{context}: boolean {v!r}")
    if isinstance(v, str):
        m = _PCT.match(v)
        if m:
            x = float(m.group(1))
            if not 0 <= x <= 100:
                raise UnknownToken(f"{context}: percentage out of range: {v!r}")
            return (int(x) if x.is_integer() else x), None
        if re.fullmatch(r"\s*\d+(\.\d+)?\s*", v):
            v = float(v)
        else:
            raise UnknownToken(f"{context}: cannot read {v!r} as a percentage")
    if not isinstance(v, (int, float)):
        raise UnknownToken(f"{context}: unexpected {type(v).__name__} {v!r}")
    if numeric == "whole":
        if not (0 <= v <= 100 and float(v).is_integer()):
            raise UnknownToken(f"{context}: {v!r} is not a whole-number percentage")
        return int(v), None
    if numeric == "fraction":
        if 0 <= v <= 1:
            x = round(v * 100, 1)
        elif float(v).is_integer() and 1 < v <= 100:
            ANOMALIES.append(f"{context}: {v!r} read as {int(v)}% in a column of 0-1 fractions")
            x = float(v)
        else:
            raise UnknownToken(f"{context}: {v!r} is neither a 0-1 fraction nor a whole percentage")
        return (int(x) if float(x).is_integer() else x), None
    raise UnknownToken(f"{context}: bare number {v!r} where a percentage string was expected")


def parse_count(v, *, context: str = "") -> tuple[int | None, str | None]:
    """Parse a count like ``'1,336'`` or ``'155'``; codes like ``'<10'`` become flags."""
    c = code_of(v)
    if c:
        return None, c
    if isinstance(v, bool):
        raise UnknownToken(f"{context}: boolean {v!r}")
    if isinstance(v, int):
        return v, None
    if isinstance(v, float):
        if v.is_integer():
            return int(v), None
        raise UnknownToken(f"{context}: fractional count {v!r}")
    m = _NUM.match(str(v))
    if not m or m.group(2):
        raise UnknownToken(f"{context}: cannot read {v!r} as a count")
    return int(m.group(1).replace(",", "")), None


def parse_fraction(v, *, context: str = "", digits: int = 1) -> tuple[float | None, str | None]:
    """Parse a 0–1 fraction (board indicators) into a percentage."""
    c = code_of(v)
    if c:
        return None, c
    if isinstance(v, str):
        try:
            v = float(v.strip())
        except ValueError:
            raise UnknownToken(f"{context}: cannot read {v!r} as a fraction") from None
    if not isinstance(v, (int, float)) or isinstance(v, bool):
        raise UnknownToken(f"{context}: unexpected {v!r}")
    if not -1.0 <= v <= 1.0:
        raise UnknownToken(f"{context}: fraction out of range {v!r}")
    pct = round(v * 100, digits)
    return (int(pct) if float(pct).is_integer() else pct), None


def flags(code: str | None) -> dict:
    """The flags stored next to a null value."""
    if code is None:
        return {"suppressed": False, "small_cohort": False}
    c = CODES[code]
    return {"suppressed": c["suppressed"], "small_cohort": c["small_cohort"], "code": c["code"]}


def norm_postal(v) -> str | None:
    if _blank(v):
        return None
    s = re.sub(r"\s+", "", str(v)).upper()
    return s if re.fullmatch(r"[A-Z]\d[A-Z]\d[A-Z]\d", s) else None


def fsa_of(postal: str | None) -> str | None:
    return postal[:3] if postal else None


def clean_text(v) -> str | None:
    if _blank(v):
        return None
    s = re.sub(r"\s+", " ", str(v)).strip()
    return s or None


def clean_url(v) -> str | None:
    s = clean_text(v)
    if not s:
        return None
    if not re.match(r"^https?://", s, re.I):
        s = "https://" + s.lstrip("/")
    return s
