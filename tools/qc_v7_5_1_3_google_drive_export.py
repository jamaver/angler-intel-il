#!/usr/bin/env python3
"""Focused QC for the optional, non-authoritative Google Drive export queue."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
import integrations.google_drive as drive


def _make_backup(backups: Path) -> Path:
    archive = backups / "angler_intel_v7_runtime_backup_20260808_qc.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("data/angler_intel.sqlite3", b"")
    manifest = {
        "verified": True,
        "created_at": "2026-08-08T12:00:00+00:00",
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "database": {"metrics": {"integrity_check": "ok", "foreign_key_check": []}},
    }
    archive.with_suffix(".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return archive


def main() -> int:
    errors: list[str] = []
    previous_env = {key: os.environ.get(key) for key in ("AI_GDRIVE_ENABLED", "AI_GDRIVE_REMOTE", "AI_GDRIVE_ROOT", "AI_RCLONE_BIN")}
    old = (drive.BASE_DIR, drive.BACKUP_DIR, drive.REPORTS_DIR)
    try:
        with tempfile.TemporaryDirectory(prefix="angler-v7-5-1-3-qc-") as temp:
            base = Path(temp); backups = base / "backups"; reports = base / "reports"; backups.mkdir(); reports.mkdir()
            fake = base / "rclone"
            log = base / "rclone.log"
            fake.write_text("#!/bin/sh\nprintf '%s\\n' \"$*\" >> '" + str(log) + "'\ncase \"$1\" in listremotes) echo 'anglerdrive:';; esac\nexit 0\n", encoding="utf-8")
            fake.chmod(0o755)
            db = base / "data" / "angler_intel.sqlite3"
            with connect(db) as conn:
                migrate(conn, db_path=str(db))
                conn.execute("INSERT INTO trip_reports(id, report_title, json_path, html_path, legacy_payload_json, created_at) VALUES('report-1', 'QC', 'reports/report-1.json', 'reports/report-1.html', '{}', '2026-08-08T12:00:00+00:00')")
            (reports / "report-1.json").write_text("{}", encoding="utf-8")
            (reports / "report-1.html").write_text("<html></html>", encoding="utf-8")
            archive = _make_backup(backups)
            drive.BASE_DIR, drive.BACKUP_DIR, drive.REPORTS_DIR = base, backups, reports
            os.environ.update({"AI_GDRIVE_ENABLED": "1", "AI_GDRIVE_REMOTE": "anglerdrive", "AI_GDRIVE_ROOT": "Angler Intel", "AI_RCLONE_BIN": str(fake)})
            if not drive.test_connection().get("ok"):
                errors.append("fake rclone connection should pass")
            drive.queue_verified_backup(archive, db_path=db)
            drive.queue_report_export("report-1", db_path=db, reports_dir=reports)
            result = drive.upload_pending(db_path=db)
            if not result.get("ok") or result.get("uploaded") != 4:
                errors.append("verified backup and report artifact pairs should upload")
            rerun = drive.upload_pending(db_path=db)
            if rerun.get("uploaded") != 0:
                errors.append("completed exports should not upload twice")
            if "copyto" not in log.read_text(encoding="utf-8") or "sync" in log.read_text(encoding="utf-8"):
                errors.append("provider must use copyto and never sync")
            try:
                drive.queue_report_export("../escape", db_path=db, reports_dir=reports)
            except ValueError:
                pass
            else:
                errors.append("malicious report IDs must be rejected")
            archive.with_suffix(".manifest.json").write_text('{"verified": false}', encoding="utf-8")
            try:
                drive.queue_verified_backup(archive, db_path=db)
            except ValueError:
                pass
            else:
                errors.append("unverified backups must be rejected")
            os.environ["AI_GDRIVE_ENABLED"] = "0"
            disabled = drive.upload_pending(db_path=db)
            if disabled.get("status") != "disabled":
                errors.append("disabled Drive must leave the local queue safe")
    finally:
        drive.BASE_DIR, drive.BACKUP_DIR, drive.REPORTS_DIR = old
        for key, value in previous_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    provider = (ROOT / "integrations" / "google_drive.py").read_text(encoding="utf-8")
    if "shell=True" in provider or '"sync"' in provider or "'sync'" in provider:
        errors.append("provider must not use shell execution or rclone sync")
    if "rclone.conf" in provider and "read_text" in provider:
        errors.append("provider must not read rclone credentials")
    if errors:
        print("FAIL: " + "; ".join(errors))
        return 1
    print("PASS: V7.5.1.3 Google Drive export QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
