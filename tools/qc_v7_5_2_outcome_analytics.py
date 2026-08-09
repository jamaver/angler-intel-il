#!/usr/bin/env python3
"""Focused QC for V7.5.2 direct trip outcome analytics."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.personal_analytics import build_trip_outcome_analytics


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-5-2-qc-") as temp_dir:
        db = Path(temp_dir) / "outcomes.sqlite3"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            conn.execute("UPDATE data_authority SET authority='sqlite' WHERE domain IN ('reports', 'recommendations')")
            conn.execute("INSERT INTO trips(id, title, legacy_payload_json) VALUES ('trip-1', 'QC', '{}')")
            for report_id in ("report-1", "report-2", "report-3"):
                conn.execute("INSERT INTO trip_reports(id, trip_id, status, legacy_payload_json) VALUES (?, 'trip-1', 'active', '{}')", (report_id,))
            conn.executemany(
                """INSERT INTO trip_outcomes(trip_id, report_id, outcome, notes, legacy_payload_json, trip_occurred,
                   catch_count, followed_plan, completed_at, updated_at) VALUES ('trip-1', ?, ?, '', '{}', ?, ?, ?, ?, ?)""",
                [
                    ("report-1", "completed", 1, 2, "exact", "2026-08-01T00:00:00+00:00", "2026-08-01T00:00:00+00:00"),
                    ("report-2", "no_catch", 1, 0, "partial", "2026-08-02T00:00:00+00:00", "2026-08-02T00:00:00+00:00"),
                    ("report-3", "did_not_fish", 0, 0, "did_not_fish", "2026-08-03T00:00:00+00:00", "2026-08-03T00:00:00+00:00"),
                ],
            )
            conn.commit()
        payload = build_trip_outcome_analytics(db)
        sample = payload["sample"]
        assert sample["planned_reports"] == 3
        assert sample["completed_outcomes"] == 3
        assert sample["fished_trips"] == 2
        assert sample["did_not_fish_trips"] == 1
        assert sample["trips_with_catches"] == 1
        assert sample["no_catch_trips"] == 1
        assert sample["catch_success_percent"] == 50.0
        assert payload["notes"] and "excluded" in payload["notes"][1].lower()
        with connect(db, read_only=True) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    print("PASS: V7.5.2 outcome analytics QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
