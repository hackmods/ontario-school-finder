// /compare/?ids=a,b,c — up to six schools side by side: every published measure, same school years.
import { qs, qsa, esc, SYSTEMS, km, fmtKm, dataUrl, t as tr, u, num as locNum, gradesOffered } from "./lib.js";
import { getCompare, setCompare, MAX_COMPARE } from "./compare-store.js";
import { lineChart, shortYear } from "./linechart.js";

const root = qs("[data-compare-root]");

// t() that also remembers the English text of each result, so the CSV download keeps English row labels
// (the same file whatever the page language). CSV section names and column headers are plain English literals.
const EN = new Map();
const fill = (s, vars) => (vars ? s.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m)) : s);
const t = (s, vars) => {
  const out = tr(s, vars);
  EN.set(out, fill(s, vars));
  return out;
};
const unEsc = (x) => x.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&#39;/g, "'").replace(/&amp;/g, "&");
const csvLabel = (label) => { const plain = unEsc(String(label).replace(/<[^>]+>/g, "")); return EN.get(plain) ?? EN.get(label) ?? plain; };

// the full placeholder is cut off in a phone-width box, like the home and search boxes
const addBox = qs("#cq");
if (addBox && matchMedia("(max-width: 480px)").matches) addBox.placeholder = t("Add a school");
const COLORS = ["var(--s1)", "var(--s2)", "var(--s3)", "var(--s4)", "var(--s5)", "var(--s6)"];
const ORDER = ["g3-reading", "g3-writing", "g3-math", "g6-reading", "g6-writing", "g6-math", "g9-math", "g9-math-academic", "g9-math-applied", "osslt"];
const GRADES = ["JK", "K", "G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8", "G9", "G10", "G11", "G12"];
const GRADE_LABEL = (g) => (g === "JK" ? t("Junior kindergarten") : g === "K" ? t("Kindergarten") : t("Grade {n}", { n: g.slice(1) }));
// grade codes from the data: "JK", "K" (senior kindergarten), "3"
const gradeNm = (g) => (g === "JK" ? t("Junior kindergarten") : g === "K" ? t("Senior kindergarten") : t("Grade {n}", { n: g }));
const AREA_FIELDS = ["population", "children_0_14_pct", "couple_hh_children_pct", "one_parent_hh_pct", "median_household_income", "low_income_0_17_pct", "home_other_pct", "home_french_pct"];

const state = { schools: [], fsas: {}, meta: null, ctx: null, boards: null, opts: { prov: true, board: false, diff: false }, csv: [] };

// ---------------------------------------------------------------- loading
function idsFromUrl() {
  const v = new URLSearchParams(location.search).get("ids");
  return v ? [...new Set(v.split(",").map((x) => x.trim()).filter(Boolean))].slice(0, MAX_COMPARE) : null;
}

const getJSON = (path) => fetch(dataUrl(path)).then((r) => (r.ok ? r.json() : Promise.reject(new Error(`${r.status} ${path}`))));

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
const pv = (v) => t("{n}%", { n: v }); // 12% (French: 12 %)
const pct = (v) => (v == null ? "—" : pv(v));
const num = (v) => (v == null ? "—" : locNum(v));
const money = (v) => (v == null ? "—" : t("${amount}", { amount: locNum(v) }));
const codeChip = (code) => `<span class="code" title="${esc(t(state.meta.codes?.[code]?.explain || ""))}">${esc(code || "—")}</span>`;
const swatch = (i) => `<span class="swatch" style="background:${COLORS[i]}"></span>`;

function th(schools) {
  return `<thead><tr><th scope="col" class="sticky">${t("Measure")}</th>${schools.map((s, i) => `<th scope="col">${swatch(i)}<a href="${u(`/school/${s.bsid}/`)}">${esc(s.name)}</a></th>`).join("")}</tr></thead>`;
}

/** rows: [{label, sub, cells: [html], raw: [value]}] — also recorded for CSV (every row, whatever is hidden). The CSV is English. */
function table(section, schools, rows, { caption, extraHead = "", extra = null } = {}) {
  for (const r of rows) state.csv.push([section, csvLabel(r.label), r.year || "", ...r.raw.map((v) => (v == null ? "" : v)), ...(extra ? [r.extraRaw ?? ""] : [])]);
  const head = th(schools).replace("</tr></thead>", `${extraHead}</tr></thead>`);
  // "Only rows that differ" hides rows where every school has the same value. A missing value counts as a
  // value ("—" is not the same as "12"), so a gap in one school's data is never hidden as "the same".
  const same = (r) => schools.length > 1 && !r.keep && r.raw.every((v) => String(v ?? "") === String(r.raw[0] ?? ""));
  return `<div class="table-wrap cmp-table"><table>${caption ? `<caption>${caption}</caption>` : ""}${head}<tbody>${rows
    .map((r) => `<tr${same(r) ? ' class="cmp-same"' : ""}><th scope="row" class="sticky">${r.label}${r.sub ? `<div class="small muted">${r.sub}</div>` : ""}</th>${r.cells.map((c) => `<td class="n">${c}</td>`).join("")}${extra ? `<td class="n muted">${r.extra ?? "—"}</td>` : ""}</tr>`)
    .join("")}</tbody></table></div>`;
}

// program badge labels arrive from the data ("French Immersion", "SHSM · 3 sectors")
const badgeLabel = (b) => {
  const m = b.key === "shsm" && /^SHSM · (\d+) sectors?$/.exec(b.label);
  return m ? (+m[1] === 1 ? t("SHSM · 1 sector") : t("SHSM · {n} sectors", { n: m[1] })) : t(b.label);
};
const badgeList = (bs) => (bs?.length ? bs.map((b) => `<span class="badge badge-prog prog-${esc(b.key)}">${esc(badgeLabel(b))}</span>`).join(" ") : `<span class="muted">${t("None listed")}</span>`);

// "Grade 1 to Grade 8", rebuilt from the Ministry's range ("1-8") the way site/family.py words it
const gradeSpan = (s) => {
  const g = gradesOffered(s.grades);
  if (!g) return s.family?.grade_span ? t(s.family.grade_span) : s.grades || "—";
  const first = gradeNm(g[0]);
  const last = g[g.length - 1];
  return last === "JK" || last === "K" ? first : t("{first} to {last}", { first, last: t("Grade {n}", { n: last }) });
};

// The practical facts first: grades, programs and how to get in, before any chart.
function practical(schools) {
  const fam = (s) => s.family || {};
  const csLabel = (s) => {
    const st = s.class_size_status?.status;
    if (s.level !== "elementary") return `<span class="muted">${t("Not applicable (high school)")}</span>`;
    if (st === "reported") { const r = s.class_size?.[s.class_size.length - 1]; return r ? t("Reported to {year}", { year: esc(r.year) }) : t("Reported"); }
    if (st === "match_unresolved") return `<span class="muted">${t("Source match unresolved")}</span>`;
    return `<span class="muted">${t("Not in the class lists")}</span>`;
  };
  const link = (x, fallback) => (x ? `<a href="${esc(x.url)}" rel="noopener">${esc(x.title)}</a>` : `<span class="muted">${fallback}</span>`);
  const rows = [
    { label: t("Grades offered"), sub: t("Ministry school list"), cells: schools.map((s) => esc(gradeSpan(s))), raw: schools.map((s) => s.grades) },
    { label: t("Programs"), sub: t("French Immersion, Extended French, SHSM; French-language schools teach in French all day"), cells: schools.map((s) => badgeList(fam(s).badges)), raw: schools.map((s) => (fam(s).badges || []).map((b) => b.label).join("; ")) },
    { label: t("School type"), cells: schools.map((s) => esc(t(s.special || "Regular school"))), raw: schools.map((s) => s.special || "Regular school") },
    {
      label: t("French Immersion: how to get in"), sub: t("from the board's own page"),
      cells: schools.map((s) => {
        const f = fam(s);
        const boardPage = f.fi_page ? `<div class="small"><a href="${esc(f.fi_page.url)}" rel="noopener">${t("Board's page")}</a></div>` : "";
        if (!(f.badges || []).some((b) => b.key === "french-immersion")) return '<span class="muted">—</span>';
        if (f.fi_entry) return `${t("Starts in {grades}", { grades: esc(f.fi_entry.map(gradeNm).join(t(" or "))) })}${boardPage}`;
        if (s.level === "secondary" && f.fi_page) return `${t("Continues from elementary Immersion")}${boardPage}`;
        return `<span class="muted">${f.info_collected ? t("Not published") : t("Not yet collected")}</span>`;
      }),
      raw: schools.map((s) => (fam(s).fi_entry || []).join(", ")),
    },
    { label: t("Which school serves an address"), cells: schools.map((s) => link(fam(s).locator, t("Ask the board"))), raw: schools.map((s) => fam(s).locator?.url || "") },
    { label: t("How to register"), cells: schools.map((s) => link(fam(s).register, t("Not yet collected"))), raw: schools.map((s) => fam(s).register?.url || "") },
    { label: t("Attending outside your area"), cells: schools.map((s) => (fam(s).transfer ? (fam(s).transfer.kind === "not_found" ? `<span class="muted">${t("Not published by the board")}</span>` : link(fam(s).transfer, "")) : `<span class="muted">${t("Not yet collected")}</span>`)), raw: schools.map((s) => fam(s).transfer?.url || "") },
    { label: t("Licensed child care at the school's address"), sub: t("a licence is not a guarantee of space"), cells: schools.map((s) => (s.childcare.at_address.length ? t("Yes ({n})", { n: s.childcare.at_address.length }) : t("None listed"))), raw: schools.map((s) => s.childcare.at_address.length) },
    { label: t("Class sizes"), cells: schools.map(csLabel), raw: schools.map((s) => s.class_size_status?.status || "") },
  ];
  return `<section class="cmp-section" id="cmp-practical"><h2>${t("At a glance")}</h2><p class="block-intro">${t("Practical facts first. Registration, program and transfer details come from each board's own pages where we have collected them; always confirm with the board.")}</p>${table("At a glance", schools, rows)}</section>`;
}

// Warn when schools' latest figures are from different years, instead of letting them sit side by side silently.
function yearWarning(kind, years) {
  const yrs = [...new Set(years.filter(Boolean))];
  const msg = kind === "eqao"
    ? "The latest EQAO results differ by school ({years}), so these columns aren't all the same year."
    : "The latest class-size years differ by school ({years}), so these columns aren't all the same year.";
  return yrs.length > 1 ? `<p class="note note-warn small cmp-warn"><span>${t(msg, { years: yrs.map(esc).join(", ") })}</span></p>` : "";
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
    if (f) return f[key] ? t("Yes") : t("No");
    return s.language === "French" ? `<span class="muted">${t("French-language school")}</span>` : `<span class="muted">${t("Not in the list")}</span>`;
  };
  const raw = (s, key) => (s.programs?.fsl ? (s.programs.fsl[key] ? "yes" : "no") : "");
  return [
    { label: t("French Immersion"), sub: t("Ministry FSL list, 2024-25 (preliminary)"), cells: schools.map((s) => cell(s, "immersion")), raw: schools.map((s) => raw(s, "immersion")) },
    { label: t("Extended French"), sub: t("Ministry FSL list, 2024-25 (preliminary)"), cells: schools.map((s) => cell(s, "extended")), raw: schools.map((s) => raw(s, "extended")) },
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
    { label: t("Board"), cells: schools.map((s) => `<a href="${u(`/board/${s.board_number}/`)}">${esc(s.board_name)}</a>`), raw: schools.map((s) => s.board_name) },
    { label: t("System"), cells: schools.map((s) => esc(t(SYSTEMS[s.system] || ""))), raw: schools.map((s) => SYSTEMS[s.system]) },
    { label: t("Level and grades"), cells: schools.map((s) => `${esc(t(cap(s.level)))} · ${esc(s.grades || "")}`), raw: schools.map((s) => `${cap(s.level)} ${s.grades || ""}`) },
    { label: t("Language"), cells: schools.map((s) => esc(t(s.language))), raw: schools.map((s) => s.language) },
    { label: t("Address"), cells: schools.map((s) => esc([s.address, s.city].filter(Boolean).join(", "))), raw: schools.map((s) => [s.address, s.city].filter(Boolean).join(", ")) },
    { label: t("Postal area"), cells: schools.map((s) => `<a href="${u(`/fsa/${s.fsa}/`)}">${esc(s.fsa)}</a>`), raw: schools.map((s) => s.fsa) },
    { label: t("Open at this school number since"), sub: t("1969 is the earliest date the Ministry's list uses; not the building's age"), cells: schools.map((s) => esc(s.family?.opened || "—")), raw: schools.map((s) => s.family?.opened || "") },
    { label: t("Students (latest)"), cells: schools.map((s) => { const e = latestEnrol(s); return e ? `${num(e.value)}<div class="small muted">${esc(e.year)}</div>` : "—"; }), raw: schools.map((s) => latestEnrol(s)?.value) },
    { label: t("Enrolment change (5 years)"), cells: schools.map((s) => { const c = change(s); return c ? `${c.d >= 0 ? "+" : "−"}${num(Math.abs(c.d))}<div class="small muted">${t("since {year}", { year: esc(c.since) })}</div>` : "—"; }), raw: schools.map((s) => change(s)?.d) },
    {
      label: t("EarlyON centres in the postal area"), sub: t("free programs for children up to 6"),
      cells: schools.map((s) => (s.earlyon_in_fsa ? `<a href="${u(`/fsa/${s.fsa}/#earlyon`)}">${s.earlyon_in_fsa}</a>` : t("None listed"))),
      raw: schools.map((s) => s.earlyon_in_fsa || 0),
    },
    ...frenchRows(schools),
    {
      label: t("Student nutrition program"), sub: t("Historical only: Ministry list from December 2017; current availability unverified"),
      cells: schools.map((s) => (s.programs?.nutrition ? t("Historically listed: {meals}", { meals: esc(s.programs.nutrition.meals.map((x) => t(x)).join(", ")) }) : `<span class="muted">${t("Not on the 2017 list (may have one now)")}</span>`)),
      raw: schools.map((s) => (s.programs?.nutrition ? `historically listed (2017): ${s.programs.nutrition.meals.join("; ")}` : "")),
    },
    {
      label: t("Specialist High Skills Majors"), sub: t("career-sector programs, 2025-26"),
      cells: schools.map((s) => (s.programs?.shsm ? `${s.programs.shsm.sectors.length}<div class="small muted">${esc(s.programs.shsm.sectors.map((p) => t(p.sector)).join(", "))}</div>` : s.level === "secondary" ? t("None listed") : "—")),
      raw: schools.map((s) => (s.programs?.shsm ? s.programs.shsm.sectors.map((p) => p.sector).join("; ") : "")),
    },
  ];
  if (schools.length > 1) {
    rows.push({ label: t("Distance from {name}", { name: esc(short(first.name)) }), cells: schools.map((s, i) => (i === 0 ? "—" : fmtKm(km([first.lon, first.lat], [s.lon, s.lat])))), raw: schools.map((s, i) => (i === 0 ? "" : km([first.lon, first.lat], [s.lon, s.lat]).toFixed(1))) });
  }
  rows.push({ label: t("Links"), cells: schools.map((s) => [s.website ? `<a href="${esc(s.website)}" rel="noopener">${t("Website")}</a>` : "", `<a href="${esc(s.links.eqao)}" rel="noopener">${t("EQAO")}</a>`, s.phone ? `<a href="tel:${esc(s.phone.replace(/-/g, ""))}">${esc(s.phone)}</a>` : ""].filter(Boolean).join("<br>")), raw: schools.map((s) => s.website) });
  return `<section class="cmp-section" id="cmp-overview"><h2>${t("Details")}</h2>${table("Details", schools, rows)}</section>`;
}

function eqao(schools) {
  const meta = state.meta;
  const present = ORDER.filter((a) => schools.some((s) => s.eqao.some((e) => e.assessment === a)));
  if (!present.length) return `<section class="cmp-section" id="cmp-eqao"><h2>${t("EQAO results")}</h2><div class="note"><div><p>${t("None of these schools has EQAO results in the source data (no Grade 3, 6, 9 or 10 students, or special-purpose schools).")}</p></div></div></section>`;
  const langs = [...new Set(schools.map((s) => s.language))];
  const provByLang = {};
  for (const m of meta.province_medians) (provByLang[`${m.assessment}|${m.language}`] ||= {})[m.year] = m.median;
  // EQAO started new trend lines in 2021-22 (online assessments, new design, new math standards). Charts,
  // tables and the change row use the current era only; paper-era years are listed apart, never joined.
  const from = meta.eqao_eras?.current_from || "2021-22";
  const isCurrent = (e) => (e.era ? e.era === "current" : e.year >= from);
  const latestBySchool = schools.map((s) => s.eqao.filter(isCurrent).reduce((m, e) => (e.year > m ? e.year : m), ""));
  const intro = [
    t("Share of each school’s students meeting the provincial standard, from {from}, when EQAO’s current online assessments began a new trend line. Each year is a different group of students.", { from: esc(from) }),
    state.opts.prov ? t("The dotted line is the median Ontario school of the same language.") : "",
    state.opts.board ? t("Thin dashed lines are each school’s board median.") : "",
    t("Earlier paper-based results are listed at the end of this section and never joined to these."),
  ].filter(Boolean).join(" ");
  let html = `<section class="cmp-section" id="cmp-eqao"><h2>${t("EQAO results")} <span class="badge">${t("{from} to {to}", { from: esc(from), to: esc(meta.latest_eqao_year) })}</span></h2>
    <p class="block-intro">${intro}</p>
    ${yearWarning("eqao", latestBySchool)}`;
  const paperRows = [];
  for (const a of present) {
    const info = meta.assessments[a];
    const grade = t(info.grade);
    const subject = t(info.subject);
    for (const s of schools) for (const e of s.eqao) if (e.assessment === a && !isCurrent(e)) paperRows.push({ s, e, info });
    let years = meta.eqao_years.filter((y) => y >= from && schools.some((s) => s.eqao.some((e) => e.assessment === a && e.year === y && isCurrent(e))));
    if (!years.length) continue; // Grade 9 academic/applied: paper era only
    const series = [];
    schools.forEach((s, i) => {
      const values = {};
      const bvals = {};
      for (const e of s.eqao) if (e.assessment === a && isCurrent(e)) { values[e.year] = e.pct_at_or_above_standard; bvals[e.year] = e.board_median; }
      series.push({ label: s.name, color: COLORS[i], values });
      if (state.opts.board) series.push({ label: t("{board} median", { board: s.board_name }), color: COLORS[i], values: bvals, dash: "5 4", width: 1.5 });
    });
    if (state.opts.prov) for (const l of langs) series.push({ label: t("Ontario median ({language})", { language: t(l) }), color: "var(--c-prov)", values: Object.fromEntries(Object.entries(provByLang[`${a}|${l}`] || {}).filter(([y]) => y >= from)), dash: "2 4", width: 2 });
    const rows = years.map((y) => {
      const cells = [], raw = [];
      for (const s of schools) {
        const e = s.eqao.find((x) => x.assessment === a && x.year === y);
        if (!e) { cells.push('<span class="muted">—</span>'); raw.push(null); }
        else if (e.pct_at_or_above_standard == null) { cells.push(codeChip(e.code)); raw.push(e.code); }
        else { cells.push(`${pv(e.pct_at_or_above_standard)}${state.opts.board && e.board_median != null ? `<div class="small muted">${t("board {pct}", { pct: pv(e.board_median) })}</div>` : ""}`); raw.push(e.pct_at_or_above_standard); }
      }
      const pm = langs.map((l) => provByLang[`${a}|${l}`]?.[y]).filter((v) => v != null);
      return { label: esc(y), year: y, cells, raw, extra: pm.length ? pm.map((v) => pv(v)).join(" / ") : "—", extraRaw: pm.join(" / ") };
    });
    // change within the current era only: first to latest result from 2021-22 on (different students each year)
    const trend = schools.map((s) => {
      const pts = s.eqao.filter((e) => e.assessment === a && isCurrent(e) && e.pct_at_or_above_standard != null).sort((x, y) => x.year.localeCompare(y.year));
      if (pts.length < 2) return null;
      return { d: +(pts[pts.length - 1].pct_at_or_above_standard - pts[0].pct_at_or_above_standard).toFixed(1), from: pts[0].year, to: pts[pts.length - 1].year };
    });
    rows.push({
      label: `<b>${t("Change since {from}", { from: esc(from) })}</b>`, sub: t("first to latest result on the current assessments; different students each year"), year: "change",
      cells: trend.map((tn) => {
        if (!tn) return "—";
        const sign = tn.d > 0 ? "+" : tn.d < 0 ? "−" : "±";
        const mag = Math.abs(tn.d);
        return `<b>${mag === 1 ? t("{sign}{n} pt", { sign, n: num(mag) }) : t("{sign}{n} pts", { sign, n: num(mag) })}</b><div class="small muted">${esc(tn.from)}–${esc(tn.to.slice(-2))}</div>`;
      }),
      raw: trend.map((x) => (x ? x.d : null)), extra: "",
    });
    html += `<figure class="chart-card cmp-chart" style="margin:16px 0 0" id="cmp-${a}">
      <h3>${esc(grade)} · ${esc(subject)}</h3>
      ${legend(schools, state.opts.prov ? [`<li><i class="l-prov"></i>${t("Ontario median")}</li>`] : [])}
      ${chart(years, series, { gap: false, max: 100, title: t("{grade} {subject} by year, {from} to {to}", { grade, subject, from: years[0], to: years[years.length - 1] }) })}
      <details class="data-table"${wideScreen() ? " open" : ""}><summary>${t("Show the numbers")}</summary>${table(`EQAO ${info.grade} ${info.subject}`, schools, rows, { caption: t("{grade} {subject}: share meeting the standard", { grade: esc(grade), subject: esc(subject) }), extraHead: `<th scope="col">${t("Ontario median")}</th>`, extra: true })}</details>
    </figure>`;
  }
  if (paperRows.length) {
    // the CSV keeps these too, marked as the earlier era
    for (const { s, e, info } of paperRows) state.csv.push(["EQAO earlier paper-based (not comparable)", `${info.grade} ${info.subject}`, e.year, ...schools.map((x) => (x === s ? (e.pct_at_or_above_standard ?? e.code ?? "") : "")), ""]);
    const byKey = new Map();
    for (const { s, e, info } of paperRows) {
      const k = `${info.grade} ${info.subject}|${e.year}`;
      if (!byKey.has(k)) byKey.set(k, { label: `${t(info.grade)} ${t(info.subject)}`, year: e.year, vals: new Map() });
      byKey.get(k).vals.set(s.bsid, e);
    }
    const body = [...byKey.values()].map((r) => `<tr><th scope="row" class="sticky">${esc(r.label)}<div class="small muted">${esc(r.year)}</div></th>${schools.map((s) => { const e = r.vals.get(s.bsid); return `<td class="n">${!e ? '<span class="muted">—</span>' : e.pct_at_or_above_standard == null ? codeChip(e.code) : pv(e.pct_at_or_above_standard)}</td>`; }).join("")}</tr>`).join("");
    const paper = meta.eqao_eras?.eras?.paper;
    html += `<details class="data-table card" style="margin-top:16px"><summary>${t("Earlier results, {years}: a different test, not comparable", { years: esc(t(paper?.label || "2016-17 to 2018-19")) })}</summary>
      <p class="small muted">${esc(t(paper?.explain || ""))} ${t("No change is calculated between these and {from} or later.", { from: esc(from) })}</p>
      <div class="table-wrap cmp-table"><table><caption>${t("Paper-based EQAO results")}</caption>${th(schools)}<tbody>${body}</tbody></table></div></details>`;
  }
  return html + "</section>";
}

// What students said in EQAO's questionnaire: the latest year, one table per grade.
function experience(schools) {
  const sq = state.meta.student_questionnaire || {};
  const blocks = Object.entries(sq).filter(([sid]) => schools.some((s) => (s.student_experience || []).some((b) => b.source_id === sid)));
  if (!blocks.length) return "";
  let html = `<section class="cmp-section" id="cmp-experience"><h2>${t("Student experience")} <span class="badge">${esc(blocks[0][1].year)}</span></h2>
    <p class="block-intro">${t("Share of students who agreed, from EQAO’s questionnaire: students’ own views, not a measure of a school’s quality. The Ontario column is EQAO’s figure for every student who answered. Grades use different answer scales, so compare within a grade only.")}</p>`;
  for (const [sid, m] of blocks) {
    const grade = m.grade === "10" ? t("Grade 10 (OSSLT)") : t("Grade {n}", { n: m.grade });
    const blockOf = (s) => (s.student_experience || []).find((b) => b.source_id === sid);
    const rows = [{ label: t("Students who answered"), year: m.year, keep: true, cells: schools.map((s) => { const b = blockOf(s); return !b ? `<span class="muted">${t("No students in this grade")}</span>` : b.withheld ? `<span class="muted">${t("Withheld (too few students)")}</span>` : num(b.respondents); }), raw: schools.map((s) => { const b = blockOf(s); return b ? (b.withheld ? "withheld" : b.respondents) : ""; }), extra: "", extraRaw: "" }];
    for (const q of m.questions) {
      const it = (s) => blockOf(s)?.items.find((x) => x.key === q.key);
      const prov = schools.map((s) => it(s)?.province_pct).find((v) => v != null);
      rows.push({
        label: t("“{question}”", { question: esc(t(q.question)) }), sub: t("agreed: {answers}", { answers: esc(q.agree.map((a) => t(a)).join(t(" or ")).toLowerCase()) }), year: m.year,
        cells: schools.map((s) => { const x = it(s); const b = blockOf(s); return !b ? '<span class="muted">—</span>' : !x ? `<span class="muted">${t("Not asked")}</span>` : x.agree_pct == null ? codeChip(x.code) : `${pv(x.agree_pct)}<div class="small muted">${t("board {pct}", { pct: pct(x.board_pct) })}</div>`; }),
        raw: schools.map((s) => { const x = it(s); return x ? (x.agree_pct ?? x.code) : null; }),
        extra: pct(prov), extraRaw: prov ?? "",
      });
    }
    html += `<h3 style="margin-top:16px">${esc(grade)}</h3>${table(`Student experience ${m.grade === "10" ? "Grade 10 (OSSLT)" : `Grade ${m.grade}`}`, schools, rows, { caption: t("{grade}, {year}: share of students who agreed", { grade: esc(grade), year: esc(m.year) }), extraHead: `<th scope="col">${t("Ontario")}</th>`, extra: true })}`;
  }
  return html + `<p class="small muted">${t("Share of students who fully took part in the assessment, including those who skipped the question. Board figures are EQAO’s for the school’s whole board.")}</p></section>`;
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
  return `<section class="cmp-section" id="cmp-enrolment"><h2>${t("Enrolment")} <span class="badge">${t("{from} to {to}", { from: esc(years[0]), to: esc(years[years.length - 1]) })}</span></h2>
    <div class="chart-card">${legend(schools)}${chart(years, series, { unit: "", min: 0, title: t("Enrolment by year") })}
    <details class="data-table"><summary>${t("Show every year")}</summary>${table("Enrolment", schools, rows)}</details>
    <p class="small muted">${t("Headcount reported by boards; rounded to the nearest 5 since 2018-19.")}</p></div></section>`;
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
  rows.unshift({ label: t("School year"), cells: latest.map((l) => (l ? esc(l.year) : "—")), raw: latest.map((l) => l?.year) });
  return `<section class="cmp-section" id="cmp-grades"><h2>${t("Students by grade")}</h2><p class="block-intro">${t("How many students are in each grade, from each school’s latest file. Small counts are withheld ({code}).", { code: '<span class="code">&lt;10</span>' })}</p>${table("Students by grade", schools, rows)}</section>`;
}

function classSizes(schools) {
  const any = schools.some((s) => s.class_size?.length);
  // say why a school has no class sizes: a high school (not applicable), a name the class lists share with
  // another school in the board (source match unresolved), or not in the lists at all
  const why = (s) => {
    const st = s.class_size_status?.status;
    if (s.level !== "elementary") return t("{name}: not applicable (the Ministry publishes class sizes for elementary schools only).", { name: esc(s.name) });
    if (st === "match_unresolved") return t("{name}: source match unresolved. The class lists name schools without a number, and another school in its board has the same name, so neither can be shown.", { name: esc(s.name) });
    if (st === "not_listed") return t("{name}: not in the Ministry’s class lists.", { name: esc(s.name) });
    return "";
  };
  const missing = schools.filter((s) => !s.class_size?.length).map(why).filter(Boolean);
  const missingNote = missing.length ? `<div class="note" style="margin-top:12px"><div>${missing.map((m) => `<p>${m}</p>`).join("")}</div></div>` : "";
  if (!any) return `<section class="cmp-section" id="cmp-class"><h2>${t("Class sizes")}</h2>${missingNote}</section>`;
  const years = [...new Set(schools.flatMap((s) => (s.class_size || []).map((r) => r.year)))].sort();
  const series = schools.map((s, i) => ({ label: s.name, color: COLORS[i], values: Object.fromEntries((s.class_size || []).map((r) => [r.year, r.primary_avg])) }));
  if (state.opts.prov) {
    const lang = schools[0].language;
    const pvals = {};
    for (const s of schools) for (const r of s.class_size || []) if (s.language === lang && r.primary_province_median != null) pvals[r.year] = r.primary_province_median;
    series.push({ label: t("Ontario median"), color: "var(--c-prov)", values: pvals, dash: "2 4", width: 2 });
  }
  const latestYear = years[years.length - 1];
  const at = (s) => (s.class_size || []).find((r) => r.year === latestYear) || (s.class_size || []).slice(-1)[0];
  const metric = (label, sub, f, fmt = (v) => v) => ({
    label, sub, year: latestYear,
    cells: schools.map((s) => { const r = at(s); const v = r ? f(r) : null; return v == null ? '<span class="muted">—</span>' : fmt(v); }),
    raw: schools.map((s) => { const r = at(s); return r ? f(r) : null; }),
  });
  const rows = [
    metric(t("School year"), "", (r) => r.year),
    metric(t("Average class size, all classes"), "", (r) => r.avg_all),
    metric(t("Grades 1–3 classes: average size"), t("Ontario’s rule: at most 23, and 90% of classes 20 or fewer"), (r) => r.primary_avg),
    metric(t("Grades 1–3 classes with 20 or fewer students"), "", (r) => r.primary_le20_pct, (v) => pv(v)),
    metric(t("Largest Grade 1–3 class"), "", (r) => r.primary_max),
    metric(t("Kindergarten classes: average size"), "", (r) => r.kinder_avg),
    metric(t("Grades 4–8 classes: average size"), "", (r) => r.junior_avg),
    metric(t("Combined-grade classes"), t("classes mixing kindergarten, primary and junior grades"), (r) => r.combined_classes),
    metric(t("Number of classes"), "", (r) => r.classes),
  ];
  return `<section class="cmp-section" id="cmp-class"><h2>${t("Class sizes")} <span class="badge">${t("{from} to {to}", { from: esc(years[0]), to: esc(latestYear) })}</span></h2>
    <p class="block-intro">${t("Computed from the Ministry’s list of every elementary class (counted each September). Before 2014-15 only primary classes were listed, so the long trend uses Grades 1–3 classes.")}</p>
    <div class="chart-card">${legend(schools, state.opts.prov ? [`<li><i class="l-prov"></i>${t("Ontario median")}</li>`] : [])}
    ${chart(years, series, { unit: "", min: 0, max: 30, title: t("Average Grades 1–3 class size by year") })}
    ${yearWarning("class", schools.filter((s) => s.class_size?.length).map((s) => s.class_size[s.class_size.length - 1].year))}
    ${table("Class sizes", schools, rows, { caption: t("Latest year") })}${missingNote}</div></section>`;
}

// Each school's board, from one shared file: spending per student, suspensions, French Immersion share
function boardContext(schools) {
  const bc = state.boards;
  if (!bc) return "";
  const b = (s) => bc.boards[s.board_number] || {};
  const rows = [
    { label: t("Board"), cells: schools.map((s) => `<a href="${u(`/board/${s.board_number}/#context`)}">${esc(s.board_name)}</a>`), raw: schools.map((s) => s.board_name) },
    { label: t("Spending per student"), sub: t("{year} · Ontario's middle board {amount}", { year: esc(bc.spending_year), amount: money(bc.spending_median) }), cells: schools.map((s) => money(b(s).sp)), raw: schools.map((s) => b(s).sp) },
    { label: t("Students suspended"), sub: t("share of the board's students, latest year"), cells: schools.map((s) => (b(s).sr != null ? `${pv(b(s).sr)}<div class="small muted">${t("{year} · Ontario {pct}", { year: esc(b(s).sry), pct: pv(b(s).srp) })}</div>` : "—")), raw: schools.map((s) => b(s).sr) },
    { label: t("Students in French Immersion"), sub: t("share of the board's students, {year}", { year: esc(bc.fsl_year) }), cells: schools.map((s) => (b(s).fi != null ? pv(b(s).fi) : '<span class="muted">—</span>')), raw: schools.map((s) => b(s).fi) },
  ];
  return `<section class="cmp-section" id="cmp-board"><h2>${t("School board context")}</h2><p class="block-intro">${t("These describe each school's whole board, not the school itself. Details are on each board's page.")}</p>${table("Board context", schools, rows)}</section>`;
}

function students(schools) {
  const fields = state.meta.context_fields;
  const year = schools[0]?.context.year;
  const rows = fields.map((f) => ({
    label: esc(t(f.label)), sub: esc(t(f.definition)), year,
    cells: schools.map((s) => { const it = s.context.items.find((x) => x.key === f.key); return !it ? "—" : it.value != null ? pv(it.value) : codeChip(it.code); }),
    raw: schools.map((s) => { const it = s.context.items.find((x) => x.key === f.key); return it ? (it.value ?? it.code) : null; }),
    extra: state.ctx ? pct(state.ctx.province?.[schools[0].language]?.[f.key]) : "—",
    extraRaw: state.ctx?.province?.[schools[0].language]?.[f.key] ?? "",
  }));
  return `<section class="cmp-section" id="cmp-students"><h2>${t("About the students")} <span class="badge">${esc(year || "")}</span></h2>
    <p class="block-intro">${t("Who each school serves. These describe the student population; they are not measures of quality. The Ministry rounds these to whole percentages, so 0% can still mean a few students. How many students are identified as gifted also depends on each board’s identification practice, so compare it within a board.")}</p>
    ${table("Students", schools, rows, { extraHead: `<th scope="col">${t("Ontario median")}</th>`, extra: true })}</section>`;
}

function area(schools) {
  const fields = state.meta.census_fields.filter((f) => AREA_FIELDS.includes(f.key));
  const fmt = (f, v) => (v == null ? "—" : f.unit === "pct" ? pv(v) : f.unit === "dollars" ? money(v) : num(v));
  const rows = [{ label: t("Postal area"), cells: schools.map((s) => `<a href="${u(`/fsa/${s.fsa}/`)}">${esc(s.fsa)}</a>`), raw: schools.map((s) => s.fsa) }].concat(
    fields.map((f) => ({ label: esc(t(f.label)), year: "2021", cells: schools.map((s) => fmt(f, state.fsas[s.fsa]?.census?.[f.key])), raw: schools.map((s) => state.fsas[s.fsa]?.census?.[f.key]) })),
  );
  return `<section class="cmp-section" id="cmp-area"><h2>${t("The surrounding area")} <span class="badge">${t("2021 Census")}</span></h2>
    <p class="block-intro">${t("Statistics Canada figures for each school’s postal area (everyone who lives there, not only school families).")}</p>${table("Area", schools, rows)}</section>`;
}

function nearby(schools) {
  const rows = [
    { label: t("Licensed child care at the school’s address"), cells: schools.map((s) => (s.childcare.at_address.length ? s.childcare.at_address.map((c) => esc(c.name)).join("<br>") : t("None listed"))), raw: schools.map((s) => s.childcare.at_address.map((c) => c.name).join("; ")) },
    { label: t("Licensed child care sites in the postal area"), cells: schools.map((s) => num(s.childcare.in_fsa_count)), raw: schools.map((s) => s.childcare.in_fsa_count) },
    { label: t("Nearest other school of the same level"), cells: schools.map((s) => (s.nearby[0] ? `<a href="${u(`/school/${s.nearby[0].bsid}/`)}">${esc(s.nearby[0].name)}</a><div class="small muted">${t("{n} km", { n: locNum(s.nearby[0].km) })}</div>` : "—")), raw: schools.map((s) => (s.nearby[0] ? `${s.nearby[0].name} (${s.nearby[0].km} km)` : "")) },
  ];
  return `<section class="cmp-section" id="cmp-nearby"><h2>${t("Child care and nearby")}</h2>${table("Child care and nearby", schools, rows)}</section>`;
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
    const head = `${esc(t(pub))}${one ? ` · <a href="${esc(one[1])}" rel="noopener">${esc(t(one[0]))}</a>` : ""}`;
    const sets = [...p.sets.entries()].sort(([a, x], [b, y]) => (x.length > 1) - (y.length > 1) || a.localeCompare(b));
    const lis = sets.map(([stem, items]) => {
      items.sort((a, b) => a.label.localeCompare(b.label));
      if (items.length === 1) {
        const src = items[0];
        return `<li><a class="t" href="${esc(src.url)}" rel="noopener">${esc(src.title)}</a><span class="m">${one ? "" : `<a href="${esc(src.licence_url)}" rel="noopener">${esc(t(src.licence))}</a> · `}${src.retrieved ? `${t("retrieved {date}", { date: esc(src.retrieved) })} · ` : ""}<span class="tnum">${esc(src.source_id)}</span></span></li>`;
      }
      const yrs = items.map((src) => `<a href="${esc(src.url)}" rel="noopener" title="${esc(src.title)} · ${esc(src.source_id)}">${esc(src.label)}</a>`).join("");
      return `<li class="src-set"><span class="t">${esc(stem)}</span><span class="yrs">${yrs}</span><span class="m">${t("{n} files", { n: items.length })}</span></li>`;
    }).join("");
    return `<div class="src-group"><h3 class="src-pub">${head}</h3><ul class="src-list">${lis}</ul></div>`;
  });
  return `<section class="cmp-section" id="cmp-sources"><h2>${t("Sources")}</h2><div class="src-groups">${groups.join("")}</div></section>`;
}

// ---------------------------------------------------------------- render
function renderChips(schools) {
  const ul = qs("[data-cmp-chips]");
  const empty = schools.length < MAX_COMPARE ? `<li class="cmp-chip cmp-chip-empty">${schools.length ? t("Add up to {n} more", { n: MAX_COMPARE - schools.length }) : t("Add 2 to {n} schools", { n: MAX_COMPARE })}</li>` : "";
  ul.innerHTML = schools
    .map((s, i) => `<li class="cmp-chip">${swatch(i)}<a href="${u(`/school/${s.bsid}/`)}">${esc(short(s.name))}</a><button type="button" class="icon-btn" data-remove="${esc(s.bsid)}" aria-label="${t("Remove {name}", { name: esc(s.name) })}"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18"/></svg></button></li>`)
    .join("") + empty;
  ul.querySelectorAll("[data-remove]").forEach((b) => b.addEventListener("click", () => go((state.ids || state.schools.map((s) => s.bsid)).filter((id) => id !== b.dataset.remove))));
}

function render() {
  const schools = state.schools;
  renderChips(schools);
  const has = schools.length > 0;
  for (const sel of ["[data-cmp-actions]", "[data-cmp-options]", "[data-cmp-nav]"]) qs(sel).hidden = !has;
  if (!has) {
    root.innerHTML = `<div class="note"><div><p>${t("Pick schools with the box above, or press {compare} on any school page or search result. You can compare up to {max}.", { compare: `<strong>${t("Compare")}</strong>`, max: MAX_COMPARE })}</p></div></div>`;
    return;
  }
  charts.length = 0;
  state.csv = [["Section", "Measure", "Year", ...schools.map((s) => `${s.name} (${s.bsid})`), "Ontario median"]]; // English headers on purpose
  const single = schools.length === 1 ? `<div class="note" style="margin-bottom:16px"><div><p>${t("Add at least one more school to compare side by side.")}</p></div></div>` : "";
  root.classList.toggle("diff-only", state.opts.diff && schools.length > 1);
  // on paper the toggle is hidden, so say that rows are left out
  const diffNote = `<p class="cmp-diff-note small muted">${t("Only rows where the schools differ are shown. Rows where every school has the same value are left out.")}</p>`;
  root.innerHTML = single + diffNote + practical(schools) + overview(schools) + eqao(schools) + experience(schools) + enrolment(schools) + grades(schools) + classSizes(schools) + students(schools) + area(schools) + boardContext(schools) + nearby(schools) + sourcesList(schools) +
    `<p class="small muted" style="margin-top:20px">${t("Every school is shown for the same school years. “—” means no value for that school and year; codes such as {code} are explained in {link}. Medians are computed by this site from the same Ministry files.", { code: '<span class="code">N/R</span>', link: `<a href="${u("/methodology/#codes")}">${t("How it works")}</a>` })}</p>`;
  drawCharts();
}

// state.ids is the list the visitor asked for, set at once; state.schools is what has loaded. Adding or removing
// works from state.ids, so a school picked while others are still loading never drops them, and a load that a
// later change has overtaken is ignored.
let loadSeq = 0;
async function go(ids) {
  ids = [...new Set(ids)].slice(0, MAX_COMPARE);
  state.ids = ids;
  const seq = ++loadSeq;
  history.replaceState(null, "", u(ids.length ? `/compare/?ids=${ids.join(",")}` : "/compare/"));
  if (!state.schools.length) root.innerHTML = `<p class="loading">${t("Loading schools…")}</p>`;
  let missing = [];
  try {
    const r = await load(ids);
    if (seq !== loadSeq) return;
    state.schools = ids.map((id) => r.schools.find((s) => s.bsid === id)).filter(Boolean);
    missing = r.missing;
  } catch {
    if (seq !== loadSeq) return;
    root.innerHTML = `<div class="note note-warn"><div><p>${t("Couldn’t load the comparison. Check your connection and try again.")}</p></div></div>`;
    return;
  }
  render();
  if (missing.length) root.insertAdjacentHTML("afterbegin", `<div class="note note-warn" style="margin-bottom:12px"><div><p>${missing.length > 1 ? t("Couldn’t find school numbers {list}.", { list: missing.map(esc).join(", ") }) : t("Couldn’t find school number {list}.", { list: missing.map(esc).join(", ") })}</p></div></div>`);
  setCompare(state.schools.map((s) => ({ id: s.bsid, name: s.name })));
}

// ---------------------------------------------------------------- controls
document.addEventListener("osf:pick", (e) => {
  const ids = [...(state.ids || state.schools.map((s) => s.bsid))];
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
    span.textContent = t("Link copied");
  } catch {
    span.textContent = t("Copy the address bar");
  }
  setTimeout(() => (span.textContent = t("Copy link")), 2500);
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
