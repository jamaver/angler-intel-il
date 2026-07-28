#!/usr/bin/env python3
"""Focused QC for V7.3.5c SQLite report reads and artifact repair."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.reports_authority import load_authoritative_report, repair_report_artifacts, save_report_sqlite_authoritative
from persistence.repositories import SQLiteReportsIndexRepository
import angler_reports_v38 as report_routes
from app import app as flask_app


def render(meta, payload, selected_forecast_date=None):
    return f"<html><body>{meta['id']} {selected_forecast_date or ''} {payload.get('zip', '')}</body></html>"


def fixture(report_id):
    meta = {"id": report_id, "title": "QC", "zip": "60543", "created": "2026-07-28T15:00:00+00:00", "json_file": f"{report_id}.json", "html_file": f"{report_id}.html", "selected_forecast_date": "2026-07-30"}
    return meta, {"meta": dict(meta), "payload": {"zip": "60543", "selected_forecast_date": "2026-07-30"}, "summary": {"zip": "60543"}}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-5c-qc-") as temp_dir:
        temp = Path(temp_dir); db = temp / "reports.sqlite3"; index = temp / "reports_index.json"; reports = temp / "reports"
        with connect(db) as conn:
            migrate(conn, db_path=str(db)); conn.execute("UPDATE data_authority SET authority='sqlite' WHERE domain='reports'"); conn.commit()
        meta, wrapped = fixture("report-qc-c")
        saved = save_report_sqlite_authoritative(meta, wrapped, render(meta, wrapped["payload"]), db_path=db, index_path=index, reports_dir=reports)
        assert not saved.warning
        assert SQLiteReportsIndexRepository(db).read()[0]["id"] == meta["id"]
        (reports / meta["json_file"]).unlink(); (reports / meta["html_file"]).unlink(); index.unlink()
        loaded = load_authoritative_report(meta["id"], db)
        assert loaded.wrapped_snapshot["payload"]["zip"] == "60543"
        repaired = repair_report_artifacts(meta["id"], render_html=render, db_path=db, index_path=index, reports_dir=reports)
        assert repaired.compatibility_export == "ok" and repaired.html_export == "ok", repaired
        assert json.loads((reports / meta["json_file"]).read_text(encoding="utf-8"))["meta"]["id"] == meta["id"]
        assert meta["id"] in (reports / meta["html_file"]).read_text(encoding="utf-8")
        with connect(db, read_only=True) as conn:
            row = dict(conn.execute("SELECT compatibility_export_status, html_export_status FROM trip_reports WHERE id=?", (meta["id"],)).fetchone())
            assert row == {"compatibility_export_status": "ok", "html_export_status": "ok"}
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []

        # The real staged route reads a complete SQLite snapshot when selected.
        old_index, old_reports = report_routes.INDEX_PATH, report_routes.REPORTS_DIR
        old_db = os.environ.get("AI_SQLITE_DB_PATH")
        old_source = os.environ.get("AI_REPORTS_READ_SOURCE")
        old_enabled = os.environ.get("AI_ENABLE_V7_STAGED_READS")
        try:
            report_routes.INDEX_PATH, report_routes.REPORTS_DIR = index, reports
            os.environ["AI_SQLITE_DB_PATH"] = str(db)
            os.environ["AI_REPORTS_READ_SOURCE"] = "sqlite"
            os.environ["AI_ENABLE_V7_STAGED_READS"] = "1"
            with flask_app.test_client() as client:
                response = client.get(f"/api/reports/view/{meta['id']}")
            assert response.status_code == 200 and "QC" in response.get_data(as_text=True)
        finally:
            report_routes.INDEX_PATH, report_routes.REPORTS_DIR = old_index, old_reports
            for key, old in (("AI_SQLITE_DB_PATH", old_db), ("AI_REPORTS_READ_SOURCE", old_source), ("AI_ENABLE_V7_STAGED_READS", old_enabled)):
                if old is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old
    print("PASS: V7.3.5c report reads and repair QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
