from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import jsonify, request, send_file

from persistence.provenance import file_sha256
from tools.v7_0_backup import BACKUPS, create_backup
from tools.v7_0_restore_rehearsal import rehearse_restore


BASE_DIR = Path(__file__).resolve().parent
BACKUP_DIR = BACKUPS
LEGACY_BACKUP_DIR = BACKUP_DIR / "user-data"
LATEST_MANIFEST = BACKUP_DIR / "latest_v7_runtime_backup_manifest.json"
V7_PREFIX = "angler_intel_v7_runtime_backup_"


def _timestamp(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds")


def _safe_filename(value: str) -> str:
    name = str(value or "").strip()
    candidate = Path(name)
    if not name or candidate.is_absolute() or candidate.name != name:
        raise ValueError("Backup filename must be a single archive filename")
    if not name.endswith(".zip"):
        raise ValueError("Backup must be a zip archive")
    return name


def _manifest_for(archive: Path) -> Path:
    return archive.with_suffix(".manifest.json")


def _verified_v7_record(archive: Path) -> dict[str, Any] | None:
    if not archive.name.startswith(V7_PREFIX):
        return None
    manifest_path = _manifest_for(archive)
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not manifest.get("verified") or manifest.get("archive_sha256") != file_sha256(archive):
        return None
    database = manifest.get("database") or {}
    metrics = database.get("metrics") or {}
    return {
        "filename": archive.name,
        "manifest_filename": manifest_path.name,
        "kind": "v7_verified",
        "label": manifest.get("label") or "Verified V7 runtime backup",
        "size_bytes": archive.stat().st_size,
        "size_mb": round(archive.stat().st_size / 1024 / 1024, 2),
        "modified": _timestamp(archive),
        "created_at": manifest.get("created_at"),
        "verified": True,
        "archive_sha256": manifest.get("archive_sha256"),
        "sqlite_integrity": metrics.get("integrity_check"),
        "foreign_key_check": metrics.get("foreign_key_check", []),
        "authority": manifest.get("authority", {}),
        "download_url": f"/api/app-health/backups/download/{archive.name}",
        "manifest_download_url": f"/api/app-health/backups/manifest/{archive.name}",
    }


def _legacy_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    roots = (LEGACY_BACKUP_DIR, BACKUP_DIR)
    seen: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        for archive in root.glob("*.zip"):
            resolved = archive.resolve()
            if resolved in seen or archive.name.startswith(V7_PREFIX):
                continue
            seen.add(resolved)
            records.append({
                "filename": archive.name,
                "kind": "legacy",
                "label": "Legacy - not verified for SQLite authority",
                "size_bytes": archive.stat().st_size,
                "size_mb": round(archive.stat().st_size / 1024 / 1024, 2),
                "modified": _timestamp(archive),
                "verified": False,
            })
    return sorted(records, key=lambda item: item["modified"], reverse=True)


def _backups() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    verified = [record for archive in BACKUP_DIR.glob(f"{V7_PREFIX}*.zip") if (record := _verified_v7_record(archive))]
    return sorted(verified, key=lambda item: item["modified"], reverse=True), _legacy_records()


def _v7_archive(filename: str) -> Path:
    safe = _safe_filename(filename)
    if not safe.startswith(V7_PREFIX):
        raise ValueError("Only verified V7 backup archives are supported by this action")
    path = (BACKUP_DIR / safe).resolve()
    if BACKUP_DIR.resolve() not in path.parents or not path.exists() or not _verified_v7_record(path):
        raise FileNotFoundError("Verified V7 backup not found")
    return path


def _downloadable_legacy(filename: str) -> Path:
    safe = _safe_filename(filename)
    for root in (LEGACY_BACKUP_DIR, BACKUP_DIR):
        path = (root / safe).resolve()
        if root.resolve() in path.parents and path.exists() and path.is_file() and not safe.startswith(V7_PREFIX):
            return path
    raise FileNotFoundError("Backup not found")


def _refresh_latest_manifest() -> None:
    verified, _ = _backups()
    if not verified:
        LATEST_MANIFEST.unlink(missing_ok=True)
        return
    manifest_path = BACKUP_DIR / verified[0]["manifest_filename"]
    LATEST_MANIFEST.write_text(manifest_path.read_text(encoding="utf-8"), encoding="utf-8")


def _delete_backup(filename: str) -> str:
    safe = _safe_filename(filename)
    if safe.startswith(V7_PREFIX):
        archive = _v7_archive(safe)
        archive.unlink()
        _manifest_for(archive).unlink(missing_ok=True)
        _refresh_latest_manifest()
        return safe
    archive = _downloadable_legacy(safe)
    archive.unlink()
    return safe


def register_health_backup_routes_v443(app):
    @app.route("/api/app-health/backups")
    def app_health_backups_v443():
        verified, legacy = _backups()
        return jsonify({
            "ok": True,
            "version": "v7.5.1.2-verified-app-health-backups",
            "verified_backups": verified,
            "legacy_backups": legacy,
            "backups": verified + legacy,
        })

    @app.route("/api/app-health/backups/create", methods=["POST"])
    def app_health_create_backup_v443():
        try:
            manifest = create_backup(label="app_health")
            archive = BASE_DIR / str(manifest["archive"])
            record = _verified_v7_record(archive)
            if not record:
                raise RuntimeError("V7 backup verification did not produce a verified archive")
            return jsonify({"ok": True, "backup": record})
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500

    @app.route("/api/app-health/backups/restore", methods=["POST"])
    def app_health_restore_backup_v443():
        return jsonify({
            "ok": False,
            "error": "Live restore is disabled for SQLite-authoritative deployments. Use a verified restore rehearsal and the maintenance runbook.",
        }), 410

    @app.route("/api/app-health/backups/rehearse", methods=["POST"])
    def app_health_rehearse_backup_v7():
        payload = request.get_json(silent=True) or {}
        try:
            archive = _v7_archive(str(payload.get("filename") or ""))
            result = rehearse_restore(archive)
            return jsonify({"ok": bool((result.get("validation") or {}).get("ok")), "rehearsal": result})
        except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400

    @app.route("/api/app-health/backups/download/<filename>")
    def app_health_download_backup_v443(filename: str):
        try:
            path = _v7_archive(filename) if str(filename).startswith(V7_PREFIX) else _downloadable_legacy(filename)
            return send_file(path, as_attachment=True, download_name=path.name)
        except (FileNotFoundError, ValueError):
            return jsonify({"ok": False, "error": "Backup not found"}), 404

    @app.route("/api/app-health/backups/manifest/<filename>")
    def app_health_download_backup_manifest_v7(filename: str):
        try:
            archive = _v7_archive(filename)
            manifest = _manifest_for(archive)
            return send_file(manifest, as_attachment=True, download_name=manifest.name)
        except (FileNotFoundError, ValueError):
            return jsonify({"ok": False, "error": "Verified backup manifest not found"}), 404

    @app.route("/api/app-health/backups/delete", methods=["POST"])
    def app_health_delete_backup_v443():
        payload = request.get_json(silent=True) or {}
        try:
            deleted = _delete_backup(str(payload.get("filename") or ""))
            verified, legacy = _backups()
            return jsonify({"ok": True, "deleted": deleted, "verified_backups": verified, "legacy_backups": legacy})
        except FileNotFoundError:
            return jsonify({"ok": False, "error": "Backup not found"}), 404
        except ValueError as exc:
            return jsonify({"ok": False, "error": str(exc)}), 400
        except Exception as exc:
            return jsonify({"ok": False, "error": str(exc)}), 500
