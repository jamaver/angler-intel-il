#!/usr/bin/env python3
"""Focused QC for V7.4.2 lure and presentation analytics."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.personal_analytics import build_lure_presentation_analytics


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-4-2-qc-") as temp_dir:
        db = Path(temp_dir) / "analytics.sqlite3"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            rows = [
                ("a", "Largemouth Bass", "Fox River", "Spinnerbait", "Steady retrieve"),
                ("b", "Largemouth Bass", "Fox River", "Spinnerbait", "Steady retrieve"),
                ("c", "Crappie", "Lake Shabbona", "Jig", "Vertical"),
                ("d", "Crappie", "Lake Shabbona", "Jig", "Vertical"),
                ("e", "Crappie", "Lake Shabbona", "", ""),
            ]
            for index, (catch_id, species, waterbody, lure, rig) in enumerate(rows):
                timestamp = f"2026-07-0{index + 1}T07:00:00"
                conn.execute(
                    """INSERT INTO catches(id, timestamp, species, waterbody, lure, rig, notes, zip,
                       gear_refs_json, gear_labels_json, legacy_payload_json, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, '', '60543', '[]', '[]', '{}', ?, ?)""",
                    (catch_id, timestamp, species, waterbody, lure, rig, timestamp, timestamp),
                )
            conn.commit()
        report = build_lure_presentation_analytics(db, limit=3)
        assert report["lure_frequency"]["rows"][0]["label"] == "Jig"
        assert report["presentation_frequency"]["rows"][0]["label"] == "Steady retrieve"
        assert report["lures_by_species"][0]["label"] == "Crappie"
        assert [row["label"] for row in report["lures_by_waterbody"][:2]] == ["Fox River", "Lake Shabbona"]
        assert report["missing_data"]["rig"] == 1
        assert not report["lure_color_performance"]["available"]
        assert not report["lure_weight_performance"]["available"]
        assert "normalized field" in report["lure_color_performance"]["reason"]
        with connect(db, read_only=True) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    route_source = (ROOT / "angler_analytics_v74.py").read_text(encoding="utf-8")
    assert "/api/analytics/lures" in route_source
    assert "Admin" not in (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    print("PASS: V7.4.2 lure and presentation analytics QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
