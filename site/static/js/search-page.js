// /search/ page: full results with filters, "near me", and address search (NRCan Geolocation Service).
import { qs, qsa, esc, loadIndex, loadBoards, SYSTEMS, km, fmtKm, GRADE_ORDER, gradeName, gradesOffered, t, u, num, LANG } from "./lib.js";
import { searchAll, looksLikeAddress } from "./search.js";
import { nearest, locate } from "./near.js";
import { schoolRow } from "./results.js";
import { lazyMap, addSchoolLayer, pointsFC, boundsOf } from "./maps.js";

const root = qs("[data-results]");
const input = qs("#sq");
const params = new URLSearchParams(location.search);
const q = (params.get("q") || "").trim();
if (input) input.value = q;
// the full placeholder is cut off in a phone-width box; the hint below the box spells out every option
if (input && matchMedia("(max-width: 480px)").matches) input.placeholder = t("School, city, postal code…");

const GEOCODER = `https://www.geolocator.api.geo.ca/geolocation/${LANG}/locate`;
let lastGeocode = 0;

const filters = { level: "all", lang: "all", sys: "all", prog: "all", grade: params.get("grade") || "all" };
// program filters use flags from the search index: fi = French Immersion (Ministry list), fb = French Immersion
// (the board's own list), ef = Extended French, sh = SHSM sectors
const PROGRAMS = { fi: (r) => r.fi || r.fb, ef: (r) => r.ef, sh: (r) => r.sh };
let base = [];
let distances = null;
let heading = "";
let shown = 30;
let mapRows = [];
let mapRef = null;
let sortBy = ""; // "" = the default for the kind of search: nearest first for a location, best match for text, A to Z for a postal area
let textSearch = true; // a postal-area search lists schools A to Z already, so it has no "best match" order
let showUnknownGrades = false;
if (!GRADE_ORDER.includes(filters.grade)) filters.grade = "all";

// A school "offers" a grade when the Ministry's grade range includes it. A missing range is unknown, not
// "no": those schools are counted and can be shown on request instead of silently disappearing.
const gradeState = (r) => {
  if (filters.grade === "all") return "yes";
  const g = gradesOffered(r.g);
  return g == null ? "unknown" : g.includes(filters.grade) ? "yes" : "no";
};

function applyFilters(rows) {
  return rows.filter(
    (r) => (filters.level === "all" || r.l === filters.level) && (filters.lang === "all" || r.lang === filters.lang) && (filters.sys === "all" || r.sys === filters.sys) && (filters.prog === "all" || PROGRAMS[filters.prog](r))
      && (gradeState(r) === "yes" || (showUnknownGrades && gradeState(r) === "unknown")),
  );
}

// Order: best match (the search's own order), A to Z, or nearest first (straight-line, when there is a location).
// There is deliberately no ordering by results: this is not a leaderboard.
function sorted(rows) {
  const by = sortBy || (distances ? "dist" : textSearch ? "rel" : "az");
  if (by === "az") return [...rows].sort((a, b) => a.n.localeCompare(b.n, "en-CA", { sensitivity: "base" }));
  if (by === "dist" && distances) return [...rows].sort((a, b) => (distances.get(a.id) ?? 1e9) - (distances.get(b.id) ?? 1e9));
  return rows;
}

function gradeSelect() {
  const opts = [["all", t("Any grade")], ...GRADE_ORDER.map((g) => [g, t(gradeName(g))])];
  return `<label class="sel"><span>${t("Grade")}</span><select data-grade>${opts.map(([v, name]) => `<option value="${v}"${filters.grade === v ? " selected" : ""}>${esc(name)}</option>`).join("")}</select></label>`;
}

function sortSelect() {
  const by = sortBy || (distances ? "dist" : textSearch ? "rel" : "az");
  const opts = [...(distances ? [["dist", t("Nearest first (straight line)")]] : textSearch ? [["rel", t("Best match")]] : []), ["az", t("Name, A to Z")]];
  if (opts.length < 2) return ""; // a postal area lists A to Z only: no choice to offer
  return `<label class="sel"><span>${t("Order")}</span><select data-sort>${opts.map(([v, name]) => `<option value="${v}"${by === v ? " selected" : ""}>${esc(name)}</option>`).join("")}</select></label>`;
}

function chipGroup(name, label, opts) {
  return `<div class="chips" role="group" aria-label="${label}">${opts
    .map(([v, text]) => `<button class="chip${filters[name] === v ? " on" : ""}" type="button" data-f="${name}" data-v="${v}" aria-pressed="${filters[name] === v}">${text}</button>`)
    .join("")}</div>`;
}

function unknownNote(n) {
  if (n === 1) return showUnknownGrades ? t("1 school has no published grade range and is included.") : t("1 school has no published grade range.");
  return showUnknownGrades ? t("{n} schools have no published grade range and are included.", { n: num(n) }) : t("{n} schools have no published grade range.", { n: num(n) });
}

function unknownBtn(n) {
  return showUnknownGrades ? (n === 1 ? t("Hide it") : t("Hide them")) : n === 1 ? t("Show it") : t("Show them");
}

function render(extraTop = "") {
  const rows = sorted(applyFilters(base));
  const unknown = filters.grade === "all" ? 0 : base.filter((r) => gradeState(r) === "unknown").length;
  const gradeNote = filters.grade === "all" ? "" : `<p class="small muted" style="margin:0">${t("Showing schools whose Ministry grade range includes {grade}. Check with the school: grades can change, and a program may start in a later grade.", { grade: esc(t(gradeName(filters.grade)).toLowerCase()) })}${unknown ? ` ${unknownNote(unknown)} <button class="linkish" type="button" data-unknown>${unknownBtn(unknown)}</button>` : ""}</p>`;
  const sysOpts = [["all", t("All systems")], ...Object.entries(SYSTEMS).filter(([k]) => base.some((r) => r.sys === k)).map(([k, v]) => [k, t(v)])];
  const progOpts = [["all", t("All programs")], ["fi", t("French Immersion")], ["ef", t("Extended French")], ["sh", t("Specialist High Skills Major")]].filter(([k]) => k === "all" || base.some((r) => PROGRAMS[k](r)));
  root.innerHTML = `${extraTop}
    ${base.length ? `<div class="toolbar"><h2 style="margin:0;font-size:1.25rem">${heading}</h2><span class="results-count" data-count>${rows.length === 1 ? t("1 school") : t("{n} schools", { n: num(rows.length) })}</span></div>
    <div style="display:grid;gap:10px;margin-bottom:14px">
      ${chipGroup("level", t("Level"), [["all", t("All levels")], ["E", t("Elementary")], ["S", t("Secondary")]])}
      ${base.some((r) => r.lang === "F") ? chipGroup("lang", t("Language"), [["all", t("English and French")], ["E", t("English")], ["F", t("French")]]) : ""}
      ${sysOpts.length > 2 ? chipGroup("sys", t("System"), sysOpts) : ""}
      ${progOpts.length > 1 ? chipGroup("prog", t("Programs"), progOpts) : ""}
      <div class="sel-row">${gradeSelect()}${sortSelect()}</div>
      ${gradeNote}
    </div>
    <div class="results-layout">
      <div class="map-shell results-map"><div class="map" data-map="results" aria-label="${esc(t("Map of these results"))}"></div><div class="map-fallback" data-map-fallback><div>${t("Map loads with JavaScript.")}</div></div></div>
      <div class="results-list">
        <div class="card" style="padding:4px 16px"><ul class="list">${rows.slice(0, shown).map((r) => schoolRow(r, { distance: distances?.get(r.id) })).join("")}</ul></div>
        ${rows.length > shown ? `<p style="text-align:center;margin-top:16px"><button class="btn" type="button" data-more>${t("Show {n} more", { n: num(Math.min(30, rows.length - shown)) })}</button></p>` : ""}
      </div>
    </div>` : ""}`;
  for (const b of qsa("[data-f]", root)) {
    b.addEventListener("click", () => {
      filters[b.dataset.f] = b.dataset.v;
      shown = 30;
      render(extraTop);
    });
  }
  qs("[data-more]", root)?.addEventListener("click", () => {
    shown += 30;
    render(extraTop);
  });
  qs("[data-grade]", root)?.addEventListener("change", (e) => {
    filters.grade = e.target.value;
    shown = 30;
    // keep the grade in the address so the results can be shared or bookmarked
    const p = new URLSearchParams(location.search);
    if (filters.grade === "all") p.delete("grade");
    else p.set("grade", filters.grade);
    history.replaceState(null, "", `${location.pathname}${p.toString() ? `?${p}` : ""}`);
    render(extraTop);
    qs("[data-grade]", root)?.focus();
  });
  qs("[data-sort]", root)?.addEventListener("change", (e) => {
    sortBy = e.target.value;
    render(extraTop);
    qs("[data-sort]", root)?.focus();
  });
  qs("[data-unknown]", root)?.addEventListener("click", () => {
    showUnknownGrades = !showUnknownGrades;
    render(extraTop);
  });
  document.dispatchEvent(new CustomEvent("osf:compare"));
  mapRows = rows.slice(0, 300);
  const m = qs('[data-map="results"]', root);
  if (m) {
    lazyMap(m, { map: { center: [-79.4, 44], zoom: 6 } }, (map, gl) => {
      mapRef = map;
      addSchoolLayer(map, gl, "schools", pointsFC(mapRows), { radius: 5 });
      if (mapRows.length) map.fitBounds(boundsOf(mapRows.map((r) => [r.x, r.y])), { padding: 36, maxZoom: 14, duration: 0 });
    });
  }
}

function empty(msg) {
  root.innerHTML = `<div class="note"><div><p>${msg}</p></div></div>`;
}

async function addressSearch(text) {
  const wait = 2000 - (Date.now() - lastGeocode);
  if (wait > 0) await new Promise((r) => setTimeout(r, wait));
  lastGeocode = Date.now();
  root.innerHTML = `<p class="loading">${t("Looking up that address…")}</p>`;
  let js;
  try {
    const r = await fetch(`${GEOCODER}?q=${encodeURIComponent(text.includes("ON") || /ontario/i.test(text) ? text : `${text}, Ontario`)}`);
    js = await r.json();
  } catch {
    return empty(t("The address service didn’t answer. Try a postal code or the name of your town instead."));
  }
  const hit = (Array.isArray(js) ? js : []).find((x) => /Ontario/.test(x.title || ""));
  if (!hit) return empty(t("We couldn’t find “{text}” in Ontario. Try adding the town, or search by postal code.", { text: esc(text) }));
  const at = hit.geometry.coordinates;
  const rows = await loadIndex();
  const near = nearest(rows, at, { limit: 60 });
  distances = new Map(near.map((r) => [r.id, r.d]));
  base = near;
  heading = t("Schools nearest to {place}", { place: esc(hit.title) });
  const exact = /POSITION|ADDRESS/i.test(hit.qualifier || "");
  render(`<div class="note" style="margin-bottom:16px"><div><p>${exact ? t("Address matched by the Natural Resources Canada Geolocation Service. Distances are straight lines. The closest school is not always your designated school — check with the board.") : t("Address matched by the Natural Resources Canada Geolocation Service (matched to the street or area, not the exact address). Distances are straight lines. The closest school is not always your designated school — check with the board.")}</p></div></div>`);
}

async function run() {
  if (!q) return;
  let rows, boards;
  try {
    [rows, boards] = await Promise.all([loadIndex(), loadBoards()]);
  } catch {
    return empty(t("Search is unavailable right now. Please try again shortly."));
  }
  if (params.get("address") === "1") return addressSearch(q);
  const res = searchAll(rows, boards, q, { limit: 5000 });
  let top = "";
  if (res.kind !== "text") {
    top += `<a class="card" href="${u(`/fsa/${res.fsa}/`)}" style="display:block;text-decoration:none;color:inherit;margin-bottom:16px"><p class="eyebrow" style="margin:0">${t("Postal area")}</p><h2 style="margin:.2em 0">${res.fsa}</h2><p class="muted" style="margin:0">${t("Map of the area, its schools, 2021 Census context and licensed child care →")}</p></a>`;
    base = res.schools;
    heading = t("Schools in postal area {fsa}", { fsa: res.fsa });
    textSearch = false;
    if (!base.length) top += `<div class="note"><div><p>${t("No school has a postal code starting with {fsa}. The area page lists the closest schools.", { fsa: res.fsa })}</p></div></div>`;
  } else {
    base = res.allSchools || [];
    heading = res.cities.length === 1 && res.cities[0].count === base.length ? t("Schools in {city}", { city: esc(res.cities[0].name) }) : t("Results for “{q}”", { q: esc(q) });
    if (res.boards.length) {
      top += `<div class="chips" style="margin-bottom:16px">${res.boards.map((b) => `<a class="chip" href="${u(`/board/${b.n}/`)}">${t("Board: {name}", { name: esc(b.name) })}</a>`).join("")}</div>`;
    }
    if (!base.length && looksLikeAddress(q)) return addressSearch(q);
    if (!base.length) {
      top += `<div class="note"><div><p>${t("No schools match “{q}”. Try fewer words, a city, the first 3 characters of a postal code, or <a href=\"{url}\">search it as an address</a>.", { q: esc(q), url: u(`/search/?q=${encodeURIComponent(q)}&address=1`) })}</p></div></div>`;
    } else if (looksLikeAddress(q)) {
      top += `<p class="small"><a href="${u(`/search/?q=${encodeURIComponent(q)}&address=1`)}">${t("Search “{q}” as a street address instead →", { q: esc(q) })}</a></p>`;
    }
  }
  render(top);
}

qs("[data-near-me]")?.addEventListener("click", async (e) => {
  const btn = e.currentTarget;
  btn.disabled = true;
  try {
    const { at, rows } = await locate(qs("[data-near-status]"));
    const near = nearest(rows, at, { limit: 60 });
    distances = new Map(near.map((r) => [r.id, r.d]));
    base = near;
    heading = t("Schools nearest to you");
    history.replaceState(null, "", u("/search/"));
    if (input) input.value = "";
    render(`<div class="note" style="margin-bottom:16px"><div><p>${t("Your location stays in this tab only. Distances are straight lines; the closest school is not always your designated school.")}</p></div></div>`);
  } catch {
    /* message shown */
  } finally {
    btn.disabled = false;
  }
});

run();
