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
from persistence.mirror import resolve_reconciliation_requests

CATCHES_FILE = ROOT / "data" / "catches.json"
REPORTS_INDEX = ROOT / "data" / "reports_index.json"
REPORTS_DIR = ROOT / "reports"
DOMAINS = ("target_profile", "gear_inventory", "manual_waters", "catches", "reports")


def reconcile_domain(domain: str, db_path: str | None = None) -> dict[str, object]:
    if domain == "target_profile":
        profile = load_target_profile()
        result = mirror_target_profile(profile, TARGET_PROFILE_PATH, db_path=db_path, force=True) if db_path else mirror_target_profile(profile, TARGET_PROFILE_PATH, force=True)
        comparison = compare_target_profile(profile, db_path=db_path) if db_path else compare_target_profile(profile)
    elif domain == "gear_inventory":
        inventory = load_inventory(); source_path = inventory_path()
        result = mirror_gear_inventory(inventory, source_path, db_path=db_path, force=True) if db_path else mirror_gear_inventory(inventory, source_path, force=True)
        comparison = compare_gear_inventory(inventory, db_path=db_path) if db_path else compare_gear_inventory(inventory)
    elif domain == "manual_waters":
        result = mirror_manual_waters(CUSTOM_WATERS_PATH, db_path=db_path, force=True) if db_path else mirror_manual_waters(CUSTOM_WATERS_PATH, force=True)
        comparison = compare_manual_waters(CUSTOM_WATERS_PATH, db_path=db_path) if db_path else compare_manual_waters(CUSTOM_WATERS_PATH)
    elif domain == "catches":
        result = mirror_catches(CATCHES_FILE, db_path=db_path, force=True) if db_path else mirror_catches(CATCHES_FILE, force=True)
        comparison = compare_catches(CATCHES_FILE, db_path=db_path) if db_path else compare_catches(CATCHES_FILE)
    else:
        result = mirror_reports(REPORTS_INDEX, REPORTS_DIR, db_path=db_path, force=True) if db_path else mirror_reports(REPORTS_INDEX, REPORTS_DIR, force=True)
        comparison = compare_reports(REPORTS_INDEX, db_path=db_path) if db_path else compare_reports(REPORTS_INDEX)
    resolved_requests = 0
    if result.mirror_write_succeeded and comparison["status"] == "exact":
        from persistence.connection import DEFAULT_DB, connect
        with connect(db_path or DEFAULT_DB) as conn, conn:
            resolved_requests = resolve_reconciliation_requests(conn, domain)
    return {"result": result.as_dict(), "comparison": comparison, "resolved_requests": resolved_requests}


def main() -> int:
    parser = argparse.ArgumentParser(description="Reconcile a supported JSON domain into its SQLite mirror")
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--domain", choices=DOMAINS)
    selection.add_argument("--all", action="store_true", help="Reconcile every supported JSON-first mirror domain")
    parser.add_argument("--db", help="Override SQLite database path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    domains = DOMAINS if args.all else (args.domain,)
    results = {domain: reconcile_domain(domain, args.db) for domain in domains}
    payload = {"domains": results, "json_authoritative": True}
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0 if all(item["result"]["mirror_write_succeeded"] and item["comparison"]["status"] == "exact" for item in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
