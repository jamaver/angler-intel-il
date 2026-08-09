#!/usr/bin/env python3
"""Copy, verify, and activate the V7.6 instance runtime layout.

This tool intentionally does not stop or start the service. Run it only while
the service is stopped, after a verified V7 runtime backup. It preserves each
legacy source under ``instance/legacy_pre_v7_6`` and replaces the legacy path
with a compatibility symlink, keeping older code paths functional.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
INSTANCE = ROOT / "instance"
STATE_FILE = INSTANCE / "runtime_transition_v7_6.json"

PATHS = {
    ROOT / "data" / "angler_intel.sqlite3": INSTANCE / "angler_intel.sqlite3",
    ROOT / "data" / "authority.json": INSTANCE / "authority.json",
    ROOT / "data" / "catches.json": INSTANCE / "compatibility" / "catches.json",
    ROOT / "data" / "favorites.json": INSTANCE / "compatibility" / "favorites.json",
    ROOT / "data" / "gear_inventory.json": INSTANCE / "compatibility" / "gear_inventory.json",
    ROOT / "data" / "gear_settings.json": INSTANCE / "compatibility" / "gear_settings.json",
    ROOT / "data" / "gear_catalog_cache.json": INSTANCE / "cache" / "gear_catalog_cache.json",
    ROOT / "data" / "manual_waters.json": INSTANCE / "compatibility" / "manual_waters.json",
    ROOT / "data" / "target_profile.json": INSTANCE / "compatibility" / "target_profile.json",
    ROOT / "data" / "reports_index.json": INSTANCE / "compatibility" / "reports_index.json",
    ROOT / "data" / "gear_uploads": INSTANCE / "uploads",
    ROOT / "data" / "exports": INSTANCE / "exports",
    ROOT / "reports": INSTANCE / "reports",
    ROOT / "backups": INSTANCE / "backups",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_hashes(root: Path) -> dict[str, str]:
    if root.is_file():
        return {root.name: _hash(root)}
    return {str(path.relative_to(root)): _hash(path) for path in sorted(root.rglob("*")) if path.is_file()}


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_file() and source.suffix == ".sqlite3":
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
    elif source.is_file():
        shutil.copy2(source, target)
    else:
        shutil.copytree(source, target, symlinks=True)


def _validate(source: Path, target: Path) -> None:
    if _tree_hashes(source) != _tree_hashes(target):
        raise RuntimeError(f"Hash mismatch after copying {source.relative_to(ROOT)}")
    if target.is_file() and target.suffix == ".json":
        json.loads(target.read_text(encoding="utf-8"))
    if target.is_file() and target.suffix == ".sqlite3":
        with sqlite3.connect(f"file:{target}?mode=ro", uri=True) as conn:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("SQLite integrity check failed")
            if list(conn.execute("PRAGMA foreign_key_check")):
                raise RuntimeError("SQLite foreign-key check failed")


def status() -> dict[str, object]:
    records = []
    for legacy, target in PATHS.items():
        records.append({
            "legacy": str(legacy.relative_to(ROOT)), "instance": str(target.relative_to(ROOT)),
            "legacy_exists": legacy.exists() or legacy.is_symlink(), "legacy_is_link": legacy.is_symlink(),
            "resolved": str(legacy.resolve().relative_to(ROOT)) if (legacy.exists() or legacy.is_symlink()) else None,
            "target_exists": target.exists(),
        })
    return {"instance": str(INSTANCE), "state_exists": STATE_FILE.exists(), "paths": records}


def apply() -> dict[str, object]:
    if STATE_FILE.exists():
        raise RuntimeError("V7.6 transition state already exists; inspect --status instead of reapplying")
    legacy_root = INSTANCE / "legacy_pre_v7_6"
    records = []
    for legacy, target in PATHS.items():
        if not legacy.exists() or legacy.is_symlink():
            continue
        _copy(legacy, target)
        _validate(legacy, target)
        parked = legacy_root / legacy.relative_to(ROOT)
        parked.parent.mkdir(parents=True, exist_ok=True)
        legacy.rename(parked)
        link_tmp = legacy.with_name(legacy.name + ".v7_6_link")
        link_tmp.symlink_to(target)
        os.replace(link_tmp, legacy)
        records.append({"legacy": str(legacy.relative_to(ROOT)), "instance": str(target.relative_to(ROOT)), "parked": str(parked.relative_to(ROOT))})
    INSTANCE.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps({"schema": 1, "activated_at": _now(), "records": records}, indent=2) + "\n", encoding="utf-8")
    return {"ok": True, "records": records, "state": str(STATE_FILE.relative_to(ROOT))}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if sum(bool(value) for value in (args.status, args.dry_run, args.apply)) != 1:
        parser.error("choose exactly one of --status, --dry-run, or --apply")
    if args.apply:
        if args.confirm != "MOVE_RUNTIME_DATA":
            parser.error("--apply requires --confirm MOVE_RUNTIME_DATA")
        payload = apply()
    elif args.dry_run:
        payload = {"ok": True, "dry_run": True, **status()}
    else:
        payload = status()
    print(json.dumps(payload, indent=2) if args.json else payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
