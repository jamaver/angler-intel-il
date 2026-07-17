#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.validation import record_validation_results, validate_database


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate V7 JSON to SQLite drift")
    parser.add_argument("--db", default=str(ROOT / "data" / "angler_intel.sqlite3"), help="SQLite database path")
    parser.add_argument("--source-root", default=str(ROOT / "data"), help="Source JSON root")
    parser.add_argument("--reports-root", default=str(ROOT / "reports"), help="Reports directory")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    parser.add_argument("--output", help="Write JSON to PATH")
    parser.add_argument("--strict", action="store_true", help="Exit nonzero on drift")
    parser.add_argument("--no-record", action="store_true", help="Do not persist validation summary to SQLite")
    args = parser.parse_args()

    summary = validate_database(
        args.db,
        source_root=args.source_root,
        reports_root=args.reports_root,
    )
    if not args.no_record and Path(args.db).exists():
        try:
            record_validation_results(args.db, summary)
            summary["recorded"] = True
        except Exception as exc:
            summary["recorded"] = False
            summary.setdefault("warnings", []).append(f"Unable to record validation summary: {exc}")

    rendered = json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True)
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
    if args.json or not args.output:
        print(rendered)

    if args.strict and not summary.get("ok"):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
