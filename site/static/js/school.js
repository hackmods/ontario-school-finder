// School page: small map with the school, its nearest neighbours and its nearest-school area.
import { lazyMap, readMapData, addSchoolLayer, addArea, pointsFC, boundsOf, LAYER_COLORS, isDark } from "./maps.js";

const data = readMapData();
// every [x, y] pair in a Polygon or MultiPolygon, at any depth
const points = (c) => (typeof c[0] === "number" ? [c] : c.flatMap(points));
const container = document.querySelector('[data-map="school"]');
if (data && container) {
  lazyMap(container, { map: { center: data.center, zoom: 13 } }, (map, gl) => {
    if (data.area) {
      const official = data.area_kind === "official"; // the board's own attendance area, else the nearest-school estimate
      addArea(map, official ? "official" : "nearest", { type: "Feature", geometry: data.area, properties: {} },
        official ? { color: LAYER_COLORS.official, fill: 0.12, width: 2.2 } : { color: LAYER_COLORS.nearest, dashed: true, fill: 0.1, width: 1.5 });
    }
    const rows = [{ ...data.school, main: true, l: "" }, ...data.nearby.map((n) => ({ ...n, in: false }))];
    addSchoolLayer(map, gl, "schools", pointsFC(rows), { radius: 6 });
    const coords = rows.map((r) => [r.x, r.y]);
    if (data.area) coords.push(...points(data.area.coordinates));
    const b = boundsOf(coords);
    map.fitBounds(b, { padding: 40, maxZoom: 15, duration: 0 });
    if (!map.getSource("me")) {
      new gl.Marker({ color: isDark() ? "#56c9ad" : "#0b5d4f" }).setLngLat(data.center).addTo(map);
    }
  });
}
