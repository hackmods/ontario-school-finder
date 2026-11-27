// Small shared helpers. No dependencies.

// ---- language: pages under /fr/ are French (machine translation, unreviewed; English is the reference).
// t(text, vars) translates with the same catalogue the server pages use (site/i18n/fr/js-*.json
// and data.json, built into i18n-fr.js), falling back to English; u("/school/1/") links in the page's language.
export const LANG = document.documentElement.lang.startsWith("fr") ? "fr" : "en";
const DICT = LANG === "fr" ? (await import("./i18n-fr.js")).default : {};
export function t(s, vars) {
  let out = DICT[s] ?? s;
  if (vars) out = out.replace(/\{(\w+)\}/g, (m, k) => (k in vars ? String(vars[k]) : m));
  return out;
}
const SHARED = /^\/(data|static)\/|^\/(favicon\.ico|sitemap\.xml|robots\.txt|build\.json)/;
export const u = (path) => (LANG !== "en" && path.startsWith("/") && !path.startsWith("//") && !SHARED.test(path) && !path.startsWith(`/${LANG}/`) ? `/${LANG}${path}` : path);
/** Numbers in the page's language (French: 1 234,5). */
export const num = (n, opts) => (n == null ? "" : Number(n).toLocaleString(LANG === "fr" ? "fr-CA" : "en-CA", opts));

export const SYSTEMS = {
  "english-public": "English public",
  "english-catholic": "English Catholic",
  "french-public": "French public",
  "french-catholic": "French Catholic",
  other: "Provincial or other",
};

export const esc = (s) =>
  String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

/** Lower-case, strip accents and punctuation, unify "Saint/St./Ste" so searches forgive spelling. */
export function norm(s) {
  return String(s ?? "")
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[’'`]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .replace(/\b(saint|sainte|ste|st)\b/g, "st")
    .replace(/\s+/g, " ")
    .trim();
}

export const debounce = (fn, ms = 120) => {
  let t;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
};

/** Local storage that never throws (private windows, blocked storage). */
export const store = {
  get(k, fallback = null) {
    try {
      const v = localStorage.getItem(k);
      return v == null ? fallback : JSON.parse(v);
    } catch {
      return fallback;
    }
  },
  set(k, v) {
    try {
      localStorage.setItem(k, JSON.stringify(v));
    } catch {
      /* storage unavailable: feature just won't persist */
    }
  },
};

export function km(a, b) {
  // haversine, a/b = [lon, lat]
  const R = 6371;
  const toR = (d) => (d * Math.PI) / 180;
  const dLat = toR(b[1] - a[1]);
  const dLon = toR(b[0] - a[0]);
  const h = Math.sin(dLat / 2) ** 2 + Math.cos(toR(a[1])) * Math.cos(toR(b[1])) * Math.sin(dLon / 2) ** 2;
  return 2 * R * Math.asin(Math.sqrt(h));
}

export const fmtKm = (d) => (d < 1 ? `${num(Math.round(d * 1000), { useGrouping: false })} m` : `${d < 10 ? num(d, { minimumFractionDigits: 1, maximumFractionDigits: 1 }) : num(Math.round(d), { useGrouping: false })} km`);

/** A grade range as the Ministry writes it ("JK-8"), in the page's language (French: "M-8"; JE = senior kindergarten). */
export const gradesText = (g) => (LANG === "fr" && g ? String(g).replace(/\bJK\b/g, "M").replace(/\bSK\b/g, "JE") : g || "");

export const levelName = (l) => (l === "E" ? t("Elementary") : l === "S" ? t("Secondary") : l);

// One program vocabulary for search, maps, school pages and Compare. Keep in step with
// PROGRAM_LABELS in site/family.py (pipeline/tests/test_family.py checks they match).
export const PROGRAM_LABELS = {
  "french-language": "French-language school",
  "french-immersion": "French Immersion",
  "extended-french": "Extended French",
  shsm: "Specialist High Skills Major",
};

/** Program badges for a search-index row or map point: fi/fb = French Immersion (Ministry list / board's list). */
export function programBadges(r) {
  const out = [];
  if (r.lang === "F") out.push({ key: "french-language", label: t(PROGRAM_LABELS["french-language"]) });
  if (r.fi || r.fb) out.push({ key: "french-immersion", label: t(PROGRAM_LABELS["french-immersion"]) });
  if (r.ef) out.push({ key: "extended-french", label: t(PROGRAM_LABELS["extended-french"]) });
  if (r.sh) out.push({ key: "shsm", label: +r.sh === 1 ? t("SHSM · 1 sector") : t("SHSM · {n} sectors", { n: r.sh }) });
  return out;
}

export const badgesHTML = (r) => {
  const b = programBadges(r);
  return b.length ? `<span class="prog-badges">${b.map((x) => `<span class="badge badge-prog prog-${x.key}">${esc(x.label)}</span>`).join("")}</span>` : "";
};

// Grades in order; "K" is senior kindergarten (SK).
export const GRADE_ORDER = ["JK", "K", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12"];
export const gradeName = (g) => (g === "JK" ? t("Junior kindergarten") : g === "K" ? t("Senior kindergarten") : t("Grade {g}", { g }));

/** "JK-8" -> ["JK", "K", "1", ... "8"]; null when the range is missing or unreadable (unknown, not "none"). */
export function gradesOffered(range) {
  const m = /^\s*(JK|SK|K|\d{1,2})\s*-\s*(JK|SK|K|\d{1,2})\s*$/i.exec(range || "");
  if (!m) return null;
  const fix = (g) => (g.toUpperCase() === "SK" ? "K" : g.toUpperCase());
  const i = GRADE_ORDER.indexOf(fix(m[1]));
  const j = GRADE_ORDER.indexOf(fix(m[2]));
  return i < 0 || j < 0 || i > j ? null : GRADE_ORDER.slice(i, j + 1);
}

// Every page carries the build's data version (<html data-v>). Data fetched with it can be cached
// for good, and the next build's pages ask for fresh copies straight away.
const DATA_V = document.documentElement.dataset.v || "";
export const dataUrl = (path) => (DATA_V ? `${path}${path.includes("?") ? "&" : "?"}v=${DATA_V}` : path);

let indexPromise;
/** The compact school index (one fetch, cached for the page). */
export function loadIndex() {
  indexPromise ||= fetch(dataUrl("/data/schools-index.json"))
    .then((r) => {
      if (!r.ok) throw new Error(`index ${r.status}`);
      return r.json();
    })
    .then((rows) => {
      for (const r of rows) {
        r._n = norm(r.n);
        r._c = norm(r.c);
        r._b = norm(r.bn);
      }
      return rows;
    });
  return indexPromise;
}

let boardsPromise;
export function loadBoards() {
  boardsPromise ||= fetch(dataUrl("/data/boards-index.json")).then((r) => r.json());
  return boardsPromise;
}

export function el(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export const icon = (name) => {
  const p = {
    school: '<path d="m3 10 9-5 9 5-9 5-9-5Z"/><path d="M7 12.5V17c0 1 2.2 2.5 5 2.5s5-1.5 5-2.5v-4.5"/>',
    pin: '<path d="M12 21s-7-6.2-7-11.5A7 7 0 0 1 19 9.5C19 14.8 12 21 12 21Z"/><circle cx="12" cy="9.5" r="2.5"/>',
    city: '<path d="M4 21V9l6-3v15M10 21V4l10 4v13M3 21h18"/>',
    board: '<path d="M4 21V5l8-2v18M12 8l8 2v11M3 21h18"/>',
    search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/>',
    plus: '<path d="M12 5v14M5 12h14"/>',
    check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
    chev: '<path d="m9 6 6 6-6 6"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
  }[name];
  return `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
};

export const qs = (s, r = document) => r.querySelector(s);
export const qsa = (s, r = document) => [...r.querySelectorAll(s)];
