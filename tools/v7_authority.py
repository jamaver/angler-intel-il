#!/usr/bin/env python3
"""Operator-only authority-transition preflight for future V7.3 domains.

V7.3.0 intentionally has no registered authority-changing domain. This command
provides repeatable gates and explicit refusal output; later V7.3.x tasks add
one domain implementation at a time.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.validation import validate_database

DOMAINS = ("target_profile", "gear_inventory", "manual_waters", "catches", "reports", "recommendations")


def preflight(domain: str, backup_manifest: Path, db: Path, source_root: Path, reports_root: Path) -> dict[str, object]:
    errors: list[str] = []
    manifest: dict[str, object] = {}
    try:
        manifest = json.loads(backup_manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Backup manifest is unreadable: {exc}")
    if manifest and not manifest.get("json_source_of_truth"):
        errors.append("Backup manifest does not confirm JSON source-of-truth coverage.")
    if not db.exists():
        errors.append(f"SQLite database is unavailable: {db}")

    authority = None; integrity = None; foreign_keys: list[object] = []
    if db.exists():
        try:
            with connect(db, read_only=True) as conn:
                row = conn.execute("SELECT authority FROM data_authority WHERE domain = ?", (domain,)).fetchone()
                authority = row["authority"] if row else "json"
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                foreign_keys = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
            if integrity != "ok": errors.append(f"SQLite integrity_check returned {integrity!r}.")
            if foreign_keys: errors.append("SQLite foreign_key_check returned violations.")
            if authority != "json": errors.append(f"Expected JSON authority before transition, found {authority!r}.")
        except Exception as exc:
            errors.append(f"SQLite preflight failed: {exc}")

    validation = validate_database(db, source_root=source_root, reports_root=reports_root) if db.exists() else {"ok": False, "totals": {}}
    if not validation.get("ok"):
        errors.append("Canonical JSON/SQLite drift validation did not pass.")
    return {
        "domain": domain,
        "backup_manifest": str(backup_manifest),
        "backup_verified": bool(manifest),
        "authority_before": authority,
        "integrity_check": integrity,
        "foreign_key_check": foreign_keys,
        "validation_ok": bool(validation.get("ok")),
        "validation_totals": validation.get("totals", {}),
        "ready": not errors,
        "errors": errors,
        "sqlite_authority_enabled": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="V7.3 operator-only authority-transition gates")
    parser.add_argument("action", choices=("preflight", "transition"))
    parser.add_argument("--domain", required=True, choices=DOMAINS)
    parser.add_argument("--backup-manifest", required=True)
    parser.add_argument("--db", default=str(ROOT / "data" / "angler_intel.sqlite3"))
    parser.add_argument("--source-root", default=str(ROOT / "data"))
    parser.add_argument("--reports-root", default=str(ROOT / "reports"))
    parser.add_argument("--confirm-domain", help="Must exactly match --domain for a future transition")
    parser.add_argument("--execute", action="store_true", help="Request transition after preflight; V7.3.0 refuses this safely")
    args = parser.parse_args()
    result = preflight(args.domain, Path(args.backup_manifest), Path(args.db), Path(args.source_root), Path(args.reports_root))
    if args.action == "transition":
        if args.confirm_domain != args.domain:
            result["errors"].append("--confirm-domain must exactly match --domain.")
        if not args.execute:
            result["errors"].append("Transition is dry-run only until --execute is supplied.")
        # No V7.3.x domain writer contract is registered by V7.3.0.
        result["errors"].append("No authority-changing domain is registered in V7.3.0; authority remains JSON.")
        result["ready"] = False
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ready") and args.action == "preflight" else 2


if __name__ == "__main__":
    raise SystemExit(main())
