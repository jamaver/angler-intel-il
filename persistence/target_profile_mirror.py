"""Target-profile reconciliation while JSON remains authoritative."""
from __future__ import annotations

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps, record_hash
from .connection import DEFAULT_DB
from .mirror import MirrorResult, mirror_after_json_write
from .provenance import file_sha256

BASE_DIR = Path(__file__).resolve().parents[1]
PROFILE_ID = "current"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _slug(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "-", str(value or "").strip().lower()).strip("-") or "species"


def _source_label(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(BASE_DIR))
    except ValueError:
        return str(path)


def target_profile_operation_id(profile: dict[str, Any]) -> str:
    """Derive a retry-safe ID from the complete JSON profile snapshot."""
    return f"target-profile-{record_hash(profile)}"


def _favorite_species(profile: dict[str, Any]) -> list[str]:
    values = profile.get("favorite_species")
    if not isinstance(values, list):
        return []
    return [str(value).strip() for value in values if str(value).strip()]


def _write_target_profile(conn: sqlite3.Connection, profile: dict[str, Any], source_path: Path) -> None:
    """Reconcile one complete profile without writing its JSON source."""
    authority_row = conn.execute(
        "SELECT authority FROM data_authority WHERE domain = 'target_profile'"
    ).fetchone()
    if authority_row and authority_row["authority"] == "sqlite":
        raise RuntimeError(
            "target_profile is SQLite-authoritative; JSON-to-SQLite mirroring is disabled."
        )
    source_hash = file_sha256(source_path)
    source_label = _source_label(source_path)
    updated_at = str(profile.get("updated_at") or _utc_now())
    favorites = _favorite_species(profile)
    payload_json = canonical_dumps(profile)

    conn.execute(
        """
        INSERT INTO target_profiles(
            id, default_target_species, current_trip_target, favorite_species_json,
            legacy_payload_json, source_path, source_hash, source_key, created_at, updated_at
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            default_target_species = excluded.default_target_species,
            current_trip_target = excluded.current_trip_target,
            favorite_species_json = excluded.favorite_species_json,
            legacy_payload_json = excluded.legacy_payload_json,
            source_path = excluded.source_path,
            source_hash = excluded.source_hash,
            source_key = excluded.source_key,
            updated_at = excluded.updated_at
        """,
        (
            PROFILE_ID,
            str(profile.get("default_target_species") or ""),
            str(profile.get("current_trip_target") or ""),
            canonical_dumps(favorites),
            payload_json,
            source_label,
            source_hash,
            PROFILE_ID,
            str(profile.get("created_at") or updated_at),
            updated_at,
        ),
    )
    conn.execute("DELETE FROM target_profile_species WHERE target_profile_id = ?", (PROFILE_ID,))
    for index, species_name in enumerate(favorites, start=1):
        species_id = _slug(species_name)
        # V7.1.1 does not seed or change species reference data. The complete
        # ordered favorite list remains preserved in target_profiles even before
        # that reference domain has been reconciled.
        if conn.execute("SELECT 1 FROM species WHERE id = ?", (species_id,)).fetchone():
            conn.execute(
                """
                INSERT INTO target_profile_species(target_profile_id, species_id, preference, source_path)
                VALUES(?, ?, ?, ?)
                """,
                (PROFILE_ID, species_id, f"favorite-{index}", source_label),
            )

    now = _utc_now()
    conn.execute(
        """
        INSERT INTO source_files(
            domain, logical_name, path, file_hash, record_count, source_of_truth,
            generated_only, last_seen_at, last_imported_at
        ) VALUES('target_profile', 'target_profile', ?, ?, 1, 'json', 0, ?, ?)
        ON CONFLICT(domain, path) DO UPDATE SET
            file_hash = excluded.file_hash,
            record_count = excluded.record_count,
            source_of_truth = 'json',
            generated_only = 0,
            last_seen_at = excluded.last_seen_at,
            last_imported_at = excluded.last_imported_at
        """,
        (source_label, source_hash, now, now),
    )
    conn.execute(
        """
        INSERT INTO legacy_record_map(
            domain, source_path, source_key, normalized_id, payload_hash, source_hash,
            status, notes, created_at
        ) VALUES('target_profile', ?, ?, ?, ?, ?, 'mapped', NULL, ?)
        ON CONFLICT(domain, source_path, source_key) DO UPDATE SET
            normalized_id = excluded.normalized_id,
            payload_hash = excluded.payload_hash,
            source_hash = excluded.source_hash,
            status = 'mapped',
            notes = NULL
        """,
        (source_label, PROFILE_ID, PROFILE_ID, record_hash(profile), source_hash, now),
    )
    conn.execute(
        """
        INSERT INTO data_authority(domain, authority, source_path, source_hash, note, updated_at)
        VALUES('target_profile', 'json', ?, ?, 'JSON remains authoritative during V7.1 target-profile mirroring.', ?)
        ON CONFLICT(domain) DO UPDATE SET
            authority = 'json',
            source_path = excluded.source_path,
            source_hash = excluded.source_hash,
            note = excluded.note,
            updated_at = excluded.updated_at
        """,
        (source_label, source_hash, now),
    )


def mirror_target_profile(
    profile: dict[str, Any],
    source_path: str | Path,
    *,
    db_path: str | Path = DEFAULT_DB,
    force: bool = False,
) -> MirrorResult:
    """Mirror an already-saved JSON target profile into normalized SQLite."""
    path = Path(source_path)
    profile_copy = dict(profile)
    base_operation_id = target_profile_operation_id(profile_copy)
    return mirror_after_json_write(
        "target_profile",
        lambda conn: _write_target_profile(conn, profile_copy, path),
        operation_id=f"{base_operation_id}-reconcile-{uuid.uuid4().hex}" if force else base_operation_id,
        db_path=db_path,
        details={
            "profile_id": PROFILE_ID,
            "source_path": _source_label(path),
            "profile_hash": record_hash(profile_copy),
            "favorite_count": len(_favorite_species(profile_copy)),
        },
    )


def compare_target_profile(profile: dict[str, Any], *, db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    """Read-only drift comparison for the complete JSON profile snapshot."""
    database = Path(db_path)
    result: dict[str, Any] = {"status": "missing_in_sqlite", "differences": []}
    if not database.exists():
        result["differences"].append("SQLite database is unavailable.")
        return result

    try:
        from .connection import connect

        with connect(database, read_only=True) as conn:
            row = conn.execute("SELECT * FROM target_profiles WHERE id = ?", (PROFILE_ID,)).fetchone()
            if not row:
                result["differences"].append("Target profile mirror is missing.")
                return result
            expected = {
                "default_target_species": str(profile.get("default_target_species") or ""),
                "current_trip_target": str(profile.get("current_trip_target") or ""),
                "favorite_species_json": canonical_dumps(_favorite_species(profile)),
                "updated_at": str(profile.get("updated_at") or ""),
            }
            for key, value in expected.items():
                if str(row[key] or "") != value:
                    result["differences"].append(key)
            result["status"] = "exact" if not result["differences"] else "changed"
            return result
    except Exception as exc:
        result["status"] = "invalid_source"
        result["differences"].append(str(exc))
        return result
