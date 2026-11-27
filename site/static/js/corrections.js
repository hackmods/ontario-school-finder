// Corrections page: name the school the visitor came from, and pre-fill the request.
import { loadIndex, esc, levelName, t, u } from "./lib.js";

const id = new URLSearchParams(location.search).get("school");
const box = document.querySelector("[data-correction-school]");
if (id && box) {
  loadIndex().then((rows) => {
    const r = rows.find((x) => x.id === id);
    if (!r) return;
    box.hidden = false;
    box.innerHTML = `<p class="eyebrow" style="margin:0">${t("Reporting about")}</p><h2 style="margin:.2em 0">${esc(r.n)}</h2><p class="muted" style="margin:0">${esc(levelName(r.l))} · ${esc(r.bn)} · ${t("school number {id}", { id: esc(r.id) })}</p>`;
    const mail = document.querySelector("[data-correction-mail]");
    if (mail) mail.href = `${mail.href.split("?")[0]}?subject=${encodeURIComponent(`Correction: ${r.n} (${r.id})`)}`;
    // GitHub issue forms take the title and any field by its id ("page" in data-correction.yml)
    const link = document.querySelector("[data-correction-link]");
    if (link && link.hostname === "github.com") {
      const url = new URL(link.href);
      url.searchParams.set("title", `Correction: ${r.n} (${r.id})`);
      url.searchParams.set("page", `${location.origin}${u(`/school/${r.id}/`)}`);
      link.href = url.toString();
    }
  });
}
