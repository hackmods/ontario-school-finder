// Client-side multi-series line chart (SVG string). Mirrors the server-rendered charts' look.
import { esc } from "./lib.js";

const GAP = ["2018-19", "2021-22"]; // EQAO did not run in 2019-20 or 2020-21

export const shortYear = (y) => (y && y.length === 7 ? `${y.slice(2, 4)}–${y.slice(-2)}` : y);

/**
 * years: ordered list of school years on the x axis
 * series: [{label, color, values: {year: number|null}, dash, width, marker}]
 * opts: {min, max, unit: "%"|"", gap: bool, title, h, w}
 * Pass w = the chart's real width in CSS pixels so the drawing is 1:1 and labels stay 12px on any screen.
 */
export function lineChart(years, series, opts = {}) {
  const w = Math.max(260, Math.round(opts.w || 640));
  const h = opts.h || Math.round(Math.min(300, Math.max(200, w * 0.36)));
  const pl = 44, pr = 16, pt = 14, pb = 30;
  const unit = opts.unit ?? "%";
  const vals = series.flatMap((s) => years.map((y) => s.values[y])).filter((v) => v != null);
  let min = opts.min ?? 0;
  let max = opts.max ?? (vals.length ? Math.max(...vals) : 1);
  if (opts.max == null) {
    const span = max - min || 1;
    max = niceCeil(max + span * 0.08);
  }
  // x positions with an extra half-step across the pandemic gap
  const slots = [];
  let pos = 0;
  years.forEach((y, i) => {
    if (opts.gap && i && years[i - 1] === GAP[0] && y === GAP[1]) pos += 0.8;
    slots.push(pos);
    pos += 1;
  });
  const span = slots[slots.length - 1] || 1;
  const X = (i) => (years.length === 1 ? (pl + w - pr) / 2 : pl + ((w - pl - pr) * slots[i]) / span);
  const Y = (v) => pt + (h - pt - pb) * (1 - (v - min) / (max - min || 1));
  const out = [`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(opts.title || "Chart")}" preserveAspectRatio="xMidYMid meet">`];
  if (opts.gap) {
    const a = years.indexOf(GAP[0]), b = years.indexOf(GAP[1]);
    if (a >= 0 && b === a + 1) {
      out.push(`<rect class="gap-band" x="${X(a) + 12}" y="${pt}" width="${X(b) - X(a) - 24}" height="${h - pt - pb}" rx="4"/>`);
      out.push(`<text class="gap-label" x="${(X(a) + X(b)) / 2}" y="${pt + 12}" text-anchor="middle">no tests</text>`);
    }
  }
  for (const t of ticks(min, max)) {
    out.push(`<line class="grid-line" x1="${pl}" x2="${w - pr}" y1="${Y(t)}" y2="${Y(t)}"/>`);
    out.push(`<text class="axis-label" x="${pl - 6}" y="${Y(t) + 4}" text-anchor="end">${fmt(t)}${unit}</text>`);
  }
  // label every k-th year (always the latest) so labels keep at least 44px apart
  const slot = (w - pl - pr) / span; // span counts the extra room drawn for the pandemic gap
  const every = Math.max(1, Math.ceil(44 / slot));
  years.forEach((y, i) => {
    if ((years.length - 1 - i) % every === 0) out.push(`<text class="axis-label" x="${X(i)}" y="${h - 10}" text-anchor="middle">${shortYear(y)}</text>`);
  });
  for (const s of series) {
    let d = "", on = false;
    years.forEach((y, i) => {
      const v = s.values[y];
      if (v == null) { on = false; return; }
      d += `${on ? "L" : "M"}${X(i).toFixed(1)},${Y(v).toFixed(1)} `;
      on = true;
    });
    if (d) out.push(`<path d="${d}" fill="none" style="stroke:${s.color}" stroke-width="${s.width || 2.5}" ${s.dash ? `stroke-dasharray="${s.dash}"` : ""} stroke-linejoin="round" stroke-linecap="round"/>`);
    if (s.marker !== false) {
      years.forEach((y, i) => {
        const v = s.values[y];
        if (v == null) return;
        out.push(`<circle cx="${X(i).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="${s.dash ? 2.5 : 3.5}" style="fill:${s.dash ? s.color : "var(--surface)"};stroke:${s.color}" stroke-width="2"><title>${esc(s.label)}, ${esc(y)}: ${fmt(v)}${unit}</title></circle>`);
      });
    }
  }
  out.push("</svg>");
  return out.join("");
}

function niceCeil(v) {
  if (v <= 10) return Math.ceil(v);
  const mag = 10 ** Math.floor(Math.log10(v));
  return Math.ceil(v / (mag / 2)) * (mag / 2);
}

function ticks(min, max) {
  const span = max - min;
  const raw = span / 4;
  const mag = 10 ** Math.floor(Math.log10(raw || 1));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => span / s <= 5) || raw;
  const out = [];
  for (let t = Math.ceil(min / step) * step; t <= max + 1e-9; t += step) out.push(+t.toFixed(6));
  return out;
}

const fmt = (v) => (Math.abs(v) >= 1000 ? Math.round(v).toLocaleString("en-CA") : String(+(+v).toFixed(1)));
