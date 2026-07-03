from __future__ import annotations

from typing import Any

try:
    from tools.sqlite_waterbody_preflight import collect_preflight
except Exception:
    collect_preflight = None


def get_sqlite_waterbodies_health_for_app() -> dict[str, Any]:
    """
    Read-only App Health summary for the v5.1 waterbody migration prep.

    v5.1 proves the waterbody mirror exists, matches the catalog, and is exportable
    without changing JSON authority.
    """
    if collect_preflight is None:
        return {
            "ok": False,
            "summary": "Waterbody migration preflight unavailable",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation until explicit migration",
            "current_authority": "json",
            "authority_flipped": False,
            "errors": ["Waterbody preflight tool could not be imported."],
            "warnings": [],
        }

    try:
        preflight = collect_preflight()
    except Exception as exc:
        return {
            "ok": False,
            "summary": "Waterbody migration preflight failed",
            "json_source_of_truth": True,
            "sqlite_role": "mirror/read-only foundation until explicit migration",
            "current_authority": "json",
            "authority_flipped": False,
            "errors": [str(exc)],
            "warnings": [],
        }

    preflight["summary"] = (
        "Waterbody mirror, export, and catalog counts are ready for a later migration."
        if preflight.get("ok")
        else "Waterbody migration prep needs attention before any authority change."
    )
    return preflight
