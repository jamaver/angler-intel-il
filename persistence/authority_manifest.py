"""Atomic runtime authority manifest used when SQLite is unavailable.

The manifest is deliberately outside SQLite.  It prevents a database outage
from being interpreted as a return to JSON authority after a domain has been
explicitly transitioned.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .authority import V7_DOMAINS
from .runtime_paths import DATA_DIR

MANIFEST_SCHEMA = 1
DEFAULT_PATH = DATA_DIR / "authority.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def manifest_path(path: str | Path | None = None) -> Path:
    return Path(path) if path is not None else Path(os.environ.get("AI_AUTHORITY_MANIFEST", DEFAULT_PATH))


def read_manifest(path: str | Path | None = None) -> tuple[dict[str, Any] | None, str | None]:
    resolved = manifest_path(path)
    if not resolved.exists():
        return None, "manifest_missing"
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"manifest_invalid: {exc}"
    if not isinstance(payload, dict) or payload.get("schema") != MANIFEST_SCHEMA:
        return None, "manifest_invalid: unsupported schema"
    domains = payload.get("domains")
    if not isinstance(domains, dict):
        return None, "manifest_invalid: domains must be an object"
    invalid = {str(key): value for key, value in domains.items() if str(key) not in V7_DOMAINS or value not in {"json", "sqlite"}}
    if invalid:
        return None, "manifest_invalid: invalid domain authority"
    return payload, None


def write_manifest(domains: dict[str, str], path: str | Path | None = None) -> Path:
    resolved = manifest_path(path)
    normalized = {domain: str(domains.get(domain, "json")) for domain in V7_DOMAINS}
    if any(value not in {"json", "sqlite"} for value in normalized.values()):
        raise ValueError("Manifest authorities must be json or sqlite")
    payload = {"schema": MANIFEST_SCHEMA, "updated_at": _now(), "domains": normalized}
    resolved.parent.mkdir(parents=True, exist_ok=True)
    temporary = resolved.with_suffix(resolved.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, resolved)
    try:
        directory_fd = os.open(str(resolved.parent), os.O_DIRECTORY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        pass
    return resolved


def set_manifest_authority(domain: str, authority: str, path: str | Path | None = None) -> Path:
    if domain not in V7_DOMAINS or authority not in {"json", "sqlite"}:
        raise ValueError("Invalid authority update")
    payload, error = read_manifest(path)
    if error and error != "manifest_missing":
        raise RuntimeError(error)
    domains = dict((payload or {}).get("domains") or {})
    domains[domain] = authority
    return write_manifest(domains, path)
