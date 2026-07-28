#!/usr/bin/env python3
"""Focused QC for V7.1.5 JSON-first saved report mirroring."""
from __future__ import annotations

import sys
import tempfile
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)) if str(ROOT) not in sys.path else None

import angler_reports_v38 as reports
from app import app as flask_app
from persistence.connection import connect
from persistence.migrations import migrate
from persistence.authority_manifest import write_manifest
from persistence.reports_mirror import compare_reports, mirror_reports


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-1-5-qc-") as temp_dir:
        temp = Path(temp_dir); db = temp / "a.sqlite3"; index = temp / "reports_index.json"; directory = temp / "reports"
        with connect(db) as conn: migrate(conn, db_path=str(db))
        old_index, old_dir, old_mirror = reports.INDEX_PATH, reports.REPORTS_DIR, reports.mirror_reports
        old_db = os.environ.get("AI_SQLITE_DB_PATH")
        old_manifest = os.environ.get("AI_AUTHORITY_MANIFEST")
        try:
            manifest = temp / "authority.json"
            write_manifest({}, manifest)
            os.environ["AI_SQLITE_DB_PATH"] = str(db)
            os.environ["AI_AUTHORITY_MANIFEST"] = str(manifest)
            reports.INDEX_PATH, reports.REPORTS_DIR = index, directory
            reports.mirror_reports = lambda source, folder: mirror_reports(source, folder, db_path=db)
            with flask_app.app_context():
                meta = reports._save_report({"zip": "60543", "title": "QC Report", "intel": {}}, title="QC Report", zip_code="60543")
                assert compare_reports(index, db_path=db)["status"] == "exact"
                assert reports._delete_report_assets(meta["id"])["remaining_count"] == 0
                assert compare_reports(index, db_path=db)["status"] == "exact"
                reports._save_report({"zip": "60543", "title": "QC Report 2", "intel": {}}, title="QC Report 2", zip_code="60543")
                assert reports._delete_all_report_assets()["remaining_count"] == 0
                assert compare_reports(index, db_path=db)["status"] == "exact"
        finally:
            reports.INDEX_PATH, reports.REPORTS_DIR, reports.mirror_reports = old_index, old_dir, old_mirror
            if old_db is None:
                os.environ.pop("AI_SQLITE_DB_PATH", None)
            else:
                os.environ["AI_SQLITE_DB_PATH"] = old_db
            if old_manifest is None:
                os.environ.pop("AI_AUTHORITY_MANIFEST", None)
            else:
                os.environ["AI_AUTHORITY_MANIFEST"] = old_manifest
    print("PASS: V7.1.5 report mirror QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
