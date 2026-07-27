#!/usr/bin/env python3
"""Focused QC for V7.2.5 JSON-returning report-index comparison reads."""
from __future__ import annotations
import json, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0, str(ROOT))
from persistence.connection import connect
from persistence.importers import import_reports
from persistence.migrations import migrate
from persistence.repositories import JsonReportsIndexRepository, SQLiteReportsIndexRepository, read_domain
def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-2-5-qc-") as temp_dir:
        root = Path(temp_dir); index = root / "reports_index.json"; reports = root / "reports"; db = root / "reports.sqlite3"; reports.mkdir()
        records = [{"id": "report-1", "title": "QC Report", "created": "2026-07-27T18:00:00", "json_file": "report-1.json"}]
        index.write_text(json.dumps(records), encoding="utf-8"); (reports / "report-1.json").write_text(json.dumps({"meta": {"id": "report-1"}}), encoding="utf-8")
        with connect(db) as conn: migrate(conn, db_path=str(db)); import_reports(conn, index, reports)
        result = read_domain("reports", json_repository=JsonReportsIndexRepository(index), sqlite_repository=SQLiteReportsIndexRepository(db), source="compare_json")
        assert result.effective_source == "json" and result.comparison_status == "exact"
        fallback = read_domain("reports", json_repository=JsonReportsIndexRepository(index), sqlite_repository=SQLiteReportsIndexRepository(root / "missing.sqlite3"), source="sqlite_with_json_fallback")
        assert fallback.fallback_used and fallback.value[0]["id"] == "report-1"
    print("PASS: V7.2.5 report staged reads QC")
    return 0
if __name__ == "__main__": raise SystemExit(main())
