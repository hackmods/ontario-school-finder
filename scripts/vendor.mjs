// Copies the only third-party front-end files we ship (MapLibre GL, Inter font) into site/static.
// They are committed, so building the site never needs npm. Re-run after bumping versions in package.json.
//
// MapLibre goes into a folder named after its version (site/static/vendor/maplibre/<version>/). Since v6
// it is an ES module that loads its shared chunk and its worker relative to itself, so a version-named
// folder is what keeps a browser from ever mixing two versions' pieces. After an upgrade, point
// LIB in site/static/js/maps.js at the new folder: site/generate.py stops the build if they differ.
import { copyFileSync, mkdirSync, existsSync, readFileSync, writeFileSync, readdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const nm = join(root, "node_modules");
const mlVersion = JSON.parse(readFileSync(join(nm, "maplibre-gl/package.json"), "utf8")).version;
const mlDir = `site/static/vendor/maplibre/${mlVersion}`;

// clear out other MapLibre versions (and the pre-v6 flat files) so only one ships
const mlRoot = join(root, "site/static/vendor/maplibre");
if (existsSync(mlRoot)) for (const name of readdirSync(mlRoot)) if (name !== mlVersion) rmSync(join(mlRoot, name), { recursive: true, force: true });

const copies = [
  ["maplibre-gl/dist/maplibre-gl.mjs", `${mlDir}/maplibre-gl.mjs`],
  ["maplibre-gl/dist/maplibre-gl-shared.mjs", `${mlDir}/maplibre-gl-shared.mjs`],
  ["maplibre-gl/dist/maplibre-gl-worker.mjs", `${mlDir}/maplibre-gl-worker.mjs`],
  ["maplibre-gl/dist/maplibre-gl.css", `${mlDir}/maplibre-gl.css`],
  ["maplibre-gl/LICENSE.txt", `${mlDir}/LICENSE.txt`],
  ["@fontsource-variable/inter/files/inter-latin-wght-normal.woff2", "site/static/fonts/inter-latin-wght-normal.woff2"],
  ["@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2", "site/static/fonts/inter-latin-ext-wght-normal.woff2"],
  ["@fontsource-variable/inter/LICENSE", "site/static/fonts/LICENSE-Inter.txt"],
];
for (const [from, to] of copies) {
  const src = join(nm, from);
  if (!existsSync(src)) throw new Error(`missing ${src} — run npm install first`);
  mkdirSync(join(root, to, ".."), { recursive: true });
  if (to.endsWith(".mjs")) {
    // source maps aren't shipped, so drop the pointer to them (it only makes DevTools ask for a missing file)
    writeFileSync(join(root, to), readFileSync(src, "utf8").replace(/\n\/\/# sourceMappingURL=\S+\s*$/, "\n"));
  } else copyFileSync(src, join(root, to));
  console.log("vendored", to);
}
