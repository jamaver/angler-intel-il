#!/usr/bin/env python3
"""Focused QC for V7.1.3 JSON-first manual-water mirror writes."""
from __future__ import annotations

import ast
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence import water_registry
from persistence.authority import V7_AUTHORITY
from persistence.connection import connect
from persistence.manual_waters_mirror import compare_manual_waters, mirror_manual_waters
from persistence.migrations import migrate
from persistence.mirror import MirrorResult


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def fixture_waters() -> list[dict]:
    return [
        {
            "id": "manual-pond", "name": "Manual Pond", "type": "pond",
            "city": "Oswego", "county": "Kendall", "state": "IL",
            "lat": 41.68, "lon": -88.35, "species": ["Largemouth Bass"],
            "species_ids": ["largemouth_bass"], "access": ["public"],
            "habitat": ["weeds"], "notes": "Keep raw custom fields.",
            "confidence": "user-added", "manual": True, "source": "manual",
            "favorite": True, "stocked_trout": False, "catch_history_count": 2,
            "custom_metadata": {"status": "active"}, "created_at": "2026-07-22T12:00:00-05:00",
        },
        {
            "id": "manual-unmapped", "name": "Unmapped Water", "type": "creek",
            "city": "Yorkville", "state": "IL", "species": ["Crappie"],
            "notes": "Coordinates will be added later.", "manual": True, "source": "manual",
        },
    ]


def main() -> int:
    for rel in (
        "intelligence/water_registry.py",
        "persistence/manual_waters_mirror.py",
        "tools/v7_1_reconcile.py",
    ):
        ast.parse((ROOT / rel).read_text(encoding="utf-8"))

    with tempfile.TemporaryDirectory(prefix="angler-v7-1-3-qc-") as temp_dir:
        temp = Path(temp_dir)
        db = temp / "angler_intel.sqlite3"
        source = temp / "manual_waters.json"
        waters = fixture_waters()
        write_json(source, waters)
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        with connect(db) as conn:
            migrate(conn, db_path=str(db))

        first = mirror_manual_waters(source, db_path=db)
        assert first.source_write_succeeded and first.mirror_write_succeeded and not first.idempotent
        assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash, "mirror changed manual-water JSON"
        assert compare_manual_waters(source, db_path=db)["status"] == "exact"
        assert mirror_manual_waters(source, db_path=db).idempotent

        # Reconciliation must repair a mirror gap even when the JSON source
        # returns to a hash that was mirrored successfully in the past.
        with connect(db) as conn, conn:
            conn.execute("DELETE FROM waterbodies WHERE id = 'manual-pond'")
        assert compare_manual_waters(source, db_path=db)["status"] == "changed"
        repaired = mirror_manual_waters(source, db_path=db, force=True)
        assert repaired.mirror_write_succeeded and not repaired.idempotent
        assert compare_manual_waters(source, db_path=db)["status"] == "exact"

        with connect(db, read_only=True) as conn:
            rows = [dict(row) for row in conn.execute("SELECT * FROM waterbodies WHERE manual = 1 ORDER BY id")]
            assert len(rows) == 2, "coordinate-less manual waters must be retained"
            pond = next(row for row in rows if row["id"] == "manual-pond")
            unmapped = next(row for row in rows if row["id"] == "manual-unmapped")
            assert pond["name"] == "Manual Pond" and pond["favorite"] == 1
            assert pond["city"] == "Oswego" and pond["confidence"] == "user-added"
            assert json.loads(pond["legacy_payload_json"])["custom_metadata"]["status"] == "active"
            assert unmapped["lat"] is None and unmapped["lon"] is None
            status = conn.execute(
                "SELECT status, notes FROM legacy_record_map WHERE domain = 'manual_waters' AND source_key = 'manual-unmapped'"
            ).fetchone()
            assert status and status["status"] == "invalid_source" and "Coordinates" in status["notes"]
            assert conn.execute("SELECT authority FROM data_authority WHERE domain = 'manual_waters'").fetchone()[0] == V7_AUTHORITY

        # Full-document reconciliation handles favorite edits and deletion.
        edited = fixture_waters()[:1]
        edited[0]["favorite"] = False
        edited[0]["notes"] = "Updated note"
        write_json(source, edited)
        assert mirror_manual_waters(source, db_path=db).mirror_write_succeeded
        assert compare_manual_waters(source, db_path=db)["status"] == "exact"
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT COUNT(*) FROM waterbodies WHERE manual = 1").fetchone()[0] == 1
            row = conn.execute("SELECT favorite, notes FROM waterbodies WHERE id = 'manual-pond'").fetchone()
            assert row and row["favorite"] == 0 and row["notes"] == "Updated note"

        # Malformed records remain in the source and are explicitly reported.
        invalid = fixture_waters() + [{"id": "bad-no-name", "lat": 40.0, "lon": -88.0}, "not-a-water"]
        write_json(source, invalid)
        assert mirror_manual_waters(source, db_path=db).mirror_write_succeeded
        assert compare_manual_waters(source, db_path=db)["status"] == "exact"
        with connect(db, read_only=True) as conn:
            invalid_count = conn.execute(
                "SELECT COUNT(*) FROM legacy_record_map WHERE domain = 'manual_waters' AND status = 'invalid_source'"
            ).fetchone()[0]
            assert invalid_count >= 2

        # Duplicate IDs are a non-fatal mirror failure, never a silent merge.
        duplicate = fixture_waters() + [dict(fixture_waters()[0])]
        write_json(source, duplicate)
        duplicate_result = mirror_manual_waters(source, db_path=db)
        assert not duplicate_result.mirror_write_succeeded and duplicate_result.source_write_succeeded
        assert "duplicate ID" in (duplicate_result.error or "")

        # Missing SQLite is non-fatal and never creates a database or changes JSON.
        offline_source = temp / "offline_manual_waters.json"
        write_json(offline_source, fixture_waters())
        before_offline = hashlib.sha256(offline_source.read_bytes()).hexdigest()
        missing_db = temp / "missing.sqlite3"
        offline = mirror_manual_waters(offline_source, db_path=missing_db)
        assert not offline.mirror_write_succeeded and offline.source_write_succeeded and not missing_db.exists()
        assert hashlib.sha256(offline_source.read_bytes()).hexdigest() == before_offline

        # The actual registry writer saves JSON before a non-fatal mirror failure.
        original_path = water_registry.CUSTOM_WATERS_PATH
        original_mirror = water_registry.mirror_manual_waters
        try:
            writer_source = temp / "writer_manual_waters.json"
            write_json(writer_source, [])
            water_registry.CUSTOM_WATERS_PATH = writer_source
            captured: dict[str, object] = {}

            def failed_mirror(saved_path):
                captured["path"] = saved_path
                return MirrorResult("manual_waters", "fixture", True, False, error="fixture unavailable")

            water_registry.mirror_manual_waters = failed_mirror
            record = water_registry.append_custom_water_record(
                {"name": "Offline Pond", "type": "pond", "lat": 41.0, "lon": -88.0}
            )
            saved = json.loads(writer_source.read_text(encoding="utf-8"))
            assert any(item.get("id") == record["id"] for item in saved)
            assert captured["path"] == writer_source
        finally:
            water_registry.CUSTOM_WATERS_PATH = original_path
            water_registry.mirror_manual_waters = original_mirror

    print("PASS: V7.1.3 manual water mirror QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
