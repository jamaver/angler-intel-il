#!/usr/bin/env python3
"""Hydrate legacy report snapshots in SQLite before V7.3.5e transition."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.reports_authority import reconcile_legacy_report_snapshots, report_transition_preflight


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "angler_intel.sqlite3"))
    parser.add_argument("--index", default=str(ROOT / "data" / "reports_index.json"))
    parser.add_argument("--reports", default=str(ROOT / "reports"))
    parser.add_argument("--apply", action="store_true", help="Confirm SQLite-only snapshot hydration")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("Refusing reconciliation without --apply")
    result = reconcile_legacy_report_snapshots(db_path=args.db, index_path=args.index, reports_dir=args.reports)
    result["preflight"] = report_transition_preflight(args.db)
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result)
    return 0 if result["ok"] and result["preflight"].get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
