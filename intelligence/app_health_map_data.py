from __future__ import annotations

from typing import Any

try:
    from intelligence.map_data import get_map_data_readiness
except Exception:
    get_map_data_readiness = None


def get_map_data_health_for_app() -> dict[str, Any]:
    """Read-only App Health summary for map data readiness."""
    if get_map_data_readiness is None:
        return {
            "ok": False,
            "summary": "Map data readiness unavailable",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": ["Map data helper could not be imported."],
            "warnings": [],
        }

    try:
        readiness = get_map_data_readiness()
    except Exception as exc:
        return {
            "ok": False,
            "summary": "Map data readiness failed",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation",
            "errors": [str(exc)],
            "warnings": [],
        }

    return {
        "ok": bool(readiness.get("ok")),
        "summary": "Map data ready for prototype" if readiness.get("ok") else "Map data needs attention",
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "map_dashboard_planned": True,
        "record_count": readiness.get("record_count", 0),
        "source_path": readiness.get("source_path"),
        "bounds": readiness.get("bounds"),
        "missing_coords": readiness.get("missing_coords", []),
        "missing_species_ids": readiness.get("missing_species_ids", []),
        "unknown_species_ids": readiness.get("unknown_species_ids", []),
        "warnings": readiness.get("warnings", []),
        "errors": [],
    }
