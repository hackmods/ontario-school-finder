// The compare list: up to 3 schools, kept only in this browser's local storage.
import { store } from "./lib.js";

export const MAX_COMPARE = 3;

export function getCompare() {
  const v = store.get("osf-compare", []);
  return Array.isArray(v) ? v.filter((x) => x && x.id).slice(0, MAX_COMPARE) : [];
}

export function setCompare(list) {
  store.set("osf-compare", list.slice(0, MAX_COMPARE));
  document.dispatchEvent(new CustomEvent("osf:compare", { detail: list.slice(0, MAX_COMPARE) }));
}

export function toggleCompare(id, name) {
  const list = getCompare();
  const i = list.findIndex((x) => x.id === id);
  if (i >= 0) list.splice(i, 1);
  else {
    if (list.length >= MAX_COMPARE) list.shift();
    list.push({ id, name });
  }
  setCompare(list);
}
