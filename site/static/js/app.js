// Runs on every page: menu, theme, compare tray, and search boxes.
import { store, qs, qsa } from "./lib.js";
import { getCompare, setCompare, toggleCompare } from "./compare-store.js";

// ---- mobile menu --------------------------------------------------------
const toggle = qs("[data-menu-toggle]");
const menu = qs("#mobile-menu");
toggle?.addEventListener("click", () => {
  const open = !menu.classList.contains("open");
  menu.classList.toggle("open", open);
  toggle.setAttribute("aria-expanded", String(open));
});

// ---- theme --------------------------------------------------------------
const themeBtn = qs("[data-theme-toggle]");
const order = ["auto", "light", "dark"];
function applyTheme(t) {
  if (t === "auto") delete document.documentElement.dataset.theme;
  else document.documentElement.dataset.theme = t;
  if (themeBtn) themeBtn.querySelector("span").textContent = `Theme: ${t}`;
  document.dispatchEvent(new CustomEvent("osf:theme", { detail: t }));
}
applyTheme(store.get("osf-theme-choice", "auto"));
themeBtn?.addEventListener("click", () => {
  const cur = store.get("osf-theme-choice", "auto");
  const next = order[(order.indexOf(cur) + 1) % order.length];
  store.set("osf-theme-choice", next);
  try {
    if (next === "auto") localStorage.removeItem("osf-theme");
    else localStorage.setItem("osf-theme", next);
  } catch {}
  applyTheme(next);
});

// ---- compare list (max 3, saved only in this browser) ------------------
function renderCompare() {
  const list = getCompare();
  for (const b of qsa("[data-compare-count]")) {
    b.textContent = String(list.length);
    b.hidden = list.length === 0;
  }
  for (const btn of qsa("[data-compare-toggle]")) {
    const on = list.some((x) => x.id === btn.dataset.compareToggle);
    btn.setAttribute("aria-pressed", String(on));
    const label = btn.querySelector("span:not(.visually-hidden)");
    if (label) label.textContent = on ? "Added to compare" : "Compare";
    btn.title = on ? "Remove from compare" : "Add to compare";
  }
  const tray = qs("[data-compare-tray]");
  if (tray) {
    const onComparePage = document.body.classList.contains("page-compare");
    tray.hidden = list.length === 0 || onComparePage;
    document.body.classList.toggle("has-tray", !tray.hidden);
    qs("[data-compare-label]", tray).textContent = list.length === 1 ? `1 school: ${list[0].name} · add another` : `${list.length} of 6 schools to compare`;
    qs("[data-compare-link]", tray).href = `/compare/?ids=${list.map((x) => encodeURIComponent(x.id)).join(",")}`;
  }
}
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-compare-toggle]");
  if (btn) toggleCompare(btn.dataset.compareToggle, btn.dataset.compareName || btn.dataset.compareToggle);
  if (e.target.closest("[data-compare-clear]")) setCompare([]);
});
window.addEventListener("storage", (e) => e.key === "osf-compare" && renderCompare());
document.addEventListener("osf:compare", renderCompare);
renderCompare();

// ---- search boxes: load the search module only when a page has one -------
if (qs("[data-search]")) import("./search.js");

// ---- sideways-scrolling strips: fade the edge that has more to show -----
// Tables, the section nav and the letter bar scroll sideways on phones; without a cue people
// never find the columns or links past the edge. Tables with a sticky first column only fade right.
const seen = new WeakSet();
const ro = "ResizeObserver" in window ? new ResizeObserver((es) => es.forEach((e) => e.target._fade?.())) : null;
function fadeEdges(el) {
  if (seen.has(el)) return;
  seen.add(el);
  const keepLeft = !!el.querySelector(".sticky");
  el._fade = () => {
    const max = el.scrollWidth - el.clientWidth;
    el.classList.toggle("fade-l", !keepLeft && max > 2 && el.scrollLeft > 2);
    el.classList.toggle("fade-r", max > 2 && el.scrollLeft < max - 2);
  };
  el.addEventListener("scroll", el._fade, { passive: true });
  ro?.observe(el);
  el._fade();
}
const scanStrips = () => qsa(".table-wrap, .subnav .wrap, .az").forEach(fadeEdges);
scanStrips();
const mainEl = qs("#main");
if (mainEl && "MutationObserver" in window) {
  let t = 0;
  new MutationObserver(() => { cancelAnimationFrame(t); t = requestAnimationFrame(scanStrips); }).observe(mainEl, { childList: true, subtree: true });
}

// ---- sticky sub-navigation highlight -------------------------------------
const sub = qsa(".subnav a");
if (sub.length && "IntersectionObserver" in window) {
  const map = new Map(sub.map((a) => [a.getAttribute("href").slice(1), a]));
  const strip = qs(".subnav .wrap");
  const calm = matchMedia("(prefers-reduced-motion: reduce)");
  const io = new IntersectionObserver(
    (entries) => {
      for (const en of entries) {
        if (en.isIntersecting) {
          sub.forEach((a) => a.classList.remove("active"));
          const a = map.get(en.target.id);
          if (!a) continue;
          a.classList.add("active");
          // keep the current section visible in the strip on phones
          if (strip && strip.scrollWidth > strip.clientWidth) strip.scrollTo({ left: a.offsetLeft - (strip.clientWidth - a.offsetWidth) / 2, behavior: calm.matches ? "auto" : "smooth" });
        }
      }
    },
    { rootMargin: "-40% 0px -55% 0px" },
  );
  map.forEach((_, id) => {
    const t = document.getElementById(id);
    if (t) io.observe(t);
  });
}


// ---- print: show every "Show the numbers" table, then put them back --------
// Phones fold the year tables; a printed page should carry the numbers whatever the screen was.
let printOpened = [];
window.addEventListener("beforeprint", () => {
  printOpened = qsa("details.data-table:not([open])");
  printOpened.forEach((d) => (d.open = true));
});
window.addEventListener("afterprint", () => {
  printOpened.forEach((d) => (d.open = false));
  printOpened = [];
});

// ---- copy buttons: <button data-copy="#id"> copies that element's text ----------
document.addEventListener("click", async (e) => {
  const b = e.target.closest("[data-copy]");
  if (!b) return;
  const src = document.querySelector(b.dataset.copy);
  const label = b.querySelector("span");
  if (!src) return;
  try {
    await navigator.clipboard.writeText(src.textContent.trim());
    if (label) label.textContent = "Copied";
  } catch {
    // no clipboard permission: select the text so the visitor can copy it themselves
    const r = document.createRange();
    r.selectNodeContents(src);
    getSelection().removeAllRanges();
    getSelection().addRange(r);
    if (label) label.textContent = "Selected: press copy";
  }
  setTimeout(() => label && (label.textContent = "Copy the text"), 2500);
});
