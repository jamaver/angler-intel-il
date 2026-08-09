#!/usr/bin/env python3
"""Focused QC for the V7.6 runtime-directory transition tool."""
from __future__ import annotations

import ast
import importlib.util
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    tool = ROOT / "tools" / "v7_6_runtime_transition.py"
    source = tool.read_text(encoding="utf-8")
    ast.parse(source)
    for needle in ("--dry-run", "--apply", "MOVE_RUNTIME_DATA", "legacy_pre_v7_6", "PRAGMA integrity_check", "PRAGMA foreign_key_check"):
        assert needle in source, f"missing transition safety: {needle}"
    config = (ROOT / "deploy" / "systemd" / "angler-intel-runtime.conf").read_text(encoding="utf-8")
    for needle in ("AI_INSTANCE_DIR", "AI_SQLITE_DB_PATH", "AI_AUTHORITY_MANIFEST"):
        assert needle in config
    docs = (ROOT / "docs" / "v7" / "V7_6_RUNTIME_DIRECTORY_TRANSITION.md").read_text(encoding="utf-8")
    assert "verified V7 backup" in docs
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert "backups/" in ignore and "reports/" in ignore and "data/angler_intel.sqlite3" in ignore
    spec = importlib.util.spec_from_file_location("runtime_transition", tool)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with tempfile.TemporaryDirectory(prefix="angler-v7-6-qc-") as temp_dir:
        root = Path(temp_dir)
        source = root / "data" / "target_profile.json"
        source.parent.mkdir(parents=True)
        source.write_text(json.dumps({"default_species": "Largemouth Bass"}), encoding="utf-8")
        module.ROOT = root
        module.INSTANCE = root / "instance"
        module.STATE_FILE = module.INSTANCE / "runtime_transition_v7_6.json"
        module.PATHS = {source: module.INSTANCE / "compatibility" / "target_profile.json"}
        result = module.apply()
        assert result["ok"] and source.is_symlink()
        assert json.loads(source.read_text(encoding="utf-8"))["default_species"] == "Largemouth Bass"
        assert (module.INSTANCE / "legacy_pre_v7_6" / "data" / "target_profile.json").exists()
    print("PASS: V7.6 runtime directory transition QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
