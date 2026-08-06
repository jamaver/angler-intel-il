from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from persistence.connection import connect
from persistence.authority import default_authority_map
from persistence.authority import V7_DOMAINS
from persistence.authority_manifest import manifest_path, read_manifest
from persistence.authority_resolution import resolve_authority
from persistence.mirror import get_mirror_status, get_reconciliation_summary
from persistence.runtime_paths import resolve_runtime_path
from persistence.legacy_references import decision_summary, unresolved_references
from intelligence.target_profile import get_target_profile_read_diagnostics

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backups"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _latest_row(conn, query: str) -> dict[str, Any] | None:
    try:
        row = conn.execute(query).fetchone()
        return dict(row) if row else None
    except Exception:
        return None


def _authority_rows(conn) -> list[dict[str, Any]]:
    try:
        rows = [dict(row) for row in conn.execute("SELECT domain, authority, source_path, source_hash, updated_at FROM data_authority ORDER BY domain")]
        if rows:
            return rows
    except Exception:
        pass
    return list(default_authority_map().values())


def _runtime_conflicts() -> list[dict[str, Any]]:
    domains = {
        "gear_inventory": DATA_DIR / "gear_inventory.json",
        "manual_waters": DATA_DIR / "manual_waters.json",
        "target_profile": DATA_DIR / "target_profile.json",
        "gear_settings": DATA_DIR / "gear_settings.json",
        "catches": DATA_DIR / "catches.json",
        "favorites": DATA_DIR / "favorites.json",
        "reports_index": DATA_DIR / "reports_index.json",
        "sqlite": DATA_DIR / "angler_intel.sqlite3",
    }
    conflicts: list[dict[str, Any]] = []
    for domain, legacy_path in domains.items():
        resolved = resolve_runtime_path(domain, legacy_path=legacy_path, repo_default=legacy_path)
        if resolved.conflict:
            conflicts.append(
                {
                    "domain": domain,
                    "resolved_path": str(resolved.path),
                    "conflict_paths": resolved.conflict_paths,
                }
            )
    return conflicts


def _mirror_summary(rows: list[dict[str, Any]]) -> dict[str, int]:
    summary: dict[str, int] = {}
    for row in rows:
        status = str(row.get("status") or "unknown")
        summary[status] = summary.get(status, 0) + 1
    return summary


def _legacy_reference_summary(conn) -> dict[str, Any]:
    try:
        rows = unresolved_references(conn)
        by_relationship: dict[str, int] = {}
        for row in rows:
            relationship = str(row.get("relationship") or "unknown")
            by_relationship[relationship] = by_relationship.get(relationship, 0) + 1
        return {"available": True, "total": len(rows), "by_relationship": by_relationship, "decisions": decision_summary(conn)}
    except Exception as exc:
        return {"available": False, "total": 0, "by_relationship": {}, "decisions": {}, "error": str(exc)}


def get_v7_health_for_app() -> dict[str, Any]:
    db_path = DATA_DIR / "angler_intel.sqlite3"
    payload: dict[str, Any] = {
        "ok": False,
        "available": False,
        "database": str(db_path),
        "schema_version": None,
        "current_authority": "json",
        "authorities": list(default_authority_map().values()),
        "last_migration_run": None,
        "last_validation_run": None,
        "validation_drift": {},
        "integrity_check": None,
        "foreign_key_check": [],
        "latest_verified_backup": None,
        "runtime_path_conflicts": _runtime_conflicts(),
        "mirror_status": [],
        "mirror_summary": {},
        "reconciliation_summary": {"pending": [], "pending_total": 0, "stale": [], "stale_total": 0},
        "legacy_reference_summary": {"available": False, "total": 0, "by_relationship": {}, "decisions": {}},
        "target_profile_read": get_target_profile_read_diagnostics(),
        "warnings": [],
        "errors": [],
        "authority_manifest": {"path": str(manifest_path()), "error": None, "domains": {}},
        "authority_resolutions": [],
        "compatibility_exports": {},
        "report_artifact_repair": {},
        "report_read_fallback": {},
        "report_lifecycle": {},
        "recommendation_adherence": {},
    }

    manifest, manifest_error = read_manifest()
    payload["authority_manifest"] = {"path": str(manifest_path()), "error": manifest_error, "domains": (manifest or {}).get("domains", {})}
    payload["authority_resolutions"] = [asdict(resolve_authority(domain, db_path)) for domain in V7_DOMAINS]

    if not db_path.exists():
        payload["warnings"].append("SQLite database not available yet.")
        return payload

    payload["available"] = True
    try:
        with connect(db_path, read_only=True) as conn:
            payload["schema_version"] = conn.execute("PRAGMA user_version").fetchone()[0]
            try:
                payload["integrity_check"] = conn.execute("PRAGMA integrity_check").fetchone()[0]
            except Exception as exc:
                payload["warnings"].append(f"integrity_check unavailable: {exc}")
            try:
                payload["foreign_key_check"] = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
            except Exception as exc:
                payload["warnings"].append(f"foreign_key_check unavailable: {exc}")

            authority_rows = _authority_rows(conn)
            payload["authorities"] = authority_rows
            if authority_rows:
                values = {str(row.get("authority") or "json") for row in authority_rows}
                payload["current_authority"] = values.pop() if len(values) == 1 else "mixed"

            payload["last_migration_run"] = _latest_row(
                conn,
                "SELECT run_at, mode, status, details_json FROM migration_runs ORDER BY id DESC LIMIT 1",
            )
            payload["last_validation_run"] = _latest_row(
                conn,
                "SELECT run_at, mode, status, summary_json FROM validation_runs ORDER BY id DESC LIMIT 1",
            )
            latest_validation = payload["last_validation_run"] or {}
            try:
                summary = json.loads(latest_validation.get("summary_json") or "{}")
                payload["validation_drift"] = summary.get("totals", {}) if isinstance(summary, dict) else {}
            except Exception:
                payload["validation_drift"] = {}
            payload["mirror_status"] = get_mirror_status(conn)
            payload["mirror_summary"] = _mirror_summary(payload["mirror_status"])
            payload["reconciliation_summary"] = get_reconciliation_summary(conn)
            payload["legacy_reference_summary"] = _legacy_reference_summary(conn)
            for domain in ("target_profile", "gear_inventory", "manual_waters", "catches", "reports"):
                row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (f"v7.{domain}.compatibility_export",)).fetchone()
                if row:
                    try:
                        payload["compatibility_exports"][domain] = json.loads(row["value_json"] or "{}")
                    except Exception:
                        payload["compatibility_exports"][domain] = {"status": "invalid"}
            for key, destination in (("v7.reports.artifact_repair", "report_artifact_repair"), ("v7.reports.read_fallback", "report_read_fallback"), ("v7.reports.deletion", "report_lifecycle")):
                row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", (key,)).fetchone()
                if row:
                    try:
                        payload[destination] = json.loads(row["value_json"] or "{}")
                    except Exception:
                        payload[destination] = {"status": "invalid"}
            row = conn.execute("SELECT value_json FROM app_settings WHERE key = ?", ("v7.recommendations.adherence",)).fetchone()
            if row:
                try:
                    payload["recommendation_adherence"] = json.loads(row["value_json"] or "{}")
                except Exception:
                    payload["recommendation_adherence"] = {"status": "invalid"}
    except Exception as exc:
        payload["errors"].append(str(exc))

    backup_manifest = BACKUP_DIR / "latest_v7_runtime_backup_manifest.json"
    if backup_manifest.exists():
        payload["latest_verified_backup"] = _read_json(backup_manifest)
    elif (BACKUP_DIR / "latest_backup_manifest.json").exists():
        payload["latest_verified_backup"] = _read_json(BACKUP_DIR / "latest_backup_manifest.json")

    payload["ok"] = bool(payload["available"]) and not payload["errors"]
    payload["target_profile_read"] = get_target_profile_read_diagnostics()
    return payload
