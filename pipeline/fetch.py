"""Downloading with a cache and a manifest of what was fetched, from where, and when."""
from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from . import config


class SourceUnavailable(RuntimeError):
    """A source could not be downloaded (HTTP error, blocked, or not the expected file)."""


class SchemaChanged(RuntimeError):
    """A source file no longer has the columns we expect."""


_session: requests.Session | None = None


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = config.USER_AGENT
    return _session


def _load_manifest() -> dict:
    if config.MANIFEST.exists():
        return json.loads(config.MANIFEST.read_text(encoding="utf-8"))
    return {}


def _save_manifest(m: dict) -> None:
    config.MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    config.MANIFEST.write_text(json.dumps(m, indent=2, sort_keys=True), encoding="utf-8")


def record(source_id: str, *, url: str, path: Path | None, note: str = "") -> dict:
    """Write (or refresh) the manifest entry for a source and return it."""
    m = _load_manifest()
    entry = m.get(source_id, {})
    entry.update({"url": url, "note": note})
    if path is not None and path.exists():
        data = path.read_bytes()
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        entry["bytes"] = len(data)
        entry["file"] = path.name
    entry.setdefault("retrieved", datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
    m[source_id] = entry
    _save_manifest(m)
    return entry


def manifest_entry(source_id: str) -> dict:
    return _load_manifest().get(source_id, {})


def _looks_like_block_page(resp: requests.Response, expect: str) -> bool:
    ctype = resp.headers.get("content-type", "").lower()
    if expect in ("xlsx", "zip") and "html" in ctype:
        return True
    head = resp.content[:4000].lower()
    return b"security check" in head or b"captcha" in head or b"validating your web browser" in head


def download(source_id: str, url: str, *, expect: str, filename: str | None = None, retries: int = 3) -> Path:
    """Download ``url`` into the raw cache (once) and record it in the manifest.

    ``expect`` is one of ``xlsx``, ``txt``, ``zip``, ``json``, ``csv`` and is checked against
    what actually came back, so an error page is never parsed as data.
    """
    config.RAW.mkdir(parents=True, exist_ok=True)
    name = filename or f"{source_id}.{expect}"
    path = config.RAW / name
    if path.exists() and path.stat().st_size > 0:
        if source_id not in _load_manifest():
            record(source_id, url=url, path=path)
        return path
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            resp = session().get(url, timeout=config.TIMEOUT)
        except requests.RequestException as e:  # network trouble: retry with backoff
            last_err = e
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code == 404:
            raise SourceUnavailable(f"{source_id}: {url} returned 404 — the dataset URL has changed. Check the dataset page and update pipeline/sources.py.")
        if resp.status_code in (403, 429) or _looks_like_block_page(resp, expect):
            raise SourceUnavailable(f"{source_id}: {url} is blocked for automated downloads (HTTP {resp.status_code}, browser/security check). Not bypassing it.")
        if resp.status_code >= 500:
            last_err = SourceUnavailable(f"{source_id}: HTTP {resp.status_code} from {url}")
            time.sleep(2 * (attempt + 1))
            continue
        if resp.status_code != 200:
            raise SourceUnavailable(f"{source_id}: HTTP {resp.status_code} from {url}")
        data = resp.content
        if expect == "xlsx" and not data.startswith(b"PK"):
            raise SourceUnavailable(f"{source_id}: expected an .xlsx file from {url} but got something else ({resp.headers.get('content-type')}).")
        if expect == "zip" and not data.startswith(b"PK"):
            raise SourceUnavailable(f"{source_id}: expected a .zip file from {url}.")
        path.write_bytes(data)
        record(source_id, url=url, path=path)
        return path
    raise SourceUnavailable(f"{source_id}: could not download {url}: {last_err}")


def get_json(url: str, *, params: dict | None = None, headers: dict | None = None, retries: int = 3) -> dict | list:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = session().get(url, params=params, headers=headers or {}, timeout=config.TIMEOUT)
            if r.status_code >= 500:
                raise SourceUnavailable(f"HTTP {r.status_code} from {r.url}")
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError, SourceUnavailable) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise SourceUnavailable(f"Could not read JSON from {url}: {last}")


def get_text(url: str, *, headers: dict | None = None, retries: int = 3) -> str:
    last: Exception | None = None
    for attempt in range(retries):
        try:
            r = session().get(url, headers=headers or {}, timeout=config.TIMEOUT)
            if r.status_code >= 500:
                raise SourceUnavailable(f"HTTP {r.status_code} from {r.url}")
            r.raise_for_status()
            return r.text
        except (requests.RequestException, SourceUnavailable) as e:
            last = e
            time.sleep(2 * (attempt + 1))
    raise SourceUnavailable(f"Could not read {url}: {last}")
