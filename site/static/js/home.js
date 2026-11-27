// Home page: "Use my location", quick-try buttons, and the map picture that answers the search box.
import { qs, qsa, loadIndex, t, u, num } from "./lib.js";
import { nearest, locate } from "./near.js";
import { schoolRow } from "./results.js";

const input = qs("#q");
// the example placeholder doesn't fit a phone-width box; the "Or try" links below give the examples there
if (input && matchMedia("(max-width: 480px)").matches) input.placeholder = t("School, city or postal code");
for (const b of qsa("[data-try]")) {
  b.addEventListener("click", () => {
    input.value = b.dataset.try;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
  });
}

// The dot map beside the search box. It is a cached picture (no map library on the home page); matches
// are drawn over it with the same projection generate.py used, the highlighted suggestion pulses, and
// the whole card links to where those schools are on a real map.
const hero = qs("[data-hero-map]");
const heroMap = hero && (() => {
  const hits = qs("[data-hero-hits]", hero);
  const cap = qs("[data-hero-cap]", hero);
  const go = qs("[data-hero-go]", hero);
  const [minx, maxx, miny, maxy] = hero.dataset.bounds.split(",").map(Number);
  const W = +hero.dataset.w;
  const H = +hero.dataset.h;
  const colors = JSON.parse(hero.dataset.colors);
  const zoomEl = qs("[data-hero-zoom]", hero);
  const idle = { cap: cap.textContent, go: go.textContent, href: hero.getAttribute("href") };
  const onMap = ([x, y]) => x >= minx && x <= maxx && y >= miny && y <= maxy;
  const xy = ([x, y]) => [((x - minx) / (maxx - minx)) * W, H - ((y - miny) / (maxy - miny)) * H];
  const f = (v) => v.toFixed(2);
  let lit = new Map();
  let s = 1; // current zoom
  let view = [0, W, 0, H]; // the part of the picture in sight, in picture units
  let drawn = 0; // guards the context layer against a newer draw

  const pick = (sorted, p) => sorted[Math.round(p * (sorted.length - 1))];
  // Zoom onto these points (up to 12x) so a town's schools aren't a speck; 1 = whole picture.
  function zoomTo(pts) {
    s = 1;
    let tx = 0;
    let ty = 0;
    if (pts.length) {
      // frame the middle 90% when there are many, so one far-off namesake doesn't stop the zoom
      const trim = pts.length >= 20 ? 0.05 : 0;
      const xs = pts.map((p) => p[0]).sort((a, b) => a - b);
      const ys = pts.map((p) => p[1]).sort((a, b) => a - b);
      const [x0, x1, y0, y1] = [pick(xs, trim), pick(xs, 1 - trim), pick(ys, trim), pick(ys, 1 - trim)];
      s = Math.max(1, Math.min(12, W / Math.max((x1 - x0) * 1.6, 1), H / Math.max((y1 - y0) * 1.6, 1)));
      // centre the points, without showing past the picture's edges
      tx = Math.min(0, Math.max(W - s * W, W / 2 - (s * (x0 + x1)) / 2));
      ty = Math.min(0, Math.max(H - s * H, H / 2 - (s * (y0 + y1)) / 2));
    }
    view = [-tx / s, (W - tx) / s, -ty / s, (H - ty) / s];
    zoomEl.style.transform = s === 1 ? "" : `translate(${f((tx / W) * 100)}%, ${f((ty / H) * 100)}%) scale(${f(s)})`;
    hits.style.setProperty("--s", f(s));
    hero.classList.toggle("is-zoomed", s > 1.2);
  }

  // Zoomed in, the picture's own dots would grow into blobs: hide it and draw the schools around the
  // matches at their usual size instead, from the school list the search has already loaded.
  function context(token) {
    if (s <= 1.2) return;
    loadIndex().then((all) => {
      if (token !== drawn) return;
      const [vx0, vx1, vy0, vy1] = view;
      let out = "";
      for (const r of all) {
        if (lit.has(r.id) || !onMap([r.x, r.y])) continue;
        const [cx, cy] = xy([r.x, r.y]);
        if (cx >= vx0 && cx <= vx1 && cy >= vy0 && cy <= vy1) out += `<circle cx="${f(cx)}" cy="${f(cy)}" r="${f(1.9 / s)}" fill="${colors[r.sys] || colors.other}"/>`;
      }
      const g = qs("[data-hero-ctx]", hits);
      if (g) g.innerHTML = out;
    });
  }

  function show({ rows = [], you = null, text, link, href }) {
    lit = new Map(rows.map((r) => [r.id, r]));
    const pts = rows.filter((r) => onMap([r.x, r.y])).slice(0, 1500).map((r) => [...xy([r.x, r.y]), r]);
    const youPt = you && onMap(you) ? xy(you) : null;
    zoomTo(youPt ? [...pts, youPt] : pts);
    let svg = `<g class="ctx" data-hero-ctx></g>`;
    svg += pts.map(([cx, cy, r]) => `<circle cx="${f(cx)}" cy="${f(cy)}" r="${f(3.4 / s)}" fill="${colors[r.sys] || colors.other}"/>`).join("");
    if (youPt) svg += `<circle class="you" cx="${f(youPt[0])}" cy="${f(youPt[1])}" r="${f(5.5 / s)}"/>`;
    hits.innerHTML = svg;
    context(++drawn);
    hero.classList.toggle("is-lit", rows.length > 0 || !!youPt);
    cap.textContent = text;
    go.textContent = link;
    hero.setAttribute("href", href);
  }

  function reset() {
    lit = new Map();
    drawn++;
    hits.innerHTML = "";
    zoomTo([]);
    hero.classList.remove("is-lit");
    cap.textContent = idle.cap;
    go.textContent = idle.go;
    hero.setAttribute("href", idle.href);
  }

  function focus(id) {
    hits.querySelector(".ring")?.remove();
    const r = id && lit.get(id);
    if (!r || !onMap([r.x, r.y])) return;
    const [cx, cy] = xy([r.x, r.y]);
    hits.insertAdjacentHTML("beforeend", `<circle class="ring pulse" cx="${f(cx)}" cy="${f(cy)}" r="${f(7 / s)}"/>`);
  }

  // How many of these schools sit north of the picture (it covers southern Ontario only).
  const north = (rows) => rows.filter((r) => !onMap([r.x, r.y])).length;
  return { show, reset, focus, north, onMap };
})();

const btn = qs("[data-near-me]");
const status = qs("[data-near-status]");
const panel = qs("[data-near-results]");
const list = qs("[data-near-list]");
let state = null;
let level = "all";
let query = null;

function showNear() {
  if (!heroMap || !state) return heroMap?.reset();
  const rows = nearest(state.rows, state.at, { level, limit: 12 });
    heroMap.show({ rows, you: state.at, text: heroMap.onMap(state.at) ? t("Your {n} nearest schools", { n: num(rows.length) }) : t("Your {n} nearest schools · you’re north of this map", { n: num(rows.length) }), link: t("See the list ↓"), href: "#near" });
}

function render() {
  if (!state) return;
  list.innerHTML = nearest(state.rows, state.at, { level, limit: 12 }).map((r) => schoolRow(r, { distance: r.d })).join("");
  document.dispatchEvent(new CustomEvent("osf:compare"));
  if (!query) showNear();
}
btn?.addEventListener("click", async () => {
  btn.disabled = true;
  try {
    state = await locate(status);
    panel.hidden = false;
    render();
    panel.scrollIntoView({ behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth", block: "start" });
  } catch {
    /* message already shown */
  } finally {
    btn.disabled = false;
  }
});
for (const c of qsa("[data-near-level]")) {
  c.addEventListener("click", () => {
    level = c.dataset.nearLevel;
    qsa("[data-near-level]").forEach((x) => { x.classList.toggle("on", x === c); x.setAttribute("aria-pressed", String(x === c)); });
    render();
  });
}

const box = qs("[data-search-home]");
box?.addEventListener("osf:results", (e) => {
  if (!heroMap) return;
  query = e.detail;
  if (!query) return showNear();
  const { q, kind, fsa, schools } = query;
  const n = schools.length;
  if (!n) return heroMap.show({ rows: [], text: t("No schools match “{q}”", { q }), link: t("Open the map →"), href: u("/map/") });
  const off = heroMap.north(schools);
  const N = num(n);
  const head = kind === "text" ? (n === 1 ? t("1 school matches “{q}”", { q }) : t("{n} schools match “{q}”", { n: N, q })) : n === 1 ? t("1 school in postal area {fsa}", { fsa }) : t("{n} schools in postal area {fsa}", { n: N, fsa });
  const text = !off ? head : off === n ? t("{head} · all north of this map", { head }) : t("{head} · {n} north of this map", { head, n: num(off) });
  heroMap.show({
    rows: schools,
    text,
    link: kind === "text" ? t("See them on a map →") : t("Open {fsa} →", { fsa }),
    href: kind === "text" ? u(`/search/?q=${encodeURIComponent(q)}`) : u(`/fsa/${fsa}/`),
  });
});
box?.addEventListener("osf:active", (e) => heroMap?.focus(e.detail?.id));
