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
from persistence.migrations import migrate
from persistence.target_profile_authority import activate_target_profile_authority
from persistence.gear_inventory_authority import activate_gear_inventory_authority
from persistence.manual_waters_authority import activate_manual_waters_authority
from persistence.catches_authority import activate_catches_authority

DOMAINS = ("target_profile", "gear_inventory", "manual_waters", "catches", "reports", "recommendations")
REGISTERED_TRANSITIONS = {"target_profile", "gear_inventory", "manual_waters", "catches"}


def preflight(domain: str, backup_manifest: Path, db: Path, source_root: Path, reports_root: Path) -> dict[str, object]:
    errors: list[str] = []
    manifest: dict[str, object] = {}
    try:
        manifest = json.loads(backup_manifest.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Backup manifest is unreadable: {exc}")
    if manifest and not manifest.get("verified"):
        errors.append("Backup manifest has not completed verification.")
    if manifest and not isinstance(manifest.get("authority"), dict):
        errors.append("Backup manifest does not include per-domain authority coverage.")
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
    # `ok` covers record parity and SQLite integrity.  A warning status still
    # represents unresolved/invalid/orphan references that need an explicit
    # operator decision before a future authority transition.  Never present
    # that state as transition-ready merely because all source rows mirrored.
    if validation.get("status") != "ok":
        errors.append("Validation contains unresolved warning entries; remediate or explicitly classify them before transition.")
    legacy_reference_warnings = [
        diff for diff in validation.get("diffs", [])
        if isinstance(diff, dict) and diff.get("status") in {"unmapped_reference", "orphan_reference", "invalid_source"}
    ]
    return {
        "domain": domain,
        "backup_manifest": str(backup_manifest),
        "backup_verified": bool(manifest),
        "authority_before": authority,
        "integrity_check": integrity,
        "foreign_key_check": foreign_keys,
        "validation_ok": bool(validation.get("ok")),
        "validation_status": validation.get("status"),
        "validation_totals": validation.get("totals", {}),
        "legacy_reference_warning_count": len(legacy_reference_warnings),
        "legacy_reference_warning_domains": sorted({str(item.get("domain")) for item in legacy_reference_warnings}),
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
        if args.domain not in REGISTERED_TRANSITIONS:
            result["errors"].append("No authority-changing contract is registered for this domain; authority remains JSON.")
        elif result["ready"] and args.confirm_domain == args.domain and args.execute:
            try:
                with connect(Path(args.db)) as conn:
                    migrate(conn, db_path=str(args.db))
                if args.domain == "target_profile":
                    exported = activate_target_profile_authority(Path(args.db), Path(args.source_root) / "target_profile.json")
                elif args.domain == "gear_inventory":
                    exported = activate_gear_inventory_authority(Path(args.db), Path(args.source_root) / "gear_inventory.json")
                elif args.domain == "manual_waters":
                    exported = activate_manual_waters_authority(Path(args.db), Path(args.source_root) / "manual_waters.json")
                elif args.domain == "catches":
                    exported = activate_catches_authority(Path(args.db), Path(args.source_root) / "catches.json")
                else:
                    raise ValueError(f"No authority activation implementation for {args.domain}")
                result["transitioned"] = True
                result["authority_after"] = "sqlite"
                result["sqlite_authority_enabled"] = True
                result["exported_record"] = exported
            except Exception as exc:
                result["errors"].append(f"{args.domain} transition failed: {exc}")
        result["ready"] = not result["errors"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
