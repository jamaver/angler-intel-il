#!/usr/bin/env python3
"""Focused QC for V7.5.0 trip completion records and API contract."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.trip_completion import TripCompletionError, load_trip_completion, record_trip_completion


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-5-0-qc-") as temp_dir:
        db = Path(temp_dir) / "completion.sqlite3"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            conn.execute("INSERT INTO trips(id, title, legacy_payload_json) VALUES ('trip-1', 'QC Trip', '{}')")
            conn.execute("INSERT INTO trip_reports(id, trip_id, legacy_payload_json) VALUES ('report-1', 'trip-1', '{}')")
            conn.commit()
        saved = record_trip_completion({"report_id": "report-1", "trip_occurred": True, "catch_count": 0, "followed_plan": "partial", "actual_waterbody": "Fox River", "satisfaction": 4}, db)
        assert saved["outcome"] == "no_catch" and saved["trip_id"] == "trip-1"
        updated = record_trip_completion({"report_id": "report-1", "trip_occurred": True, "catch_count": 2, "followed_plan": "exact"}, db)
        assert updated["id"] == saved["id"] and updated["outcome"] == "completed"
        loaded = load_trip_completion("report-1", db)
        assert loaded and loaded["catch_count"] == 2 and loaded["followed_plan"] == "exact"
        skipped = record_trip_completion({"report_id": "report-1", "trip_occurred": False, "catch_count": 9}, db)
        assert skipped["outcome"] == "did_not_fish" and skipped["catch_count"] == 0
        try:
            record_trip_completion({"report_id": "report-1", "satisfaction": 7}, db)
        except TripCompletionError:
            pass
        else:
            raise AssertionError("invalid satisfaction accepted")
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT count(*) FROM trip_outcomes").fetchone()[0] == 1
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    template = (ROOT / "templates" / "reports.html").read_text(encoding="utf-8")
    assert "tripCompletionDialog" in template and "Complete Trip" in template
    assert "/api/trips/completion" in (ROOT / "angler_trip_completion_v75.py").read_text(encoding="utf-8")
    assert "Admin" not in (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    print("PASS: V7.5.0 trip completion QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
