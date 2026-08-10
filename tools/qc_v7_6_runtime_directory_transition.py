#!/usr/bin/env python3
"""End-to-end temporary-tree QC for the V7.6.1 runtime transition."""
from __future__ import annotations

import ast
import importlib.util
import json
import sqlite3
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _module():
    tool = ROOT / "tools" / "v7_6_runtime_transition.py"
    spec = importlib.util.spec_from_file_location("runtime_transition", tool)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _configure(module, root: Path) -> dict[Path, Path]:
    paths = {
        root / "data" / "target_profile.json": root / "instance" / "compatibility" / "target_profile.json",
        root / "data" / "angler_intel.sqlite3": root / "instance" / "angler_intel.sqlite3",
        root / "data" / "gear_uploads": root / "instance" / "uploads",
        root / "data" / "exports": root / "instance" / "exports",
        root / "reports": root / "instance" / "reports",
        root / "backups": root / "instance" / "backups",
    }
    module.ROOT = root
    module.INSTANCE = root / "instance"
    module.STATE_FILE = module.INSTANCE / "runtime_transition_v7_6.json"
    module.PATHS = paths
    return paths


def _seed(root: Path) -> None:
    (root / "data" / "gear_uploads").mkdir(parents=True)
    (root / "data" / "exports").mkdir(parents=True)
    (root / "reports").mkdir(parents=True)
    (root / "backups").mkdir(parents=True)
    (root / "data" / "target_profile.json").write_text(json.dumps({"default_species": "Largemouth Bass"}), encoding="utf-8")
    (root / "data" / "gear_uploads" / "rod.png").write_bytes(b"upload")
    (root / "data" / "exports" / "out.json").write_text("{}", encoding="utf-8")
    (root / "reports" / "trip.json").write_text("{}", encoding="utf-8")
    (root / "backups" / "backup.zip").write_bytes(b"zip")
    db = root / "data" / "angler_intel.sqlite3"
    with sqlite3.connect(db) as conn:
        conn.execute("CREATE TABLE catches (id TEXT PRIMARY KEY, species TEXT)")
        conn.execute("INSERT INTO catches VALUES ('catch-1', 'Bass')")


def main() -> int:
    tool = ROOT / "tools" / "v7_6_runtime_transition.py"
    ast.parse(tool.read_text(encoding="utf-8"))
    for needle in ("--resume", "--rollback", "RESUME_RUNTIME_DATA", "ROLLBACK_RUNTIME_DATA", "schema\": 2", "assert_logical_database_match"):
        assert needle in tool.read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="angler-v7-6-qc-") as temp_dir:
        root = Path(temp_dir)
        _seed(root)
        module = _module()
        paths = _configure(module, root)
        result = module.apply()
        assert result["ok"]
        for legacy, target in paths.items():
            assert legacy.is_symlink() and legacy.resolve() == target.resolve() and target.exists()
        assert module.status()["state"]["schema"] == 2
        # Existing destinations prevent reapply; rollback restores only an
        # unchanged instance copy.
        try:
            module.apply()
            raise AssertionError("repeated apply unexpectedly succeeded")
        except RuntimeError:
            pass
        rolled = module.rollback()
        assert rolled["ok"]
        for legacy in paths:
            assert legacy.exists() and not legacy.is_symlink()

    with tempfile.TemporaryDirectory(prefix="angler-v7-6-resume-") as temp_dir:
        root = Path(temp_dir)
        _seed(root)
        module = _module()
        paths = _configure(module, root)
        legacy, target = next(iter(paths.items()))
        state = module._new_state()
        module._write_state(state)
        module._copy(legacy, target)  # simulated interruption after copy
        module._set(state, legacy, "copied")
        resumed = module.resume()
        assert resumed["ok"] and legacy.is_symlink()
        # Logical database mismatch must reject verification.
        db_legacy = root / "instance" / "legacy_pre_v7_6" / "data" / "angler_intel.sqlite3"
        db_target = root / "instance" / "angler_intel.sqlite3"
        with sqlite3.connect(db_target) as conn:
            conn.execute("INSERT INTO catches VALUES ('catch-2', 'Walleye')")
        try:
            module._validate(db_legacy, db_target)
            raise AssertionError("SQLite content mismatch unexpectedly passed")
        except RuntimeError:
            pass
    print("PASS: V7.6.1 runtime transition workflow QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
