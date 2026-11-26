// Home page: "Use my location", quick-try buttons.
import { qs, qsa } from "./lib.js";
import { nearest, locate } from "./near.js";
import { schoolRow } from "./results.js";

const input = qs("#q");
for (const b of qsa("[data-try]")) {
  b.addEventListener("click", () => {
    input.value = b.dataset.try;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
  });
}

const btn = qs("[data-near-me]");
const status = qs("[data-near-status]");
const panel = qs("[data-near-results]");
const list = qs("[data-near-list]");
let state = null;
let level = "all";
function render() {
  if (!state) return;
  list.innerHTML = nearest(state.rows, state.at, { level, limit: 12 }).map((r) => schoolRow(r, { distance: r.d })).join("");
}
btn?.addEventListener("click", async () => {
  btn.disabled = true;
  try {
    state = await locate(status);
    panel.hidden = false;
    render();
    panel.scrollIntoView({ behavior: "smooth", block: "start" });
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
