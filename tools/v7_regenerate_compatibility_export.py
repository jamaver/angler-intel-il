#!/usr/bin/env python3
"""Regenerate one SQLite-authoritative domain's JSON compatibility export."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.authority_resolution import require_write_authority
from persistence.catches_authority import _payload_from_database as catches_payload, save_catches_sqlite_authoritative
from persistence.gear_inventory_authority import _inventory_from_database, save_gear_inventory_sqlite_authoritative
from persistence.manual_waters_authority import _payload_from_database as waters_payload, save_manual_waters_sqlite_authoritative
from persistence.target_profile_authority import _profile_from_row, save_target_profile_sqlite_authoritative
from persistence.connection import connect


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate a V7 JSON compatibility export")
    parser.add_argument("--domain", required=True, choices=("target_profile", "gear_inventory", "manual_waters", "catches"))
    parser.add_argument("--db", default=str(ROOT / "data" / "angler_intel.sqlite3"))
    parser.add_argument("--confirm-domain", required=True)
    args = parser.parse_args()
    if args.confirm_domain != args.domain:
        parser.error("--confirm-domain must exactly match --domain")
    db = Path(args.db)
    if require_write_authority(args.domain, db) != "sqlite":
        raise SystemExit("Selected domain is not SQLite-authoritative and writable")
    if args.domain == "target_profile":
        with connect(db, read_only=True) as conn:
            row = conn.execute("SELECT * FROM target_profiles WHERE id = 'current'").fetchone()
        if not row:
            raise SystemExit("SQLite target profile is missing")
        save_target_profile_sqlite_authoritative(_profile_from_row(row), db, ROOT / "data" / "target_profile.json")
    elif args.domain == "gear_inventory":
        save_gear_inventory_sqlite_authoritative(_inventory_from_database(db), db, ROOT / "data" / "gear_inventory.json")
    elif args.domain == "manual_waters":
        save_manual_waters_sqlite_authoritative(waters_payload(db), db, ROOT / "data" / "manual_waters.json")
    else:
        save_catches_sqlite_authoritative(catches_payload(db), db, ROOT / "data" / "catches.json")
    print(f"Compatibility export regenerated for {args.domain}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
