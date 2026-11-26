// FSA page: the postal area outline and the schools in and near it.
import { lazyMap, readMapData, addSchoolLayer, addArea, pointsFC, boundsOf, LAYER_COLORS } from "./maps.js";

const data = readMapData();
const container = document.querySelector('[data-map="fsa"]');
if (data && container) {
  lazyMap(container, { map: { center: [-79.4, 44], zoom: 8 } }, (map, gl) => {
    if (data.boundary) addArea(map, "fsa", { type: "Feature", geometry: data.boundary, properties: {} }, { color: LAYER_COLORS.fsa, fill: 0.07, width: 2.5 });
    addSchoolLayer(map, gl, "schools", pointsFC(data.schools), { radius: 6 });
    const coords = data.boundary ? [data.boundary.coordinates] : [];
    if (data.schools.length) coords.push(data.schools.map((s) => [s.x, s.y]));
    if (coords.length) map.fitBounds(boundsOf(coords), { padding: 36, maxZoom: 14, duration: 0 });
  });
}
