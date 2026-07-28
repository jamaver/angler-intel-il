"""SQLite-authoritative catch-log contract for V7.3.4.

The legacy JSON document remains a byte-compatible compatibility export.  All
SQLite-first writes use the complete catch envelope so older catch-learning
and report code can continue reading the same shape during the transition.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .canonical_json import canonical_dumps
from .catches_mirror import CATCHES_ENVELOPE_KEY, _utc_now, _write_catches
from .connection import DEFAULT_DB, connect

EXPORT_STATUS_KEY = "v7.catches.compatibility_export"


def _prepare_json_export(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".v7-export.tmp")
    temporary.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return temporary


def _set_export_status(conn, status: str, *, error: str | None = None) -> None:
    conn.execute(
        """INSERT INTO app_settings(key, value_json, updated_at) VALUES(?, ?, ?)
           ON CONFLICT(key) DO UPDATE SET value_json=excluded.value_json, updated_at=excluded.updated_at""",
        (EXPORT_STATUS_KEY, canonical_dumps({"domain": "catches", "status": status, "error": error}), _utc_now()),
    )


def is_catches_sqlite_authoritative(db_path: str | Path = DEFAULT_DB) -> bool:
    database = Path(db_path)
    if not database.exists():
        return False
    try:
        with connect(database, read_only=True) as conn:
            row = conn.execute("SELECT authority FROM data_authority WHERE domain = 'catches'").fetchone()
            return bool(row and row["authority"] == "sqlite")
    except Exception:
        return False


def _payload_from_database(db_path: str | Path) -> Any:
    with connect(db_path, read_only=True) as conn:
        row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (CATCHES_ENVELOPE_KEY,)).fetchone()
    if not row:
        raise ValueError("SQLite catches envelope is missing")
    payload = json.loads(row["value_json"] or "[]")
    if not isinstance(payload, (list, dict)):
        raise ValueError("SQLite catches envelope is invalid")
    return payload


def _write_sqlite_first(
    payload: Any,
    db_path: str | Path,
    json_path: Path,
    *,
    usage_events: list[dict[str, Any]] | None = None,
) -> Any:
    temporary = _prepare_json_export(json_path, payload)
    try:
        with connect(db_path) as conn:
            with conn:
                _write_catches(conn, payload, json_path, usage_events, authority="sqlite")
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


def activate_catches_authority(db_path: str | Path, json_path: str | Path) -> Any:
    path = Path(json_path)
    try:
        payload = _payload_from_database(db_path)
    except ValueError:
        payload = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    return _write_sqlite_first(payload, db_path, path)


def save_catches_sqlite_authoritative(
    catches: Any,
    db_path: str | Path,
    json_path: str | Path,
    *,
    usage_events: list[dict[str, Any]] | None = None,
) -> Any:
    return _write_sqlite_first(catches, db_path, Path(json_path), usage_events=usage_events)
