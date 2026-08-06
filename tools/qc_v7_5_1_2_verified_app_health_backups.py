#!/usr/bin/env python3
"""Focused QC for verified V7 App Health backup operations."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import app as flask_app
import angler_health_backup_v443 as backup_mod


def _archive(root: Path, name: str, *, verified: bool = True) -> Path:
    archive = root / name
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        bundle.writestr("data/authority.json", '{"schema": 1, "domains": {}}')
        bundle.writestr("data/angler_intel.sqlite3", b"")
    manifest = {
        "verified": verified,
        "archive_sha256": hashlib.sha256(archive.read_bytes()).hexdigest(),
        "database": {"metrics": {"integrity_check": "ok", "foreign_key_check": []}},
        "authority": {"reports": {"authority": "sqlite"}},
    }
    archive.with_suffix(".manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return archive


def main() -> int:
    errors: list[str] = []
    with tempfile.TemporaryDirectory(prefix="angler-v7-5-1-2-qc-") as tmp:
        root = Path(tmp); backups = root / "backups"; legacy = backups / "user-data"
        backups.mkdir(); legacy.mkdir()
        verified = _archive(backups, "angler_intel_v7_runtime_backup_20260805_test.zip")
        (legacy / "angler-intel-cli-backup-legacy.zip").write_bytes(b"legacy")

        old = (backup_mod.BACKUP_DIR, backup_mod.LEGACY_BACKUP_DIR, backup_mod.LATEST_MANIFEST, backup_mod.rehearse_restore)
        backup_mod.BACKUP_DIR = backups
        backup_mod.LEGACY_BACKUP_DIR = legacy
        backup_mod.LATEST_MANIFEST = backups / "latest_v7_runtime_backup_manifest.json"
        backup_mod.rehearse_restore = lambda path: {"archive": str(path), "validation": {"ok": True}}
        try:
            client = flask_app.test_client()
            listing = client.get("/api/app-health/backups")
            payload = listing.get_json() or {}
            if listing.status_code != 200 or len(payload.get("verified_backups") or []) != 1:
                errors.append("verified V7 backups should be listed separately")
            if len(payload.get("legacy_backups") or []) != 1:
                errors.append("legacy backups should be listed separately")
            v7 = (payload.get("verified_backups") or [{}])[0]
            if not v7.get("verified") or v7.get("sqlite_integrity") != "ok":
                errors.append("verified metadata must include SQLite verification")
            if client.get(v7.get("download_url") or "").status_code != 200:
                errors.append("verified archive download should work")
            if client.get(v7.get("manifest_download_url") or "").status_code != 200:
                errors.append("verified manifest download should work")
            rehearsal = client.post("/api/app-health/backups/rehearse", json={"filename": verified.name})
            if rehearsal.status_code != 200 or not (rehearsal.get_json() or {}).get("ok"):
                errors.append("restore rehearsal should use only a verified V7 archive")
            restore = client.post("/api/app-health/backups/restore", json={"filename": verified.name})
            if restore.status_code != 410:
                errors.append("live directory replacement restore must be disabled")
            if client.post("/api/app-health/backups/rehearse", json={"filename": "../escape.zip"}).status_code != 400:
                errors.append("rehearsal must reject traversal")
            deleted = client.post("/api/app-health/backups/delete", json={"filename": verified.name})
            if deleted.status_code != 200 or verified.exists() or verified.with_suffix(".manifest.json").exists():
                errors.append("V7 delete must remove archive and paired manifest")
        finally:
            backup_mod.BACKUP_DIR, backup_mod.LEGACY_BACKUP_DIR, backup_mod.LATEST_MANIFEST, backup_mod.rehearse_restore = old

    backup_text = (ROOT / "angler_health_backup_v443.py").read_text(encoding="utf-8")
    if "backup_user_data.sh" in backup_text or "restore_user_data_backup" in backup_text:
        errors.append("App Health must not use legacy shell backup or live restore helper")
    if "create_backup" not in backup_text or "rehearse_restore" not in backup_text:
        errors.append("App Health must use V7 backup and rehearsal services")
    if errors:
        print("FAIL: " + "; ".join(errors))
        return 1
    print("PASS: V7.5.1.2 verified App Health backups QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
