// Renders the PNG app icons and the social share image from inline HTML/SVG with Playwright.
// Run once after changing the logo: node scripts/make-icons.mjs
import { chromium } from "@playwright/test";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const out = join(root, "site", "static", "img");
const svg = readFileSync(join(out, "icon.svg"), "utf8");
const font = readFileSync(join(root, "site", "static", "fonts", "inter-latin-wght-normal.woff2")).toString("base64");

const browser = await chromium.launch();
const page = await browser.newPage();

async function shot(html, w, h, file) {
  await page.setViewportSize({ width: w, height: h });
  await page.setContent(`<!doctype html><html><head><style>
    @font-face{font-family:Inter;src:url(data:font/woff2;base64,${font}) format("woff2");font-weight:100 900}
    html,body{margin:0;width:${w}px;height:${h}px;overflow:hidden;font-family:Inter,sans-serif}</style></head><body>${html}</body></html>`);
  await page.waitForTimeout(150);
  await page.screenshot({ path: join(out, file), omitBackground: false });
  console.log("wrote", file);
}

for (const s of [180, 192, 512]) {
  await shot(`<div style="width:${s}px;height:${s}px">${svg.replace("<svg ", `<svg width="${s}" height="${s}" `)}</div>`, s, s, `icon-${s}.png`);
}
// maskable: logo inside the 80% safe zone on a full-bleed brand background
await shot(`<div style="width:512px;height:512px;background:#0b5d4f;display:grid;place-items:center">${svg.replace("<svg ", '<svg width="380" height="380" ')}</div>`, 512, 512, "icon-maskable-512.png");

await shot(`<div style="width:1200px;height:630px;box-sizing:border-box;padding:72px 80px;background:
    radial-gradient(60% 70% at 10% 10%, rgba(11,93,79,.22), transparent 70%),
    radial-gradient(50% 60% at 95% 0%, rgba(232,163,61,.22), transparent 70%), #f6f5f1;color:#15171b;display:flex;flex-direction:column;justify-content:space-between">
  <div style="display:flex;align-items:center;gap:20px">${svg.replace("<svg ", '<svg width="76" height="76" ')}<div style="font-size:34px;font-weight:700;letter-spacing:-.02em">Ontario School Finder</div></div>
  <div><div style="font-size:72px;line-height:1.05;font-weight:750;letter-spacing:-.035em;max-width:980px">Find a school. <span style="color:#0b5d4f">See the facts in context.</span></div>
  <div style="margin-top:26px;font-size:30px;color:#454a52">Every Ontario public school · EQAO results over time · a source for every number</div></div>
  <div style="font-size:24px;color:#61666e;font-weight:600">Free · No ads · No tracking · No rankings</div></div>`, 1200, 630, "og.png");

await browser.close();
