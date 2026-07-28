#!/usr/bin/env python3
"""Focused QC for the non-authoritative V7.3.5a report contract."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.report_authority_contract import build_report_authority_plan
from persistence.reports_mirror import mirror_reports


def _fixture(report_id: str = "20260728-qc-report") -> tuple[dict, dict, str]:
    meta = {
        "id": report_id,
        "title": "QC Report",
        "json_file": f"{report_id}.json",
        "html_file": f"{report_id}.html",
    }
    wrapped = {"meta": dict(meta), "payload": {"zip": "60543", "intel": {}}, "summary": {"zip": "60543"}}
    return meta, wrapped, "<!doctype html><title>QC Report</title>"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-5a-qc-") as temp_dir:
        temp = Path(temp_dir)
        db = temp / "angler.sqlite3"
        index = temp / "reports_index.json"
        reports = temp / "reports"
        reports.mkdir()
        meta, wrapped, rendered_html = _fixture()
        original = json.dumps(wrapped, sort_keys=True).encode("utf-8")
        plan = build_report_authority_plan(meta, wrapped, rendered_html)
        assert plan.status == "active"
        assert plan.trip_id == plan.report_id
        assert plan.authoritative_payload_hash
        assert plan.html_export_hash
        assert hashlib.sha256(json.dumps(wrapped, sort_keys=True).encode("utf-8")).digest() == hashlib.sha256(original).digest()
        try:
            build_report_authority_plan({**meta, "json_file": "../bad.json"}, wrapped, rendered_html)
            raise AssertionError("Unsafe artifact path was accepted")
        except ValueError:
            pass

        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            columns = {row[1] for row in conn.execute("PRAGMA table_info(trip_reports)")}
            required = {
                "status", "deleted_at", "snapshot_payload_json", "authoritative_payload_hash",
                "compatibility_export_status", "html_export_status", "artifact_error",
            }
            assert required.issubset(columns), columns
            authority = conn.execute("SELECT authority FROM data_authority WHERE domain = 'reports'").fetchone()
            assert authority and authority["authority"] == "json"

        index.write_text(json.dumps([meta]), encoding="utf-8")
        (reports / meta["json_file"]).write_text(json.dumps(wrapped), encoding="utf-8")
        (reports / meta["html_file"]).write_text(rendered_html, encoding="utf-8")
        mirrored = mirror_reports(index, reports, db_path=db)
        assert mirrored.mirror_write_succeeded, mirrored

        with connect(db) as conn:
            conn.execute("UPDATE data_authority SET authority = 'sqlite' WHERE domain = 'reports'")
            conn.commit()
        rejected = mirror_reports(index, reports, db_path=db)
        assert not rejected.mirror_write_succeeded and "SQLite-authoritative" in (rejected.error or ""), rejected

    print("PASS: V7.3.5a report authority contract QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
