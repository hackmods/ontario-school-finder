// /compare/?ids=a,b,c — up to three schools side by side, same measures, same years.
import { qs, esc, SYSTEMS } from "./lib.js";
import { getCompare, setCompare, MAX_COMPARE } from "./compare-store.js";

const root = qs("[data-compare-root]");
const ORDER = ["g3-reading", "g3-writing", "g3-math", "g6-reading", "g6-writing", "g6-math", "g9-math", "g9-math-academic", "g9-math-applied", "osslt"];
let meta = null;

function idsFromUrl() {
  const v = new URLSearchParams(location.search).get("ids");
  return v ? v.split(",").map((x) => x.trim()).filter(Boolean).slice(0, MAX_COMPARE) : null;
}

async function loadSchool(id) {
  const r = await fetch(`/data/schools/${encodeURIComponent(id)}.json`);
  if (!r.ok) throw new Error(id);
  return r.json();
}

const pct = (v) => (v == null ? "—" : `${v}%`);
const val = (row) => (!row ? '<span class="muted">—</span>' : row.pct_at_or_above_standard != null ? `${row.pct_at_or_above_standard}%` : `<span class="code" title="${esc(meta?.codes?.[row.code]?.explain || "")}">${esc(row.code || "—")}</span>`);

function spark(rows) {
  const pts = rows.filter((r) => r.pct_at_or_above_standard != null);
  if (pts.length < 2) return "";
  const w = 90, h = 26;
  const step = w / (rows.length - 1 || 1);
  let d = "", started = false;
  rows.forEach((r, i) => {
    const v = r.pct_at_or_above_standard;
    if (v == null) { started = false; return; }
    d += `${started ? "L" : "M"}${(i * step).toFixed(1)},${(h - 2 - (h - 4) * v / 100).toFixed(1)} `;
    started = true;
  });
  return `<svg viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" aria-hidden="true" style="vertical-align:middle;color:var(--c-school)"><path d="${d}" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
}

function render(schools) {
  if (!schools.length) {
    root.innerHTML = `<div class="note"><div><p>No schools picked yet. Use the box above, or press <strong>Compare</strong> on any school page. You can compare up to ${MAX_COMPARE}.</p></div></div>`;
    return;
  }
  const n = schools.length;
  // same years: for each assessment, the latest year in which at least one picked school has a row
  const assess = ORDER.filter((a) => schools.some((s) => s.eqao.some((e) => e.assessment === a)));
  const rowsFor = (s, a) => s.eqao.filter((e) => e.assessment === a).sort((x, y) => x.year.localeCompare(y.year));
  const latestYear = Object.fromEntries(assess.map((a) => [a, schools.flatMap((s) => rowsFor(s, a)).map((e) => e.year).sort().pop()]));
  const enrolYear = schools.flatMap((s) => s.enrolment.map((e) => e.year)).sort().pop();
  const ctxKeys = (meta?.context_fields || []).map((c) => c);
  const col = (s) => {
    const enrol = s.enrolment.find((e) => e.year === enrolYear);
    let html = `<div class="card compare-col">
      <p class="small muted" style="margin:0 0 4px">${esc(SYSTEMS[s.system] || "")} · ${esc(s.level)}</p>
      <h2><a href="/school/${s.bsid}/">${esc(s.name)}</a></h2>
      <p class="small muted" style="margin:0 0 10px">${esc(s.board_name)} · ${esc(s.city || "")}</p>
      <button class="btn btn-sm btn-ghost" type="button" data-remove="${esc(s.bsid)}" style="margin:0 0 6px -8px">Remove</button>
      <div class="cmp-row"><span>Grades</span><b>${esc(s.grades || "—")}</b></div>
      <div class="cmp-row"><span>Language</span><b>${esc(s.language)}</b></div>
      <div class="cmp-row"><span>Enrolment ${esc(enrolYear || "")}</span><b>${enrol ? (enrol.value != null ? enrol.value.toLocaleString("en-CA") : `<span class="code">${esc(enrol.code)}</span>`) : "—"}</b></div>
      <div class="cmp-row"><span>Child care at address</span><b>${s.childcare.at_address.length ? `Yes (${s.childcare.at_address.length})` : "No"}</b></div>
      <h3 style="margin:18px 0 4px;font-size:.95rem">EQAO, share meeting the standard</h3>`;
    for (const a of assess) {
      const info = meta.assessments[a];
      const rows = rowsFor(s, a);
      const row = rows.find((e) => e.year === latestYear[a]);
      html += `<div class="cmp-row"><span>${esc(info.grade)} ${esc(info.subject.toLowerCase())}<br><span class="small">${esc(latestYear[a])}${row?.board_median != null ? ` · board ${pct(row.board_median)}` : ""}</span></span><b>${val(row)}<br>${spark(rows)}</b></div>`;
    }
    html += `<h3 style="margin:18px 0 4px;font-size:.95rem">Students, ${esc(s.context.year)}</h3>`;
    for (const c of ctxKeys) {
      const it = s.context.items.find((x) => x.key === c.key);
      html += `<div class="cmp-row"><span>${esc(c.label)}</span><b>${it?.value != null ? `${it.value}%` : `<span class="code">${esc(it?.code || "—")}</span>`}</b></div>`;
    }
    return html + "</div>";
  };
  root.innerHTML = `<div class="compare-grid" style="--n:${n}">${schools.map(col).join("")}</div>
    <p class="small muted" style="margin-top:16px">Each EQAO row uses the same school year for every school (the latest year any of them has). “—” means the school has no result for that year; codes are explained in <a href="/methodology/#codes">How it works</a>. Sources are listed on each school’s page.</p>`;
  root.querySelectorAll("[data-remove]").forEach((b) =>
    b.addEventListener("click", () => {
      const left = getCompare().filter((x) => x.id !== b.dataset.remove);
      setCompare(left);
      go(left.map((x) => x.id));
    }),
  );
}

async function go(ids) {
  history.replaceState(null, "", ids.length ? `/compare/?ids=${ids.join(",")}` : "/compare/");
  root.innerHTML = '<p class="loading">Loading schools…</p>';
  meta ||= await fetch("/data/meta.json").then((r) => r.json());
  const res = await Promise.allSettled(ids.map(loadSchool));
  const schools = res.filter((r) => r.status === "fulfilled").map((r) => r.value);
  const missing = ids.filter((_, i) => res[i].status !== "fulfilled");
  render(schools);
  if (missing.length) root.insertAdjacentHTML("afterbegin", `<div class="note note-warn" style="margin-bottom:12px"><div><p>Couldn’t find school number${missing.length > 1 ? "s" : ""} ${missing.map(esc).join(", ")}.</p></div></div>`);
  // keep the stored list in step with what is shown
  setCompare(schools.map((s) => ({ id: s.bsid, name: s.name })));
}

const fromUrl = idsFromUrl();
go(fromUrl || getCompare().map((x) => x.id));

document.addEventListener("osf:pick", (e) => {
  const list = getCompare();
  if (!list.some((x) => x.id === e.detail.id)) {
    if (list.length >= MAX_COMPARE) list.shift();
    list.push({ id: e.detail.id, name: e.detail.name });
  }
  setCompare(list);
  go(list.map((x) => x.id));
});
