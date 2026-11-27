// Check every school website link from the Ministry's list and sort the results, so broken or hijacked links can
// be reviewed by a person before the site stops showing them.
//   node scripts/check-school-links.mjs <output.json>       (after the pipeline has built site/data)
// Categories: ok, dead (no such domain, 404/410), parked (a domain-for-sale page), elsewhere (lands on another
// site whose title doesn't look like a school or board: review by hand), unchecked (a bot filter, a time-out or a
// certificate this PC can't verify: never treated as broken). Nothing here changes the site; see
// site/school-links.json for the reviewed list the site uses.
import fs from "node:fs";
import path from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = process.argv[2];
if (!out) { console.error("usage: node scripts/check-school-links.mjs <output.json>"); process.exit(1); }
const idx = JSON.parse(fs.readFileSync(path.join(ROOT, "site/data/schools-index.json"), "utf8"));
const byUrl = new Map();
for (const r of idx) {
  const s = JSON.parse(fs.readFileSync(path.join(ROOT, "site/data/schools", `${r.id}.json`), "utf8"));
  if (!s.website) continue;
  if (!byUrl.has(s.website)) byUrl.set(s.website, { url: s.website, schools: [], board_website: s.board_website, names: [] });
  byUrl.get(s.website).schools.push(s.bsid);
  byUrl.get(s.website).names.push(s.name);
}

const PARKED = /domain (is )?for sale|buy this domain|this domain (has been|is) registered|registered at internic|parked (free|domain)|domain parking|hugedomains|sedo\.com|dan\.com|afternic|godaddy\.com\/domainsearch|this domain may be for sale|is for sale!/i;
const SCHOOLISH = /school|[eé]cole|coll[eè]g|academ|secondary|elementary|[eé]l[eé]mentaire|public|catholi|district|board|conseil|\bcs[a-z]*\b|education|learning|centre|center|institut|\bss\b|\bps\b|\bces\b|\bchs\b/i;

function fetchOne(url) {
  return new Promise((resolve) => {
    const args = ["-sL", "-b", "", "-A", "Mozilla/5.0", "--max-time", "25", "--max-redirs", "10", "-w", "\n@@CURL@@%{http_code} %{url_effective}", url];
    const p = spawn("curl", args, { windowsHide: true });
    let buf = Buffer.alloc(0);
    p.stdout.on("data", (d) => { if (buf.length < 400000) buf = Buffer.concat([buf, d]); });
    p.on("close", (code) => {
      const text = buf.toString("utf8");
      const i = text.lastIndexOf("\n@@CURL@@");
      const meta = i >= 0 ? text.slice(i + 9).trim() : "";
      const body = i >= 0 ? text.slice(0, i) : text;
      const [status, final] = meta.split(" ");
      const title = ((body.match(/<title[^>]*>([\s\S]*?)<\/title>/i) || [])[1] || "").replace(/\s+/g, " ").trim().slice(0, 160);
      resolve({ exit: code, status: status || "000", final: final || url, title, parked: PARKED.test(body.slice(0, 60000)) });
    });
  });
}

const host = (u) => { try { return new URL(u).host.replace(/^www\./, "").toLowerCase(); } catch { return ""; } };
const root = (h) => h.split(".").slice(-3).join(".").replace(/^[^.]+\.(on\.ca|qc\.ca|edu\.on\.ca)$/, (m) => m); // close enough for "same organisation"
const sameOrg = (a, b) => { const x = host(a), y = host(b); if (!x || !y) return false; const ax = x.split("."), ay = y.split("."); return ax.slice(-2).join(".") === ay.slice(-2).join(".") || ax.slice(-3).join(".") === ay.slice(-3).join("."); };

function classify(e, r) {
  if (r.exit === 6) return "dead";           // no such domain
  if ([7, 28].includes(r.exit)) return "unchecked"; // couldn't connect / timed out: may be temporary
  if ([35, 60].includes(r.exit)) return "unchecked"; // TLS this PC can't verify
  if (["404", "410"].includes(r.status)) return "dead";
  if (r.status !== "200") return "unchecked";
  if (r.parked) return "parked";
  if (!sameOrg(e.url, r.final) && !sameOrg(e.board_website || "", r.final) && !SCHOOLISH.test(r.title)) return "elsewhere";
  return "ok";
}

const list = [...byUrl.values()];
let done = 0;
const results = new Array(list.length);
let next = 0;
await Promise.all(Array.from({ length: 12 }, async () => {
  while (next < list.length) {
    const k = next++;
    const e = list[k];
    const r = await fetchOne(e.url);
    results[k] = { ...e, ...r, category: classify(e, r) };
    if (++done % 250 === 0) console.error(`${done}/${list.length}`);
  }
}));
const counts = results.reduce((a, r) => ((a[r.category] = (a[r.category] || 0) + 1), a), {});
fs.writeFileSync(out, JSON.stringify({ checked: new Date().toLocaleDateString("en-CA"), counts, results }, null, 1));
console.log(JSON.stringify(counts));
