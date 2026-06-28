from __future__ import annotations

from typing import Any

try:
    from tools.app_backup import backup_status
except Exception:
    backup_status = None


def get_backup_health_for_app() -> dict[str, Any]:
    """
    Read-only backup status for App Health.

    Creating backups should remain an explicit maintenance action.
    This helper only reports current backup health/status.
    """
    if backup_status is None:
        return {
            "ok": False,
            "available": False,
            "summary": "Backup status unavailable",
            "errors": ["Backup tool could not be imported."],
            "json_source_of_truth": True,
        }

    try:
        status = backup_status()
    except Exception as exc:
        return {
            "ok": False,
            "available": False,
            "summary": "Backup status failed",
            "errors": [str(exc)],
            "json_source_of_truth": True,
        }

    latest = status.get("latest")
    archive_count = int(status.get("archive_count", 0))

    return {
        "ok": archive_count > 0,
        "available": True,
        "summary": "Backups available" if archive_count > 0 else "No full backups created yet",
        "archive_count": archive_count,
        "latest": latest,
        "recent": status.get("recent", []),
        "backup_root": status.get("backup_root"),
        "json_source_of_truth": True,
        "sqlite_role": status.get("sqlite_role", "mirror/read-only foundation"),
    }
