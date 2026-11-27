// Which translatable strings have no French entry yet?
//   node scripts/i18n-coverage.mjs [file ...]     (default: every template, script and Python file)
// Finds _("...") / _h("...") in templates and Python, and t("...") in scripts, and checks each against the merged
// catalogue in site/i18n/fr/*.json. Strings built at run time (labels from data files) are checked at build time
// instead: site/i18n/missing-fr.txt lists what a build fell back to English for.
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.join(path.dirname(fileURLToPath(import.meta.url)), "..");
const cat = {};
for (const f of fs.readdirSync(path.join(ROOT, "site/i18n/fr")).filter((f) => f.endsWith(".json"))) {
  Object.assign(cat, JSON.parse(fs.readFileSync(path.join(ROOT, "site/i18n/fr", f), "utf8")));
}
let files = process.argv.slice(2);
if (!files.length) {
  files = [
    ...fs.readdirSync(path.join(ROOT, "site/templates")).map((f) => `site/templates/${f}`),
    ...fs.readdirSync(path.join(ROOT, "site/static/js")).filter((f) => f.endsWith(".js") && f !== "i18n-fr.js").map((f) => `site/static/js/${f}`),
    "site/generate.py", "site/family.py",
  ];
}
// a string literal in double quotes, single quotes or backticks (no ${} inside a translatable backtick string)
const LIT = String.raw`(?:"((?:[^"\\]|\\.)*)"|'((?:[^'\\]|\\.)*)'|\`((?:[^\`\\$]|\\.)*)\`)`;
const RE = { js: new RegExp(String.raw`\bt\(\s*` + LIT, "g"), other: new RegExp(String.raw`\b_h?\(\s*` + LIT, "g") };
const unescape = (s) => s.replace(/\\(["'`\\])/g, "$1").replace(/\\n/g, "\n");
let missing = 0, total = 0;
for (const f of files) {
  const src = fs.readFileSync(path.join(ROOT, f), "utf8");
  const re = f.endsWith(".js") ? RE.js : RE.other;
  const found = new Set();
  for (const m of src.matchAll(re)) found.add(unescape(m[1] ?? m[2] ?? m[3]));
  const miss = [...found].filter((s) => !(s in cat));
  total += found.size;
  missing += miss.length;
  if (miss.length) console.log(`${f}: ${miss.length} of ${found.size} missing\n  ` + miss.slice(0, 40).map((s) => JSON.stringify(s)).join("\n  "));
}
console.log(`\n${total} strings, ${missing} without French.`);
process.exitCode = missing ? 1 : 0;
