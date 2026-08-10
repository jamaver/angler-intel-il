#!/usr/bin/env python3
"""Journaled V7.6 runtime relocation with explicit resume and rollback.

The tool never starts or stops Angler Intel. Run apply, resume, and rollback
only with the service stopped and a verified V7 backup available.
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
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.sqlite_digest import assert_logical_database_match, logical_database_digest

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


def _same_content(left: Path, right: Path) -> bool:
    if left.is_file() and right.is_file() and left.suffix == ".sqlite3":
        try:
            assert_logical_database_match(left, right)
            return True
        except RuntimeError:
            return False
    return _tree_hashes(left) == _tree_hashes(right)


def _copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if source.is_file() and source.suffix == ".sqlite3":
        if target.exists():
            target.unlink()
        with sqlite3.connect(f"file:{source}?mode=ro", uri=True) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
    elif source.is_file():
        shutil.copy2(source, target)
    else:
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, symlinks=True)


def _validate(source: Path, target: Path) -> dict[str, Any]:
    if not source.exists() or not target.exists():
        raise RuntimeError("Runtime source or destination is missing during validation")
    if source.is_file() and source.suffix == ".sqlite3":
        return assert_logical_database_match(source, target)
    if _tree_hashes(source) != _tree_hashes(target):
        raise RuntimeError(f"Hash mismatch after copying {source.relative_to(ROOT)}")
    if target.is_file() and target.suffix == ".json":
        json.loads(target.read_text(encoding="utf-8"))
    return {"match": True}


def _relative(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _parked(legacy: Path) -> Path:
    return INSTANCE / "legacy_pre_v7_6" / legacy.relative_to(ROOT)


def _item(legacy: Path, target: Path) -> dict[str, Any]:
    return {"target": _relative(target), "parked": _relative(_parked(legacy)), "status": "pending", "updated_at": _now(), "error": None}


def _new_state() -> dict[str, Any]:
    return {"schema": 2, "started_at": _now(), "completed_at": None, "items": {_relative(legacy): _item(legacy, target) for legacy, target in PATHS.items()}}


def _load_state() -> dict[str, Any] | None:
    if not STATE_FILE.exists():
        return None
    payload = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    if payload.get("schema") == 2 and isinstance(payload.get("items"), dict):
        return payload
    # V7.6 initial state did not journal individual steps. Its recorded paths
    # are already linked, so normalize it as completed without moving data.
    if payload.get("schema") == 1 and isinstance(payload.get("records"), list):
        state = _new_state()
        for record in payload["records"]:
            item = state["items"].get(str(record.get("legacy") or ""))
            if item:
                item["status"] = "complete"
        state["completed_at"] = payload.get("activated_at") or _now()
        return state
    raise RuntimeError("Runtime transition state is malformed")


def _write_state(state: dict[str, Any]) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = STATE_FILE.with_suffix(".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2, sort_keys=True)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, STATE_FILE)


def _set(state: dict[str, Any], legacy: Path, status: str, *, error: str | None = None) -> None:
    item = state["items"][_relative(legacy)]
    item["status"] = status
    item["error"] = error
    item["updated_at"] = _now()
    _write_state(state)


def _link(legacy: Path, target: Path) -> None:
    if legacy.is_symlink():
        if legacy.resolve() != target.resolve():
            raise RuntimeError(f"Compatibility link points to an unexpected target: {_relative(legacy)}")
        return
    if legacy.exists():
        raise RuntimeError(f"Legacy path still exists before link activation: {_relative(legacy)}")
    temporary = legacy.with_name(legacy.name + ".v7_6_link")
    temporary.symlink_to(target)
    os.replace(temporary, legacy)


def _advance_item(state: dict[str, Any], legacy: Path, target: Path) -> None:
    item = state["items"][_relative(legacy)]
    status = str(item.get("status") or "pending")
    parked = _parked(legacy)
    if status == "complete":
        return
    try:
        if status == "pending":
            _copy(legacy, target)
            _set(state, legacy, "copied")
            status = "copied"
        if status == "copied":
            _validate(legacy, target)
            _set(state, legacy, "verified")
            status = "verified"
        if status == "verified":
            parked.parent.mkdir(parents=True, exist_ok=True)
            if legacy.exists() and not legacy.is_symlink():
                legacy.rename(parked)
            elif not parked.exists():
                raise RuntimeError(f"Cannot park missing legacy path: {_relative(legacy)}")
            _set(state, legacy, "parked")
            status = "parked"
        if status == "parked":
            _link(legacy, target)
            _set(state, legacy, "linked")
            status = "linked"
        if status == "linked":
            _set(state, legacy, "complete")
    except Exception as exc:
        _set(state, legacy, "failed", error=f"{type(exc).__name__}: {exc}")
        raise


def status() -> dict[str, Any]:
    state = _load_state()
    records = []
    for legacy, target in PATHS.items():
        item = (state or {}).get("items", {}).get(_relative(legacy), {})
        records.append({
            "legacy": _relative(legacy), "instance": _relative(target),
            "status": item.get("status", "untracked"), "error": item.get("error"),
            "legacy_exists": legacy.exists() or legacy.is_symlink(), "legacy_is_link": legacy.is_symlink(),
            "resolved": _relative(legacy.resolve()) if (legacy.exists() or legacy.is_symlink()) else None,
            "target_exists": target.exists(),
        })
    return {"instance": str(INSTANCE), "state": state, "paths": records}


def apply() -> dict[str, Any]:
    if STATE_FILE.exists():
        raise RuntimeError("Transition state already exists; use --status or --resume")
    state = _new_state()
    _write_state(state)
    for legacy, target in PATHS.items():
        if legacy.exists() and not legacy.is_symlink():
            _advance_item(state, legacy, target)
    state["completed_at"] = _now()
    _write_state(state)
    return {"ok": True, **status()}


def resume() -> dict[str, Any]:
    state = _load_state()
    if state is None:
        raise RuntimeError("No runtime transition state exists to resume")
    for legacy, target in PATHS.items():
        item = state["items"][_relative(legacy)]
        if item.get("status") == "failed":
            parked = _parked(legacy)
            if legacy.is_symlink():
                item["status"] = "linked"
            elif parked.exists() and not legacy.exists():
                item["status"] = "parked"
            elif legacy.exists() and target.exists():
                item["status"] = "copied"
            elif legacy.exists():
                item["status"] = "pending"
            else:
                raise RuntimeError(f"Cannot determine a safe resume point: {_relative(legacy)}")
            _write_state(state)
        if item.get("status") != "complete":
            _advance_item(state, legacy, target)
    state["completed_at"] = _now()
    _write_state(state)
    return {"ok": True, **status()}


def rollback() -> dict[str, Any]:
    state = _load_state()
    if state is None:
        raise RuntimeError("No runtime transition state exists to roll back")
    restored: list[str] = []
    for legacy, target in reversed(list(PATHS.items())):
        item = state["items"].get(_relative(legacy), {})
        parked = _parked(legacy)
        if item.get("status") not in {"complete", "linked", "parked"}:
            continue
        if not parked.exists() or not target.exists():
            raise RuntimeError(f"Cannot roll back missing runtime item: {_relative(legacy)}")
        if not _same_content(parked, target):
            raise RuntimeError(f"Refusing rollback because current instance data diverged: {_relative(legacy)}")
        if legacy.is_symlink():
            legacy.unlink()
        elif legacy.exists():
            raise RuntimeError(f"Refusing rollback because legacy path is occupied: {_relative(legacy)}")
        legacy.parent.mkdir(parents=True, exist_ok=True)
        parked.rename(legacy)
        _set(state, legacy, "pending")
        restored.append(_relative(legacy))
    state["rolled_back_at"] = _now()
    state["completed_at"] = None
    _write_state(state)
    return {"ok": True, "restored": restored, **status()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument("--status", action="store_true")
    modes.add_argument("--dry-run", action="store_true")
    modes.add_argument("--apply", action="store_true")
    modes.add_argument("--resume", action="store_true")
    modes.add_argument("--rollback", action="store_true")
    parser.add_argument("--confirm", default="")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.apply:
        if args.confirm != "MOVE_RUNTIME_DATA":
            parser.error("--apply requires --confirm MOVE_RUNTIME_DATA")
        payload = apply()
    elif args.resume:
        if args.confirm != "RESUME_RUNTIME_DATA":
            parser.error("--resume requires --confirm RESUME_RUNTIME_DATA")
        payload = resume()
    elif args.rollback:
        if args.confirm != "ROLLBACK_RUNTIME_DATA":
            parser.error("--rollback requires --confirm ROLLBACK_RUNTIME_DATA")
        payload = rollback()
    elif args.dry_run:
        payload = {"ok": True, "dry_run": True, **status()}
    else:
        payload = status()
    print(json.dumps(payload, indent=2, sort_keys=True) if args.json else payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
