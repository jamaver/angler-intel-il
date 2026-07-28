#!/usr/bin/env python3
"""Focused QC for V7.3.5b SQLite-first report creation."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
import persistence.reports_authority as reports_authority


def fixture(report_id: str) -> tuple[dict, dict, str]:
    meta = {
        "id": report_id, "title": "Bass Plan", "zip": "60543",
        "created": "2026-07-28T15:00:00+00:00",
        "json_file": f"{report_id}.json", "html_file": f"{report_id}.html",
        "view_url": f"/api/reports/view/{report_id}",
        "selected_forecast_date": "2026-07-30", "selected_forecast_label": "Thursday, July 30",
        "forecast_day_index": 2,
    }
    payload = {
        "zip": "60543", "target_species": "largemouth bass",
        "selected_forecast_date": "2026-07-30", "intel": {"target_species": "largemouth bass"},
    }
    return meta, {"meta": dict(meta), "payload": payload, "summary": {"zip": "60543"}}, "<!doctype html><title>Bass Plan</title>"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-5b-qc-") as temp_dir:
        temp = Path(temp_dir); db = temp / "angler.sqlite3"; index = temp / "reports_index.json"; reports = temp / "reports"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            conn.execute("UPDATE data_authority SET authority='sqlite' WHERE domain='reports'")
            conn.commit()

        meta, wrapped, html = fixture("20260728-qc-bass")
        result = reports_authority.save_report_sqlite_authoritative(meta, wrapped, html, db_path=db, index_path=index, reports_dir=reports)
        assert result.compatibility_export == "ok" and result.html_export == "ok", result
        assert json.loads((reports / meta["json_file"]).read_text(encoding="utf-8"))["payload"]["zip"] == "60543"
        assert json.loads(index.read_text(encoding="utf-8"))[0]["id"] == meta["id"]
        assert (reports / meta["html_file"]).read_text(encoding="utf-8") == html
        with connect(db, read_only=True) as conn:
            report = dict(conn.execute("SELECT * FROM trip_reports WHERE id=?", (meta["id"],)).fetchone())
            trip = dict(conn.execute("SELECT * FROM trips WHERE id=?", (meta["id"],)).fetchone())
            assert report["status"] == "active"
            assert report["snapshot_payload_json"]
            assert report["compatibility_export_status"] == "ok"
            assert report["html_export_status"] == "ok"
            assert trip["selected_forecast_date"] == "2026-07-30"

        # An artifact error must not undo the committed report.
        original_write = reports_authority._atomic_write
        def fail_html(path: Path, content: str) -> None:
            if path.suffix == ".html":
                raise OSError("simulated HTML output failure")
            original_write(path, content)
        reports_authority._atomic_write = fail_html
        try:
            bad_meta, bad_wrapped, bad_html = fixture("20260728-qc-html-failure")
            failed = reports_authority.save_report_sqlite_authoritative(bad_meta, bad_wrapped, bad_html, db_path=db, index_path=index, reports_dir=reports)
        finally:
            reports_authority._atomic_write = original_write
        assert failed.compatibility_export == "ok" and failed.html_export == "failed", failed
        with connect(db, read_only=True) as conn:
            stored = dict(conn.execute("SELECT status, html_export_status FROM trip_reports WHERE id=?", (bad_meta["id"],)).fetchone())
            assert stored == {"status": "active", "html_export_status": "failed"}
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    print("PASS: V7.3.5b SQLite-first report creation QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
