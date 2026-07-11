#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

APP_ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = APP_ROOT / "backups"
USER_DATA_BACKUP_DIR = BACKUP_ROOT / "user-data"
ALLOWED_ROOTS = {
    "data",
    "intelligence",
    "static/lures",
    "static/fish",
}
allowed_roots = ALLOWED_ROOTS


def _safe_name(filename: str) -> str:
    name = str(filename or "").strip()
    if not name:
        raise ValueError("Backup filename is required")

    candidate = Path(name)
    if candidate.is_absolute():
        raise ValueError("Absolute backup paths are not allowed")

    safe = candidate.name
    if safe != name:
        raise ValueError("Backup filename must not include path separators")

    if not safe.endswith(".zip"):
        raise ValueError("Backup must be a zip archive")

    if not re.match(r"^(angler-intel-cli-backup-|angler_intel_backup_).+\.zip$", safe):
        raise ValueError("Backup filename does not match the allowed naming convention")

    return safe


def safe_user_data_backup_path(filename: str) -> Path:
    safe = _safe_name(filename)
    USER_DATA_BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    path = (USER_DATA_BACKUP_DIR / safe).resolve()
    if USER_DATA_BACKUP_DIR.resolve() not in path.parents:
        raise ValueError("Backup path escaped the backup directory")
    return path


def _snapshot_pre_restore(base_dir: Path, snapshot_root: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    snapshot_dir = snapshot_root / f"pre-restore-{timestamp}"
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    for rel in ALLOWED_ROOTS:
        src = base_dir / rel
        if not src.exists():
            continue
        dst = snapshot_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
        else:
            shutil.copy2(src, dst)

    return snapshot_dir


def restore_user_data_backup(
    archive_path: Path,
    *,
    base_dir: Path = APP_ROOT,
    create_snapshot: bool = True,
) -> dict[str, Any]:
    archive_path = archive_path.expanduser().resolve()
    if not archive_path.exists() or not archive_path.is_file():
        raise ValueError(f"Backup not found: {archive_path}")

    if create_snapshot:
        snapshot_dir = _snapshot_pre_restore(base_dir, base_dir / "backups" / "pre-restore")
    else:
        snapshot_dir = None

    restored_roots: list[str] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        with zipfile.ZipFile(archive_path) as zf:
            for info in zf.infolist():
                name = info.filename
                if name.startswith("/") or ".." in Path(name).parts:
                    raise ValueError(f"Unsafe path in backup: {name}")

                if name.endswith("/"):
                    continue

                parts = Path(name).parts
                root1 = parts[0] if parts else ""
                root2 = "/".join(parts[:2]) if len(parts) >= 2 else root1
                if root1 not in allowed_roots and root2 not in allowed_roots:
                    continue

                zf.extract(info, tmp)

        for rel in allowed_roots:
            src = tmp / rel
            if not src.exists():
                continue

            dst = base_dir / rel
            dst.parent.mkdir(parents=True, exist_ok=True)

            if dst.exists():
                if dst.is_dir():
                    shutil.rmtree(dst)
                else:
                    dst.unlink()

            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

            restored_roots.append(rel)

    return {
        "ok": True,
        "archive": str(archive_path),
        "restored_roots": restored_roots,
        "pre_restore_snapshot": str(snapshot_dir) if snapshot_dir else None,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restore Angler Intel user-data backup")
    parser.add_argument("backup_zip", help="Path to a user-data backup archive")
    parser.add_argument("--json", action="store_true", help="Emit JSON output")
    args = parser.parse_args(argv)

    try:
        result = restore_user_data_backup(Path(args.backup_zip))
    except Exception as exc:
        payload = {"ok": False, "error": str(exc)}
        if args.json:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        else:
            print(f"Restore failed: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Restore complete from: {result['archive']}")
        print(f"Restored roots: {', '.join(result['restored_roots']) or 'none'}")
        if result.get("pre_restore_snapshot"):
            print(f"Pre-restore snapshot: {result['pre_restore_snapshot']}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
