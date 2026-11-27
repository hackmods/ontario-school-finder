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


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def record(source_id: str, *, url: str, path: Path | None, note: str = "", resp: requests.Response | None = None,
           new_bytes: bool = False) -> dict:
    """Write (or refresh) the manifest entry for a source and return it.

    ``retrieved`` is when these bytes were downloaded: it only moves when a download brought different bytes
    (``new_bytes``). ``checked`` is the last time the publisher confirmed our copy is current. The server's ETag
    and Last-Modified are kept so a refresh can ask "has it changed?" instead of downloading again."""
    m = _load_manifest()
    entry = m.get(source_id, {})
    entry.update({"url": url, "note": note})
    if path is not None and path.exists():
        data = path.read_bytes()
        entry["sha256"] = hashlib.sha256(data).hexdigest()
        entry["bytes"] = len(data)
        entry["file"] = path.name
    if resp is not None:
        for key, header in (("etag", "ETag"), ("last_modified", "Last-Modified")):
            if resp.headers.get(header):
                entry[key] = resp.headers[header]
        entry["checked"] = _now()
    if new_bytes:
        entry["retrieved"] = _now()
    entry.setdefault("retrieved", _now())
    m[source_id] = entry
    _save_manifest(m)
    return entry


# Set by ``python -m pipeline.build --refresh``: cached files are kept, but each one is checked with the
# publisher once per run (a conditional request when the server gave an ETag or Last-Modified date).
REVALIDATE = False
_revalidated: set[str] = set()


def _revalidate(source_id: str, url: str, path: Path, expect: str) -> Path:
    """Ask the publisher whether a cached file changed; replace it only when it did."""
    _revalidated.add(source_id)
    entry = manifest_entry(source_id)
    headers = {}
    if entry.get("etag"):
        headers["If-None-Match"] = entry["etag"]
    if entry.get("last_modified"):
        headers["If-Modified-Since"] = entry["last_modified"]
    try:
        resp = session().get(url, timeout=config.TIMEOUT, headers=headers)
    except requests.RequestException:
        return path  # can't reach it now: keep the copy we have (its retrieved date stays honest)
    if resp.status_code == 304:
        record(source_id, url=url, path=path, resp=resp)
        return path
    if resp.status_code != 200 or _looks_like_block_page(resp, expect) or (expect in ("xlsx", "zip") and not resp.content.startswith(b"PK")):
        return path  # an error or a block page is never a reason to drop good data
    changed = hashlib.sha256(resp.content).hexdigest() != entry.get("sha256")
    if changed:
        path.write_bytes(resp.content)
    record(source_id, url=url, path=path, resp=resp, new_bytes=changed)
    return path


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
        if REVALIDATE and source_id not in _revalidated:
            return _revalidate(source_id, url, path, expect)
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
        record(source_id, url=url, path=path, resp=resp, new_bytes=True)
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
