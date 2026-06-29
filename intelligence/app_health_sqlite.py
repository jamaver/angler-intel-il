from __future__ import annotations

from typing import Any

try:
    from tools.sqlite_diagnostics import collect_diagnostics
except Exception:  # defensive import safety for Flask startup
    collect_diagnostics = None


def get_sqlite_health_for_app() -> dict[str, Any]:
    """
    Read-only SQLite health summary for App Health.

    Important:
    - JSON remains the source of truth.
    - SQLite is still a mirror/foundation layer.
    - This helper should not make Flask depend on SQLite being perfect.
    """
    if collect_diagnostics is None:
        return {
            "ok": False,
            "available": False,
            "summary": "SQLite diagnostics unavailable",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": ["Diagnostics module could not be imported."],
        }

    try:
        diagnostics = collect_diagnostics()
    except Exception as exc:
        return {
            "ok": False,
            "available": False,
            "summary": "SQLite diagnostics failed",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": [str(exc)],
        }

    table_counts = diagnostics.get("tables", {})
    sources = diagnostics.get("sources", [])

    return {
        "ok": bool(diagnostics.get("ok")),
        "available": bool(diagnostics.get("database_exists")),
        "summary": "SQLite mirror healthy" if diagnostics.get("ok") else "SQLite mirror needs attention",
        "database": diagnostics.get("database"),
        "database_size_bytes": diagnostics.get("database_size_bytes"),
        "integrity_check": diagnostics.get("integrity_check"),
        "journal_mode": diagnostics.get("journal_mode"),
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "table_counts": table_counts,
        "sources": sources,
        "errors": diagnostics.get("errors", []),
        "warnings": diagnostics.get("warnings", []),
        "checked_at": diagnostics.get("checked_at"),
    }
