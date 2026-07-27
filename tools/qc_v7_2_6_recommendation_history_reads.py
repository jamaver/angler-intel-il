#!/usr/bin/env python3
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from persistence.connection import connect
from persistence.importers import import_reports
from persistence.migrations import migrate
from persistence.recommendation_history import compare_recommendation_history
def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-2-6-qc-") as temp_dir:
        root = Path(temp_dir); reports = root / "reports"; reports.mkdir(); index = root / "reports_index.json"; db = root / "a.sqlite3"
        report_id = "qc-report"; index.write_text(json.dumps([{ "id": report_id, "title": "QC", "created": "2026-07-27" }]), encoding="utf-8")
        (reports / f"{report_id}.json").write_text(json.dumps({"meta": {"id": report_id}, "summary": {"best_bet": {"species": "Largemouth Bass", "lure_name": "Jig", "reasons": ["QC"]}}}), encoding="utf-8")
        with connect(db) as conn: migrate(conn, db_path=str(db)); import_reports(conn, index, reports)
        assert compare_recommendation_history(reports, db)["status"] == "exact"
    print("PASS: V7.2.6 recommendation history QC")
    return 0
if __name__ == "__main__": raise SystemExit(main())
