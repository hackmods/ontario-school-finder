// Copies the only third-party front-end files we ship (MapLibre GL, Inter font) into site/static.
// They are committed, so building the site never needs npm. Re-run after bumping versions in package.json.
import { copyFileSync, mkdirSync, existsSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const nm = join(root, "node_modules");
const copies = [
  ["maplibre-gl/dist/maplibre-gl-csp.js", "site/static/vendor/maplibre/maplibre-gl-csp.js"],
  ["maplibre-gl/dist/maplibre-gl-csp-worker.js", "site/static/vendor/maplibre/maplibre-gl-csp-worker.js"],
  ["maplibre-gl/dist/maplibre-gl.css", "site/static/vendor/maplibre/maplibre-gl.css"],
  ["maplibre-gl/LICENSE.txt", "site/static/vendor/maplibre/LICENSE.txt"],
  ["@fontsource-variable/inter/files/inter-latin-wght-normal.woff2", "site/static/fonts/inter-latin-wght-normal.woff2"],
  ["@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2", "site/static/fonts/inter-latin-ext-wght-normal.woff2"],
  ["@fontsource-variable/inter/LICENSE", "site/static/fonts/LICENSE-Inter.txt"],
];
for (const [from, to] of copies) {
  const src = join(nm, from);
  if (!existsSync(src)) throw new Error(`missing ${src} — run npm install first`);
  mkdirSync(join(root, to, ".."), { recursive: true });
  copyFileSync(src, join(root, to));
  console.log("vendored", to);
}
