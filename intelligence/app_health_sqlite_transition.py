from __future__ import annotations

import json
from pathlib import Path
from typing import Any

try:
    from intelligence.app_health_backup import get_backup_health_for_app
    from intelligence.app_health_sqlite import get_sqlite_health_for_app
except Exception:
    get_backup_health_for_app = None
    get_sqlite_health_for_app = None

APP_ROOT = Path(__file__).resolve().parents[1]
PLAN_PATH = APP_ROOT / "data" / "sqlite_authority_transition_plan_v47.json"


def _read_plan() -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    if not PLAN_PATH.exists():
        return {}, ["SQLite authority transition plan file is missing."]
    try:
        payload = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return payload, warnings
        return {}, ["SQLite authority transition plan is not a JSON object."]
    except Exception as exc:
        return {}, [f"SQLite authority transition plan could not be read: {exc}"]


def get_sqlite_transition_health_for_app() -> dict[str, Any]:
    """
    Read-only App Health readiness summary for future SQLite authority.

    v4.7 is a transition plan only. JSON remains current authority until a later
    migration release proves backup, export, rollback, and QC safety.
    """
    plan, warnings = _read_plan()
    errors: list[str] = []

    sqlite_health = get_sqlite_health_for_app() if get_sqlite_health_for_app else {}
    backup_health = get_backup_health_for_app() if get_backup_health_for_app else {}

    if plan.get("authority_switch_allowed_now") is not False:
        errors.append("Plan must keep authority_switch_allowed_now=false.")

    if plan.get("current_authority") != "json":
        errors.append("Plan must keep JSON as current authority.")

    if "mirror" not in str(plan.get("sqlite_current_role", "")).lower():
        errors.append("Plan must keep SQLite role as mirror/read-only foundation.")

    readiness = {
        "plan_exists": bool(plan),
        "sqlite_ok": bool(sqlite_health.get("ok")),
        "backup_ok": bool(backup_health.get("ok")),
        "rollback_defined": bool(plan.get("rollback_plan")),
        "export_required": any(
            "export" in str(item).lower()
            for item in plan.get("required_before_authority_switch", [])
        ),
        "authority_switch_allowed_now": bool(plan.get("authority_switch_allowed_now")),
    }

    return {
        "ok": not errors and readiness["plan_exists"],
        "summary": "SQLite authority transition planned; JSON remains current authority",
        "version": plan.get("version", "v4.7-sqlite-authority-transition-plan"),
        "json_source_of_truth": True,
        "current_authority": plan.get("current_authority", "json"),
        "target_authority": plan.get("target_authority"),
        "sqlite_role": "mirror/read-only foundation",
        "readiness": readiness,
        "required_before_authority_switch": plan.get("required_before_authority_switch", []),
        "rollback_plan": plan.get("rollback_plan", []),
        "warnings": warnings,
        "errors": errors,
    }
