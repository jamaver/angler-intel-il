#!/usr/bin/env python3
"""Focused QC for V7.5.1.1 authority-aware adherence hardening."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.authority_manifest import write_manifest
from persistence.connection import connect
from persistence.migrations import migrate
from persistence.trip_completion import record_trip_completion


def _seed(db: Path) -> None:
    with connect(db) as conn:
        migrate(conn, db_path=str(db))
        conn.execute("UPDATE data_authority SET authority='sqlite' WHERE domain IN ('reports', 'recommendations')")
        conn.execute("INSERT INTO trips(id, title, legacy_payload_json) VALUES ('trip-1', 'QC Trip', '{}')")
        for report_id in ("report-1", "report-2", "report-3", "report-4"):
            conn.execute("INSERT INTO trip_reports(id, trip_id, legacy_payload_json) VALUES (?, 'trip-1', '{}')", (report_id,))
        conn.execute("""INSERT INTO recommendations(id, target_species, reasons_json, caution_json, legacy_payload_json, created_at, updated_at)
                     VALUES ('report-1-best-bet', 'Largemouth Bass', '[]', '[]', '{}', '2026-08-05T00:00:00+00:00', '2026-08-05T00:00:00+00:00')""")
        conn.commit()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-5-1-1-qc-") as temp_dir:
        root = Path(temp_dir); db = root / "authority.sqlite3"; manifest = root / "authority.json"; _seed(db)
        write_manifest({"reports": "sqlite", "recommendations": "sqlite"}, manifest)
        first = record_trip_completion({"report_id": "report-1", "trip_occurred": True, "catch_count": 0, "followed_plan": "partial", "actual_trip_date": "2026-08-05"}, db, manifest_path=manifest)
        assert first["recommendation_adherence"]["status"] == "linked" and first["outcome"] == "no_catch"
        second = record_trip_completion({"report_id": "report-1", "trip_occurred": True, "catch_count": 2, "followed_plan": "exact", "actual_trip_date": "2026-08-05"}, db, manifest_path=manifest)
        assert second["completed_at"] == first["completed_at"] and second["updated_at"] >= first["completed_at"]
        missing = record_trip_completion({"report_id": "report-2", "trip_occurred": False}, db, manifest_path=manifest)
        assert missing["outcome"] == "did_not_fish" and missing["recommendation_adherence"]["status"] == "not_linked"
        write_manifest({"reports": "sqlite", "recommendations": "json"}, manifest)
        conflict = record_trip_completion({"report_id": "report-3", "trip_occurred": True, "catch_count": 1}, db, manifest_path=manifest)
        assert conflict["recommendation_adherence"]["status"] == "unavailable"
        assert conflict["recommendation_adherence"]["effective_authority"] == "conflict"
        assert not Path(temp_dir, "missing.json").exists()
        absent = record_trip_completion({"report_id": "report-4", "trip_occurred": True}, db, manifest_path=root / "missing.json")
        assert absent["recommendation_adherence"]["status"] == "unavailable"
        manifest.write_text("{broken", encoding="utf-8")
        malformed = record_trip_completion({"report_id": "report-2", "trip_occurred": True}, db, manifest_path=manifest)
        assert malformed["recommendation_adherence"]["status"] == "unavailable"
        with connect(db) as conn:
            assert conn.execute("SELECT count(*) FROM trip_outcomes").fetchone()[0] == 4
            assert conn.execute("SELECT count(*) FROM recommendation_adherence").fetchone()[0] == 1
            try:
                conn.execute("INSERT INTO trip_outcomes(report_id, outcome, legacy_payload_json, trip_occurred, followed_plan, catch_count, completed_at, updated_at) VALUES ('report-1', 'bad', '{}', 2, 'bad', -1, 'x', 'x')")
            except Exception:
                pass
            else:
                raise AssertionError("database validation trigger accepted invalid outcome")
        with connect(db, read_only=True) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    app_health = (ROOT / "intelligence" / "app_health_v7.py").read_text(encoding="utf-8")
    assert "recommendation_adherence" in app_health
    print("PASS: V7.5.1.1 adherence hardening QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
