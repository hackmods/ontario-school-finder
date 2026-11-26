// Board page: map of the board's schools with its approximate area, and the school list filter.
import { lazyMap, readMapData, addSchoolLayer, addArea, pointsFC, boundsOf, LAYER_COLORS } from "./maps.js";
import { qsa, qs, norm, dataUrl } from "./lib.js";

const data = readMapData();
const container = document.querySelector('[data-map="board"]');
if (data && container) {
  lazyMap(container, { map: { center: [-79.4, 44], zoom: 6 } }, async (map, gl) => {
    try {
      const fc = await fetch(dataUrl("/data/geo/boards.geojson")).then((r) => r.json());
      const mine = { type: "FeatureCollection", features: fc.features.filter((f) => f.properties.board === data.board) };
      if (mine.features.length) addArea(map, "board-area", mine, { color: LAYER_COLORS.board, fill: 0.08 });
    } catch { /* area is optional */ }
    addSchoolLayer(map, gl, "schools", pointsFC(data.schools), { radius: 5 });
    if (data.schools.length) map.fitBounds(boundsOf(data.schools.map((s) => [s.x, s.y])), { padding: 40, maxZoom: 13, duration: 0 });
  });
}

// filter list
const list = qs("[data-filter-list]");
if (list) {
  let level = "all";
  const text = qs("[data-filter-text]");
  const items = qsa("li[data-level]", list);
  const groups = qsa("[data-az]", list);
  const empty = qs("[data-filter-empty]");
  const apply = () => {
    const q = norm(text?.value || "");
    for (const li of items) {
      const okL = level === "all" || li.dataset.level === level;
      const okT = !q || norm(li.dataset.text).includes(q);
      li.hidden = !(okL && okT);
    }
    // hide empty letter groups and their jump links
    let shown = 0;
    for (const g of groups) {
      const any = !!g.querySelector("li:not([hidden])");
      g.hidden = !any;
      shown += any ? 1 : 0;
      const link = qs(`[data-az-nav] a[href="#az-${g.dataset.az}"]`);
      if (link) link.hidden = !any;
    }
    if (empty) empty.hidden = shown > 0;
  };
  for (const b of qsa("[data-filter]")) {
    b.addEventListener("click", () => {
      level = b.dataset.filter;
      qsa("[data-filter]").forEach((x) => { x.classList.toggle("on", x === b); x.setAttribute("aria-pressed", String(x === b)); });
      apply();
    });
  }
  text?.addEventListener("input", apply);
}
