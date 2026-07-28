#!/usr/bin/env python3
"""Review unresolved historical catch gear/water links without changing JSON."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import DEFAULT_DB, connect
from persistence.legacy_references import record_decision, unresolved_references
from persistence.migrations import migrate


def main() -> int:
    parser = argparse.ArgumentParser(description="Operator-reviewed V7 legacy catch-reference decisions")
    parser.add_argument("action", choices=("list", "accept", "accept-all", "link"))
    parser.add_argument("--db", default=str(DEFAULT_DB))
    parser.add_argument("--catch-id")
    parser.add_argument("--relationship", choices=("gear", "waterbody"))
    parser.add_argument("--role", default="")
    parser.add_argument("--reference")
    parser.add_argument("--target-id")
    parser.add_argument("--note")
    parser.add_argument("--operator")
    parser.add_argument(
        "--confirm-preserve-historical",
        action="store_true",
        help="Required for accept-all; records no guessed target links.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    db_path = Path(args.db)
    with connect(db_path) as conn:
        migrate(conn, db_path=str(db_path))
        if args.action == "list":
            result = {"unresolved": unresolved_references(conn), "json_authoritative": True}
        elif args.action == "accept-all":
            if not args.confirm_preserve_historical:
                raise SystemExit("accept-all requires --confirm-preserve-historical")
            if not args.note or not args.operator:
                raise SystemExit("accept-all requires --note and --operator")
            pending = unresolved_references(conn)
            recorded = []
            for item in pending:
                recorded.append(
                    record_decision(
                        conn,
                        catch_id=item["catch_id"],
                        relationship=item["relationship"],
                        role=item["role"],
                        original_reference=item["reference"],
                        decision="accepted_legacy",
                        note=args.note,
                        operator_name=args.operator,
                    )
                )
            result = {
                "accepted_count": len(recorded),
                "remaining": len(unresolved_references(conn)),
                "json_authoritative": True,
                "note": "Original labels were preserved; no normalized links were guessed.",
            }
        else:
            required = (args.catch_id, args.relationship, args.reference, args.note, args.operator)
            if not all(required):
                raise SystemExit("--catch-id, --relationship, --reference, --note, and --operator are required")
            result = record_decision(
                conn,
                catch_id=args.catch_id,
                relationship=args.relationship,
                role=args.role,
                original_reference=args.reference,
                decision="accepted_legacy" if args.action == "accept" else "linked",
                target_id=args.target_id,
                note=args.note,
                operator_name=args.operator,
            )
            result["json_authoritative"] = True
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
