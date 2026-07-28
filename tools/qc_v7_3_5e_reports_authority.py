#!/usr/bin/env python3
"""Focused QC for explicit V7.3.5e reports authority transition."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.authority_manifest import read_manifest, write_manifest
from persistence.authority_resolution import resolve_authority
from persistence.connection import connect
from persistence.importers import import_reports
from persistence.migrations import migrate
from persistence.reports_authority import activate_reports_authority, reconcile_legacy_report_snapshots, report_transition_preflight


def render(meta, payload, selected_forecast_date=None):
    return f"<html><body>{meta['id']} {payload.get('zip', '')}</body></html>"


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-5e-qc-") as temp_dir:
        root = Path(temp_dir); data = root / "data"; reports = root / "reports"; data.mkdir(); reports.mkdir()
        db, index, manifest = data / "angler.sqlite3", data / "reports_index.json", data / "authority.json"
        report_id = "report-transition"
        meta = {"id": report_id, "title": "Transition QC", "zip": "60543", "created": "2026-07-28T15:00:00+00:00", "json_file": f"{report_id}.json", "html_file": f"{report_id}.html", "view_url": f"/api/reports/view/{report_id}"}
        wrapped = {"meta": dict(meta), "payload": {"zip": "60543"}, "summary": {"zip": "60543"}}
        index.write_text(json.dumps([meta]), encoding="utf-8"); (reports / meta["json_file"]).write_text(json.dumps(wrapped), encoding="utf-8"); (reports / meta["html_file"]).write_text("<html>legacy</html>", encoding="utf-8")
        with connect(db) as conn:
            migrate(conn, db_path=str(db)); import_reports(conn, index, reports)
        write_manifest({}, manifest)
        assert not report_transition_preflight(db)["ready"]
        reconciled = reconcile_legacy_report_snapshots(db_path=db, index_path=index, reports_dir=reports)
        assert reconciled["ok"] and report_transition_preflight(db)["ready"]
        results = activate_reports_authority(render_html=render, db_path=db, index_path=index, reports_dir=reports)
        assert len(results) == 1 and not results[0].warning
        # The external marker is deliberately separate and completes last.
        write_manifest({"reports": "sqlite"}, manifest)
        resolution = resolve_authority("reports", db, manifest_path=manifest)
        assert resolution.effective_authority == "sqlite" and resolution.writable
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT authority FROM data_authority WHERE domain='reports'").fetchone()[0] == "sqlite"
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
        payload, error = read_manifest(manifest)
        assert not error and payload and payload["domains"]["reports"] == "sqlite"
        assert json.loads((reports / meta["json_file"]).read_text(encoding="utf-8"))["meta"]["id"] == report_id
    print("PASS: V7.3.5e reports authority QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
