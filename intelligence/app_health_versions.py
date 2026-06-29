from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = APP_ROOT / "data"


def _parse_installed_at(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        text = str(value)
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text)
    except Exception:
        return None


def _marker_sort_key(marker: dict[str, Any]) -> tuple[int, float]:
    installed = _parse_installed_at(marker.get("installed_at"))
    if installed is not None:
        return (1, installed.timestamp())
    return (0, float(marker.get("mtime", 0)))


def _safe_marker_summary(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"{path.name} could not be read as JSON: {exc}"

    if not isinstance(payload, dict):
        return None, f"{path.name} is not a JSON object"

    marker = {
        "file": str(path.relative_to(APP_ROOT)),
        "version": payload.get("version") or path.stem.replace("version_", ""),
        "installed_at": payload.get("installed_at"),
        "json_source_of_truth": payload.get("json_source_of_truth"),
        "sqlite_role": payload.get("sqlite_role"),
        "app_health_maintenance_hub": payload.get("app_health_maintenance_hub"),
        "admin_expanded": payload.get("admin_expanded"),
        "admin_menu_restored": payload.get("admin_menu_restored"),
        "mtime": path.stat().st_mtime,
    }
    return marker, None


def get_version_health_for_app() -> dict[str, Any]:
    """
    Read-only version marker summary for App Health.

    JSON marker files remain the source for this maintenance ledger.
    SQLite remains a mirror/read-only foundation.
    """
    warnings: list[str] = []
    errors: list[str] = []
    markers: list[dict[str, Any]] = []

    try:
        paths = sorted(DATA_DIR.glob("version_*.json"))
    except Exception as exc:
        paths = []
        errors.append(f"Could not list version markers: {exc}")

    for path in paths:
        marker, warning = _safe_marker_summary(path)
        if warning:
            warnings.append(warning)
            continue
        if marker is not None:
            markers.append(marker)

    markers.sort(key=_marker_sort_key, reverse=True)
    latest = markers[0] if markers else None

    if not markers:
        errors.append("No version marker files found.")

    return {
        "ok": bool(markers) and not errors,
        "latest": latest,
        "recent": markers[:8],
        "marker_count": len(markers),
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "warnings": warnings,
        "errors": errors,
    }
