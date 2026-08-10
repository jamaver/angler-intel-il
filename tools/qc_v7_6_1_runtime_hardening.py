#!/usr/bin/env python3
"""Focused QC for V7.6.1 logical hashes, ZIP containment, and path rules."""
from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.runtime_paths import resolve_runtime_path
from persistence.safe_zip import safe_extract
from persistence.sqlite_digest import assert_logical_database_match, logical_database_digest


def _archive(path: Path, member: str) -> None:
    with zipfile.ZipFile(path, "w") as bundle:
        bundle.writestr(member, "unsafe")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-6-1-qc-") as temp_dir:
        root = Path(temp_dir)
        source = root / "source.sqlite3"
        target = root / "target.sqlite3"
        with sqlite3.connect(source) as conn:
            conn.execute("CREATE TABLE payload (id TEXT PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO payload VALUES ('a', 'one')")
        with sqlite3.connect(source) as src, sqlite3.connect(target) as dst:
            src.backup(dst)
        matched = assert_logical_database_match(source, target)
        assert matched["match"] and logical_database_digest(source)["tables"]["payload"]["rows"] == 1
        with sqlite3.connect(target) as conn:
            conn.execute("INSERT INTO payload VALUES ('b', 'two')")
        try:
            assert_logical_database_match(source, target)
            raise AssertionError("logical mismatch unexpectedly passed")
        except RuntimeError:
            pass
        for member in ("../escape", "../../etc/passwd", "/absolute", "nested/../../traversal", "C:\\escape"):
            archive = root / "unsafe.zip"
            _archive(archive, member)
            try:
                safe_extract(archive, root / "output")
                raise AssertionError(f"unsafe ZIP member accepted: {member}")
            except RuntimeError:
                pass
        # A normal sibling-looking directory inside the extraction root is
        # valid. This proves containment, rather than a brittle string prefix.
        sibling = root / "sibling.zip"
        _archive(sibling, "root-other/file")
        safe_extract(sibling, root / "output")
        assert (root / "output" / "root-other" / "file").exists()
        safe = root / "safe.zip"
        _archive(safe, "nested/file.txt")
        safe_extract(safe, root / "safe-output")
        assert (root / "safe-output" / "nested" / "file.txt").read_text(encoding="utf-8") == "unsafe"

    previous_instance = os.environ.get("AI_INSTANCE_DIR")
    previous_canonical = os.environ.get("AI_SQLITE_DB_PATH")
    previous_legacy = os.environ.get("AI_SQLITE_PATH")
    try:
        os.environ["AI_INSTANCE_DIR"] = "/tmp/ai-instance"
        os.environ["AI_SQLITE_DB_PATH"] = "/tmp/explicit.sqlite3"
        os.environ["AI_SQLITE_PATH"] = "/tmp/legacy.sqlite3"
        resolved = resolve_runtime_path("sqlite", legacy_path="/tmp/legacy-path.sqlite3", repo_default="/tmp/default.sqlite3")
        assert resolved.path == Path("/tmp/explicit.sqlite3") and resolved.source == "env"
        del os.environ["AI_SQLITE_DB_PATH"]
        resolved_alias = resolve_runtime_path("sqlite", legacy_path="/tmp/legacy-path.sqlite3", repo_default="/tmp/default.sqlite3")
        assert resolved_alias.path == Path("/tmp/legacy.sqlite3") and resolved_alias.source == "legacy_env"
    finally:
        for key, value in (("AI_INSTANCE_DIR", previous_instance), ("AI_SQLITE_DB_PATH", previous_canonical), ("AI_SQLITE_PATH", previous_legacy)):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    print("PASS: V7.6.1 runtime hardening QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
