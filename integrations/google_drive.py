"""Optional rclone-backed Google Drive export queue.

Drive is a secondary destination only. The queue is durable in SQLite, but no
cloud failure can alter local report, trip, recommendation, or authority data.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from persistence.connection import DEFAULT_DB, connect
from persistence.provenance import file_sha256
from persistence.runtime_paths import BASE_DIR

DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = BASE_DIR / "backups"
REPORTS_DIR = BASE_DIR / "reports"
V7_PREFIX = "angler_intel_v7_runtime_backup_"
MAX_OUTPUT = 1200


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _enabled(name: str, default: bool = False) -> bool:
    return str(os.environ.get(name, "1" if default else "0")).strip().lower() in {"1", "true", "yes", "on"}


def _safe_segment(value: str) -> str:
    text = str(value or "").strip().replace("\\", "/")
    if not text or text in {".", ".."} or "/" in text or "\x00" in text:
        raise ValueError("Unsafe export path segment")
    return text


@dataclass(frozen=True, slots=True)
class DriveConfig:
    enabled: bool
    remote: str
    root: str
    auto_backups: bool
    auto_reports: bool
    rclone_bin: str
    config_path: str | None


def get_config() -> DriveConfig:
    remote = str(os.environ.get("AI_GDRIVE_REMOTE", "anglerdrive")).strip()
    if not remote or any(char in remote for char in "/\\:\x00"):
        remote = ""
    root = str(os.environ.get("AI_GDRIVE_ROOT", "Angler Intel")).strip().strip("/") or "Angler Intel"
    return DriveConfig(
        enabled=_enabled("AI_GDRIVE_ENABLED"),
        remote=remote,
        root=root,
        auto_backups=_enabled("AI_GDRIVE_AUTO_BACKUPS"),
        auto_reports=_enabled("AI_GDRIVE_AUTO_REPORTS"),
        rclone_bin=str(os.environ.get("AI_RCLONE_BIN", "rclone")).strip() or "rclone",
        config_path=str(os.environ.get("AI_RCLONE_CONFIG", "")).strip() or None,
    )


def _rclone_command(config: DriveConfig, *args: str) -> list[str]:
    command = [config.rclone_bin]
    if config.config_path:
        command.extend(["--config", config.config_path])
    command.extend(args)
    return command


def _run_rclone(config: DriveConfig, *args: str, timeout: int = 25) -> dict[str, Any]:
    executable = shutil.which(config.rclone_bin) if "/" not in config.rclone_bin else config.rclone_bin
    if not executable or not Path(executable).exists():
        return {"ok": False, "error": "rclone is not installed", "code": None}
    try:
        result = subprocess.run(
            _rclone_command(config, *args),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "rclone command timed out", "code": None}
    except OSError as exc:
        return {"ok": False, "error": f"rclone execution failed: {type(exc).__name__}", "code": None}
    output = (result.stdout or "")[-MAX_OUTPUT:]
    return {"ok": result.returncode == 0, "error": None if result.returncode == 0 else f"rclone failed ({result.returncode}): {output}", "code": result.returncode}


def _remote(config: DriveConfig, *parts: str) -> str:
    if not config.remote:
        raise ValueError("Google Drive remote name is invalid")
    safe_parts = [_safe_segment(part) for part in parts]
    root_parts = [part for part in PurePosixPath(config.root).parts if part not in {"/", ".", ".."}]
    return f"{config.remote}:{PurePosixPath(*root_parts, *safe_parts).as_posix()}"


def drive_status() -> dict[str, Any]:
    config = get_config()
    available = bool(shutil.which(config.rclone_bin) or ("/" in config.rclone_bin and Path(config.rclone_bin).exists()))
    return {
        "enabled": config.enabled,
        "configured": bool(config.remote),
        "rclone_available": available,
        "remote": config.remote or None,
        "root": config.root,
        "auto_backups": config.auto_backups,
        "auto_reports": config.auto_reports,
    }


def test_connection() -> dict[str, Any]:
    config = get_config()
    if not config.enabled:
        return {"ok": False, "status": "disabled", "error": "Google Drive export is disabled."}
    remotes = _run_rclone(config, "listremotes")
    if not remotes["ok"]:
        return {"ok": False, "status": "unavailable", "error": remotes["error"]}
    listed = _run_rclone(config, "lsd", f"{config.remote}:")
    return {"ok": bool(listed["ok"]), "status": "ok" if listed["ok"] else "failed", "error": listed["error"]}


def _within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def _queue(conn, *, object_type: str, object_id: str, local_path: Path, remote_path: str) -> int:
    if not _within(local_path, BASE_DIR) or not local_path.exists() or not local_path.is_file():
        raise ValueError("Export artifact is unavailable")
    now = _now()
    local_hash = file_sha256(local_path)
    cursor = conn.execute(
        """INSERT INTO cloud_exports(provider, object_type, object_id, local_path, remote_path, local_hash, status, attempt_count, created_at, updated_at)
           VALUES('google_drive', ?, ?, ?, ?, ?, 'pending', 0, ?, ?)
           ON CONFLICT(provider, object_type, object_id, remote_path) DO UPDATE SET
             local_path=excluded.local_path, local_hash=excluded.local_hash,
             status=CASE WHEN cloud_exports.local_hash != excluded.local_hash THEN 'pending' ELSE cloud_exports.status END,
             updated_at=excluded.updated_at""",
        (object_type, object_id, str(local_path.relative_to(BASE_DIR)), remote_path, local_hash, now, now),
    )
    return int(cursor.lastrowid or 0)


def _verified_backup(archive: Path) -> dict[str, Any]:
    manifest_path = archive.with_suffix(".manifest.json")
    if not archive.name.startswith(V7_PREFIX) or not manifest_path.exists():
        raise ValueError("A verified V7 runtime backup is required")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    metrics = ((manifest.get("database") or {}).get("metrics") or {})
    if not manifest.get("verified") or manifest.get("archive_sha256") != file_sha256(archive):
        raise ValueError("Backup manifest verification failed")
    if metrics.get("integrity_check") != "ok" or metrics.get("foreign_key_check"):
        raise ValueError("Backup SQLite verification failed")
    return manifest


def queue_verified_backup(archive: str | Path, *, db_path: str | Path = DEFAULT_DB) -> list[int]:
    path = Path(archive).resolve()
    manifest = _verified_backup(path)
    created = datetime.fromisoformat(str(manifest["created_at"]).replace("Z", "+00:00"))
    year, month = created.strftime("%Y"), created.strftime("%m")
    config = get_config()
    with connect(db_path) as conn:
        with conn:
            return [
                _queue(conn, object_type="backup_archive", object_id=path.stem, local_path=path, remote_path=_remote(config, "Backups", year, month, path.name)),
                _queue(conn, object_type="backup_manifest", object_id=path.stem, local_path=path.with_suffix(".manifest.json"), remote_path=_remote(config, "Backups", year, month, path.with_suffix(".manifest.json").name)),
            ]


def queue_report_export(report_id: str, *, db_path: str | Path = DEFAULT_DB, reports_dir: str | Path = REPORTS_DIR) -> list[int]:
    safe_id = _safe_segment(report_id)
    with connect(db_path) as conn:
        row = conn.execute("SELECT id, created_at, json_path, html_path FROM trip_reports WHERE id=? AND status='active'", (safe_id,)).fetchone()
        if not row:
            raise ValueError("Active report not found")
        created = datetime.fromisoformat(str(row["created_at"]).replace("Z", "+00:00"))
        directory = Path(reports_dir)
        json_path = (BASE_DIR / str(row["json_path"])).resolve()
        html_path = (BASE_DIR / str(row["html_path"])).resolve()
        if not (_within(json_path, directory) and _within(html_path, directory)):
            raise ValueError("Report artifact path is invalid")
        config = get_config()
        year, month = created.strftime("%Y"), created.strftime("%m")
        with conn:
            return [
                _queue(conn, object_type="report_json", object_id=safe_id, local_path=json_path, remote_path=_remote(config, "Reports", year, month, safe_id, f"{safe_id}.json")),
                _queue(conn, object_type="report_html", object_id=safe_id, local_path=html_path, remote_path=_remote(config, "Reports", year, month, safe_id, f"{safe_id}.html")),
            ]


def _upload_row(row: dict[str, Any], config: DriveConfig) -> dict[str, Any]:
    local = (BASE_DIR / str(row["local_path"])).resolve()
    if not _within(local, BASE_DIR) or not local.exists() or file_sha256(local) != row["local_hash"]:
        return {"ok": False, "error": "Local export artifact is missing or has changed"}
    result = _run_rclone(config, "copyto", str(local), str(row["remote_path"]), timeout=45)
    return {"ok": bool(result["ok"]), "error": result["error"]}


def upload_pending(*, db_path: str | Path = DEFAULT_DB, object_id: str | None = None, limit: int = 40, force: bool = False) -> dict[str, Any]:
    config = get_config()
    if not config.enabled and not force:
        return {"ok": False, "status": "disabled", "uploaded": 0, "failed": 0, "pending": queue_summary(db_path).get("pending", 0)}
    connection = test_connection()
    if not connection.get("ok"):
        return {"ok": False, "status": connection.get("status"), "error": connection.get("error"), "uploaded": 0, "failed": 0}
    uploaded = failed = 0
    with connect(db_path) as conn:
        query = "SELECT * FROM cloud_exports WHERE provider='google_drive' AND status IN ('pending','failed')"
        params: list[Any] = []
        if object_id:
            query += " AND object_id=?"; params.append(object_id)
        query += " ORDER BY created_at, id LIMIT ?"; params.append(max(1, min(int(limit), 100)))
        rows = [dict(row) for row in conn.execute(query, params)]
        for row in rows:
            now = _now()
            with conn:
                conn.execute("UPDATE cloud_exports SET status='uploading', attempt_count=attempt_count+1, updated_at=?, last_error=NULL WHERE id=?", (now, row["id"]))
            result = _upload_row(row, config)
            with conn:
                if result["ok"]:
                    conn.execute("UPDATE cloud_exports SET status='ok', updated_at=?, completed_at=?, last_error=NULL WHERE id=?", (_now(), _now(), row["id"]))
                    uploaded += 1
                else:
                    conn.execute("UPDATE cloud_exports SET status='failed', updated_at=?, last_error=? WHERE id=?", (_now(), str(result["error"] or "upload failed")[:MAX_OUTPUT], row["id"]))
                    failed += 1
    return {"ok": failed == 0, "status": "ok" if failed == 0 else "partial", "uploaded": uploaded, "failed": failed, "pending": queue_summary(db_path).get("pending", 0)}


def queue_summary(db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    try:
        with connect(db_path, read_only=True) as conn:
            rows = [dict(row) for row in conn.execute("SELECT status, COUNT(*) AS total FROM cloud_exports WHERE provider='google_drive' GROUP BY status")]
            last = conn.execute("SELECT object_type, object_id, completed_at FROM cloud_exports WHERE provider='google_drive' AND status='ok' ORDER BY completed_at DESC LIMIT 1").fetchone()
            error = conn.execute("SELECT last_error FROM cloud_exports WHERE provider='google_drive' AND status='failed' ORDER BY updated_at DESC LIMIT 1").fetchone()
        counts = {str(row["status"]): int(row["total"]) for row in rows}
        return {"pending": counts.get("pending", 0), "failed": counts.get("failed", 0), "ok": counts.get("ok", 0), "last_success": dict(last) if last else None, "last_error": str(error["last_error"]) if error else None}
    except Exception as exc:
        return {"pending": 0, "failed": 0, "ok": 0, "last_success": None, "last_error": f"queue unavailable: {type(exc).__name__}"}


def public_status(db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    return {**drive_status(), **queue_summary(db_path)}
