// Shared rendering of school result rows.
import { esc, fmtKm, icon } from "./lib.js";
import { schoolSub } from "./search.js";

export function schoolRow(r, { distance } = {}) {
  const side = distance != null ? `<span class="side">${fmtKm(distance)}</span>` : "";
  return `<li><a class="row-link" href="/school/${encodeURIComponent(r.id)}/"><span class="pin sys-${esc(r.sys)}"></span><span class="main"><span class="t">${esc(r.n)}</span><span class="s" style="display:block">${esc(schoolSub(r))}${r.bn ? ` · ${esc(r.bn)}` : ""}</span></span>${side}<span class="chev">${icon("chev")}</span></a></li>`;
}
