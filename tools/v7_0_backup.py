#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sqlite3
import subprocess
import tempfile
import zipfile
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.authority import default_authority_map
from persistence.canonical_json import canonical_dumps
from persistence.importers import source_file_summaries
from persistence.provenance import file_sha256, text_sha256
from persistence.connection import connect
DATA = ROOT / "data"
BACKUPS = ROOT / "backups"
REPORTS = ROOT / "reports"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _git_commit() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return ""


def _app_release() -> str:
    app_version = DATA / "app_version.json"
    try:
        payload = json.loads(app_version.read_text(encoding="utf-8"))
        return str(payload.get("version") or payload.get("app_release") or "")
    except Exception:
        return ""


def _read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default
    except Exception:
        return default


def _sqlite_metrics(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False}
    try:
        with connect(path, read_only=True) as conn:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            fk_rows = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
            user_version = conn.execute("PRAGMA user_version").fetchone()[0]
            return {
                "exists": True,
                "integrity_check": integrity,
                "foreign_key_check": fk_rows,
                "user_version": user_version,
                "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
            }
    except Exception as exc:
        return {"exists": True, "error": str(exc)}


def _authority_map() -> dict[str, dict[str, Any]]:
    db_path = DATA / "angler_intel.sqlite3"
    if not db_path.exists():
        return default_authority_map()
    try:
        with connect(db_path, read_only=True) as conn:
            rows = [dict(row) for row in conn.execute("SELECT domain, authority, source_path, source_hash, note, updated_at FROM data_authority")]
        return {str(row["domain"]): row for row in rows} or default_authority_map()
    except Exception:
        return default_authority_map()


def _copy_json(path: Path, staging_root: Path) -> dict[str, Any]:
    rel = path.relative_to(ROOT)
    target = staging_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, target)
    return {
        "path": str(rel),
        "authority": "json",
        "size_bytes": target.stat().st_size,
        "modified_at": datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
        "sha256": file_sha256(target),
        "kind": "json",
    }


def _copy_tree(path: Path, staging_root: Path, *, generated_only: bool = True) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not path.exists():
        return records
    for item in sorted(path.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(ROOT)
        target = staging_root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        records.append(
            {
                "path": str(rel),
                "authority": "generated" if generated_only else "json",
                "size_bytes": target.stat().st_size,
                "modified_at": datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
                "sha256": file_sha256(target),
                "kind": "generated" if generated_only else "file",
            }
        )
    return records


def _copy_sqlite_backup(source: Path, staging_root: Path) -> dict[str, Any]:
    rel = source.relative_to(ROOT)
    target = staging_root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        with connect(source, read_only=True) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
        metrics = _sqlite_metrics(target)
    else:
        target.write_bytes(b"")
        metrics = {"exists": False}
    return {
        "path": str(rel),
        "authority": "sqlite",
        "size_bytes": target.stat().st_size if target.exists() else 0,
        "modified_at": datetime.fromtimestamp(target.stat().st_mtime, tz=timezone.utc).isoformat(timespec="seconds") if target.exists() else None,
        "sha256": file_sha256(target) if target.exists() else None,
        "kind": "sqlite",
        "metrics": metrics,
    }


def _build_manifest(staging_root: Path, *, label: str | None = None) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    json_targets = [
        DATA / "catches.json",
        DATA / "favorites.json",
        DATA / "gear_inventory.json",
        DATA / "gear_settings.json",
        DATA / "manual_waters.json",
        DATA / "target_profile.json",
        DATA / "reports_index.json",
        DATA / "authority.json",
        DATA / "gear_catalog_cache.json",
    ]
    for path in json_targets:
        if path.exists():
            files.append(_copy_json(path, staging_root))
    files.extend(_copy_tree(REPORTS, staging_root, generated_only=True))

    gear_uploads = DATA / "gear_uploads"
    if gear_uploads.exists():
        files.extend(_copy_tree(gear_uploads, staging_root, generated_only=False))

    sqlite_source = DATA / "angler_intel.sqlite3"
    sqlite_record = _copy_sqlite_backup(sqlite_source, staging_root)
    files.append(sqlite_record)

    authority_map = _authority_map()
    authority_values = sorted({str(value.get("authority") or "json") for value in authority_map.values()})
    manifest = {
        "backup_version": "v7.0-runtime-backup-manifest",
        "created_at": _now(),
        "app_release": _app_release(),
        "git_commit": _git_commit(),
        "label": label,
        "json_source_of_truth": not any(value == "sqlite" for value in authority_values),
        "sqlite_authority": authority_values[0] if len(authority_values) == 1 else "mixed",
        "database": sqlite_record,
        "authority": authority_map,
        "external_authority_manifest": _read_json(DATA / "authority.json", {}),
        "files": files,
        "source_manifest_hash": text_sha256(canonical_dumps(files)),
        "source_file_summaries": source_file_summaries(),
        "verified": False,
    }
    return manifest


def _zip_staging(staging_root: Path, archive_path: Path) -> None:
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(staging_root.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(staging_root))


def _verify_archive(archive_path: Path) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="angler-v7-verify-") as tmpdir:
        extract_root = Path(tmpdir)
        with zipfile.ZipFile(archive_path, "r") as zf:
            for member in zf.infolist():
                target = extract_root / member.filename
                resolved = target.resolve()
                if not str(resolved).startswith(str(extract_root.resolve())):
                    raise RuntimeError(f"Unsafe archive path: {member.filename}")
            zf.extractall(extract_root)

        json_paths = [p for p in extract_root.rglob("*.json") if p.name != "v7_runtime_backup_manifest.json"]
        for path in json_paths:
            if path.name.endswith(".sqlite3"):
                continue
            try:
                json.loads(path.read_text(encoding="utf-8"))
            except Exception as exc:
                raise RuntimeError(f"Invalid JSON in backup: {path.relative_to(extract_root)}: {exc}") from exc

        sqlite_path = extract_root / "data" / "angler_intel.sqlite3"
        if sqlite_path.exists() and sqlite_path.stat().st_size > 0:
            with connect(sqlite_path) as conn:
                integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                fk = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
                if integrity != "ok":
                    raise RuntimeError(f"Restored SQLite integrity failed: {integrity}")
                if fk:
                    raise RuntimeError(f"Restored SQLite foreign key violations: {fk}")
                return {"integrity_check": integrity, "foreign_key_check": fk}
        return {"integrity_check": "missing", "foreign_key_check": []}


def create_backup(*, label: str | None = None, output_dir: Path | None = None) -> dict[str, Any]:
    BACKUPS.mkdir(parents=True, exist_ok=True)
    output_dir = output_dir or BACKUPS
    output_dir.mkdir(parents=True, exist_ok=True)

    stamp = _stamp()
    safe_label = ""
    if label:
        safe_label = "_" + "".join(c if c.isalnum() or c in "-_" else "_" for c in label).strip("_")

    archive_path = output_dir / f"angler_intel_v7_runtime_backup_{stamp}{safe_label}.zip"
    manifest_path = output_dir / f"angler_intel_v7_runtime_backup_{stamp}{safe_label}.manifest.json"

    with tempfile.TemporaryDirectory(prefix="angler-v7-backup-") as tmpdir:
        staging_root = Path(tmpdir)
        manifest = _build_manifest(staging_root, label=label)
        manifest["archive"] = str(archive_path.relative_to(ROOT))
        manifest["manifest_path"] = str(manifest_path.relative_to(ROOT))
        manifest["verified"] = False
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        _zip_staging(staging_root, archive_path)
        verification = _verify_archive(archive_path)
        manifest["verified"] = True
        manifest["verification"] = verification
        manifest["archive_sha256"] = file_sha256(archive_path)
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    latest_manifest = BACKUPS / "latest_v7_runtime_backup_manifest.json"
    latest_manifest.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Angler Intel V7 runtime backup")
    parser.add_argument("--label", default="v7_runtime", help="Human label for the backup")
    parser.add_argument("--output-dir", default=str(BACKUPS), help="Directory for the archive and manifest")
    parser.add_argument("--json", action="store_true", help="Print JSON")
    args = parser.parse_args()

    manifest = create_backup(label=args.label, output_dir=Path(args.output_dir))
    rendered = json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True)
    if args.json:
        print(rendered)
    else:
        print(f"Created V7 backup: {manifest['archive']}")
        print(f"Manifest: {manifest['manifest_path']}")
        print("Verified SQLite-safe backup and archive extraction.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
