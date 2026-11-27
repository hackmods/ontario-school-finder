// Shared rendering of school result rows.
import { esc, fmtKm, icon, badgesHTML, t, u } from "./lib.js";
import { schoolSub } from "./search.js";

export function schoolRow(r, { distance } = {}) {
  const side = distance != null ? `<span class="side" title="${esc(t("Straight-line distance"))}">${fmtKm(distance)}</span>` : "";
  return `<li class="row-wrap"><a class="row-link" href="${u(`/school/${encodeURIComponent(r.id)}/`)}"><span class="pin sys-${esc(r.sys)}"></span><span class="main"><span class="t">${esc(r.n)}</span><span class="s" style="display:block">${esc(schoolSub(r))}${r.bn ? ` · ${esc(r.bn)}` : ""}</span>${badgesHTML(r)}</span>${side}</a><button type="button" class="icon-btn" data-compare-toggle="${esc(r.id)}" data-compare-name="${esc(r.n)}" aria-pressed="false" title="${esc(t("Add to compare"))}"><span class="visually-hidden">${esc(t("Compare {name}", { name: r.n }))}</span>${icon("plus")}</button></li>`;
}
