#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from intelligence.sqlite_foundation import DB_PATH
from tools.app_backup import backup_status

BACKUP_ROOT = APP_ROOT / "backups"
EXPORT_TOOL = APP_ROOT / "tools" / "sqlite_export_snapshot.py"
RESTORE_TOOL = APP_ROOT / "tools" / "restore_user_data.sh"
REQUIRED_TABLES = [
    "app_meta",
    "json_sources",
    "json_documents",
    "favorites_mirror",
    "catches_mirror",
    "reports_mirror",
]


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _gate(name: str, ok: bool, summary: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "summary": summary,
        "details": details or {},
    }


def _latest_backup_path(status: dict[str, Any]) -> Path | None:
    latest = status.get("latest") or {}
    rel = latest.get("path")
    if not rel:
        return None
    path = APP_ROOT / rel
    return path if path.exists() else None


def check_backup_gate() -> dict[str, Any]:
    status = backup_status()
    latest_path = _latest_backup_path(status)
    details: dict[str, Any] = {
        "archive_count": status.get("archive_count", 0),
        "latest": status.get("latest"),
        "manifest_present": False,
        "data_present": False,
        "sqlite_present": False,
    }

    if latest_path is None:
        return _gate("backup", False, "No backup archive is available.", details)

    try:
        with zipfile.ZipFile(latest_path) as zf:
            names = set(zf.namelist())
            details["manifest_present"] = "backup_manifest.json" in names
            details["data_present"] = any(name.startswith("data/") for name in names)
            details["sqlite_present"] = "data/angler_intel.sqlite3" in names

            if "backup_manifest.json" in names:
                manifest = json.loads(zf.read("backup_manifest.json").decode("utf-8"))
                details["manifest_json_source_of_truth"] = manifest.get("json_source_of_truth")
                details["manifest_sqlite_role"] = manifest.get("sqlite_role")
    except Exception as exc:
        details["error"] = str(exc)
        return _gate("backup", False, "Latest backup archive could not be inspected.", details)

    ok = bool(details["manifest_present"] and details["data_present"])
    summary = "Latest backup contains manifest and data files." if ok else "Latest backup is missing required content."
    return _gate("backup", ok, summary, details)


def check_sqlite_gate() -> dict[str, Any]:
    details: dict[str, Any] = {
        "database": str(DB_PATH.relative_to(APP_ROOT)),
        "exists": DB_PATH.exists(),
        "required_tables": REQUIRED_TABLES,
        "tables": {},
    }
    if not DB_PATH.exists():
        return _gate("sqlite_integrity", False, "SQLite database is missing.", details)

    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        details["integrity_check"] = integrity

        existing = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        for table in REQUIRED_TABLES:
            if table in existing:
                details["tables"][table] = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            else:
                details["tables"][table] = None

        meta = {}
        if "app_meta" in existing:
            meta = {
                row["key"]: row["value"]
                for row in conn.execute("SELECT key, value FROM app_meta")
            }
        details["app_meta"] = meta
    except Exception as exc:
        details["error"] = str(exc)
        return _gate("sqlite_integrity", False, "SQLite integrity check failed to run.", details)

    missing = [table for table, count in details["tables"].items() if count is None]
    ok = details.get("integrity_check") == "ok" and not missing and details.get("app_meta", {}).get("json_source_of_truth") == "true"
    summary = "SQLite mirror integrity and source markers are valid." if ok else "SQLite mirror integrity or source markers need attention."
    return _gate("sqlite_integrity", ok, summary, details)


def check_export_gate() -> dict[str, Any]:
    details: dict[str, Any] = {
        "tool": str(EXPORT_TOOL.relative_to(APP_ROOT)),
        "exists": EXPORT_TOOL.exists(),
        "database_exists": DB_PATH.exists(),
        "export_tables": REQUIRED_TABLES,
    }
    if not EXPORT_TOOL.exists():
        return _gate("export", False, "SQLite export snapshot tool is missing.", details)
    if not DB_PATH.exists():
        return _gate("export", False, "SQLite database is missing, so export cannot be proven.", details)

    try:
        source = EXPORT_TOOL.read_text(encoding="utf-8")
        details["writes_snapshot"] = "sqlite_foundation_snapshot.json" in source
        details["uses_sqlite"] = "sqlite3" in source

        conn = sqlite3.connect(DB_PATH)
        existing = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        details["readable_tables"] = sorted(table for table in REQUIRED_TABLES if table in existing)
    except Exception as exc:
        details["error"] = str(exc)
        return _gate("export", False, "Export capability could not be inspected.", details)

    ok = bool(details["writes_snapshot"] and details["uses_sqlite"] and set(REQUIRED_TABLES).issubset(set(details["readable_tables"])))
    summary = "SQLite export snapshot path is available and mirror tables are readable." if ok else "SQLite export path is incomplete."
    return _gate("export", ok, summary, details)


def check_rollback_gate() -> dict[str, Any]:
    details: dict[str, Any] = {
        "tool": str(RESTORE_TOOL.relative_to(APP_ROOT)),
        "exists": RESTORE_TOOL.exists(),
        "pre_restore_backup": False,
        "path_safety": False,
        "allowed_roots": False,
    }
    if not RESTORE_TOOL.exists():
        return _gate("rollback", False, "Rollback restore tool is missing.", details)

    try:
        source = RESTORE_TOOL.read_text(encoding="utf-8")
        details["pre_restore_backup"] = "pre-restore" in source and "copytree" in source
        details["path_safety"] = "Unsafe path in backup" in source and '".."' in source
        details["allowed_roots"] = "allowed_roots" in source and '"data"' in source
    except Exception as exc:
        details["error"] = str(exc)
        return _gate("rollback", False, "Rollback restore tool could not be inspected.", details)

    ok = bool(details["pre_restore_backup"] and details["path_safety"] and details["allowed_roots"])
    summary = "Rollback restore script includes pre-restore backup and path checks." if ok else "Rollback restore script is missing safety checks."
    return _gate("rollback", ok, summary, details)


def collect_preflight() -> dict[str, Any]:
    gates = [
        check_backup_gate(),
        check_sqlite_gate(),
        check_export_gate(),
        check_rollback_gate(),
    ]
    ok = all(gate["ok"] for gate in gates)

    return {
        "version": "v5.0-sqlite-authority-migration",
        "checked_at": now_utc(),
        "ok": ok,
        "ready_for_authority_migration": ok,
        "authority_flipped": False,
        "current_authority": "json",
        "target_authority": "sqlite-after-explicit-migration",
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation until explicit migration",
        "migration_mode": "preflight-proof",
        "gates": gates,
        "warnings": [] if ok else ["SQLite authority remains blocked until every preflight gate passes."],
        "errors": [gate["summary"] for gate in gates if not gate["ok"]],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Angler Intel SQLite authority migration preflight")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    result = collect_preflight()
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print("=== SQLite Authority Migration Preflight v5.0 ===")
        print(f"Ready for authority migration: {result['ready_for_authority_migration']}")
        print(f"Authority flipped: {result['authority_flipped']}")
        for gate in result["gates"]:
            status = "PASS" if gate["ok"] else "FAIL"
            print(f"{status}: {gate['name']} - {gate['summary']}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
