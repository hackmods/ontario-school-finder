// Shared rendering of school result rows.
import { esc, fmtKm, icon } from "./lib.js";
import { schoolSub } from "./search.js";

export function schoolRow(r, { distance } = {}) {
  const side = distance != null ? `<span class="side">${fmtKm(distance)}</span>` : "";
  return `<li class="row-wrap"><a class="row-link" href="/school/${encodeURIComponent(r.id)}/"><span class="pin sys-${esc(r.sys)}"></span><span class="main"><span class="t">${esc(r.n)}</span><span class="s" style="display:block">${esc(schoolSub(r))}${r.bn ? ` · ${esc(r.bn)}` : ""}</span></span>${side}</a><button type="button" class="icon-btn" data-compare-toggle="${esc(r.id)}" data-compare-name="${esc(r.n)}" aria-pressed="false" title="Add to compare"><span class="visually-hidden">Compare ${esc(r.n)}</span>${icon("plus")}</button></li>`;
}
