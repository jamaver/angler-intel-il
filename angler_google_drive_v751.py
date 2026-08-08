"""Maintenance-only Google Drive endpoints backed by the local export queue."""
from __future__ import annotations

import json
from pathlib import Path

from flask import jsonify, request

from integrations.google_drive import (
    BACKUP_DIR,
    public_status,
    queue_report_export,
    queue_verified_backup,
    test_connection,
    upload_pending,
)


def _latest_verified_archive() -> Path:
    manifest_path = BACKUP_DIR / "latest_v7_runtime_backup_manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    archive = Path(__file__).resolve().parent / str(payload.get("archive") or "")
    if not archive.exists():
        raise ValueError("Latest verified backup archive is unavailable")
    return archive


def register_google_drive_routes_v751(app):
    @app.route("/api/app-health/google-drive/status")
    def google_drive_status_v751():
        return jsonify({"ok": True, "google_drive": public_status()})

    @app.route("/api/app-health/google-drive/test", methods=["POST"])
    def google_drive_test_v751():
        result = test_connection()
        return jsonify({"ok": bool(result.get("ok")), "result": result}), 200 if result.get("ok") else 503

    @app.route("/api/app-health/google-drive/upload-latest-backup", methods=["POST"])
    def google_drive_upload_latest_backup_v751():
        try:
            archive = _latest_verified_archive()
            queue_verified_backup(archive)
            result = upload_pending(object_id=archive.stem)
            return jsonify({"ok": bool(result.get("ok")), "archive": archive.name, "result": result}), 200 if result.get("ok") else 503
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/app-health/google-drive/upload-pending", methods=["POST"])
    def google_drive_upload_pending_v751():
        result = upload_pending()
        return jsonify({"ok": bool(result.get("ok")), "result": result}), 200 if result.get("ok") else 503

    @app.route("/api/reports/drive", methods=["POST"])
    def google_drive_upload_report_v751():
        payload = request.get_json(silent=True) or {}
        report_id = str(payload.get("report_id") or payload.get("id") or "").strip()
        if not report_id or "/" in report_id or "\\" in report_id or ".." in report_id:
            return jsonify({"ok": False, "error": "A valid report ID is required"}), 400
        try:
            queue_report_export(report_id)
            result = upload_pending(object_id=report_id)
            return jsonify({"ok": bool(result.get("ok")), "report_id": report_id, "result": result}), 200 if result.get("ok") else 503
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
