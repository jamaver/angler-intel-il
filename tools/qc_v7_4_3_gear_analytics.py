#!/usr/bin/env python3
"""Focused QC for V7.4.3 read-only gear analytics."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.personal_analytics import build_gear_analytics


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-4-3-qc-") as temp_dir:
        db = Path(temp_dir) / "analytics.sqlite3"
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
            for item_id, label, category in (("rod-1", "Bass Rod", "rod"), ("lure-1", "White Spinnerbait", "lure"), ("line-1", "Braid", "line")):
                conn.execute("""INSERT INTO gear_items(id, category, display_name, status, favorite, quantity, legacy_payload_json)
                             VALUES (?, ?, ?, 'owned', 0, 1, '{}')""", (item_id, category, label))
            conn.execute("""INSERT INTO catches(id, timestamp, species, waterbody, lure, rig, notes, zip,
                         gear_refs_json, gear_labels_json, legacy_payload_json)
                         VALUES ('catch-1', '2026-07-01T07:00:00', 'Largemouth Bass', 'Fox River', 'Spinnerbait', '', '', '60543', '[]', '[]', '{}')""")
            conn.execute("INSERT INTO catch_gear(catch_id, gear_item_id, gear_role, legacy_label) VALUES ('catch-1', 'lure-1', 'lure', 'White Spinnerbait')")
            conn.execute("INSERT INTO gear_usage(gear_item_id, catch_id, used_at, notes) VALUES ('lure-1', 'catch-1', '2026-07-01T07:00:00', '')")
            conn.execute("INSERT INTO gear_maintenance(gear_item_id, maintenance_type, due_at, last_done_at, notes) VALUES ('rod-1', 'inspect guides', '2026-01-01', '', '')")
            conn.commit()
        report = build_gear_analytics(db, limit=3)
        assert report["sample"]["gear_items"] == 3
        assert report["sample"]["catch_gear_links"] == 1
        assert report["most_used"][0]["id"] == "lure-1"
        assert report["most_catch_linked"][0]["id"] == "lure-1"
        assert {item["id"] for item in report["underused"]} == {"rod-1", "line-1"}
        assert report["maintenance"]["due"][0]["id"] == "rod-1"
        assert not report["setup_outcomes"]["available"]
        with connect(db, read_only=True) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    route_source = (ROOT / "angler_analytics_v74.py").read_text(encoding="utf-8")
    assert "/api/analytics/gear" in route_source
    assert "Admin" not in (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
    print("PASS: V7.4.3 gear analytics QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
