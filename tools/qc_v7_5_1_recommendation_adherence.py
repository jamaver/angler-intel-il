#!/usr/bin/env python3
"""Focused QC for V7.5.1 direct recommendation adherence records."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.recommendations_authority import load_recommendation_adherence
from persistence.trip_completion import record_trip_completion


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-5-1-qc-") as temp_dir:
        db = Path(temp_dir) / "adherence.sqlite3"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            conn.execute("UPDATE data_authority SET authority='sqlite' WHERE domain='recommendations'")
            conn.execute("INSERT INTO trips(id, title, legacy_payload_json) VALUES ('trip-1', 'QC Trip', '{}')")
            conn.execute("INSERT INTO trip_reports(id, trip_id, legacy_payload_json) VALUES ('report-1', 'trip-1', '{}')")
            conn.execute("""INSERT INTO recommendations(id, target_species, reasons_json, caution_json, legacy_payload_json, created_at, updated_at)
                         VALUES ('report-1-best-bet', 'Largemouth Bass', '[]', '[]', '{}', '2026-08-04T00:00:00+00:00', '2026-08-04T00:00:00+00:00')""")
            conn.commit()
        first = record_trip_completion({"report_id": "report-1", "trip_occurred": True, "catch_count": 0, "followed_plan": "partial", "notes": "Wind changed."}, db)
        assert first["recommendation_adherence"]["status"] == "linked"
        second = record_trip_completion({"report_id": "report-1", "trip_occurred": True, "catch_count": 2, "followed_plan": "exact", "satisfaction": 5}, db)
        assert second["recommendation_adherence"]["status"] == "linked"
        loaded = load_recommendation_adherence("report-1", db)
        assert loaded and loaded["adherence"] == "exact" and loaded["catch_count"] == 2
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT count(*) FROM recommendation_adherence").fetchone()[0] == 1
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    source = (ROOT / "persistence" / "trip_completion.py").read_text(encoding="utf-8")
    assert "sync_recommendation_adherence" in source
    assert "Admin" not in (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    print("PASS: V7.5.1 recommendation adherence QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
