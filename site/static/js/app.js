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
    const label = btn.querySelector("span");
    if (label) label.textContent = on ? "Added to compare" : "Compare";
  }
  const tray = qs("[data-compare-tray]");
  if (tray) {
    const onComparePage = document.body.classList.contains("page-compare");
    tray.hidden = list.length === 0 || onComparePage;
    document.body.classList.toggle("has-tray", !tray.hidden);
    qs("[data-compare-label]", tray).textContent = list.length === 1 ? `1 school: ${list[0].name}` : `${list.length} schools to compare`;
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

// ---- sticky sub-navigation highlight -------------------------------------
const sub = qsa(".subnav a");
if (sub.length && "IntersectionObserver" in window) {
  const map = new Map(sub.map((a) => [a.getAttribute("href").slice(1), a]));
  const io = new IntersectionObserver(
    (entries) => {
      for (const en of entries) {
        if (en.isIntersecting) {
          sub.forEach((a) => a.classList.remove("active"));
          map.get(en.target.id)?.classList.add("active");
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

