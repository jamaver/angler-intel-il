#!/usr/bin/env python3
"""Operator-triggered V7.1 reconciliation for supported JSON mirror domains."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.target_profile import TARGET_PROFILE_PATH, load_target_profile
from gear.inventory import inventory_path, load_inventory
from persistence.gear_inventory_mirror import compare_gear_inventory, mirror_gear_inventory
from persistence.target_profile_mirror import compare_target_profile, mirror_target_profile
from persistence.manual_waters_mirror import compare_manual_waters, mirror_manual_waters
from intelligence.water_registry import CUSTOM_WATERS_PATH
from persistence.catches_mirror import compare_catches, mirror_catches
from persistence.reports_mirror import compare_reports, mirror_reports

CATCHES_FILE = ROOT / "data" / "catches.json"
REPORTS_INDEX = ROOT / "data" / "reports_index.json"
REPORTS_DIR = ROOT / "reports"


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile a supported JSON domain into its SQLite mirror")
    parser.add_argument("--domain", required=True, choices=("target_profile", "gear_inventory", "manual_waters", "catches", "reports"))
    parser.add_argument("--db", help="Override SQLite database path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.domain == "target_profile":
        profile = load_target_profile()
        result = mirror_target_profile(profile, TARGET_PROFILE_PATH, db_path=args.db, force=True) if args.db else mirror_target_profile(profile, TARGET_PROFILE_PATH, force=True)
        comparison = compare_target_profile(profile, db_path=args.db) if args.db else compare_target_profile(profile)
    elif args.domain == "gear_inventory":
        inventory = load_inventory()
        source_path = inventory_path()
        result = mirror_gear_inventory(inventory, source_path, db_path=args.db, force=True) if args.db else mirror_gear_inventory(inventory, source_path, force=True)
        comparison = compare_gear_inventory(inventory, db_path=args.db) if args.db else compare_gear_inventory(inventory)
    elif args.domain == "manual_waters":
        result = mirror_manual_waters(CUSTOM_WATERS_PATH, db_path=args.db, force=True) if args.db else mirror_manual_waters(CUSTOM_WATERS_PATH, force=True)
        comparison = compare_manual_waters(CUSTOM_WATERS_PATH, db_path=args.db) if args.db else compare_manual_waters(CUSTOM_WATERS_PATH)
    elif args.domain == "catches":
        result = mirror_catches(CATCHES_FILE, db_path=args.db, force=True) if args.db else mirror_catches(CATCHES_FILE, force=True)
        comparison = compare_catches(CATCHES_FILE, db_path=args.db) if args.db else compare_catches(CATCHES_FILE)
    else:
        result = mirror_reports(REPORTS_INDEX, REPORTS_DIR, db_path=args.db, force=True) if args.db else mirror_reports(REPORTS_INDEX, REPORTS_DIR, force=True)
        comparison = compare_reports(REPORTS_INDEX, db_path=args.db) if args.db else compare_reports(REPORTS_INDEX)
    payload = {"result": result.as_dict(), "comparison": comparison, "json_authoritative": True}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if result.mirror_write_succeeded and comparison["status"] == "exact" else 1


if __name__ == "__main__":
    raise SystemExit(main())
