// /map/ — every school, with optional area layers. Each layer is labelled with exactly what it is.
import { qs, qsa, loadIndex, dataUrl } from "./lib.js";
import { lazyMap, addSchoolLayer, addArea, removeArea, pointsFC, LAYER_COLORS, setSchoolFilter } from "./maps.js";

const container = qs('[data-map="explore"]');
const state = { level: "all", systems: new Set(qsa("[data-system]").map((x) => x.dataset.system)), area: "none" };
const cache = new Map();
let mapRef, glRef;

async function geo(name) {
  if (!cache.has(name)) cache.set(name, fetch(dataUrl(`/data/geo/${name}`)).then((r) => r.json()));
  return cache.get(name);
}

function schoolFilter() {
  const f = ["all", ["in", ["get", "sys"], ["literal", [...state.systems]]]];
  if (state.level !== "all") f.push(["==", ["get", "l"], state.level]);
  return f;
}

async function drawArea() {
  const map = mapRef;
  if (!map) return;
  for (const id of ["area-fsa", "area-board", "area-nearest", "area-official"]) removeArea(map, id);
  const opts = qs("[data-area-options]");
  opts.hidden = !["board", "nearest", "official"].includes(state.area);
  qs("[data-area-level-wrap]").hidden = !["nearest", "official"].includes(state.area);
  // official areas come per level from each board, so the system choice doesn't apply
  for (const el of [qs('label[for="area-system"]'), qs("[data-area-system]")]) if (el) el.hidden = state.area === "official";
  const sys = qs("[data-area-system]").value;
  const lvl = qs("[data-area-level]").value;
  try {
    if (state.area === "fsa") addArea(map, "area-fsa", await geo("fsa.geojson"), { color: LAYER_COLORS.fsa, fill: 0.05, width: 1.2 });
    if (state.area === "board") {
      const fc = await geo("boards.geojson");
      addArea(map, "area-board", { type: "FeatureCollection", features: fc.features.filter((f) => f.properties.system === sys) }, { color: LAYER_COLORS.board, fill: 0.07, width: 1.6 });
    }
    if (state.area === "nearest") addArea(map, "area-nearest", await geo(`nearest-${sys}-${lvl}.geojson`), { color: LAYER_COLORS.nearest, dashed: true, fill: 0.06, width: 1 });
    if (state.area === "official") addArea(map, "area-official", await geo(`official-${lvl}.geojson`), { color: LAYER_COLORS.official, fill: 0.08, width: 1.4 });
  } catch {
    /* layer failed to load; schools still shown */
  }
}

if (container) {
  lazyMap(container, { cooperative: false, locate: true, map: { center: [-79.6, 44.2], zoom: 6.2, minZoom: 4 } }, async (map, gl, info) => {
    mapRef = map;
    glRef = gl;
    const rows = await loadIndex();
    for (const k of state.systems) {
      const c = qs(`[data-system-count="${k}"]`);
      if (c) c.textContent = rows.filter((r) => r.sys === k).length.toLocaleString("en-CA");
    }
    addSchoolLayer(map, gl, "schools", pointsFC(rows), { radius: 4.5, labels: 12 });
    map.setPaintProperty("schools", "circle-radius", ["interpolate", ["linear"], ["zoom"], 5, 2.2, 9, 4.5, 13, 7]);
    setSchoolFilter(map, "schools", schoolFilter());
    if (info?.restyle || state.area !== "none") drawArea();
  });
}

for (const b of qsa("[data-level]")) {
  b.addEventListener("click", () => {
    state.level = b.dataset.level;
    qsa("[data-level]").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", String(x === b)); });
    if (mapRef) setSchoolFilter(mapRef, "schools", schoolFilter());
  });
}
for (const c of qsa("[data-system]")) {
  c.addEventListener("change", () => {
    if (c.checked) state.systems.add(c.dataset.system);
    else state.systems.delete(c.dataset.system);
    if (mapRef) setSchoolFilter(mapRef, "schools", schoolFilter());
  });
}
for (const r of qsa('input[name="area"]')) {
  r.addEventListener("change", () => {
    state.area = r.value;
    drawArea();
  });
}
qs("[data-area-system]")?.addEventListener("change", drawArea);
qs("[data-area-level]")?.addEventListener("change", drawArea);
