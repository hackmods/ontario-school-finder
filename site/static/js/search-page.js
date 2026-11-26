// /search/ page: full results with filters, "near me", and address search (NRCan Geolocation Service).
import { qs, qsa, esc, loadIndex, loadBoards, SYSTEMS, km, fmtKm } from "./lib.js";
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
if (input && matchMedia("(max-width: 480px)").matches) input.placeholder = "School, city, postal code…";

const GEOCODER = "https://www.geolocator.api.geo.ca/geolocation/en/locate";
let lastGeocode = 0;

const filters = { level: "all", lang: "all", sys: "all", prog: "all" };
// program filters use flags from the search index: fi = French Immersion, ef = Extended French, sh = SHSM sectors
const PROGRAMS = { fi: (r) => r.fi, ef: (r) => r.ef, sh: (r) => r.sh };
let base = [];
let distances = null;
let heading = "";
let shown = 30;
let mapRows = [];
let mapRef = null;

function applyFilters(rows) {
  return rows.filter(
    (r) => (filters.level === "all" || r.l === filters.level) && (filters.lang === "all" || r.lang === filters.lang) && (filters.sys === "all" || r.sys === filters.sys) && (filters.prog === "all" || PROGRAMS[filters.prog](r)),
  );
}

function chipGroup(name, label, opts) {
  return `<div class="chips" role="group" aria-label="${label}">${opts
    .map(([v, t]) => `<button class="chip${filters[name] === v ? " on" : ""}" type="button" data-f="${name}" data-v="${v}" aria-pressed="${filters[name] === v}">${t}</button>`)
    .join("")}</div>`;
}

function render(extraTop = "") {
  const rows = applyFilters(base);
  const sysOpts = [["all", "All systems"], ...Object.entries(SYSTEMS).filter(([k]) => base.some((r) => r.sys === k))];
  const progOpts = [["all", "All programs"], ["fi", "French Immersion"], ["ef", "Extended French"], ["sh", "Specialist High Skills Major"]].filter(([k]) => k === "all" || base.some((r) => PROGRAMS[k](r)));
  root.innerHTML = `${extraTop}
    ${base.length ? `<div class="toolbar"><h2 style="margin:0;font-size:1.25rem">${heading}</h2><span class="results-count" data-count>${rows.length} school${rows.length === 1 ? "" : "s"}</span></div>
    <div style="display:grid;gap:10px;margin-bottom:14px">
      ${chipGroup("level", "Level", [["all", "All levels"], ["E", "Elementary"], ["S", "Secondary"]])}
      ${base.some((r) => r.lang === "F") ? chipGroup("lang", "Language", [["all", "English and French"], ["E", "English"], ["F", "French"]]) : ""}
      ${sysOpts.length > 2 ? chipGroup("sys", "System", sysOpts) : ""}
      ${progOpts.length > 1 ? chipGroup("prog", "Programs", progOpts) : ""}
    </div>
    <div class="results-layout">
      <div class="map-shell results-map"><div class="map" data-map="results" aria-label="Map of these results"></div><div class="map-fallback" data-map-fallback><div>Map loads with JavaScript.</div></div></div>
      <div class="results-list">
        <div class="card" style="padding:4px 16px"><ul class="list">${rows.slice(0, shown).map((r) => schoolRow(r, { distance: distances?.get(r.id) })).join("")}</ul></div>
        ${rows.length > shown ? `<p style="text-align:center;margin-top:16px"><button class="btn" type="button" data-more>Show ${Math.min(30, rows.length - shown)} more</button></p>` : ""}
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
  root.innerHTML = '<p class="loading">Looking up that address…</p>';
  let js;
  try {
    const r = await fetch(`${GEOCODER}?q=${encodeURIComponent(text.includes("ON") || /ontario/i.test(text) ? text : `${text}, Ontario`)}`);
    js = await r.json();
  } catch {
    return empty("The address service didn’t answer. Try a postal code or the name of your town instead.");
  }
  const hit = (Array.isArray(js) ? js : []).find((x) => /Ontario/.test(x.title || ""));
  if (!hit) return empty(`We couldn’t find “${esc(text)}” in Ontario. Try adding the town, or search by postal code.`);
  const at = hit.geometry.coordinates;
  const rows = await loadIndex();
  const near = nearest(rows, at, { limit: 60 });
  distances = new Map(near.map((r) => [r.id, r.d]));
  base = near;
  heading = `Schools nearest to ${esc(hit.title)}`;
  const precise = /POSITION|ADDRESS/i.test(hit.qualifier || "") ? "" : " (matched to the street or area, not the exact address)";
  render(`<div class="note" style="margin-bottom:16px"><div><p>Address matched by the Natural Resources Canada Geolocation Service${precise}. Distances are straight lines. The closest school is not always your designated school — check with the board.</p></div></div>`);
}

async function run() {
  if (!q) return;
  let rows, boards;
  try {
    [rows, boards] = await Promise.all([loadIndex(), loadBoards()]);
  } catch {
    return empty("Search is unavailable right now. Please try again shortly.");
  }
  if (params.get("address") === "1") return addressSearch(q);
  const res = searchAll(rows, boards, q, { limit: 5000 });
  let top = "";
  if (res.kind !== "text") {
    top += `<a class="card" href="/fsa/${res.fsa}/" style="display:block;text-decoration:none;color:inherit;margin-bottom:16px"><p class="eyebrow" style="margin:0">Postal area</p><h2 style="margin:.2em 0">${res.fsa}</h2><p class="muted" style="margin:0">Map of the area, its schools, 2021 Census context and licensed child care →</p></a>`;
    base = res.schools;
    heading = `Schools in postal area ${res.fsa}`;
    if (!base.length) top += `<div class="note"><div><p>No school has a postal code starting with ${res.fsa}. The area page lists the closest schools.</p></div></div>`;
  } else {
    base = res.allSchools || [];
    heading = res.cities.length === 1 && res.cities[0].count === base.length ? `Schools in ${esc(res.cities[0].name)}` : `Results for “${esc(q)}”`;
    if (res.boards.length) {
      top += `<div class="chips" style="margin-bottom:16px">${res.boards.map((b) => `<a class="chip" href="/board/${b.n}/">Board: ${esc(b.name)}</a>`).join("")}</div>`;
    }
    if (!base.length && looksLikeAddress(q)) return addressSearch(q);
    if (!base.length) {
      top += `<div class="note"><div><p>No schools match “${esc(q)}”. Try fewer words, a city, the first 3 characters of a postal code, or <a href="/search/?q=${encodeURIComponent(q)}&address=1">search it as an address</a>.</p></div></div>`;
    } else if (looksLikeAddress(q)) {
      top += `<p class="small"><a href="/search/?q=${encodeURIComponent(q)}&address=1">Search “${esc(q)}” as a street address instead →</a></p>`;
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
    heading = "Schools nearest to you";
    history.replaceState(null, "", "/search/");
    if (input) input.value = "";
    render(`<div class="note" style="margin-bottom:16px"><div><p>Your location stays in this tab only. Distances are straight lines; the closest school is not always your designated school.</p></div></div>`);
  } catch {
    /* message shown */
  } finally {
    btn.disabled = false;
  }
});

run();
