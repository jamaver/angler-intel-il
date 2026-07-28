"""SQLite-authoritative target-profile contract for V7.3.1 only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps, record_hash
from .connection import DEFAULT_DB, connect
from .target_profile_mirror import PROFILE_ID, _favorite_species, _slug, _source_label, _utc_now


def _prepare_json_export(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".v7-export.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return temporary


def _commit_json_export(temporary: Path, path: Path) -> None:
    temporary.replace(path)


def _set_export_status(conn, status: str, *, error: str | None = None, authoritative_payload_hash: str | None = None, compatibility_export_hash: str | None = None) -> None:
    value = {"status": status, "error": error, "domain": "target_profile", "authoritative_payload_hash": authoritative_payload_hash, "compatibility_export_hash": compatibility_export_hash, "compatibility_exported_at": _utc_now() if status == "ok" else None}
    conn.execute(
        """
        INSERT INTO app_settings(key, value_json, updated_at)
        VALUES('v7.target_profile.compatibility_export', ?, ?)
        ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
        """,
        (canonical_dumps(value), _utc_now()),
    )


def is_target_profile_sqlite_authoritative(db_path: str | Path = DEFAULT_DB) -> bool:
    database = Path(db_path)
    if not database.exists():
        return False
    try:
        with connect(database, read_only=True) as conn:
            row = conn.execute("SELECT authority FROM data_authority WHERE domain = 'target_profile'").fetchone()
            return bool(row and row["authority"] == "sqlite")
    except Exception:
        return False


def _profile_from_row(row: Any) -> dict[str, Any]:
    try:
        profile = json.loads(row["legacy_payload_json"] or "{}")
    except Exception:
        profile = {}
    if not isinstance(profile, dict):
        profile = {}
    profile.update(
        {
            "default_target_species": str(row["default_target_species"] or ""),
            "current_trip_target": str(row["current_trip_target"] or ""),
            "favorite_species": json.loads(row["favorite_species_json"] or "[]"),
            "updated_at": str(row["updated_at"] or ""),
        }
    )
    return profile


def export_target_profile(db_path: str | Path, json_path: str | Path) -> dict[str, Any]:
    with connect(db_path, read_only=True) as conn:
        row = conn.execute("SELECT * FROM target_profiles WHERE id = ?", (PROFILE_ID,)).fetchone()
        if not row:
            raise ValueError("SQLite target profile is missing")
        profile = _profile_from_row(row)
    temporary = _prepare_json_export(Path(json_path), profile)
    try:
        _commit_json_export(temporary, Path(json_path))
    except Exception as exc:
        with connect(db_path) as conn:
            with conn:
                _set_export_status(conn, "failed", error=str(exc))
        raise
    with connect(db_path) as conn:
        with conn:
            _set_export_status(conn, "ok")
    return profile


def _write_profile(conn, profile: dict[str, Any], *, authority: str, source_path: Path) -> None:
    favorites = _favorite_species(profile)
    updated_at = str(profile.get("updated_at") or _utc_now())
    payload_json = canonical_dumps(profile)
    source_label = _source_label(source_path)
    conn.execute(
        """
        INSERT INTO target_profiles(id, default_target_species, current_trip_target, favorite_species_json,
          legacy_payload_json, source_path, source_hash, source_key, created_at, updated_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET default_target_species=excluded.default_target_species,
          current_trip_target=excluded.current_trip_target, favorite_species_json=excluded.favorite_species_json,
          legacy_payload_json=excluded.legacy_payload_json, source_path=excluded.source_path,
          source_hash=excluded.source_hash, source_key=excluded.source_key, updated_at=excluded.updated_at
        """,
        (PROFILE_ID, str(profile.get("default_target_species") or ""), str(profile.get("current_trip_target") or ""),
         canonical_dumps(favorites), payload_json, source_label, record_hash(profile), PROFILE_ID,
         str(profile.get("created_at") or updated_at), updated_at),
    )
    conn.execute("DELETE FROM target_profile_species WHERE target_profile_id = ?", (PROFILE_ID,))
    for index, species_name in enumerate(favorites, start=1):
        species_id = _slug(species_name)
        if conn.execute("SELECT 1 FROM species WHERE id = ?", (species_id,)).fetchone():
            conn.execute("INSERT INTO target_profile_species(target_profile_id, species_id, preference, source_path) VALUES(?, ?, ?, ?)",
                         (PROFILE_ID, species_id, f"favorite-{index}", source_label))
    conn.execute(
        """INSERT INTO data_authority(domain, authority, source_path, source_hash, note, updated_at)
           VALUES('target_profile', ?, ?, ?, ?, ?)
           ON CONFLICT(domain) DO UPDATE SET authority=excluded.authority, source_path=excluded.source_path,
             source_hash=excluded.source_hash, note=excluded.note, updated_at=excluded.updated_at""",
        (authority, source_label, record_hash(profile),
         "SQLite is authoritative; JSON is a compatibility export." if authority == "sqlite" else "JSON remains authoritative.", _utc_now()),
    )
    if authority == "sqlite":
        _set_export_status(conn, "pending", authoritative_payload_hash=record_hash(profile))


def activate_target_profile_authority(db_path: str | Path, json_path: str | Path) -> dict[str, Any]:
    """Flip only target_profile after an external preflight has passed."""
    json_path = Path(json_path)
    with connect(db_path) as conn:
        row = conn.execute("SELECT * FROM target_profiles WHERE id = ?", (PROFILE_ID,)).fetchone()
        if not row:
            raise ValueError("Target-profile mirror is missing; reconcile before transition")
        profile = _profile_from_row(row)
        temporary = _prepare_json_export(json_path, profile)
        with conn:
            _write_profile(conn, profile, authority="sqlite", source_path=json_path)
    try:
        _commit_json_export(temporary, json_path)
    except Exception as exc:
        with connect(db_path) as conn:
            with conn:
                _set_export_status(conn, "failed", error=str(exc), authoritative_payload_hash=record_hash(profile))
        raise
    with connect(db_path) as conn:
        with conn:
            _set_export_status(conn, "ok", authoritative_payload_hash=record_hash(profile), compatibility_export_hash=record_hash(profile))
    return profile


def save_target_profile_sqlite_authoritative(profile: dict[str, Any], db_path: str | Path, json_path: str | Path) -> dict[str, Any]:
    """Persist SQLite first, then refresh the non-authoritative JSON export."""
    json_path = Path(json_path)
    temporary = _prepare_json_export(json_path, profile)
    with connect(db_path) as conn:
        with conn:
            _write_profile(conn, profile, authority="sqlite", source_path=json_path)
    try:
        _commit_json_export(temporary, json_path)
    except Exception as exc:
        with connect(db_path) as conn:
            with conn:
                _set_export_status(conn, "failed", error=str(exc))
        # The authoritative SQLite transaction already committed.  Keep the
        # compatibility-export failure visible for repair without reporting
        # the profile save itself as failed.
        return profile
    with connect(db_path) as conn:
        with conn:
            _set_export_status(conn, "ok")
    return profile
