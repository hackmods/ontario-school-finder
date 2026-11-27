// MapLibre GL loader and shared map helpers. The library is self-hosted; only tiles come from OpenFreeMap.
import { esc, SYSTEMS, levelName, gradesText, badgesHTML, t, u } from "./lib.js";

// MapLibre 6 is an ES module; it loads its shared chunk and worker from the same version-named folder.
// Keep this path in step with site/static/vendor/maplibre/<version>/ (generate.py checks).
const LIB = "/static/vendor/maplibre/6.4.1/maplibre-gl.mjs";
const STYLE_LIGHT = "https://tiles.openfreemap.org/styles/positron";
const STYLE_DARK = "https://tiles.openfreemap.org/styles/dark";
export const ATTRIBUTION =
  `<a href="https://openfreemap.org" target="_blank" rel="noopener">OpenFreeMap</a> © <a href="https://www.openmaptiles.org/" target="_blank" rel="noopener">OpenMapTiles</a> ${t("Data from")} <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>`;

export const SYSTEM_COLORS = {
  light: { "english-public": "#0b6e8a", "english-catholic": "#7a3d9b", "french-public": "#b04a17", "french-catholic": "#2f6f2a", other: "#5b6068" },
  dark: { "english-public": "#4fb6d6", "english-catholic": "#c193e0", "french-public": "#f08a5a", "french-catholic": "#7fc477", other: "#a1a7af" },
};
export const LAYER_COLORS = { fsa: "#1f6feb", board: "#b0640a", nearest: "#6b4fbb", official: "#c2410c", school: "#0b5d4f", schoolDark: "#56c9ad" };

let libPromise;
export function loadMapLib() {
  libPromise ||= import(LIB).catch((e) => {
    libPromise = null; // let a later map on the page try again
    throw new Error(`map library failed to load: ${e.message}`);
  });
  return libPromise;
}

export const isDark = () => {
  const t = document.documentElement.dataset.theme;
  return t ? t === "dark" : matchMedia("(prefers-color-scheme: dark)").matches;
};

export function systemColorExpr(prop = "sys") {
  const c = SYSTEM_COLORS[isDark() ? "dark" : "light"];
  return ["match", ["get", prop], ...Object.entries(c).flat(), c.other];
}

function webglOK() {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

/**
 * Create a map when the container scrolls near the viewport.
 * onReady(map, maplibregl) adds the page's layers.
 */
export function lazyMap(container, opts, onReady) {
  if (!container) return;
  const fallback = container.parentElement.querySelector("[data-map-fallback]");
  const start = async () => {
    if (!webglOK()) {
      if (fallback) fallback.innerHTML = `<div>${t("This browser can’t draw the interactive map (WebGL is off). Everything else on the page still works.")}</div>`;
      return;
    }
    let gl;
    try {
      gl = await loadMapLib();
    } catch {
      if (fallback) fallback.innerHTML = `<div>${t("The map couldn’t load. Check your connection and refresh.")}</div>`;
      return;
    }
    const map = new gl.Map({
      container,
      style: isDark() ? STYLE_DARK : STYLE_LIGHT,
      attributionControl: false,
      cooperativeGestures: opts.cooperative ?? true,
      dragRotate: false,
      pitchWithRotate: false,
      maxPitch: 0,
      ...opts.map,
    });
    container._map = map; // lets tests ask the map what it drew (labels live on the canvas, not in the DOM)
    map.touchZoomRotate?.disableRotation();
    map.addControl(new gl.AttributionControl({ compact: true }), "bottom-right");
    map.addControl(new gl.NavigationControl({ showCompass: false }), "top-right");
    if (opts.locate) map.addControl(new gl.GeolocateControl({ trackUserLocation: false, showAccuracyCircle: false }), "top-right");
    map.once("load", () => {
      fallback?.setAttribute("hidden", "");
      onReady(map, gl);
    });
    map.on("error", (e) => {
      if (e?.error?.status === 403 || e?.error?.status === 429) console.warn("tile error", e.error.status);
    });
    document.addEventListener("osf:theme", () => {
      map.setStyle(isDark() ? STYLE_DARK : STYLE_LIGHT);
      map.once("styledata", () => onReady(map, gl, { restyle: true }));
    });
  };
  if ("IntersectionObserver" in window) {
    const io = new IntersectionObserver(
      (ents) => {
        if (ents.some((e) => e.isIntersecting)) {
          io.disconnect();
          start();
        }
      },
      { rootMargin: "300px" },
    );
    io.observe(container);
  } else start();
}

export function pointsFC(rows) {
  return {
    type: "FeatureCollection",
    features: rows.map((r) => ({
      type: "Feature",
      geometry: { type: "Point", coordinates: [r.x, r.y] },
      properties: { id: r.id, n: r.n, sys: r.sys, l: r.l || "", g: r.g || "", c: r.c || "", bn: r.bn || "", in: r.in ?? true, main: !!r.main,
        lang: r.lang || "", fi: r.fi || 0, fb: r.fb || 0, ef: r.ef || 0, sh: r.sh || 0 },
    })),
  };
}

export function popupHTML(p) {
  const sub = [levelName(p.l), gradesText(p.g), t(SYSTEMS[p.sys] || "")].filter(Boolean).join(" · ");
  return `<div class="pop"><div class="t">${esc(p.n)}</div><div class="s">${esc(sub)}${p.c ? ` · ${esc(p.c)}` : ""}</div>${badgesHTML(p)}<a href="${u(`/school/${encodeURIComponent(p.id)}/`)}">${t("View school →")}</a></div>`;
}

/**
 * Circle layer for schools, coloured by system, with names beside the dots and a popup.
 * labels: the zoom from which names show (MapLibre leaves out any that would overlap, so crowded
 * schools get theirs as you zoom in); false for none. Desktop pointers also get the name on hover.
 */
export function addSchoolLayer(map, gl, id, fc, { radius = 6, cluster = false, filter, labels = 9 } = {}) {
  if (map.getSource(id)) map.getSource(id).setData(fc);
  else map.addSource(id, { type: "geojson", data: fc, cluster, clusterRadius: 38, clusterMaxZoom: 10 });
  const color = systemColorExpr();
  if (cluster && !map.getLayer(`${id}-clusters`)) {
    map.addLayer({
      id: `${id}-clusters`, type: "circle", source: id, filter: ["has", "point_count"],
      paint: {
        "circle-color": isDark() ? "#1b4239" : "#e2f0ec", "circle-stroke-color": isDark() ? "#56c9ad" : "#0b5d4f", "circle-stroke-width": 1.5,
        "circle-radius": ["step", ["get", "point_count"], 14, 25, 18, 100, 24, 500, 30],
      },
    });
    map.addLayer({
      id: `${id}-count`, type: "symbol", source: id, filter: ["has", "point_count"],
      layout: { "text-field": ["get", "point_count_abbreviated"], "text-size": 12, "text-font": ["Noto Sans Bold"] },
      paint: { "text-color": isDark() ? "#eef0f2" : "#0a4c41" },
    });
    if (!bound(map, `${id}-clusters`)) map.on("click", `${id}-clusters`, async (e) => {
      const f = map.queryRenderedFeatures(e.point, { layers: [`${id}-clusters`] })[0];
      const z = await map.getSource(id).getClusterExpansionZoom(f.properties.cluster_id);
      map.easeTo({ center: f.geometry.coordinates, zoom: z });
    });
  }
  if (!map.getLayer(id)) {
    map.addLayer({
      id, type: "circle", source: id,
      filter: filter || (cluster ? ["!", ["has", "point_count"]] : ["all"]),
      paint: {
        "circle-color": color,
        "circle-radius": ["case", ["boolean", ["get", "main"], false], radius + 3, radius],
        "circle-stroke-color": isDark() ? "#16191c" : "#ffffff",
        "circle-stroke-width": ["case", ["boolean", ["get", "main"], false], 3, 1.5],
        "circle-opacity": ["case", ["boolean", ["get", "in"], true], 1, 0.55],
      },
    });
  }
  if (labels !== false && !map.getLayer(`${id}-labels`)) {
    map.addLayer({
      id: `${id}-labels`, type: "symbol", source: id, minzoom: labels,
      filter: filter || (cluster ? ["!", ["has", "point_count"]] : ["all"]),
      layout: {
        "text-field": ["get", "n"],
        "text-font": ["Noto Sans Regular"],
        "text-size": ["interpolate", ["linear"], ["zoom"], 9, 11, 14, 13],
        "text-max-width": 11,
        "text-variable-anchor": ["left", "right", "top", "bottom"],
        "text-radial-offset": 0.75,
        "text-justify": "auto",
        "symbol-sort-key": ["case", ["boolean", ["get", "main"], false], 0, 1], // the page's own school first
      },
      paint: {
        "text-color": isDark() ? "#e6e8eb" : "#23272d",
        "text-halo-color": isDark() ? "#16191c" : "#ffffff",
        "text-halo-width": 1.5,
        "text-opacity": ["case", ["boolean", ["get", "in"], true], 1, 0.7],
      },
    });
  }
  if (bound(map, id)) return;
  const popup = new gl.Popup({ closeButton: true, maxWidth: "280px", offset: 10 });
  const hover = new gl.Popup({ closeButton: false, closeOnClick: false, offset: 10, className: "pop-hover" });
  map.on("click", id, (e) => {
    const f = e.features[0];
    hover.remove();
    popup.setLngLat(f.geometry.coordinates).setHTML(popupHTML(f.properties)).addTo(map);
  });
  map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", id, () => {
    map.getCanvas().style.cursor = "";
    hover.remove();
  });
  if (matchMedia("(hover: hover)").matches) {
    map.on("mousemove", id, (e) => {
      const f = e.features[0];
      if (popup.isOpen()) return;
      hover.setLngLat(f.geometry.coordinates).setText(f.properties.n).addTo(map);
    });
  }
}

/** Show or hide the schools and their names together (the Map page's level and system filters). */
export function setSchoolFilter(map, id, filter) {
  map.setFilter(id, filter);
  if (map.getLayer(`${id}-labels`)) map.setFilter(`${id}-labels`, filter);
}

/** True if handlers for this layer id were already attached to this map (then marks it). */
function bound(map, id) {
  map._osfBound ||= new Set();
  if (map._osfBound.has(id)) return true;
  map._osfBound.add(id);
  return false;
}

export function addArea(map, id, data, { color, dashed = false, fill = 0.08, width = 2 } = {}) {
  if (map.getSource(id)) {
    map.getSource(id).setData(data);
    return;
  }
  map.addSource(id, { type: "geojson", data });
  const before = map.getLayer("schools") ? "schools" : undefined;
  map.addLayer({ id: `${id}-fill`, type: "fill", source: id, paint: { "fill-color": color, "fill-opacity": fill } }, before);
  map.addLayer(
    { id: `${id}-line`, type: "line", source: id, paint: { "line-color": color, "line-width": width, ...(dashed ? { "line-dasharray": [2, 1.5] } : {}) } },
    before,
  );
}

export function removeArea(map, id) {
  for (const l of [`${id}-fill`, `${id}-line`]) if (map.getLayer(l)) map.removeLayer(l);
  if (map.getSource(id)) map.removeSource(id);
}

export function boundsOf(coords) {
  let minx = 180, miny = 90, maxx = -180, maxy = -90;
  const walk = (c) => {
    if (typeof c[0] === "number") {
      minx = Math.min(minx, c[0]); maxx = Math.max(maxx, c[0]);
      miny = Math.min(miny, c[1]); maxy = Math.max(maxy, c[1]);
    } else c.forEach(walk);
  };
  walk(coords);
  return [[minx, miny], [maxx, maxy]];
}

export function readMapData() {
  const el = document.getElementById("map-data");
  try {
    return el ? JSON.parse(el.textContent) : null;
  } catch {
    return null;
  }
}
