// Renders site/static/img/icon.svg at 16, 32 and 48 px and packs them into site/static/favicon.ico
// (PNG images inside an ICO file, which every current browser reads). Browsers, bookmarking tools and
// crawlers still ask for /favicon.ico even when the page names an SVG icon.
// `npm run brand` runs this after it activates a brand; on its own: node scripts/make-favicon.mjs
import { chromium } from "@playwright/test";
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const svg = readFileSync(join(root, "site/static/img/icon.svg"), "utf8");
const sizes = [16, 32, 48];
const browser = await chromium.launch();
const pngs = [];
try {
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  for (const size of sizes) {
    await page.setViewportSize({ width: size, height: size });
    await page.setContent(`<!doctype html><html><body style="margin:0;background:transparent">${svg.replace("<svg ", `<svg width="${size}" height="${size}" style="display:block" `)}</body></html>`);
    pngs.push(await page.screenshot({ omitBackground: true, clip: { x: 0, y: 0, width: size, height: size } }));
  }
} finally {
  await browser.close();
}
// ICO layout: a 6-byte header, one 16-byte entry per image, then the images themselves
const header = Buffer.alloc(6);
header.writeUInt16LE(0, 0); // reserved
header.writeUInt16LE(1, 2); // 1 = icon
header.writeUInt16LE(pngs.length, 4);
let offset = header.length + 16 * pngs.length;
const entries = pngs.map((png, i) => {
  const e = Buffer.alloc(16);
  e.writeUInt8(sizes[i], 0); // width
  e.writeUInt8(sizes[i], 1); // height
  e.writeUInt16LE(1, 4); // colour planes
  e.writeUInt16LE(32, 6); // bits per pixel
  e.writeUInt32LE(png.length, 8);
  e.writeUInt32LE(offset, 12);
  offset += png.length;
  return e;
});
const out = join(root, "site/static/favicon.ico");
writeFileSync(out, Buffer.concat([header, ...entries, ...pngs]));
console.log(`wrote ${out} (${sizes.join(", ")} px)`);
