from __future__ import annotations

from typing import Any

try:
    from tools.sqlite_authority_preflight import collect_preflight
except Exception:
    collect_preflight = None


def get_sqlite_authority_health_for_app() -> dict[str, Any]:
    """
    Read-only App Health summary for the v5.0 SQLite authority migration gate.

    v5.0 proves backup, export, and rollback readiness. It does not flip the app
    from JSON authority to SQLite authority.
    """
    if collect_preflight is None:
        return {
            "ok": False,
            "summary": "SQLite authority migration preflight unavailable",
            "ready_for_authority_migration": False,
            "authority_flipped": False,
            "current_authority": "json",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation until explicit migration",
            "errors": ["Preflight tool could not be imported."],
            "warnings": [],
        }

    try:
        preflight = collect_preflight()
    except Exception as exc:
        return {
            "ok": False,
            "summary": "SQLite authority migration preflight failed",
            "ready_for_authority_migration": False,
            "authority_flipped": False,
            "current_authority": "json",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation until explicit migration",
            "errors": [str(exc)],
            "warnings": [],
        }

    preflight["summary"] = (
        "Backup, export, and rollback gates are proven; authority switch still requires an explicit migration."
        if preflight.get("ok")
        else "SQLite authority migration remains blocked until safety gates pass."
    )
    return preflight
