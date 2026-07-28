"""SQLite-authoritative custom-water contract for V7.3.3 only."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps
from .connection import DEFAULT_DB, connect
from .manual_waters_mirror import MANUAL_WATERS_ENVELOPE_KEY, _write_manual_waters, _utc_now

EXPORT_STATUS_KEY = "v7.manual_waters.compatibility_export"


def _prepare_json_export(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".v7-export.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return temporary


def _set_export_status(conn, status: str, *, error: str | None = None) -> None:
    conn.execute(
        """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
        (EXPORT_STATUS_KEY, canonical_dumps({"domain": "manual_waters", "status": status, "error": error}), _utc_now()),
    )


def is_manual_waters_sqlite_authoritative(db_path: str | Path = DEFAULT_DB) -> bool:
    database = Path(db_path)
    if not database.exists():
        return False
    try:
        with connect(database, read_only=True) as conn:
            row = conn.execute("SELECT authority FROM data_authority WHERE domain = 'manual_waters'").fetchone()
            return bool(row and row["authority"] == "sqlite")
    except Exception:
        return False


def _payload_from_database(db_path: str | Path) -> Any:
    with connect(db_path, read_only=True) as conn:
        row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (MANUAL_WATERS_ENVELOPE_KEY,)).fetchone()
    if not row:
        raise ValueError("SQLite manual-water envelope is missing")
    return json.loads(row["value_json"] or "[]")


def _write_sqlite_first(payload: Any, db_path: str | Path, json_path: Path) -> Any:
    temporary = _prepare_json_export(json_path, payload)
    try:
        with connect(db_path) as conn:
            with conn:
                _write_manual_waters(conn, payload, json_path, authority="sqlite", update_catalog_snapshot=False)
                _set_export_status(conn, "pending")
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    try:
        temporary.replace(json_path)
    except Exception as exc:
        with connect(db_path) as conn:
            with conn:
                _set_export_status(conn, "failed", error=str(exc))
        raise
    with connect(db_path) as conn:
        with conn:
            _set_export_status(conn, "ok")
    return payload


def activate_manual_waters_authority(db_path: str | Path, json_path: str | Path) -> Any:
    path = Path(json_path)
    try:
        payload = _payload_from_database(db_path)
    except ValueError:
        # Older V7.1 mirrors did not retain a standalone custom-water envelope.
        # At activation time JSON is still authoritative, so it is the only
        # safe compatibility source for seeding that envelope.
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return _write_sqlite_first(payload, db_path, path)


def save_manual_waters_sqlite_authoritative(payload: Any, db_path: str | Path, json_path: str | Path) -> Any:
    return _write_sqlite_first(payload, db_path, Path(json_path))
