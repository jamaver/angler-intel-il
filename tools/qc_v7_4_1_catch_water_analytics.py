#!/usr/bin/env python3
"""Focused QC for V7.4.1 catch and water frequency analytics."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.personal_analytics import build_catch_water_analytics


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-4-1-qc-") as temp_dir:
        db = Path(temp_dir) / "analytics.sqlite3"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            rows = [
                ("a", "2026-03-20T07:00:00", "Crappie", "Spring Lake", "Jig"),
                ("b", "2026-06-21T18:00:00", "Largemouth Bass", "Fox River", "Spinnerbait"),
                ("c", "2026-07-01T12:00:00", "Largemouth Bass", "Fox River", "Spinnerbait"),
                ("d", "2026-10-03T21:00:00", "Walleye", "Fox River", "Jig"),
                ("e", "", "Largemouth Bass", "", ""),
            ]
            for catch_id, timestamp, species, waterbody, lure in rows:
                conn.execute(
                    """INSERT INTO catches(id, timestamp, species, waterbody, lure, rig, notes, zip,
                       gear_refs_json, gear_labels_json, legacy_payload_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, '', '', '60543', '[]', '[]', '{}', ?, ?)""",
                    (catch_id, timestamp, species, waterbody, lure, timestamp, timestamp),
                )
            conn.commit()
        report = build_catch_water_analytics(db, limit=5)
        assert report["sample"]["catch_count"] == 5
        assert report["waterbody_frequency"]["rows"][0]["label"] == "Fox River"
        assert report["time_of_day"]["rows"][0]["label"] == "morning"
        assert report["seasonal_frequency"]["rows"][0]["label"] == "spring"
        assert report["seasonal_frequency"]["rows"][1]["label"] == "summer"
        assert report["missing_data"]["waterbody"] == 1
        assert not report["catch_rate_by_trip"]["available"]
        assert not report["no_catch_trip_frequency"]["available"]
        assert "deterministic trip IDs" in report["catch_rate_by_trip"]["reason"]
        with connect(db, read_only=True) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    route_source = (ROOT / "angler_analytics_v74.py").read_text(encoding="utf-8")
    assert "/api/analytics/catch-water" in route_source
    assert "Admin" not in (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    print("PASS: V7.4.1 catch and water analytics QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
