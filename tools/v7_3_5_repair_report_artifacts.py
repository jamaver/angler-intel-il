#!/usr/bin/env python3
"""Regenerate report JSON/HTML artifacts from an SQLite report snapshot."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import angler_reports_v38 as reports
from app import app as flask_app
from persistence.reports_authority import repair_report_artifacts


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-id", required=True)
    parser.add_argument("--db", default=str(ROOT / "data" / "angler_intel.sqlite3"))
    parser.add_argument("--confirm", action="store_true", help="Confirm writing compatibility artifacts")
    args = parser.parse_args()
    if not args.confirm:
        raise SystemExit("Refusing to write artifacts without --confirm")
    with flask_app.app_context():
        result = repair_report_artifacts(
            args.report_id, render_html=reports._render_report_html, db_path=args.db,
            index_path=reports.INDEX_PATH, reports_dir=reports.REPORTS_DIR,
        )
    print(result.response_meta())
    return 0 if not result.warning else 1


if __name__ == "__main__":
    raise SystemExit(main())
