from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from flask import jsonify, request, send_file
from tools.backup_restore import safe_user_data_backup_path, restore_user_data_backup


BASE_DIR = Path(__file__).resolve().parent
BACKUP_DIR = BASE_DIR / "backups" / "user-data"
TOOLS_DIR = BASE_DIR / "tools"


def _backup_files() -> list[dict[str, Any]]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    files = []
    for path in sorted(BACKUP_DIR.glob("*.zip"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            st = path.stat()
            files.append({
                "filename": path.name,
                "path": str(path),
                "size_bytes": st.st_size,
                "size_mb": round(st.st_size / 1024 / 1024, 2),
                "modified": datetime.fromtimestamp(st.st_mtime).isoformat(timespec="seconds"),
                "download_url": f"/api/app-health/backups/download/{path.name}",
            })
        except Exception:
            continue

    return files


def _create_backup() -> dict[str, Any]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    helper = TOOLS_DIR / "backup_user_data.sh"

    if helper.exists() and os.access(helper, os.X_OK):
        result = subprocess.run(
            ["bash", str(helper)],
            cwd=str(BASE_DIR),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=60,
        )
        return {
            "ok": result.returncode == 0,
            "method": "tools/backup_user_data.sh",
            "returncode": result.returncode,
            "output": result.stdout[-4000:],
            "backups": _backup_files()[:10],
        }

    # Fallback backup if helper is missing.
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = BACKUP_DIR / f"angler-user-data-{ts}.zip"

    import zipfile

    candidates = [
        BASE_DIR / "data" / "favorites.json",
        BASE_DIR / "data" / "catches.json",
        BASE_DIR / "data" / "reports_index.json",
        BASE_DIR / "data" / "species_settings_v431.json",
        BASE_DIR / "data" / "app_version.json",
    ]

    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in candidates:
            if path.exists():
                zf.write(path, path.relative_to(BASE_DIR))

    return {
        "ok": True,
        "method": "fallback zip",
        "created": str(out),
        "backups": _backup_files()[:10],
    }


def register_health_backup_routes_v443(app):
    @app.route("/api/app-health/backups")
    def app_health_backups_v443():
        files = _backup_files()
        return jsonify({
            "ok": True,
            "version": "v5.9-modern-ui-refresh",
            "count": len(files),
            "backups": files,
        })

    @app.route("/api/app-health/backups/create", methods=["POST"])
    def app_health_create_backup_v443():
        try:
            return jsonify(_create_backup())
        except Exception as exc:
            return jsonify({
                "ok": False,
                "error": str(exc),
            }), 500

    @app.route("/api/app-health/backups/restore", methods=["POST"])
    def app_health_restore_backup_v443():
        payload = request.get_json(silent=True) or {}
        filename = str(payload.get("filename") or payload.get("path") or "").strip()

        try:
            archive_path = safe_user_data_backup_path(filename)
            if not archive_path.exists():
                return jsonify({
                    "ok": False,
                    "error": "Backup not found",
                }), 404

            from tools.app_backup import create_backup

            pre_backup = create_backup(label=f"pre_restore_{archive_path.stem}")
            restore_result = restore_user_data_backup(archive_path)

            return jsonify({
                "ok": True,
                "version": "v5.9-modern-ui-refresh",
                "backup": {
                    "filename": archive_path.name,
                    "path": str(archive_path),
                },
                "pre_restore_backup": pre_backup,
                "restore": restore_result,
                "backups": _backup_files()[:10],
            })
        except Exception as exc:
            return jsonify({
                "ok": False,
                "error": str(exc),
            }), 400

    @app.route("/api/app-health/backups/download/<filename>")
    def app_health_download_backup_v443(filename: str):
        safe = Path(filename).name
        path = BACKUP_DIR / safe

        if not path.exists() or not path.is_file():
            return jsonify({"ok": False, "error": "Backup not found"}), 404

        return send_file(path, as_attachment=True, download_name=safe)
