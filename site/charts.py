"""Server-side SVG charts. They render without JavaScript and always sit above a text table."""
from __future__ import annotations

from html import escape

EQAO_GAP = ("2018-19", "2021-22")  # no EQAO assessments in 2019-20 and 2020-21


def _x_positions(years: list[str], left: float, right: float) -> dict[str, float]:
    """Evenly spaced years with an extra half-step where the pandemic gap is."""
    slots = []
    pos = 0.0
    for i, y in enumerate(years):
        if i and years[i - 1] == EQAO_GAP[0] and y == EQAO_GAP[1]:
            pos += 0.8
        slots.append(pos)
        pos += 1
    span = slots[-1] if slots[-1] else 1
    return {y: left + (right - left) * (s / span if len(years) > 1 else 0.5) for y, s in zip(years, slots)}


def short_year(y: str) -> str:
    # "2024-25" -> "24–25"
    return y[2:4] + "–" + y[-2:] if len(y) == 7 else y


def eqao_chart(rows: list[dict], years: list[str], *, title: str, main_key: str = "pct_at_or_above_standard",
               main_label: str = "This school", w: int = 360, h: int = 200) -> str:
    """Line chart: school (solid), board median (dashed), Ontario median (dotted)."""
    pad_l, pad_r, pad_t, pad_b = 34, 34, 14, 34
    xs = _x_positions(years, pad_l, w - pad_r)

    def y_of(v):
        return pad_t + (h - pad_t - pad_b) * (1 - v / 100)

    by_year = {r["year"]: r for r in rows}
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}" preserveAspectRatio="xMidYMid meet">']
    # pandemic gap band
    if EQAO_GAP[0] in xs and EQAO_GAP[1] in xs:
        x0, x1 = xs[EQAO_GAP[0]] + 10, xs[EQAO_GAP[1]] - 10
        if x1 > x0:
            out.append(f'<rect class="gap-band" x="{x0:.1f}" y="{pad_t}" width="{x1 - x0:.1f}" height="{h - pad_t - pad_b}" rx="4"/>')
            out.append(f'<text class="gap-label" x="{(x0 + x1) / 2:.1f}" y="{pad_t + 12}" text-anchor="middle">no tests</text>')
    for g in (0, 25, 50, 75, 100):
        y = y_of(g)
        out.append(f'<line class="grid-line" x1="{pad_l}" x2="{w - pad_r}" y1="{y:.1f}" y2="{y:.1f}"/>')
        out.append(f'<text class="axis-label" x="{pad_l - 6}" y="{y + 4:.1f}" text-anchor="end">{g}%</text>')
    for yv, x in xs.items():
        out.append(f'<text class="axis-label" x="{x:.1f}" y="{h - 12}" text-anchor="middle">{short_year(yv)}</text>')

    def path(key, cls):
        segs, cur = [], []
        for yv in years:
            r = by_year.get(yv)
            v = r.get(key) if r else None
            if v is None:
                if cur:
                    segs.append(cur)
                cur = []
                continue
            cur.append((xs[yv], y_of(v)))
        if cur:
            segs.append(cur)
        for seg in segs:
            if len(seg) == 1:
                continue
            d = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in seg)
            out.append(f'<path class="{cls}" d="{d}"/>')
        return segs

    path("province_median", "s-prov")
    path("board_median", "s-board")
    for yv in years:
        r = by_year.get(yv)
        if not r:
            continue
        for key, cls, rad in (("province_median", "p-prov", 2.5), ("board_median", "p-board", 2.5)):
            if r.get(key) is not None:
                out.append(f'<circle class="{cls}" cx="{xs[yv]:.1f}" cy="{y_of(r[key]):.1f}" r="{rad}"><title>{escape(short_year(yv))}: {r[key]}%</title></circle>')
    path(main_key, "s-school")
    last_val = None
    for yv in years:
        r = by_year.get(yv)
        if not r:
            continue
        v = r.get(main_key)
        if v is not None:
            out.append(f'<circle class="p-school" cx="{xs[yv]:.1f}" cy="{y_of(v):.1f}" r="4"><title>{escape(main_label)} {escape(short_year(yv))}: {v}%</title></circle>')
            last_val = (xs[yv], y_of(v), v)
        elif r.get("code"):
            out.append(f'<text class="code-label" x="{xs[yv]:.1f}" y="{h - pad_b - 6}" text-anchor="middle">{escape(r["code"])}</text>')
    if last_val:
        x, y, v = last_val
        out.append(f'<text class="v-label" x="{x + 8:.1f}" y="{y + 4:.1f}">{v:g}%</text>')
    out.append("</svg>")
    return "".join(out)


def bar_chart(points: list[dict], *, title: str, w: int = 640, h: int = 190) -> str:
    """Enrolment bars. Suppressed years get an outlined empty bar, never a zero."""
    if not points:
        return ""
    pad_l, pad_r, pad_t, pad_b = 8, 8, 22, 30
    vals = [p["value"] for p in points if p["value"] is not None]
    vmax = max(vals) if vals else 1
    n = len(points)
    slot = (w - pad_l - pad_r) / n
    bw = max(6.0, slot * 0.62)
    out = [f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{escape(title)}" preserveAspectRatio="xMidYMid meet">']
    base = h - pad_b
    out.append(f'<line class="grid-line" x1="{pad_l}" x2="{w - pad_r}" y1="{base}" y2="{base}"/>')
    every = 1 if n <= 8 else 2
    for i, p in enumerate(points):
        cx = pad_l + slot * i + slot / 2
        if p["value"] is None:
            out.append(f'<rect class="bar-null" x="{cx - bw / 2:.1f}" y="{base - 28}" width="{bw:.1f}" height="28" rx="3"><title>{escape(p["year"])}: {escape(p.get("code") or "not available")}</title></rect>')
        else:
            bh = max(2.0, (base - pad_t) * p["value"] / vmax)
            out.append(f'<rect class="bar" x="{cx - bw / 2:.1f}" y="{base - bh:.1f}" width="{bw:.1f}" height="{bh:.1f}" rx="3"><title>{escape(p["year"])}: {p["value"]:,}</title></rect>')
            if i == n - 1 or i % every == (n - 1) % every:
                out.append(f'<text class="bar-label" x="{cx:.1f}" y="{base - bh - 5:.1f}" text-anchor="middle">{p["value"]:,}</text>')
        if i % every == (n - 1) % every:
            out.append(f'<text class="axis-label" x="{cx:.1f}" y="{h - 10}" text-anchor="middle">{short_year(p["year"])}</text>')
    out.append("</svg>")
    return "".join(out)


def spark(points: list[float | None], w: int = 120, h: int = 32) -> str:
    vals = [v for v in points if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    rng = (hi - lo) or 1
    step = w / (len(points) - 1)
    d, started = [], False
    for i, v in enumerate(points):
        if v is None:
            started = False
            continue
        x = i * step
        y = h - 3 - (h - 6) * (v - lo) / rng
        d.append(("L" if started else "M") + f"{x:.1f},{y:.1f}")
        started = True
    return f'<svg viewBox="0 0 {w} {h}" width="{w}" height="{h}" aria-hidden="true"><path d="{" ".join(d)}" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/></svg>'
