#!/usr/bin/env python3
"""Focused QC for V7.2.1 JSON-returning target-profile comparison reads."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.importers import import_target_profile
from persistence.migrations import migrate
import intelligence.target_profile as target_profile


def main() -> int:
    old_path = target_profile.TARGET_PROFILE_PATH
    old_mode = os.environ.get("AI_TARGET_PROFILE_READ_SOURCE")
    old_db = os.environ.get("AI_SQLITE_DB_PATH")
    old_enable = os.environ.get("AI_ENABLE_V7_STAGED_READS")
    try:
        with tempfile.TemporaryDirectory(prefix="angler-v7-2-1-qc-") as temp_dir:
            temp = Path(temp_dir); source = temp / "target.json"; db = temp / "target.sqlite3"
            payload = {"default_target_species": "Largemouth Bass", "current_trip_target": "Crappie", "favorite_species": ["Crappie", "Bluegill"], "updated_at": "2026-07-23T11:00:00"}
            source.write_text(json.dumps(payload), encoding="utf-8")
            with connect(db) as conn:
                migrate(conn, db_path=str(db)); import_target_profile(conn, source)
            target_profile.TARGET_PROFILE_PATH = source
            os.environ["AI_SQLITE_DB_PATH"] = str(db)
            os.environ["AI_TARGET_PROFILE_READ_SOURCE"] = "compare_json"
            os.environ.pop("AI_ENABLE_V7_STAGED_READS", None)
            profile = target_profile.load_target_profile()
            diagnostics = target_profile.get_target_profile_read_diagnostics()
            assert profile["current_trip_target"] == "Crappie"
            assert diagnostics["effective_source"] == "json" and diagnostics["comparison_status"] == "exact"
            os.environ["AI_TARGET_PROFILE_READ_SOURCE"] = "sqlite_with_json_fallback"
            profile = target_profile.load_target_profile()
            assert target_profile.get_target_profile_read_diagnostics()["effective_source"] == "json"
            assert profile["current_trip_target"] == "Crappie"
            os.environ["AI_ENABLE_V7_STAGED_READS"] = "1"
            profile = target_profile.load_target_profile()
            assert target_profile.get_target_profile_read_diagnostics()["effective_source"] == "sqlite"
            assert profile["current_trip_target"] == "Crappie"
            os.environ["AI_SQLITE_DB_PATH"] = str(temp / "missing.sqlite3")
            profile = target_profile.load_target_profile()
            assert target_profile.get_target_profile_read_diagnostics()["fallback_used"]
            assert profile["current_trip_target"] == "Crappie"
    finally:
        target_profile.TARGET_PROFILE_PATH = old_path
        for key, value in (("AI_TARGET_PROFILE_READ_SOURCE", old_mode), ("AI_SQLITE_DB_PATH", old_db), ("AI_ENABLE_V7_STAGED_READS", old_enable)):
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    print("PASS: V7.2.1 target-profile staged reads QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
