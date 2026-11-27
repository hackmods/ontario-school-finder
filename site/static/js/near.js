// "Use my location": the position stays in memory for this tab only. Never stored or sent anywhere.
import { loadIndex, km, t } from "./lib.js";

export function nearest(rows, at, { level = "all", limit = 20 } = {}) {
  return rows
    .filter((r) => level === "all" || r.l === level)
    .map((r) => ({ ...r, d: km(at, [r.x, r.y]) }))
    .sort((a, b) => a.d - b.d)
    .slice(0, limit);
}

// Why a location request failed, in words a parent can act on. Browsers report the same "denied"
// code whether the person said no, blocked the site earlier, or the phone has location off for the
// browser, often without ever showing a question, so the message covers all three.
const FAIL = () => ({
  1: [t("Your browser didn’t share a location."), t("If no question popped up, location is switched off for this site or for your browser. Allow it in the site settings next to the web address, or turn on Location for this browser in your phone or computer settings, then try again.")],
  2: [t("Your device couldn’t work out where you are right now."), t("Try again in a moment, or use a postal code: it finds the same nearby schools.")],
  3: [t("Finding your location took too long."), t("Try again, or use a postal code: it finds the same nearby schools.")],
  unsupported: [t("This browser can’t share its location."), t("Use a postal code instead: it finds the same nearby schools.")],
  insecure: [t("Location only works on the secure (https) address of this site."), t("Use a postal code instead: it finds the same nearby schools.")],
});

function showFailure(statusEl, key) {
  if (!statusEl) return;
  const fails = FAIL();
  const [head, help] = fails[key] || fails[2];
  statusEl.innerHTML = `<strong>${head}</strong> ${help} <button type="button" class="link-btn" data-postal-fallback>${t("Type a postal code instead")}</button>`;
  statusEl.querySelector("[data-postal-fallback]").addEventListener("click", () => {
    // the page's own search box first; the header one is hidden on phones
    const input = ["#q", "#sq", "#hq"].map((s) => document.querySelector(s)).find((el) => el && el.getClientRects().length);
    if (!input) return;
    input.placeholder = t("Postal code, like K7L 3N6");
    input.focus({ preventScroll: true });
    input.scrollIntoView({ block: "center", behavior: matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  });
}

export function locate(statusEl) {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      showFailure(statusEl, "unsupported");
      return reject(new Error("unsupported"));
    }
    if (!window.isSecureContext) {
      showFailure(statusEl, "insecure");
      return reject(new Error("insecure"));
    }
    statusEl && (statusEl.textContent = t("Asking your browser for your location…"));
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const at = [pos.coords.longitude, pos.coords.latitude];
        const inOntario = at[1] > 41.6 && at[1] < 57 && at[0] > -95.2 && at[0] < -74.3;
        statusEl && (statusEl.textContent = inOntario ? t("Showing the schools closest to you.") : t("You seem to be outside Ontario, so these are the closest Ontario schools."));
        resolve({ at, rows: await loadIndex() });
      },
      (err) => {
        showFailure(statusEl, err.code);
        reject(err);
      },
      { enableHighAccuracy: false, timeout: 15000, maximumAge: 300000 },
    );
  });
}
