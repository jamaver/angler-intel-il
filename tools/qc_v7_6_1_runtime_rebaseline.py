#!/usr/bin/env python3
"""Focused QC for V7.6.1 recovery-baseline recording."""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "tools" / "v7_6_1_rebaseline_runtime.py"
    spec = importlib.util.spec_from_file_location("rebaseline", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _db(path: Path, count: int) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE catches (id TEXT PRIMARY KEY)")
        for index in range(count):
            conn.execute("INSERT INTO catches VALUES (?)", (f"catch-{index}",))


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-6-1-baseline-qc-") as temp_dir:
        root = Path(temp_dir)
        module = _load()
        module.ROOT = root
        module.INSTANCE = root / "instance"
        module.STATE_PATH = module.INSTANCE / "runtime_transition_v7_6.json"
        module.BASELINE_PATH = module.INSTANCE / "runtime_recovery_baseline_v7_6_1.json"
        module.ACTIVE_DB = module.INSTANCE / "angler_intel.sqlite3"
        module.PARKED_DB = module.INSTANCE / "legacy_pre_v7_6" / "data" / "angler_intel.sqlite3"
        module.ACTIVE_DB.parent.mkdir(parents=True)
        module.PARKED_DB.parent.mkdir(parents=True)
        _db(module.ACTIVE_DB, 1)
        _db(module.PARKED_DB, 2)
        inspected = module.inspect()
        assert inspected["match"] is False and "catches" in inspected["differences"]
        staging = root / "staging" / "data"
        staging.mkdir(parents=True)
        with sqlite3.connect(module.ACTIVE_DB) as src, sqlite3.connect(staging / "angler_intel.sqlite3") as dst:
            src.backup(dst)
        archive = root / "backup.zip"
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.write(staging / "angler_intel.sqlite3", "data/angler_intel.sqlite3")
        manifest = archive.with_suffix(".manifest.json")
        manifest.write_text(json.dumps({"verified": True}), encoding="utf-8")
        module.STATE_PATH.write_text(json.dumps({"schema": 2, "items": {"data/angler_intel.sqlite3": {"status": "complete", "rollback_eligible": True}}}), encoding="utf-8")
        recorded = module.record(archive, manifest)
        assert recorded["parked_baseline"]["rollback_eligible"] is False
        assert module.BASELINE_PATH.exists()
        state = json.loads(module.STATE_PATH.read_text(encoding="utf-8"))
        assert state["items"]["data/angler_intel.sqlite3"]["rollback_eligible"] is False
    print("PASS: V7.6.1 runtime rebaseline QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
