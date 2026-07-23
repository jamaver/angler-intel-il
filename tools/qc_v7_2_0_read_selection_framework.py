#!/usr/bin/env python3
"""Focused QC for V7.2.0 staged read-selection primitives."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.importers import import_target_profile
from persistence.migrations import migrate
from persistence.repositories import (
    JsonTargetProfileRepository,
    SQLiteTargetProfileRepository,
    read_domain,
)


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-2-0-qc-") as temp_dir:
        temp = Path(temp_dir); source = temp / "target_profile.json"; db = temp / "angler.sqlite3"
        profile = {"default_target_species": "Largemouth Bass", "current_trip_target": "Crappie", "favorite_species": ["Crappie", "Bluegill"], "updated_at": "2026-07-23T09:00:00"}
        source.write_text(json.dumps(profile), encoding="utf-8")
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            import_target_profile(conn, source)

        json_repo = JsonTargetProfileRepository(source)
        sqlite_repo = SQLiteTargetProfileRepository(db)
        assert read_domain("target_profile", json_repository=json_repo, sqlite_repository=sqlite_repo).effective_source == "json"
        assert read_domain("target_profile", json_repository=json_repo, sqlite_repository=sqlite_repo, source="sqlite").effective_source == "sqlite"
        compared = read_domain("target_profile", json_repository=json_repo, sqlite_repository=sqlite_repo, source="compare_json")
        assert compared.effective_source == "json" and compared.comparison_status == "exact"

        with connect(db) as conn, conn:
            conn.execute("UPDATE target_profiles SET legacy_payload_json = '{}' WHERE id = 'current'")
        changed = read_domain("target_profile", json_repository=json_repo, sqlite_repository=sqlite_repo, source="compare_json")
        assert changed.comparison_status == "changed" and changed.effective_source == "json"
        fallback = read_domain(
            "target_profile",
            json_repository=json_repo,
            sqlite_repository=SQLiteTargetProfileRepository(temp / "missing.sqlite3"),
            source="sqlite_with_json_fallback",
        )
        assert fallback.fallback_used and fallback.effective_source == "json" and fallback.value["current_trip_target"] == "Crappie"
        strict = read_domain(
            "target_profile",
            json_repository=json_repo,
            sqlite_repository=SQLiteTargetProfileRepository(temp / "missing.sqlite3"),
            source="sqlite",
        )
        assert strict.error and strict.value is None
    print("PASS: V7.2.0 read-selection framework QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
