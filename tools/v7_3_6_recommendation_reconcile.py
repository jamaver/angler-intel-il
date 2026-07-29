#!/usr/bin/env python3
"""Reconcile report-backed recommendation history before V7.3.6 cutover."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.recommendations_authority import (
    recommendation_transition_preflight,
    reconcile_authoritative_report_recommendations,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=str(ROOT / "data" / "angler_intel.sqlite3"))
    parser.add_argument("--apply", action="store_true", help="Confirm SQLite-only recommendation reconciliation")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if not args.apply:
        raise SystemExit("Refusing reconciliation without --apply")
    with connect(args.db) as conn:
        migrate(conn, db_path=str(args.db))
    result = reconcile_authoritative_report_recommendations(args.db)
    result["preflight"] = recommendation_transition_preflight(args.db)
    print(json.dumps(result, indent=2, sort_keys=True) if args.json else result)
    return 0 if result["ok"] and result["preflight"].get("ready") else 1


if __name__ == "__main__":
    raise SystemExit(main())
