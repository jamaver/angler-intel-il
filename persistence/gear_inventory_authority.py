"""SQLite-authoritative Gear Locker contract for V7.3.2 only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps, record_hash
from .provenance import file_sha256
from .connection import DEFAULT_DB, connect
from .gear_inventory_mirror import INVENTORY_ENVELOPE_KEY, _write_inventory, _utc_now

EXPORT_STATUS_KEY = "v7.gear_inventory.compatibility_export"


def _prepare_json_export(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".v7-export.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return temporary


def _commit_json_export(temporary: Path, path: Path) -> None:
    temporary.replace(path)


def _set_export_status(conn, status: str, *, error: str | None = None, authoritative_payload_hash: str | None = None, compatibility_export_hash: str | None = None) -> None:
    conn.execute(
        """
        INSERT INTO app_settings(key, value_json, updated_at)
        VALUES(?, ?, ?)
        ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at
        """,
        (EXPORT_STATUS_KEY, canonical_dumps({"domain": "gear_inventory", "status": status, "error": error, "authoritative_payload_hash": authoritative_payload_hash, "compatibility_export_hash": compatibility_export_hash, "compatibility_exported_at": _utc_now() if status == "ok" else None}), _utc_now()),
    )


def is_gear_inventory_sqlite_authoritative(db_path: str | Path = DEFAULT_DB) -> bool:
    database = Path(db_path)
    if not database.exists():
        return False
    try:
        with connect(database, read_only=True) as conn:
            row = conn.execute("SELECT authority FROM data_authority WHERE domain = 'gear_inventory'").fetchone()
            return bool(row and row["authority"] == "sqlite")
    except Exception:
        return False


def _inventory_from_database(db_path: str | Path) -> dict[str, Any]:
    with connect(db_path, read_only=True) as conn:
        row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (INVENTORY_ENVELOPE_KEY,)).fetchone()
    if not row:
        raise ValueError("SQLite gear inventory envelope is missing")
    payload = json.loads(row["value_json"] or "{}")
    if not isinstance(payload, dict):
        raise ValueError("SQLite gear inventory envelope is invalid")
    return payload


def export_gear_inventory(db_path: str | Path, json_path: str | Path) -> dict[str, Any]:
    json_path = Path(json_path)
    inventory = _inventory_from_database(db_path)
    temporary = _prepare_json_export(json_path, inventory)
    try:
        _commit_json_export(temporary, json_path)
    except Exception as exc:
        with connect(db_path) as conn:
            with conn:
                _set_export_status(conn, "failed", error=str(exc))
        return inventory
    with connect(db_path) as conn:
        with conn:
            _set_export_status(conn, "ok")
    return inventory


def _write_sqlite_first(
    inventory: dict[str, Any],
    db_path: str | Path,
    json_path: Path,
    *,
    usage_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    temporary = _prepare_json_export(json_path, inventory)
    try:
        with connect(db_path) as conn:
            with conn:
                _write_inventory(conn, inventory, json_path, usage_event, authority="sqlite")
                _set_export_status(conn, "pending", authoritative_payload_hash=record_hash(inventory))
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    try:
        _commit_json_export(temporary, json_path)
    except Exception as exc:
        with connect(db_path) as conn:
            with conn:
                _set_export_status(conn, "failed", error=str(exc), authoritative_payload_hash=record_hash(inventory))
        return inventory
    with connect(db_path) as conn:
        with conn:
            _set_export_status(conn, "ok", authoritative_payload_hash=record_hash(inventory), compatibility_export_hash=file_sha256(json_path))
    return inventory


def activate_gear_inventory_authority(db_path: str | Path, json_path: str | Path) -> dict[str, Any]:
    """Transition a reconciled gear envelope after external preflight gates pass."""
    inventory = _inventory_from_database(db_path)
    return _write_sqlite_first(inventory, db_path, Path(json_path))


def save_gear_inventory_sqlite_authoritative(
    inventory: dict[str, Any],
    db_path: str | Path,
    json_path: str | Path,
    *,
    usage_event: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist complete Gear Locker state in SQLite, then refresh JSON compatibility."""
    return _write_sqlite_first(inventory, db_path, Path(json_path), usage_event=usage_event)
