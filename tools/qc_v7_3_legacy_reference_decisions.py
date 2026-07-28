#!/usr/bin/env python3
"""Focused QC for reviewed legacy catch-reference decisions."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.legacy_references import decision_summary, record_decision, unresolved_references
from persistence.migrations import migrate
from persistence.validation import _validate_links


def check(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-legacy-ref-qc-") as temp_dir:
        db = Path(temp_dir) / "test.sqlite3"
        legacy_payload = {"id": "catch-1", "waterbody": "Old Mill Pond", "gear_refs": {"rod": "retired-rod"}}
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            conn.execute("INSERT INTO gear_items(id, category, legacy_payload_json) VALUES('current-rod', 'rod', '{}')")
            conn.execute("INSERT INTO waterbodies(id, name, legacy_payload_json) VALUES('current-pond', 'Current Pond', '{}')")
            conn.execute(
                """INSERT INTO catches(id, waterbody, gear_refs_json, gear_labels_json, legacy_payload_json)
                   VALUES(?, ?, ?, ?, ?)""",
                ("catch-1", "Old Mill Pond", json.dumps({"rod": "retired-rod"}), json.dumps({"rod": "Old Rod"}), json.dumps(legacy_payload)),
            )
            check(len(unresolved_references(conn)) == 2, "fixture should start with water and gear references unresolved")
            try:
                record_decision(conn, catch_id="catch-1", relationship="gear", role="rod", original_reference="retired-rod", decision="linked", target_id="missing", note="review", operator_name="qc")
            except ValueError:
                pass
            else:
                raise AssertionError("linked decision accepted a missing target")
            record_decision(conn, catch_id="catch-1", relationship="gear", role="rod", original_reference="retired-rod", decision="linked", target_id="current-rod", note="Confirmed replacement", operator_name="qc")
            record_decision(conn, catch_id="catch-1", relationship="waterbody", original_reference="Old Mill Pond", decision="accepted_legacy", note="No deterministic catalog match", operator_name="qc")
            check(unresolved_references(conn) == [], "reviewed references should no longer appear unresolved")
            summary = decision_summary(conn)
            check(summary["total"] == 2 and summary["current"] == 2 and summary["stale"] == 0, "current reviewed decisions were not summarized")
            diffs: list[dict[str, object]] = []
            totals = {"unmapped_reference": 0, "orphan_reference": 0, "generated_only": 0}
            _validate_links(conn, diffs, totals, reports_root=Path(temp_dir) / "reports", source_root=Path(temp_dir) / "data")
            check(totals["unmapped_reference"] == 0, "reviewed decisions must suppress only their exact unresolved references")
            check(conn.execute("SELECT authority FROM data_authority WHERE domain = 'catches'").fetchone()[0] == "json", "QC must retain JSON authority")
    with tempfile.TemporaryDirectory(prefix="angler-v7-legacy-cli-qc-") as temp_dir:
        root = Path(temp_dir); db = root / "cli.sqlite3"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            payload = {"id": "catch-cli", "waterbody": "Old Pond", "gear_refs": {}}
            conn.execute("INSERT INTO catches(id, waterbody, gear_refs_json, gear_labels_json, legacy_payload_json) VALUES(?, ?, '{}', '{}', ?)", ("catch-cli", "Old Pond", json.dumps(payload)))
        tool = ROOT / "tools" / "v7_3_legacy_references.py"
        blocked = subprocess.run([sys.executable, str(tool), "accept-all", "--db", str(db), "--note", "QC", "--operator", "qc"], capture_output=True, text=True)
        check(blocked.returncode != 0, "bulk preserve must require explicit confirmation")
        accepted = subprocess.run([sys.executable, str(tool), "accept-all", "--db", str(db), "--confirm-preserve-historical", "--note", "QC preserve", "--operator", "qc", "--json"], capture_output=True, text=True)
        check(accepted.returncode == 0, accepted.stderr)
        result = json.loads(accepted.stdout)
        check(result["accepted_count"] == 1 and result["remaining"] == 0, "bulk preserve did not clear only reviewed fixture references")
    print("PASS: V7.3 legacy reference decisions QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
