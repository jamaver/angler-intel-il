#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

APP_ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = APP_ROOT / "backups"
DATA_DIR = APP_ROOT / "data"

EXCLUDE_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "venv",
    ".venv",
    "env",
    "node_modules",
}

INCLUDE_TOP_LEVEL = [
    "app.py",
    "requirements.txt",
    "templates",
    "static",
    "data",
    "intelligence",
    "tools",
]

BACKUP_INDEX = BACKUP_ROOT / "backup_index.json"


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def should_exclude(path: Path) -> bool:
    parts = set(path.parts)
    if parts & EXCLUDE_DIRS:
        return True

    # Avoid recursive backups inside backups/.
    try:
        rel = path.relative_to(APP_ROOT)
        if rel.parts and rel.parts[0] == "backups":
            return True
    except ValueError:
        pass

    if path.name.endswith(".pyc"):
        return True

    return False


def safe_json_status(path: Path) -> dict:
    info = {
        "path": str(path.relative_to(APP_ROOT)),
        "exists": path.exists(),
    }

    if not path.exists():
        return info

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        info["valid_json"] = True
        info["top_level_type"] = type(payload).__name__
        if isinstance(payload, list):
            info["item_count_estimate"] = len(payload)
        elif isinstance(payload, dict):
            info["item_count_estimate"] = len(payload)
        else:
            info["item_count_estimate"] = 1
    except Exception as exc:
        info["valid_json"] = False
        info["error"] = str(exc)

    return info


def sqlite_status(path: Path) -> dict:
    info = {
        "path": str(path.relative_to(APP_ROOT)),
        "exists": path.exists(),
        "size_bytes": path.stat().st_size if path.exists() else 0,
    }

    if not path.exists():
        return info

    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        conn.execute("PRAGMA query_only=ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        info["integrity_check"] = integrity
        info["valid_sqlite"] = integrity == "ok"
    except Exception as exc:
        info["valid_sqlite"] = False
        info["error"] = str(exc)

    return info


def directory_status(path: Path) -> dict:
    info = {
        "path": str(path.relative_to(APP_ROOT)),
        "exists": path.exists(),
    }
    if not path.exists() or not path.is_dir():
        return info
    try:
        info["file_count"] = sum(1 for item in path.rglob("*") if item.is_file())
    except Exception:
        info["file_count"] = None
    return info


def collect_files() -> list[Path]:
    files: list[Path] = []

    for item in INCLUDE_TOP_LEVEL:
        path = APP_ROOT / item
        if not path.exists():
            continue

        if path.is_file():
            if not should_exclude(path):
                files.append(path)
            continue

        for sub in path.rglob("*"):
            if sub.is_file() and not should_exclude(sub):
                files.append(sub)

    return sorted(set(files))


def load_index() -> list[dict]:
    if not BACKUP_INDEX.exists():
        return []

    try:
        payload = json.loads(BACKUP_INDEX.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
    except Exception:
        pass

    return []


def save_index(items: list[dict]) -> None:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    BACKUP_INDEX.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")


def create_backup(label: str | None = None) -> dict:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    stamp = now_stamp()
    safe_label = ""
    if label:
        safe_label = "_" + "".join(c if c.isalnum() or c in "-_" else "_" for c in label).strip("_")

    archive = BACKUP_ROOT / f"angler_intel_backup_{stamp}{safe_label}.zip"
    manifest_name = "backup_manifest.json"

    files = collect_files()

    manifest = {
        "backup_version": "v4.5.2",
        "created_at": now_utc(),
        "app": "Angler Intel IL",
        "source_root": str(APP_ROOT),
        "archive": str(archive.relative_to(APP_ROOT)),
        "label": label,
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
        "file_count": len(files),
        "json_health": [
            safe_json_status(APP_ROOT / "data" / "gear_inventory.json"),
            safe_json_status(APP_ROOT / "data" / "manual_waters.json"),
            safe_json_status(APP_ROOT / "data" / "target_profile.json"),
            safe_json_status(APP_ROOT / "data" / "gear_settings.json"),
            safe_json_status(APP_ROOT / "data" / "favorites.json"),
            safe_json_status(APP_ROOT / "data" / "catches.json"),
            safe_json_status(APP_ROOT / "data" / "saved_reports.json"),
        ],
        "gear_media": directory_status(APP_ROOT / "data" / "gear_uploads"),
        "sqlite_health": sqlite_status(APP_ROOT / "data" / "angler_intel.sqlite3"),
        "included_top_level": INCLUDE_TOP_LEVEL,
    }

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            arcname = str(path.relative_to(APP_ROOT))
            zf.write(path, arcname)

        zf.writestr(manifest_name, json.dumps(manifest, indent=2, ensure_ascii=False))

    manifest["archive_size_bytes"] = archive.stat().st_size

    index = load_index()
    index.insert(0, manifest)
    index = index[:25]
    save_index(index)

    latest_manifest = BACKUP_ROOT / "latest_backup_manifest.json"
    latest_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    return manifest


def backup_status() -> dict:
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)

    archives = sorted(
        BACKUP_ROOT.glob("angler_intel_backup_*.zip"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    index = load_index()

    latest = None
    if archives:
        latest_path = archives[0]
        latest = {
            "path": str(latest_path.relative_to(APP_ROOT)),
            "size_bytes": latest_path.stat().st_size,
            "modified_at_epoch": latest_path.stat().st_mtime,
        }

    return {
        "backup_version": "v4.5.2",
        "backup_root": str(BACKUP_ROOT.relative_to(APP_ROOT)),
        "archive_count": len(archives),
        "latest": latest,
        "index_count": len(index),
        "recent": index[:5],
        "json_source_of_truth": True,
        "sqlite_role": "mirror/read-only foundation",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Angler Intel IL backup tool")
    parser.add_argument("--create", action="store_true", help="Create a full backup zip")
    parser.add_argument("--status", action="store_true", help="Show backup status")
    parser.add_argument("--label", default=None, help="Optional backup label")
    parser.add_argument("--json", action="store_true", help="Output JSON only")
    args = parser.parse_args()

    if args.create:
        result = create_backup(args.label)
    else:
        result = backup_status()

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if args.create:
            print("Backup created")
            print(f"Archive: {result['archive']}")
            print(f"Files: {result['file_count']}")
            print(f"Size: {result.get('archive_size_bytes')} bytes")
            print("JSON remains source of truth.")
        else:
            print("=== Backup Status ===")
            print(f"Backup root: {result['backup_root']}")
            print(f"Archives: {result['archive_count']}")
            if result["latest"]:
                print(f"Latest: {result['latest']['path']}")
                print(f"Latest size: {result['latest']['size_bytes']} bytes")
            else:
                print("Latest: none")
            print("JSON remains source of truth.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
