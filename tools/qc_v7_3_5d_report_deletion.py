#!/usr/bin/env python3
"""Focused QC for V7.3.5d SQLite report lifecycle operations."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
import persistence.reports_authority as authority


def render(meta, payload, selected_forecast_date=None):
    return f"<html><body>{meta['id']} {payload.get('zip', '')}</body></html>"


def save_fixture(db, index, reports, report_id):
    meta = {"id": report_id, "title": report_id, "zip": "60543", "created": "2026-07-28T15:00:00+00:00", "json_file": f"{report_id}.json", "html_file": f"{report_id}.html"}
    wrapped = {"meta": dict(meta), "payload": {"zip": "60543"}, "summary": {"zip": "60543"}}
    return authority.save_report_sqlite_authoritative(meta, wrapped, render(meta, wrapped["payload"]), db_path=db, index_path=index, reports_dir=reports), meta


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-5d-qc-") as temp_dir:
        temp = Path(temp_dir); db = temp / "reports.sqlite3"; index = temp / "reports_index.json"; reports = temp / "reports"
        with connect(db) as conn:
            migrate(conn, db_path=str(db)); conn.execute("UPDATE data_authority SET authority='sqlite' WHERE domain='reports'"); conn.commit()
        _, meta = save_fixture(db, index, reports, "report-delete")
        deleted = authority.soft_delete_authoritative_report(meta["id"], db_path=db, index_path=index, reports_dir=reports)
        assert deleted.status == "deleted" and set(deleted.deleted_files) == {meta["json_file"], meta["html_file"]}
        assert not (reports / meta["json_file"]).exists() and not (reports / meta["html_file"]).exists()
        with connect(db, read_only=True) as conn:
            report = dict(conn.execute("SELECT status, deleted_at FROM trip_reports WHERE id=?", (meta["id"],)).fetchone())
            assert report["status"] == "deleted" and report["deleted_at"]
            assert conn.execute("SELECT 1 FROM trips WHERE id=?", (meta["id"],)).fetchone() is not None
        restored = authority.restore_authoritative_report(meta["id"], render_html=render, db_path=db, index_path=index, reports_dir=reports)
        assert restored.compatibility_export == "ok" and restored.html_export == "ok"
        assert (reports / meta["json_file"]).exists() and (reports / meta["html_file"]).exists()

        _, second = save_fixture(db, index, reports, "report-delete-all")
        all_deleted = authority.soft_delete_all_authoritative_reports(db_path=db, index_path=index, reports_dir=reports)
        assert {item.report_id for item in all_deleted} == {meta["id"], second["id"]}
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT COUNT(*) FROM trip_reports WHERE status='active'").fetchone()[0] == 0
            assert conn.execute("SELECT COUNT(*) FROM trips").fetchone()[0] == 2
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    print("PASS: V7.3.5d report deletion QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
