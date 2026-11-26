// "Use my location": the position stays in memory for this tab only. Never stored or sent anywhere.
import { loadIndex, km } from "./lib.js";

export function nearest(rows, at, { level = "all", limit = 20 } = {}) {
  return rows
    .filter((r) => level === "all" || r.l === level)
    .map((r) => ({ ...r, d: km(at, [r.x, r.y]) }))
    .sort((a, b) => a.d - b.d)
    .slice(0, limit);
}

export function locate(statusEl) {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      statusEl && (statusEl.textContent = "This browser can’t share its location. Search by postal code instead.");
      return reject(new Error("unsupported"));
    }
    statusEl && (statusEl.textContent = "Asking your browser for your location…");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const at = [pos.coords.longitude, pos.coords.latitude];
        const inOntario = at[1] > 41.6 && at[1] < 57 && at[0] > -95.2 && at[0] < -74.3;
        statusEl && (statusEl.textContent = inOntario ? "Showing the schools closest to you." : "You seem to be outside Ontario, so these are the closest Ontario schools.");
        resolve({ at, rows: await loadIndex() });
      },
      (err) => {
        const msg = err.code === 1 ? "Location permission was declined. You can still search by name, city or postal code." : "Couldn’t get your location. Try searching by postal code.";
        statusEl && (statusEl.textContent = msg);
        reject(err);
      },
      { enableHighAccuracy: false, timeout: 12000, maximumAge: 300000 },
    );
  });
}
