// Check every link in the hand-checked board records (site/board-info/<board>.json).
//   node scripts/check-board-links.mjs            all boards
//   node scripts/check-board-links.mjs B66150     one board
// 200 is fine. 403, 429 and an empty 202 mean the site refuses automated checks (a bot filter): open those in a
// browser instead; never try to get around the filter. A certificate failure on this PC (curl exit 60/35) is listed
// the same way, since Windows root stores go out of date. Anything else is a broken link to fix.
import fs from "node:fs";
import path from "node:path";
import { execFile } from "node:child_process";
import { fileURLToPath } from "node:url";

const DIR = path.join(path.dirname(fileURLToPath(import.meta.url)), "..", "site", "board-info");
const only = process.argv.slice(2);
const files = fs.readdirSync(DIR).filter((f) => /^B\d{5}\.json$/.test(f) && (!only.length || only.includes(f.slice(0, 6))));

function code(url) {
  return new Promise((res) =>
    execFile("curl", ["-sL", "-b", "", "-o", "/dev/null", "-w", "%{http_code}", "-A", "Mozilla/5.0", "--max-time", "40", url],
      { windowsHide: true }, (err, out) => res(err?.code === 60 || err?.code === 35 ? "TLS" : out?.trim() || "ERR")));
}

async function pool(items, n, fn) {
  const out = new Array(items.length);
  let i = 0;
  await Promise.all(Array.from({ length: n }, async () => { while (i < items.length) { const k = i++; out[k] = await fn(items[k]); } }));
  return out;
}

let broken = 0, walled = 0, total = 0;
for (const f of files) {
  const b = JSON.parse(fs.readFileSync(path.join(DIR, f), "utf8"));
  const recs = [...b.records, ...Object.values(b.schools || {}).flatMap((s) => s.records), ...(b.decisions || [])];
  const urls = [...new Set([...recs.flatMap((r) => [r.url, ...(r.related || []).map((x) => x.url)]), ...(b.school_programs || []).map((l) => l.url)])];
  const codes = await pool(urls, 8, code);
  total += urls.length;
  const bad = urls.map((u, i) => [u, codes[i]]).filter(([, c]) => c !== "200");
  const wall = bad.filter(([, c]) => ["403", "429", "202", "TLS"].includes(c));
  const fix = bad.filter(([, c]) => !["403", "429", "202", "TLS"].includes(c));
  walled += wall.length;
  broken += fix.length;
  if (bad.length) {
    console.log(`${f.slice(0, 6)} ${b.short}`);
    for (const [u, c] of fix) console.log(`  BROKEN ${c} ${u}`);
    for (const [u, c] of wall) console.log(`  check in a browser (${c}) ${u}`);
  }
}
console.log(`\n${files.length} boards, ${total} links: ${broken} broken, ${walled} to check in a browser.`);
process.exitCode = broken ? 1 : 0;
