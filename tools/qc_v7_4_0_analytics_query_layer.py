#!/usr/bin/env python3
"""Focused QC for the V7.4.0 read-only personal analytics query layer."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.personal_analytics import AnalyticsInputError, build_catch_water_analytics, build_personal_analytics


def _insert(conn, catch_id, timestamp, species, waterbody, lure):
    conn.execute(
        """INSERT INTO catches(id, timestamp, species, waterbody, lure, rig, notes, zip,
           gear_refs_json, gear_labels_json, legacy_payload_json, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, '', '', '60543', '[]', '[]', '{}', ?, ?)""",
        (catch_id, timestamp, species, waterbody, lure, timestamp, timestamp),
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-4-0-qc-") as temp_dir:
        db = Path(temp_dir) / "analytics.sqlite3"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            samples = [
                ("c1", "2026-07-01T06:30:00", "Largemouth Bass", "Fox River", "Spinnerbait"),
                ("c2", "2026-07-01T18:30:00", "Largemouth Bass", "Fox River", "Jig"),
                ("c3", "2026-07-02T12:00:00", "Crappie", "Lake Shabbona", "Jig"),
                ("c4", "2026-07-03T21:00:00", "Largemouth Bass", "Fox River", "Spinnerbait"),
                ("c5", "2026-07-04T07:30:00", "Bluegill", "Lake Shabbona", "Bobber"),
                ("c6", "2026-07-05T14:00:00", "Largemouth Bass", "Fox River", "Spinnerbait"),
                ("c7", "2026-07-06T17:00:00", "Crappie", "Lake Shabbona", "Jig"),
                ("c8", "", "", "", ""),
            ]
            for sample in samples:
                _insert(conn, *sample)
            conn.commit()
            before = conn.execute("SELECT count(*) FROM catches").fetchone()[0]
        summary = build_personal_analytics(db, limit=3)
        assert summary["sample"]["catch_count"] == 8
        assert summary["sample"]["quality"] == "solid"
        assert summary["top_species"][0] == {"label": "Largemouth Bass", "count": 4, "share_percent": 50.0}
        assert summary["top_waterbodies"][0]["label"] == "Fox River"
        assert [row["label"] for row in summary["top_lures"][:2]] == ["Jig", "Spinnerbait"]
        assert summary["missing_data"]["timestamp"] == 1
        assert any("Frequency summaries" in note for note in summary["notes"])
        filtered = build_personal_analytics(db, date_from="2026-07-02", date_to="2026-07-05", species="Largemouth Bass")
        assert filtered["sample"]["catch_count"] == 2
        catch_water = build_catch_water_analytics(db, limit=3)
        assert catch_water["waterbody_frequency"]["rows"][0]["label"] == "Fox River"
        assert catch_water["time_of_day"]["available"]
        assert catch_water["seasonal_frequency"]["rows"][1]["label"] == "summer"
        assert not catch_water["catch_rate_by_trip"]["available"]
        assert not catch_water["no_catch_trip_frequency"]["available"]
        try:
            build_personal_analytics(db, date_from="not-a-date")
        except AnalyticsInputError:
            pass
        else:
            raise AssertionError("invalid date was accepted")
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT count(*) FROM catches").fetchone()[0] == before
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    app_text = (ROOT / "app.py").read_text(encoding="utf-8")
    assert "register_analytics_routes_v74" in app_text
    assert "catch-water" in (ROOT / "angler_analytics_v74.py").read_text(encoding="utf-8")
    assert "Admin" not in (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    print("PASS: V7.4.0 analytics query layer QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
