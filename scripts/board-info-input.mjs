// Write a researcher's input file for one board: its website, the address lookup we already link, and every
// school with its number, city, level, grades and the Ministry's French program flags (for matching a board's
// own program list to school numbers). Run after the pipeline has built site/data.
//   node scripts/board-info-input.mjs B66052 <folder>
// See docs/board-info-briefs/research.md.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const [board, out = "."] = process.argv.slice(2);
if (!/^B\d{5}$/.test(board || "")) {
  console.error("usage: node scripts/board-info-input.mjs <board number, e.g. B66052> [output folder]");
  process.exit(1);
}
const read = (p) => JSON.parse(fs.readFileSync(path.join(ROOT, p), "utf8"));
const b = read(`site/data/boards/${board.toLowerCase()}.json`);
const loc = read("site/locators.json").boards[board] || null;
const schools = b.schools.map((id) => {
  const d = read(`site/data/schools/${id}.json`);
  const f = (d.programs || {}).fsl || {};
  const sh = (d.programs || {}).shsm;
  return { bsid: d.bsid, name: d.name, city: d.city, level: d.level, grades: d.grades, language: d.language, special: d.special || null,
    ministry_fsl: f.year ? { year: f.year, immersion: !!f.immersion, extended: !!f.extended, core: !!f.core } : null, shsm_sectors: sh ? sh.sectors.length : 0 };
});
const file = path.join(out, `${board}.json`);
fs.mkdirSync(out, { recursive: true });
fs.writeFileSync(file, JSON.stringify({ board, name_on_this_site: b.name, system: b.system, website: b.website, locator: loc, school_count: schools.length, schools }, null, 1));
console.log(`wrote ${file} (${schools.length} schools)`);
