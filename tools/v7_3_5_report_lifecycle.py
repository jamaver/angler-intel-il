#!/usr/bin/env python3
"""Operator-only SQLite report soft-delete and restore utility."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app as flask_app
import angler_reports_v38 as reports
from persistence.reports_authority import restore_authoritative_report, soft_delete_all_authoritative_reports, soft_delete_authoritative_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--delete")
    actions.add_argument("--restore")
    actions.add_argument("--delete-all", action="store_true")
    parser.add_argument("--db", default=str(ROOT / "data" / "angler_intel.sqlite3"))
    parser.add_argument("--confirm", action="store_true", help="Confirm changing authoritative report lifecycle state")
    args = parser.parse_args()
    if not args.confirm:
        raise SystemExit("Refusing lifecycle change without --confirm")
    kwargs = {"db_path": args.db, "index_path": reports.INDEX_PATH, "reports_dir": reports.REPORTS_DIR}
    if args.delete:
        result = soft_delete_authoritative_report(args.delete, **kwargs)
    elif args.delete_all:
        result = soft_delete_all_authoritative_reports(**kwargs)
    else:
        with flask_app.app_context():
            result = restore_authoritative_report(args.restore, render_html=reports._render_report_html, **kwargs)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
