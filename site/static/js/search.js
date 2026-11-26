// Search engine + accessible combobox. Auto-attaches to every [data-search] on the page.
import { esc, norm, debounce, loadIndex, loadBoards, levelName, SYSTEMS, icon, qsa } from "./lib.js";

const SOFT = new Set(["school", "schools", "ps", "public", "catholic", "elementary", "secondary", "high", "the", "of", "cs", "ss", "es", "css", "chs", "ces", "hs", "sch", "college", "academy", "ecole", "elementaire", "secondaire", "catholique", "publique", "intermediate", "middle", "senior", "junior", "and", "de", "du", "la", "le"]);
const FSA_RE = /^[a-z]\d[a-z]$/;
const POSTAL_RE = /^[a-z]\d[a-z]\d[a-z]\d$/;

export function acronym(name) {
  const words = name.split(/[\s-]+/).filter(Boolean);
  if (words.length < 2) return "";
  const last = words[words.length - 1];
  const head = words.slice(0, -1).filter((w) => !/^(of|and|de|du|des|la|le)$/i.test(w));
  return (/^[A-Z]{2,}$/.test(last) ? head.map((w) => w[0]).join("") + last : words.map((w) => w[0]).join("")).toLowerCase();
}

export function looksLikeAddress(q) {
  return /^\s*\d+[a-z]?\s+[a-z]/i.test(q) && q.trim().split(/\s+/).length >= 2 && !/^\s*\d+\s*(km|m)\s*$/i.test(q);
}

export function classify(q) {
  const compact = q.toLowerCase().replace(/\s+/g, "");
  if (POSTAL_RE.test(compact)) return { kind: "postal", fsa: compact.slice(0, 3).toUpperCase(), postal: compact.toUpperCase() };
  if (FSA_RE.test(compact)) return { kind: "fsa", fsa: compact.toUpperCase() };
  return { kind: "text" };
}

/** Score every school against the query. Returns sorted schools plus city and board matches. */
export function searchAll(rows, boards, q, { limit = 50 } = {}) {
  const qn = norm(q);
  const out = { q, qn, ...classify(q), schools: [], cities: [], boards: [] };
  if (!qn) return out;
  if (out.kind !== "text") {
    out.schools = rows.filter((r) => r.f === out.fsa).sort((a, b) => a.n.localeCompare(b.n));
    return out;
  }
  const tokens = qn.split(" ").filter(Boolean);
  const hard = tokens.filter((t) => !SOFT.has(t));
  const useTokens = hard.length ? hard : tokens;
  const cityCount = new Map();
  const scored = [];
  for (const r of rows) {
    const nameT = r._nt || (r._nt = r._n.split(" "));
    const cityT = r._ct || (r._ct = r._c.split(" "));
    let score = 0;
    let ok = true;
    for (const t of useTokens) {
      const inName = nameT.some((w) => w.startsWith(t));
      const inCity = cityT.some((w) => w.startsWith(t));
      if (!inName && !inCity && !(r.f && r.f.toLowerCase() === t)) {
        ok = false;
        break;
      }
      score += inName ? 25 : 0;
      score += inCity ? 12 : 0;
      if (nameT.includes(t)) score += 8;
    }
    if (!ok) continue;
    for (const t of tokens) if (SOFT.has(t) && nameT.some((w) => w.startsWith(t))) score += 6;
    if (r._n.startsWith(qn)) score += 60;
    if (r._n === qn) score += 80;
    if (r._c === qn) {
      score += 30;
      cityCount.set(r.c, (cityCount.get(r.c) || 0) + 1);
    }
    score -= r.n.length / 50;
    scored.push([score, r]);
  }
  scored.sort((a, b) => b[0] - a[0] || a[1].n.localeCompare(b[1].n));
  out.total = scored.length;
  out.schools = scored.slice(0, limit).map((x) => x[1]);
  out.allSchools = scored.map((x) => x[1]);
  out.cities = [...cityCount.entries()].map(([name, count]) => ({ name, count }));
  if (boards) {
    out.boards = boards
      .filter((b) => {
        const bn = norm(b.name);
        return bn.includes(qn) || acronym(b.name) === qn.replace(/\s/g, "") || (qn.length >= 3 && bn.split(" ").some((w) => w.startsWith(qn)));
      })
      .slice(0, 4);
  }
  return out;
}

function highlight(text, qn) {
  const safe = esc(text);
  if (!qn) return safe;
  const toks = qn.split(" ").filter((t) => t.length > 1 && !SOFT.has(t));
  if (!toks.length) return safe;
  // highlight on the normalized form by walking words
  return safe.replace(/[\p{L}\p{N}]+/gu, (w) => (toks.some((t) => norm(w).startsWith(t)) ? `<mark>${w}</mark>` : w));
}

export function schoolSub(r) {
  return [levelName(r.l), r.g, SYSTEMS[r.sys] || "", r.c].filter(Boolean).join(" · ");
}

class Combobox {
  constructor(root) {
    this.root = root;
    this.input = root.querySelector("input[type=search]");
    this.list = root.querySelector(".suggest");
    this.form = root.querySelector("form");
    this.mode = root.hasAttribute("data-search-compare") ? "compare" : "go";
    this.items = [];
    this.active = -1;
    if (!this.input || !this.list) return;
    const run = debounce(() => this.update(), 90);
    this.input.addEventListener("input", run);
    this.input.addEventListener("focus", () => {
      loadIndex();
      if (this.input.value.trim()) this.update();
    });
    this.input.addEventListener("keydown", (e) => this.key(e));
    document.addEventListener("click", (e) => {
      if (!root.contains(e.target)) this.close();
    });
    this.form?.addEventListener("submit", (e) => {
      if (this.active >= 0 && this.items[this.active]) {
        e.preventDefault();
        this.choose(this.items[this.active]);
      } else if (this.mode === "compare") {
        e.preventDefault();
        if (this.items[0]) this.choose(this.items[0]);
      }
    });
  }

  async update() {
    const q = this.input.value.trim();
    if (!q) return this.close();
    let rows, boards;
    if (!this.loaded) {
      this.list.innerHTML = '<div class="empty" role="status">Loading the school list…</div>';
      this.open();
    }
    try {
      [rows, boards] = await Promise.all([loadIndex(), loadBoards()]);
      this.loaded = true;
    } catch {
      this.list.innerHTML = '<div class="empty">Search is unavailable right now. Check your connection and try again.</div>';
      return this.open();
    }
    if (this.input.value.trim() !== q) return;
    const res = searchAll(rows, this.mode === "compare" ? null : boards, q, { limit: 7 });
    const items = [];
    let html = "";
    const add = (group, item) => {
      if (group && !html.includes(`data-g="${group}"`)) html += `<div class="grp" data-g="${group}" role="presentation">${group}</div>`;
      const i = items.length;
      items.push(item);
      html += `<a id="${this.list.id}-o${i}" role="option" aria-selected="false" href="${item.href}" data-i="${i}"><span class="ico">${icon(item.icon)}</span><span><span class="t" style="display:block">${item.t}</span><span class="s" style="display:block">${item.s}</span></span></a>`;
    };
    if (this.mode !== "compare") {
      if (res.kind !== "text") {
        add("Postal area", { href: `/fsa/${res.fsa}/`, icon: "pin", t: `Postal area ${esc(res.fsa)}`, s: `${res.schools.length} school${res.schools.length === 1 ? "" : "s"} · map, census and child care` });
      }
      for (const c of res.cities.slice(0, 2)) add("Cities", { href: `/search/?q=${encodeURIComponent(c.name)}`, icon: "city", t: `Schools in ${esc(c.name)}`, s: `${c.count} school${c.count === 1 ? "" : "s"}` });
      for (const b of res.boards.slice(0, 2)) add("Boards", { href: `/board/${b.n}/`, icon: "board", t: highlight(b.name, res.qn), s: `${SYSTEMS[b.sys] || ""} · ${b.count} schools` });
    }
    for (const r of res.schools.slice(0, res.kind === "text" ? 7 : 5)) {
      add("Schools", { href: `/school/${r.id}/`, icon: "school", t: highlight(r.n, res.qn), s: esc(schoolSub(r)), id: r.id, name: r.n });
    }
    if (this.mode !== "compare" && looksLikeAddress(q)) {
      add("Address", { href: `/search/?q=${encodeURIComponent(q)}&address=1`, icon: "search", t: `Find schools near “${esc(q)}”`, s: "Address search by Natural Resources Canada" });
    }
    if (this.mode !== "compare" && (res.total || 0) > 7) {
      add(null, { href: `/search/?q=${encodeURIComponent(q)}`, icon: "search", t: `See all ${res.total} results`, s: "Filter by level, language and board" });
    }
    if (!items.length) html = `<div class="empty">No matches for “${esc(q)}”. Try a shorter name, a city, or the first 3 characters of a postal code.</div>`;
    this.items = items;
    this.active = -1;
    this.list.innerHTML = html;
    this.list.querySelectorAll("a[role=option]").forEach((a) =>
      a.addEventListener("click", (e) => {
        const it = this.items[+a.dataset.i];
        if (this.mode === "compare") {
          e.preventDefault();
          this.choose(it);
        }
      }),
    );
    this.open();
  }

  choose(item) {
    if (this.mode === "compare" && item.id) {
      document.dispatchEvent(new CustomEvent("osf:pick", { detail: { id: item.id, name: item.name } }));
      this.input.value = "";
      this.close();
      return;
    }
    location.href = item.href;
  }

  key(e) {
    if (this.list.hidden && e.key === "ArrowDown") return this.update();
    const n = this.items.length;
    if (e.key === "ArrowDown" && n) {
      e.preventDefault();
      this.move((this.active + 1) % n);
    } else if (e.key === "ArrowUp" && n) {
      e.preventDefault();
      this.move((this.active - 1 + n) % n);
    } else if (e.key === "Escape") {
      this.close();
    }
  }

  move(i) {
    const opts = this.list.querySelectorAll("[role=option]");
    opts.forEach((o) => o.setAttribute("aria-selected", "false"));
    this.active = i;
    const o = opts[i];
    if (o) {
      o.setAttribute("aria-selected", "true");
      o.scrollIntoView({ block: "nearest" });
      this.input.setAttribute("aria-activedescendant", o.id);
    }
  }

  open() {
    this.list.hidden = false;
    this.input.setAttribute("aria-expanded", "true");
  }

  close() {
    this.list.hidden = true;
    this.active = -1;
    this.input.setAttribute("aria-expanded", "false");
    this.input.removeAttribute("aria-activedescendant");
  }
}

export function attachAll() {
  for (const root of qsa("[data-search]")) {
    if (!root._cb) root._cb = new Combobox(root);
  }
}

attachAll();
