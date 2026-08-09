#!/usr/bin/env python3
"""Focused QC for V7.5.3 shadow-only personal intelligence."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.migrations import migrate
from persistence.personal_analytics import build_shadow_personal_intelligence


def _seed(db: Path, rows: list[tuple[int, int, str]]) -> None:
    with connect(db) as conn:
        migrate(conn, db_path=str(db))
        conn.execute("INSERT INTO trips(id, title, legacy_payload_json) VALUES ('trip-1', 'QC', '{}')")
        for index, (occurred, catches, adherence) in enumerate(rows, 1):
            report_id = f"report-{index}"
            conn.execute("INSERT INTO trip_reports(id, trip_id, status, legacy_payload_json) VALUES (?, 'trip-1', 'active', '{}')", (report_id,))
            conn.execute(
                """INSERT INTO trip_outcomes(trip_id, report_id, outcome, notes, legacy_payload_json, trip_occurred,
                   catch_count, followed_plan, completed_at, updated_at) VALUES ('trip-1', ?, 'completed', '', '{}', ?, ?, ?, ?, ?)""",
                (report_id, occurred, catches, adherence, f"2026-08-{index:02d}T00:00:00+00:00", f"2026-08-{index:02d}T00:00:00+00:00"),
            )
        conn.commit()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-5-3-qc-") as temp_dir:
        db = Path(temp_dir) / "shadow.sqlite3"
        _seed(db, [(1, 1, "exact"), (1, 0, "partial"), (0, 0, "did_not_fish")])
        sparse = build_shadow_personal_intelligence(db)
        assert sparse["evidence_count"] == 2
        assert sparse["proposed_adjustment"] == 0
        assert sparse["live_ranking_changed"] is False
        assert sparse["sample_quality"] == "none"

        db2 = Path(temp_dir) / "shadow-enough.sqlite3"
        _seed(db2, [(1, 1, "exact")] * 8 + [(1, 0, "changed_water"), (0, 0, "did_not_fish")])
        eligible = build_shadow_personal_intelligence(db2)
        assert eligible["evidence_count"] == 8
        assert eligible["sample_quality"] == "eligible_for_later_review"
        assert -5 <= eligible["proposed_adjustment"] <= 5
        assert eligible["excluded_outcomes"] == 2
        with connect(db2, read_only=True) as conn:
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert list(conn.execute("PRAGMA foreign_key_check")) == []
    source = (ROOT / "persistence" / "personal_analytics.py").read_text(encoding="utf-8")
    assert "live_ranking_changed\": False" in source
    print("PASS: V7.5.3 shadow personal intelligence QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
