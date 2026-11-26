// Render complete web assets from the preserved SVG masters, then activate one set.
// npm run brand -- --brand field-guide     npm run brand -- --all
import { chromium } from "@playwright/test";
import { copyFileSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const configPath = join(root, "branding", "brand.json");
const config = JSON.parse(readFileSync(configPath, "utf8"));
const args = process.argv.slice(2);
let selected = config.active;
let all = false;
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--all") all = true;
  else if (args[i] === "--brand" && args[i + 1]) selected = args[++i];
  else throw new Error("Usage: npm run brand -- [--brand <name>] [--all]");
}
if (!Object.hasOwn(config.variants, selected)) {
  throw new Error(`Unknown brand ${selected}. Choose ${Object.keys(config.variants).join(", ")}.`);
}
const files = ["brand-logo.svg", "brand-logo-reversed.svg", "icon.svg", "icon-180.png",
  "icon-192.png", "icon-512.png", "icon-maskable-512.png", "og.png"];
const font = readFileSync(join(root, "site/static/fonts/inter-latin-wght-normal.woff2")).toString("base64");
const browser = await chromium.launch();
try {
  const page = await browser.newPage({ deviceScaleFactor: 1 });
  async function shot(body, width, height, file) {
    await page.setViewportSize({ width, height });
    await page.setContent(`<!doctype html><html><head><style>
      @font-face{font-family:Inter;src:url(data:font/woff2;base64,${font}) format("woff2");font-weight:100 900}
      *{box-sizing:border-box}html,body{margin:0;width:${width}px;height:${height}px;overflow:hidden;font-family:Inter,sans-serif}
      svg{display:block}</style></head><body>${body}</body></html>`);
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: file });
  }
  const inner = svg => svg.replace(/^<svg\b[^>]*>/, "").replace(/<\/svg>\s*$/, "").replace(/<title>[^<]*<\/title>/, "");
  for (const id of all ? Object.keys(config.variants) : [selected]) {
    const brand = config.variants[id];
    const dir = join(root, "branding/trillium-retro", id);
    const out = join(dir, "web");
    mkdirSync(out, { recursive: true });
    const lockup = name => readFileSync(join(dir, name), "utf8")
      .replace('viewBox="0 0 590 205"', 'viewBox="10 7 570 171"')
      .replace("<svg ", `<svg data-brand="${id}" `);
    const logo = lockup("logo.svg");
    writeFileSync(join(out, "brand-logo.svg"), logo);
    writeFileSync(join(out, "brand-logo-reversed.svg"), lockup("logo-reversed.svg"));
    const mark = inner(readFileSync(join(dir, "mark.svg"), "utf8"));
    // At favicon sizes, Field Guide retains two heavier contours; large icons retain all three.
    const faviconMark = id === "field-guide" ? mark.replaceAll('stroke-width="8"', 'stroke-width="12"')
      .replace(/<path stroke="#[a-fA-F0-9]+" d="M100 49[^"]*"\/>/g, "") : mark;
    const icon = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" data-brand="${id}"><title>Ontario School Finder</title><rect width="64" height="64" rx="13" fill="${brand.background}"/><g transform="translate(4 7) scale(.28)">${faviconMark}</g></svg>`;
    writeFileSync(join(out, "icon.svg"), icon);
    for (const size of [180, 192, 512]) {
      await shot(`<div style="width:100%;height:100%;background:${brand.background};display:grid;place-items:center"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 190" width="${size * .84}" height="${size * .80}">${mark}</svg></div>`, size, size, join(out, `icon-${size}.png`));
    }
    // Full square background and mark within the central 80%-diameter maskable safe circle.
    await shot(`<div style="width:512px;height:512px;background:${brand.background};display:grid;place-items:center"><svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 190" width="330" height="314">${mark}</svg></div>`, 512, 512, join(out, "icon-maskable-512.png"));
    await shot(`<div style="width:1200px;height:630px;padding:48px 72px;background:${brand.background};color:${brand.ink};display:flex;flex-direction:column;justify-content:space-between">
      <div>${logo.replace("<svg ", '<svg width="480" height="144" ')}</div>
      <div><div style="font-size:64px;line-height:1.09;font-weight:750;letter-spacing:-.035em">Find a school.<br>See the facts in context.</div>
      <div style="margin-top:22px;font-size:27px;line-height:1.4">Ontario public schools · Results over time · Original sources</div></div>
      <div style="font-size:23px;font-weight:600">Free · No ads · No tracking · No rankings</div></div>`, 1200, 630, join(out, "og.png"));
    console.log(`Rendered ${brand.name}: ${files.length} web assets`);
  }
  for (const file of files) copyFileSync(join(root, "branding/trillium-retro", selected, "web", file), join(root, "site/static/img", file));
  config.active = selected;
  writeFileSync(configPath, JSON.stringify(config, null, 2) + "\n");
  console.log(`Active brand: ${selected}. Rebuild site/generate.py before publishing.`);
} finally {
  await browser.close();
}
