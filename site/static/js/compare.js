// /compare/?ids=a,b,c — up to six schools side by side: every published measure, same school years.
import { qs, qsa, esc, SYSTEMS, km, fmtKm, dataUrl } from "./lib.js";
import { getCompare, setCompare, MAX_COMPARE } from "./compare-store.js";
import { lineChart, shortYear } from "./linechart.js";

const root = qs("[data-compare-root]");
// the full placeholder is cut off in a phone-width box, like the home and search boxes
const addBox = qs("#cq");
if (addBox && matchMedia("(max-width: 480px)").matches) addBox.placeholder = "Add a school";
const COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)"];
const ORDER = ["g3-reading", "g3-writing", "g3-math", "g6-reading", "g6-writing", "g6-math", "g9-math", "g9-math-academic", "g9-math-applied", "osslt"];
const GRADES = ["JK", "K", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12"];
const GRADE_LABEL = (g) => (g === "JK" ? "Junior kindergarten" : g === "K" ? "Kindergarten" : `Grade ${g.slice(1)}`);
const AREA_FIELDS = ["population", "children_0_14_pct", "couple_hh_children_pct", "one_parent_hh_pct", "median_household_income", "low_income_0_17_pct", "home_other_pct", "home_french_pct"];

const state = { schools: [], fsas: {}, meta: null, ctx: null, boards: null, opts: { prov: true, board: false }, csv: [] };

// ---------------------------------------------------------------- loading
function idsFromUrl() {
  const v = new URLSearchParams(location.search).get("ids");
  return v ? [...new Set(v.split(",").map((x) => x.trim()).filter(Boolean))].slice(0, MAX_COMPARE) : null;
}

const getJSON = (u) => fetch(dataUrl(u)).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${u}`))));

async function load(ids) {
  state.meta ||= await getJSON("/data/meta.json");
  state.ctx ||= await getJSON("/data/context-medians.json").catch(() => null);
  state.boards ||= await getJSON("/data/boards-context.json").catch(() => null); // ~5 KB: every board's headline figures
  const res = await Promise.allSettled(ids.map((id) => getJSON(`/data/schools/${encodeURIComponent(id)}.json`)));
  const schools = res.filter((r) => r.status === "fulfilled").map((r) => r.value);
  const missing = ids.filter((_, i) => res[i].status !== "fulfilled");
  await Promise.all(
    [...new Set(schools.map((s) => s.fsa))].filter((f) => f && !state.fsas[f]).map((f) => getJSON(`/data/fsa/${f}.json`).then((j) => (state.fsas[f] = j)).catch(() => {})),
  );
  return { schools, missing };
}

// ---------------------------------------------------------------- helpers
const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : "");
const pct = (v) => (v == null ? "—" : `${v}%`);
const num = (v) => (v == null ? "—" : Number(v).toLocaleString("en-CA"));
const money = (v) => (v == null ? "—" : `$${Number(v).toLocaleString("en-CA")}`);
const codeChip = (code) => `<span class="code" title="${esc(state.meta.codes?.[code]?.explain || "")}">${esc(code || "—")}</span>`;
const swatch = (i) => `<span class="swatch" style="background:${COLORS[i]}"></span>`;

function th(schools) {
  return `<thead><tr><th scope="col" class="sticky">Measure</th>${schools.map((s, i) => `<th scope="col">${swatch(i)}<a href="/school/${s.bsid}/">${esc(s.name)}</a></th>`).join("")}</tr></thead>`;
}

/** rows: [{label, sub, cells: [html], raw: [value]}] — also recorded for CSV. */
function table(section, schools, rows, { caption, extraHead = "", extra = null } = {}) {
  for (const r of rows) state.csv.push([section, r.label.replace(/<[^>]+>/g, ""), r.year || "", ...r.raw.map((v) => (v == null ? "" : v)), ...(extra ? [r.extraRaw ?? ""] : [])]);
  const head = th(schools).replace("</tr></thead>", `${extraHead}</tr></thead>`);
  return `<div class="table-wrap cmp-table"><table>${caption ? `<caption>${caption}</caption>` : ""}${head}<tbody>${rows
    .map((r) => `<tr><th scope="row" class="sticky">${r.label}${r.sub ? `<div class="small muted">${r.sub}</div>` : ""}</th>${r.cells.map((c) => `<td class="n">${c}</td>`).join("")}${extra ? `<td class="n muted">${r.extra ?? "—"}</td>` : ""}</tr>`)
    .join("")}</tbody></table></div>`;
}

function legend(schools, extras = []) {
  return `<ul class="legend-inline">${schools.map((s, i) => `<li>${swatch(i)}${esc(short(s.name))}</li>`).join("")}${extras.join("")}</ul>`;
}
const short = (n) => (n.length > 34 ? `${n.slice(0, 32)}…` : n);

// Charts are drawn after the page is built, at the width each one actually gets, so the SVG is 1:1
// with the screen and its labels stay readable on a phone. They are redrawn when that width changes.
const charts = [];
function chart(years, series, opts) {
  charts.push([years, series, opts]);
  return `<div class="chart" data-lc="${charts.length - 1}"></div>`;
}
function drawCharts() {
  for (const el of qsa("[data-lc]", root)) {
    const w = Math.round(el.clientWidth);
    if (!w || +el.dataset.w === w) continue;
    const [years, series, opts] = charts[+el.dataset.lc];
    el.dataset.w = String(w);
    el.innerHTML = lineChart(years, series, { ...opts, w });
  }
}
let redraw = 0;
if ("ResizeObserver" in window) new ResizeObserver(() => { cancelAnimationFrame(redraw); redraw = requestAnimationFrame(drawCharts); }).observe(root);
// Year-by-year tables under each EQAO chart: open on wide screens, one tap away on phones.
const wideScreen = () => matchMedia("(min-width: 900px)").matches;

// ---------------------------------------------------------------- sections
// French programs (Ministry FSL list, English-language schools only)
function frenchRows(schools) {
  const cell = (s, key) => {
    const f = s.programs?.fsl;
    if (f) return f[key] ? "Yes" : "No";
    return s.language === "French" ? '<span class="muted">French-language school</span>' : '<span class="muted">Not in the list</span>';
  };
  const raw = (s, key) => (s.programs?.fsl ? (s.programs.fsl[key] ? "yes" : "no") : "");
  return [
    { label: "French Immersion", sub: "2024-25", cells: schools.map((s) => cell(s, "immersion")), raw: schools.map((s) => raw(s, "immersion")) },
    { label: "Extended French", sub: "2024-25", cells: schools.map((s) => cell(s, "extended")), raw: schools.map((s) => raw(s, "extended")) },
  ];
}

function overview(schools) {
  const first = schools[0];
  const latestEnrol = (s) => [...s.enrolment].reverse().find((e) => e.value != null);
  const change = (s) => {
    const v = s.enrolment.filter((e) => e.value != null);
    if (v.length < 2) return null;
    const last = v[v.length - 1];
    const past = [...v].reverse().find((e) => +e.year.slice(0, 4) <= +last.year.slice(0, 4) - 5) || v[0];
    return { d: last.value - past.value, since: past.year };
  };
  const rows = [
    { label: "Board", cells: schools.map((s) => `<a href="/board/${s.board_number}/">${esc(s.board_name)}</a>`), raw: schools.map((s) => s.board_name) },
    { label: "System", cells: schools.map((s) => esc(SYSTEMS[s.system] || "")), raw: schools.map((s) => SYSTEMS[s.system]) },
    { label: "Level and grades", cells: schools.map((s) => `${esc(cap(s.level))} · ${esc(s.grades || "")}`), raw: schools.map((s) => `${cap(s.level)} ${s.grades || ""}`) },
    { label: "Language", cells: schools.map((s) => esc(s.language)), raw: schools.map((s) => s.language) },
    { label: "Special program", cells: schools.map((s) => esc(s.special || "—")), raw: schools.map((s) => s.special) },
    { label: "Address", cells: schools.map((s) => esc([s.address, s.city].filter(Boolean).join(", "))), raw: schools.map((s) => [s.address, s.city].filter(Boolean).join(", ")) },
    { label: "Postal area", cells: schools.map((s) => `<a href="/fsa/${s.fsa}/">${esc(s.fsa)}</a>`), raw: schools.map((s) => s.fsa) },
    { label: "Opened", cells: schools.map((s) => esc(s.date_open ? s.date_open.slice(0, 4) : "—")), raw: schools.map((s) => s.date_open?.slice(0, 4)) },
    { label: "Students (latest)", cells: schools.map((s) => { const e = latestEnrol(s); return e ? `${num(e.value)}<div class="small muted">${esc(e.year)}</div>` : "—"; }), raw: schools.map((s) => latestEnrol(s)?.value) },
    { label: "Enrolment change (5 years)", cells: schools.map((s) => { const c = change(s); return c ? `${c.d >= 0 ? "+" : "−"}${num(Math.abs(c.d))}<div class="small muted">since ${esc(c.since)}</div>` : "—"; }), raw: schools.map((s) => change(s)?.d) },
    { label: "Licensed child care at the school", cells: schools.map((s) => (s.childcare.at_address.length ? `Yes (${s.childcare.at_address.length})` : "No")), raw: schools.map((s) => s.childcare.at_address.length) },
    {
      label: "EarlyON centres in the postal area", sub: "free programs for children up to 6",
      cells: schools.map((s) => (s.earlyon_in_fsa ? `<a href="/fsa/${s.fsa}/#earlyon">${s.earlyon_in_fsa}</a>` : "None listed")),
      raw: schools.map((s) => s.earlyon_in_fsa || 0),
    },
    ...frenchRows(schools),
    {
      label: "Student nutrition program", sub: "Ministry list from December 2017",
      cells: schools.map((s) => (s.programs?.nutrition ? esc(s.programs.nutrition.meals.join(", ")) : '<span class="muted">Not listed</span>')),
      raw: schools.map((s) => (s.programs?.nutrition ? s.programs.nutrition.meals.join("; ") : "")),
    },
    {
      label: "Specialist High Skills Majors", sub: "career-sector programs, 2025-26",
      cells: schools.map((s) => (s.programs?.shsm ? `${s.programs.shsm.sectors.length}<div class="small muted">${esc(s.programs.shsm.sectors.map((p) => p.sector).join(", "))}</div>` : s.level === "secondary" ? "None listed" : "—")),
      raw: schools.map((s) => (s.programs?.shsm ? s.programs.shsm.sectors.map((p) => p.sector).join("; ") : "")),
    },
  ];
  if (schools.length > 1) {
    rows.push({ label: `Distance from ${esc(short(first.name))}`, cells: schools.map((s, i) => (i === 0 ? "—" : fmtKm(km([first.lon, first.lat], [s.lon, s.lat])))), raw: schools.map((s, i) => (i === 0 ? "" : km([first.lon, first.lat], [s.lon, s.lat]).toFixed(1))) });
  }
  rows.push({ label: "Links", cells: schools.map((s) => [s.website ? `<a href="${esc(s.website)}" rel="noopener">Website</a>` : "", `<a href="${esc(s.links.eqao)}" rel="noopener">EQAO</a>`, s.phone ? `<a href="tel:${esc(s.phone.replace(/-/g, ""))}">${esc(s.phone)}</a>` : ""].filter(Boolean).join("<br>")), raw: schools.map((s) => s.website) });
  return `<section class="cmp-section" id="cmp-overview"><h2>Overview</h2>${table("Overview", schools, rows)}</section>`;
}

function eqao(schools) {
  const meta = state.meta;
  const present = ORDER.filter((a) => schools.some((s) => s.eqao.some((e) => e.assessment === a)));
  if (!present.length) return `<section class="cmp-section" id="cmp-eqao"><h2>EQAO results</h2><div class="note"><div><p>None of these schools has EQAO results in the source data (no Grade 3, 6, 9 or 10 students, or special-purpose schools).</p></div></div></section>`;
  const langs = [...new Set(schools.map((s) => s.language))];
  const provByLang = {};
  for (const m of meta.province_medians) (provByLang[`${m.assessment}|${m.language}`] ||= {})[m.year] = m.median;
  let html = `<section class="cmp-section" id="cmp-eqao"><h2>EQAO results <span class="badge">${esc(meta.eqao_years[0])} to ${esc(meta.latest_eqao_year)}</span></h2>
    <p class="block-intro">Share of each school’s students meeting the provincial standard, every year the source publishes. ${state.opts.prov ? "The dotted line is the median Ontario school of the same language." : ""} ${state.opts.board ? "Thin dashed lines are each school’s board median." : ""}</p>`;
  for (const a of present) {
    const info = meta.assessments[a];
    let years = meta.eqao_years.filter((y) => schools.some((s) => s.eqao.some((e) => e.assessment === a && e.year === y)));
    const series = [];
    schools.forEach((s, i) => {
      const values = {};
      const bvals = {};
      for (const e of s.eqao) if (e.assessment === a) { values[e.year] = e.pct_at_or_above_standard; bvals[e.year] = e.board_median; }
      series.push({ label: s.name, color: COLORS[i], values });
      if (state.opts.board) series.push({ label: `${s.board_name} median`, color: COLORS[i], values: bvals, dash: "5 4", width: 1.5 });
    });
    if (state.opts.prov) for (const l of langs) series.push({ label: `Ontario median (${l})`, color: "var(--c-prov)", values: provByLang[`${a}|${l}`] || {}, dash: "2 4", width: 2 });
    const rows = years.map((y) => {
      const cells = [], raw = [];
      for (const s of schools) {
        const e = s.eqao.find((x) => x.assessment === a && x.year === y);
        if (!e) { cells.push('<span class="muted">—</span>'); raw.push(null); }
        else if (e.pct_at_or_above_standard == null) { cells.push(codeChip(e.code)); raw.push(e.code); }
        else { cells.push(`${e.pct_at_or_above_standard}%${state.opts.board && e.board_median != null ? `<div class="small muted">board ${e.board_median}%</div>` : ""}`); raw.push(e.pct_at_or_above_standard); }
      }
      const pm = langs.map((l) => provByLang[`${a}|${l}`]?.[y]).filter((v) => v != null);
      return { label: esc(y), year: y, cells, raw, extra: pm.length ? pm.map((v) => `${v}%`).join(" / ") : "—", extraRaw: pm.join(" / ") };
    });
    // change since each school's first result
    const trend = schools.map((s) => {
      const pts = s.eqao.filter((e) => e.assessment === a && e.pct_at_or_above_standard != null).sort((x, y) => x.year.localeCompare(y.year));
      if (pts.length < 2) return null;
      return { d: +(pts[pts.length - 1].pct_at_or_above_standard - pts[0].pct_at_or_above_standard).toFixed(1), from: pts[0].year, to: pts[pts.length - 1].year };
    });
    rows.push({ label: "<b>Change over the period</b>", sub: "first to latest result", year: "change", cells: trend.map((t) => (t ? `<b>${t.d > 0 ? "+" : t.d < 0 ? "−" : "±"}${Math.abs(t.d)} pt${Math.abs(t.d) === 1 ? "" : "s"}</b><div class="small muted">${esc(t.from)}–${esc(t.to.slice(-2))}</div>` : "—")), raw: trend.map((t) => (t ? t.d : null)), extra: "" });
    html += `<figure class="chart-card cmp-chart" style="margin:16px 0 0" id="cmp-${a}">
      <h3>${esc(info.grade)} · ${esc(info.subject)}</h3>
      ${legend(schools, state.opts.prov ? ['<li><i class="l-prov"></i>Ontario median</li>'] : [])}
      ${chart(years, series, { gap: true, max: 100, title: `${info.grade} ${info.subject} by year` })}
      <details class="data-table"${wideScreen() ? " open" : ""}><summary>Show the numbers</summary>${table(`EQAO ${info.grade} ${info.subject}`, schools, rows, { caption: `${esc(info.grade)} ${esc(info.subject)}: share meeting the standard`, extraHead: '<th scope="col">Ontario median</th>', extra: true })}</details>
    </figure>`;
  }
  return html + "</section>";
}

function enrolment(schools) {
  const years = [...new Set(schools.flatMap((s) => s.enrolment.map((e) => e.year)))].sort();
  if (!years.length) return "";
  const series = schools.map((s, i) => ({ label: s.name, color: COLORS[i], values: Object.fromEntries(s.enrolment.map((e) => [e.year, e.value])) }));
  const rows = [...years].reverse().map((y) => ({
    label: esc(y), year: y,
    cells: schools.map((s) => { const e = s.enrolment.find((x) => x.year === y); return !e ? '<span class="muted">—</span>' : e.value == null ? codeChip(e.code) : num(e.value); }),
    raw: schools.map((s) => { const e = s.enrolment.find((x) => x.year === y); return e ? (e.value ?? e.code) : null; }),
  }));
  return `<section class="cmp-section" id="cmp-enrolment"><h2>Enrolment <span class="badge">${esc(years[0])} to ${esc(years[years.length - 1])}</span></h2>
    <div class="chart-card">${legend(schools)}${chart(years, series, { unit: "", min: 0, title: "Enrolment by year" })}
    <details class="data-table"><summary>Show every year</summary>${table("Enrolment", schools, rows)}</details>
    <p class="small muted">Headcount reported by boards; rounded to the nearest 5 since 2018-19.</p></div></section>`;
}

function grades(schools) {
  const latest = schools.map((s) => s.grade_enrolment?.[s.grade_enrolment.length - 1]);
  if (!latest.some(Boolean)) return "";
  const used = GRADES.filter((g) => latest.some((l) => l && g in l.grades));
  const rows = used.map((g) => ({
    label: GRADE_LABEL(g), year: latest.find(Boolean).year,
    cells: latest.map((l) => (!l || !(g in l.grades) ? '<span class="muted">—</span>' : l.grades[g] == null ? codeChip(l.codes[g]) : num(l.grades[g]))),
    raw: latest.map((l) => (l && g in l.grades ? (l.grades[g] ?? l.codes[g]) : null)),
  }));
  rows.unshift({ label: "School year", cells: latest.map((l) => (l ? esc(l.year) : "—")), raw: latest.map((l) => l?.year) });
  return `<section class="cmp-section" id="cmp-grades"><h2>Students by grade</h2><p class="block-intro">How many students are in each grade, from each school’s latest file. Small counts are withheld (<span class="code">&lt;10</span>).</p>${table("Students by grade", schools, rows)}</section>`;
}

function classSizes(schools) {
  const any = schools.some((s) => s.class_size?.length);
  if (!any) return `<section class="cmp-section" id="cmp-class"><h2>Class sizes</h2><div class="note"><div><p>The Ministry publishes class sizes for elementary schools only.</p></div></div></section>`;
  const years = [...new Set(schools.flatMap((s) => (s.class_size || []).map((r) => r.year)))].sort();
  const series = schools.map((s, i) => ({ label: s.name, color: COLORS[i], values: Object.fromEntries((s.class_size || []).map((r) => [r.year, r.primary_avg])) }));
  if (state.opts.prov) {
    const lang = schools[0].language;
    const pv = {};
    for (const s of schools) for (const r of s.class_size || []) if (s.language === lang && r.primary_province_median != null) pv[r.year] = r.primary_province_median;
    series.push({ label: "Ontario median", color: "var(--c-prov)", values: pv, dash: "2 4", width: 2 });
  }
  const latestYear = years[years.length - 1];
  const at = (s) => (s.class_size || []).find((r) => r.year === latestYear) || (s.class_size || []).slice(-1)[0];
  const metric = (label, sub, f, fmt = (v) => v) => ({
    label, sub, year: latestYear,
    cells: schools.map((s) => { const r = at(s); const v = r ? f(r) : null; return v == null ? '<span class="muted">—</span>' : fmt(v); }),
    raw: schools.map((s) => { const r = at(s); return r ? f(r) : null; }),
  });
  const rows = [
    metric("School year", "", (r) => r.year),
    metric("Average class size, all classes", "", (r) => r.avg_all),
    metric("Grades 1–3 classes: average size", "Ontario’s rule: at most 23, and 90% of classes 20 or fewer", (r) => r.primary_avg),
    metric("Grades 1–3 classes with 20 or fewer students", "", (r) => r.primary_le20_pct, (v) => `${v}%`),
    metric("Largest Grade 1–3 class", "", (r) => r.primary_max),
    metric("Kindergarten classes: average size", "", (r) => r.kinder_avg),
    metric("Grades 4–8 classes: average size", "", (r) => r.junior_avg),
    metric("Combined-grade classes", "classes mixing kindergarten, primary and junior grades", (r) => r.combined_classes),
    metric("Number of classes", "", (r) => r.classes),
  ];
  return `<section class="cmp-section" id="cmp-class"><h2>Class sizes <span class="badge">${esc(years[0])} to ${esc(latestYear)}</span></h2>
    <p class="block-intro">Computed from the Ministry’s list of every elementary class (counted each September). Before 2014-15 only primary classes were listed, so the long trend uses Grades 1–3 classes.</p>
    <div class="chart-card">${legend(schools, state.opts.prov ? ['<li><i class="l-prov"></i>Ontario median</li>'] : [])}
    ${chart(years, series, { unit: "", min: 0, max: 30, title: "Average Grades 1–3 class size by year" })}
    ${table("Class sizes", schools, rows, { caption: "Latest year" })}</div></section>`;
}

// Each school's board, from one shared file: spending per student, suspensions, French Immersion share
function boardContext(schools) {
  const bc = state.boards;
  if (!bc) return "";
  const b = (s) => bc.boards[s.board_number] || {};
  const rows = [
    { label: "Board", cells: schools.map((s) => `<a href="/board/${s.board_number}/#context">${esc(s.board_name)}</a>`), raw: schools.map((s) => s.board_name) },
    { label: "Spending per student", sub: `${esc(bc.spending_year)} · Ontario's middle board ${money(bc.spending_median)}`, cells: schools.map((s) => money(b(s).sp)), raw: schools.map((s) => b(s).sp) },
    { label: "Students suspended", sub: "share of the board's students, latest year", cells: schools.map((s) => (b(s).sr != null ? `${b(s).sr}%<div class="small muted">${esc(b(s).sry)} · Ontario ${b(s).srp}%</div>` : "—")), raw: schools.map((s) => b(s).sr) },
    { label: "Students in French Immersion", sub: `share of the board's students, ${esc(bc.fsl_year)}`, cells: schools.map((s) => (b(s).fi != null ? `${b(s).fi}%` : '<span class="muted">—</span>')), raw: schools.map((s) => b(s).fi) },
  ];
  return `<section class="cmp-section" id="cmp-board"><h2>School board context</h2><p class="block-intro">These describe each school's whole board, not the school itself. Details are on each board's page.</p>${table("Board context", schools, rows)}</section>`;
}

function students(schools) {
  const fields = state.meta.context_fields;
  const year = schools[0]?.context.year;
  const rows = fields.map((f) => ({
    label: esc(f.label), sub: esc(f.definition), year,
    cells: schools.map((s) => { const it = s.context.items.find((x) => x.key === f.key); return !it ? "—" : it.value != null ? `${it.value}%` : codeChip(it.code); }),
    raw: schools.map((s) => { const it = s.context.items.find((x) => x.key === f.key); return it ? (it.value ?? it.code) : null; }),
    extra: state.ctx ? pct(state.ctx.province?.[schools[0].language]?.[f.key]) : "—",
    extraRaw: state.ctx?.province?.[schools[0].language]?.[f.key] ?? "",
  }));
  return `<section class="cmp-section" id="cmp-students"><h2>About the students <span class="badge">${esc(year || "")}</span></h2>
    <p class="block-intro">Who each school serves. These describe the student population; they are not measures of quality.</p>
    ${table("Students", schools, rows, { extraHead: `<th scope="col">Ontario median</th>`, extra: true })}</section>`;
}

function area(schools) {
  const fields = state.meta.census_fields.filter((f) => AREA_FIELDS.includes(f.key));
  const fmt = (f, v) => (v == null ? "—" : f.unit === "pct" ? `${v}%` : f.unit === "dollars" ? money(v) : num(v));
  const rows = [{ label: "Postal area", cells: schools.map((s) => `<a href="/fsa/${s.fsa}/">${esc(s.fsa)}</a>`), raw: schools.map((s) => s.fsa) }].concat(
    fields.map((f) => ({ label: esc(f.label), year: "2021", cells: schools.map((s) => fmt(f, state.fsas[s.fsa]?.census?.[f.key])), raw: schools.map((s) => state.fsas[s.fsa]?.census?.[f.key]) })),
  );
  return `<section class="cmp-section" id="cmp-area"><h2>The surrounding area <span class="badge">2021 Census</span></h2>
    <p class="block-intro">Statistics Canada figures for each school’s postal area (everyone who lives there, not only school families).</p>${table("Area", schools, rows)}</section>`;
}

function nearby(schools) {
  const rows = [
    { label: "Licensed child care at the school’s address", cells: schools.map((s) => (s.childcare.at_address.length ? s.childcare.at_address.map((c) => esc(c.name)).join("<br>") : "None listed")), raw: schools.map((s) => s.childcare.at_address.map((c) => c.name).join("; ")) },
    { label: "Licensed child care sites in the postal area", cells: schools.map((s) => num(s.childcare.in_fsa_count)), raw: schools.map((s) => s.childcare.in_fsa_count) },
    { label: "Nearest other school of the same level", cells: schools.map((s) => (s.nearby[0] ? `<a href="/school/${s.nearby[0].bsid}/">${esc(s.nearby[0].name)}</a><div class="small muted">${s.nearby[0].km} km</div>` : "—")), raw: schools.map((s) => (s.nearby[0] ? `${s.nearby[0].name} (${s.nearby[0].km} km)` : "")) },
  ];
  return `<section class="cmp-section" id="cmp-nearby"><h2>Child care and nearby</h2>${table("Child care and nearby", schools, rows)}</section>`;
}

function sourcesList(schools) {
  const seen = new Map();
  for (const s of schools) for (const src of s.sources) seen.set(src.source_id, src);
  // grouped by publisher and dataset, like the school pages: a yearly dataset is one row with a link per year
  const pubs = new Map();
  for (const src of seen.values()) {
    const m = /^(.*?)\s*\(([^()]*)\)$/.exec(src.title);
    const [stem, label] = m ? [m[1], m[2]] : [src.title, ""];
    if (!pubs.has(src.publisher)) pubs.set(src.publisher, { lics: new Map(), sets: new Map() });
    const p = pubs.get(src.publisher);
    p.lics.set(src.licence, src.licence_url);
    if (!p.sets.has(stem)) p.sets.set(stem, []);
    p.sets.get(stem).push({ ...src, label });
  }
  const groups = [...pubs.entries()].sort(([a], [b]) => a.localeCompare(b)).map(([pub, p]) => {
    const one = p.lics.size === 1 ? [...p.lics.entries()][0] : null;
    const head = `${esc(pub)}${one ? ` · <a href="${esc(one[1])}" rel="noopener">${esc(one[0])}</a>` : ""}`;
    const sets = [...p.sets.entries()].sort(([a, x], [b, y]) => (x.length > 1) - (y.length > 1) || a.localeCompare(b));
    const lis = sets.map(([stem, items]) => {
      items.sort((a, b) => a.label.localeCompare(b.label));
      if (items.length === 1) {
        const src = items[0];
        return `<li><a class="t" href="${esc(src.url)}" rel="noopener">${esc(src.title)}</a><span class="m">${one ? "" : `<a href="${esc(src.licence_url)}" rel="noopener">${esc(src.licence)}</a> · `}${src.retrieved ? `retrieved ${esc(src.retrieved)} · ` : ""}<span class="tnum">${esc(src.source_id)}</span></span></li>`;
      }
      const yrs = items.map((src) => `<a href="${esc(src.url)}" rel="noopener" title="${esc(src.title)} · ${esc(src.source_id)}">${esc(src.label)}</a>`).join("");
      return `<li class="src-set"><span class="t">${esc(stem)}</span><span class="yrs">${yrs}</span><span class="m">${items.length} files</span></li>`;
    }).join("");
    return `<div class="src-group"><h3 class="src-pub">${head}</h3><ul class="src-list">${lis}</ul></div>`;
  });
  return `<section class="cmp-section" id="cmp-sources"><h2>Sources</h2><div class="src-groups">${groups.join("")}</div></section>`;
}

// ---------------------------------------------------------------- render
function renderChips(schools) {
  const ul = qs("[data-cmp-chips]");
  ul.innerHTML = schools
    .map((s, i) => `<li class="cmp-chip">${swatch(i)}<a href="/school/${s.bsid}/">${esc(short(s.name))}</a><button type="button" class="icon-btn" data-remove="${esc(s.bsid)}" aria-label="Remove ${esc(s.name)}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg></button></li>`)
    .join("") + (schools.length < MAX_COMPARE ? `<li class="cmp-chip cmp-chip-empty">${schools.length ? `Add up to ${MAX_COMPARE - schools.length} more` : `Add 2 to ${MAX_COMPARE} schools`}</li>` : "");
  ul.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", () => go(state.schools.map((s) => s.bsid).filter((id) => id !== b.dataset.remove))));
}

function render() {
  const schools = state.schools;
  renderChips(schools);
  const has = schools.length > 0;
  for (const sel of ["[data-cmp-actions]", "[data-cmp-options]", "[data-cmp-nav]"]) qs(sel).hidden = !has;
  if (!has) {
    root.innerHTML = `<div class="note"><div><p>Pick schools with the box above, or press <strong>Compare</strong> on any school page or search result. You can compare up to ${MAX_COMPARE}.</p></div></div>`;
    return;
  }
  charts.length = 0;
  state.csv = [["Section", "Measure", "Year", ...schools.map((s) => `${s.name} (${s.bsid})`), "Ontario median"]];
  const single = schools.length === 1 ? `<div class="note" style="margin-bottom:16px"><div><p>Add at least one more school to compare side by side.</p></div></div>` : "";
  root.innerHTML = single + overview(schools) + eqao(schools) + enrolment(schools) + grades(schools) + classSizes(schools) + students(schools) + area(schools) + boardContext(schools) + nearby(schools) + sourcesList(schools) +
    `<p class="small muted" style="margin-top:20px">Every school is shown for the same school years. “—” means no value for that school and year; codes such as <span class="code">N/R</span> are explained in <a href="/methodology/#codes">How it works</a>. Medians are computed by this site from the same Ministry files.</p>`;
  drawCharts();
}

async function go(ids) {
  ids = [...new Set(ids)].slice(0, MAX_COMPARE);
  history.replaceState(null, "", ids.length ? `/compare/?ids=${ids.join(",")}` : "/compare/");
  if (!state.schools.length) root.innerHTML = '<p class="loading">Loading schools…</p>';
  let missing = [];
  try {
    const r = await load(ids);
    state.schools = ids.map((id) => r.schools.find((s) => s.bsid === id)).filter(Boolean);
    missing = r.missing;
  } catch {
    root.innerHTML = '<div class="note note-warn"><div><p>Couldn’t load the comparison. Check your connection and try again.</p></div></div>';
    return;
  }
  render();
  if (missing.length) root.insertAdjacentHTML("afterbegin", `<div class="note note-warn" style="margin-bottom:12px"><div><p>Couldn’t find school number${missing.length > 1 ? "s" : ""} ${missing.map(esc).join(", ")}.</p></div></div>`);
  setCompare(state.schools.map((s) => ({ id: s.bsid, name: s.name })));
}

// ---------------------------------------------------------------- controls
document.addEventListener("osf:pick", (e) => {
  const ids = state.schools.map((s) => s.bsid);
  if (ids.includes(e.detail.id)) return;
  if (ids.length >= MAX_COMPARE) ids.shift();
  go([...ids, e.detail.id]);
});
for (const box of qsa("[data-opt]")) {
  box.addEventListener("change", () => {
    state.opts[box.dataset.opt] = box.checked;
    render();
  });
}
qs("[data-cmp-share]")?.addEventListener("click", async (e) => {
  const span = e.currentTarget.querySelector("span");
  try {
    await navigator.clipboard.writeText(location.href);
    span.textContent = "Link copied";
  } catch {
    span.textContent = "Copy the address bar";
  }
  setTimeout(() => (span.textContent = "Copy link"), 2500);
});
qs("[data-cmp-csv]")?.addEventListener("click", () => {
  const csv = state.csv.map((r) => r.map((v) => `"${String(v ?? "").replace(/"/g, '""')}"`).join(",")).join("\r\n");
  const url = URL.createObjectURL(new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: `school-comparison-${state.schools.map((s) => s.bsid).join("-")}.csv` });
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
qs("[data-cmp-print]")?.addEventListener("click", () => window.print());

go(idsFromUrl() || getCompare().map((x) => x.id));
