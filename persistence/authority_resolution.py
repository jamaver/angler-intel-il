"""Fail-closed authority resolution for production persistence writes."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .authority_manifest import read_manifest
from .connection import DEFAULT_DB, connect

EffectiveAuthority = Literal["json", "sqlite", "sqlite_unavailable", "conflict"]


@dataclass(frozen=True, slots=True)
class AuthorityResolution:
    domain: str
    manifest_authority: str | None
    database_authority: str | None
    effective_authority: EffectiveAuthority
    status: str
    writable: bool
    error: str | None = None


class AuthorityWriteError(RuntimeError):
    def __init__(self, resolution: AuthorityResolution):
        self.resolution = resolution
        super().__init__(resolution.error or f"{resolution.domain} is not writable")

    @property
    def http_status(self) -> int:
        return 503 if self.resolution.effective_authority == "sqlite_unavailable" else 409


def resolve_authority(domain: str, db_path: str | Path = DEFAULT_DB, *, manifest_path: str | Path | None = None) -> AuthorityResolution:
    manifest, manifest_error = read_manifest(manifest_path)
    manifest_authority = None if manifest is None else (manifest.get("domains") or {}).get(domain)
    database_authority = None
    database_error = None
    database = Path(db_path)
    if database.exists():
        try:
            with connect(database, read_only=True) as conn:
                check = conn.execute("PRAGMA quick_check").fetchone()[0]
                if check != "ok":
                    raise RuntimeError(f"SQLite quick_check returned {check!r}")
                row = conn.execute("SELECT authority FROM data_authority WHERE domain = ?", (domain,)).fetchone()
                database_authority = str(row["authority"]) if row else None
        except Exception as exc:
            database_error = f"database_unavailable: {type(exc).__name__}: {exc}"
    else:
        database_error = "database_unavailable: SQLite database file is missing"

    if manifest_error and manifest_error != "manifest_missing":
        return AuthorityResolution(domain, None, database_authority, "conflict", "manifest_invalid", False, manifest_error)
    if manifest_authority == "sqlite" and database_error:
        return AuthorityResolution(domain, manifest_authority, database_authority, "sqlite_unavailable", "database_unavailable", False, database_error)
    if manifest_authority == "sqlite" and database_authority == "sqlite":
        return AuthorityResolution(domain, manifest_authority, database_authority, "sqlite", "ok", True)
    if manifest_authority == "sqlite" and database_authority != "sqlite":
        return AuthorityResolution(domain, manifest_authority, database_authority, "conflict", "marker_conflict", False, "External authority manifest and SQLite authority disagree")
    if manifest_authority == "json" and database_authority in {None, "json"}:
        return AuthorityResolution(domain, manifest_authority, database_authority, "json", "ok" if not database_error else "database_unavailable_json", True, database_error)
    if manifest_authority == "json" and database_authority == "sqlite":
        return AuthorityResolution(domain, manifest_authority, database_authority, "conflict", "marker_conflict", False, "External authority manifest and SQLite authority disagree")
    if manifest_error == "manifest_missing" and database_authority == "sqlite":
        return AuthorityResolution(domain, None, database_authority, "conflict", "manifest_missing", False, "Authority manifest is missing for a SQLite-authoritative domain")
    if manifest_error == "manifest_missing" and database_error:
        return AuthorityResolution(domain, None, None, "conflict", "manifest_missing", False, "Authority manifest is missing; refusing writes until authority is verified")
    if manifest_error == "manifest_missing" and database_authority in {None, "json"}:
        return AuthorityResolution(domain, None, database_authority, "json", "legacy_json", True)
    return AuthorityResolution(domain, manifest_authority, database_authority, "conflict", "unknown", False, "Unable to resolve authority safely")


def require_write_authority(
    domain: str,
    db_path: str | Path = DEFAULT_DB,
    *,
    manifest_path: str | Path | None = None,
) -> str:
    resolution = resolve_authority(domain, db_path, manifest_path=manifest_path)
    if not resolution.writable:
        raise AuthorityWriteError(resolution)
    return resolution.effective_authority
