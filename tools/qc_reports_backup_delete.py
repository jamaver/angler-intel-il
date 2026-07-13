#!/usr/bin/env python3
from __future__ import annotations

import ast
import json
import tempfile
import zipfile
import sys
from pathlib import Path

from flask import Flask

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from app import app as flask_app
import angler_reports_v38 as reports_mod
import angler_health_backup_v443 as backup_mod
import tools.backup_restore as backup_helper

errors: list[str] = []


def assert_contains(path: Path, needle: str, message: str) -> None:
    text = path.read_text(encoding="utf-8")
    if needle not in text:
        errors.append(message)


def build_report_fixture(base: Path) -> dict[str, Path]:
    reports_dir = base / "reports"
    data_dir = base / "data"
    reports_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    report_id = "qc-delete-report-20260713"
    json_name = f"{report_id}.json"
    html_name = f"{report_id}.html"
    (reports_dir / json_name).write_text(json.dumps({"payload": {"title": "QC report"}}), encoding="utf-8")
    (reports_dir / html_name).write_text("<html><body>qc report</body></html>", encoding="utf-8")
    (data_dir / "reports_index.json").write_text(json.dumps([{
        "id": report_id,
        "title": "QC report",
        "created": "2026-07-13T08:00:00",
        "zip": "60543",
        "json_file": json_name,
        "html_file": html_name,
        "view_url": f"/api/reports/view/{report_id}",
        "html_url": f"/api/reports/download/{html_name}",
        "json_url": f"/api/reports/download/{json_name}",
    }], indent=2), encoding="utf-8")
    return {
        "report_id": report_id,
        "reports_dir": reports_dir,
        "data_dir": data_dir,
        "json_path": reports_dir / json_name,
        "html_path": reports_dir / html_name,
        "index_path": data_dir / "reports_index.json",
    }


def build_backup_fixture(base: Path) -> dict[str, Path]:
    backup_dir = base / "backups" / "user-data"
    backup_dir.mkdir(parents=True, exist_ok=True)
    filename = "angler-intel-cli-backup-qc-delete.zip"
    path = backup_dir / filename
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("data/favorites.json", "[]")
    return {"backup_dir": backup_dir, "filename": filename, "path": path}


def main() -> int:
    for rel in ("app.py", "angler_reports_v38.py", "angler_health_backup_v443.py", "static/js/app_health_backups_v443.js"):
        path = APP_ROOT / rel
        if not path.exists():
            errors.append(f"Missing {rel}")
            continue
        if path.suffix == ".py":
            try:
                ast.parse(path.read_text(encoding="utf-8"))
            except SyntaxError as exc:
                errors.append(f"{rel} syntax error: {exc}")

    assert_contains(APP_ROOT / "templates/reports.html" if (APP_ROOT / "templates/reports.html").exists() else APP_ROOT / "angler_reports_v38.py", "data-delete-report", "Reports page should expose delete controls")
    assert_contains(APP_ROOT / "static/js/app_health_backups_v443.js", "data-delete-backup", "App Health backups UI should expose delete controls")

    original_reports_dir = reports_mod.REPORTS_DIR
    original_reports_index = reports_mod.INDEX_PATH
    original_data_dir = reports_mod.DATA_DIR
    original_backup_dir = backup_mod.BACKUP_DIR
    original_user_data_backup_dir = backup_helper.USER_DATA_BACKUP_DIR

    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            report_fixture = build_report_fixture(tmp)
            backup_fixture = build_backup_fixture(tmp)

            reports_mod.REPORTS_DIR = report_fixture["reports_dir"]
            reports_mod.DATA_DIR = report_fixture["data_dir"]
            reports_mod.INDEX_PATH = report_fixture["index_path"]
            backup_mod.BACKUP_DIR = backup_fixture["backup_dir"]
            backup_helper.USER_DATA_BACKUP_DIR = backup_fixture["backup_dir"]

            client = flask_app.test_client()

            bad_report = client.post("/api/reports/delete", json={"report_id": "../escape"})
            if bad_report.status_code != 400:
                errors.append("Report delete should reject traversal")

            deleted_report = client.post("/api/reports/delete", json={"report_id": report_fixture["report_id"]})
            if deleted_report.status_code != 200:
                errors.append(f"Report delete failed with HTTP {deleted_report.status_code}")
            else:
                payload = deleted_report.get_json(silent=True) or {}
                if payload.get("ok") is not True:
                    errors.append("Report delete did not return ok=true")
                if report_fixture["json_path"].exists() or report_fixture["html_path"].exists():
                    errors.append("Report delete did not remove report files")
                index_payload = json.loads(report_fixture["index_path"].read_text(encoding="utf-8"))
                if any(item.get("id") == report_fixture["report_id"] for item in index_payload):
                    errors.append("Report delete did not update reports index")

            bad_backup = client.post("/api/app-health/backups/delete", json={"filename": "../escape.zip"})
            if bad_backup.status_code != 400:
                errors.append("Backup delete should reject traversal")

            bad_backup_ext = client.post("/api/app-health/backups/delete", json={"filename": "not-a-backup.txt"})
            if bad_backup_ext.status_code != 400:
                errors.append("Backup delete should reject non-zip paths")

            deleted_backup = client.post("/api/app-health/backups/delete", json={"filename": backup_fixture["filename"]})
            if deleted_backup.status_code != 200:
                errors.append(f"Backup delete failed with HTTP {deleted_backup.status_code}")
            else:
                payload = deleted_backup.get_json(silent=True) or {}
                if payload.get("ok") is not True:
                    errors.append("Backup delete did not return ok=true")
                if backup_fixture["path"].exists():
                    errors.append("Backup delete did not remove backup file")

    finally:
        reports_mod.REPORTS_DIR = original_reports_dir
        reports_mod.INDEX_PATH = original_reports_index
        reports_mod.DATA_DIR = original_data_dir
        backup_mod.BACKUP_DIR = original_backup_dir
        backup_helper.USER_DATA_BACKUP_DIR = original_user_data_backup_dir

    if errors:
        print("QC FAILED: reports and backup delete")
        for error in errors:
            print(f" - {error}")
        raise SystemExit(1)

    print("QC PASSED: reports and backup delete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
