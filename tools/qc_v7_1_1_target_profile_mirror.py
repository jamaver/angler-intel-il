#!/usr/bin/env python3
"""Focused QC for V7.1.1 target-profile JSON-first mirror writes."""
from __future__ import annotations

import ast
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence import target_profile
from persistence.authority import V7_AUTHORITY
from persistence.connection import connect
from persistence.migrations import migrate
from persistence.mirror import MirrorResult
from persistence.target_profile_mirror import compare_target_profile, mirror_target_profile


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def seed_species(conn, species_id: str, name: str) -> None:
    conn.execute(
        """
        INSERT INTO species(id, name, group_name, tier, enabled, legacy_payload_json, source_path, source_hash, source_key)
        VALUES(?, ?, '', '', 1, '{}', 'fixture', 'fixture', ?)
        """,
        (species_id, name, species_id),
    )


def main() -> int:
    ast.parse((ROOT / "app.py").read_text(encoding="utf-8"))
    ast.parse((ROOT / "intelligence" / "target_profile.py").read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="angler-v7-1-1-qc-") as temp_dir:
        temp = Path(temp_dir)
        db = temp / "angler_intel.sqlite3"
        source = temp / "target_profile.json"
        profile = {
            "default_target_species": "Largemouth Bass",
            "current_trip_target": "Crappie",
            "favorite_species": ["Crappie", "Largemouth Bass"],
            "updated_at": "2026-07-21T12:00:00-05:00",
        }
        write_json(source, profile)
        before_hash = hashlib.sha256(source.read_bytes()).hexdigest()

        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            seed_species(conn, "largemouth-bass", "Largemouth Bass")
            seed_species(conn, "crappie", "Crappie")

        first = mirror_target_profile(profile, source, db_path=db)
        assert first.source_write_succeeded and first.mirror_write_succeeded and not first.idempotent
        assert hashlib.sha256(source.read_bytes()).hexdigest() == before_hash, "mirror changed authoritative JSON"
        assert compare_target_profile(profile, db_path=db)["status"] == "exact"

        with connect(db, read_only=True) as conn:
            row = conn.execute("SELECT * FROM target_profiles WHERE id = 'current'").fetchone()
            assert row and row["default_target_species"] == "Largemouth Bass"
            assert row["current_trip_target"] == "Crappie"
            assert json.loads(row["favorite_species_json"]) == ["Crappie", "Largemouth Bass"]
            preferences = [dict(row) for row in conn.execute("SELECT species_id, preference FROM target_profile_species ORDER BY preference")]
            assert preferences == [
                {"species_id": "crappie", "preference": "favorite-1"},
                {"species_id": "largemouth-bass", "preference": "favorite-2"},
            ]
            authority = conn.execute("SELECT authority FROM data_authority WHERE domain = 'target_profile'").fetchone()
            assert authority and authority["authority"] == V7_AUTHORITY
            assert conn.execute("SELECT 1 FROM source_files WHERE domain = 'target_profile'").fetchone()
            assert conn.execute("SELECT 1 FROM legacy_record_map WHERE domain = 'target_profile'").fetchone()

        duplicate = mirror_target_profile(profile, source, db_path=db)
        assert duplicate.mirror_write_succeeded and duplicate.idempotent

        # Current-trip reset and favorite removal replace the complete mirror state.
        reset_profile = {
            "default_target_species": "Largemouth Bass",
            "current_trip_target": "",
            "favorite_species": ["Largemouth Bass"],
            "updated_at": "2026-07-21T12:05:00-05:00",
        }
        write_json(source, reset_profile)
        assert mirror_target_profile(reset_profile, source, db_path=db).mirror_write_succeeded
        assert compare_target_profile(reset_profile, db_path=db)["status"] == "exact"
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT current_trip_target FROM target_profiles WHERE id = 'current'").fetchone()[0] == ""
            assert conn.execute("SELECT COUNT(*) FROM target_profile_species WHERE target_profile_id = 'current'").fetchone()[0] == 1

        # SQLite failure is non-fatal and never changes the source file.
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        missing = mirror_target_profile(reset_profile, source, db_path=temp / "missing.sqlite3")
        assert not missing.mirror_write_succeeded and missing.source_write_succeeded
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash

        # The production writer saves JSON before calling the non-fatal mirror hook.
        original_path = target_profile.TARGET_PROFILE_PATH
        original_mirror = target_profile.mirror_target_profile
        original_db = os.environ.get("AI_SQLITE_DB_PATH")
        captured: dict[str, object] = {}
        try:
            target_profile.TARGET_PROFILE_PATH = source
            # This QC validates the V7.1 JSON-authoritative writer, even when
            # the live application has later transitioned this domain.
            os.environ["AI_SQLITE_DB_PATH"] = str(db)

            def failed_mirror(saved_profile, saved_path):
                captured["profile"] = saved_profile
                captured["path"] = saved_path
                return MirrorResult("target_profile", "fixture", True, False, error="fixture unavailable")

            target_profile.mirror_target_profile = failed_mirror
            saved = target_profile.save_target_profile({"favorite_species_add": "Crappie"})
            assert json.loads(source.read_text(encoding="utf-8")) == saved
            assert captured["profile"] == saved and captured["path"] == source
        finally:
            target_profile.TARGET_PROFILE_PATH = original_path
            target_profile.mirror_target_profile = original_mirror
            if original_db is None:
                os.environ.pop("AI_SQLITE_DB_PATH", None)
            else:
                os.environ["AI_SQLITE_DB_PATH"] = original_db

    print("PASS: V7.1.1 target-profile mirror QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
