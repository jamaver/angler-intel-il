from __future__ import annotations

VERSION = "0013_v7_trip_completion"
DESCRIPTION = "Structured trip completion and outcome fields"

UP_SQL = """
ALTER TABLE trip_outcomes ADD COLUMN trip_occurred INTEGER NOT NULL DEFAULT 1;
ALTER TABLE trip_outcomes ADD COLUMN actual_waterbody TEXT;
ALTER TABLE trip_outcomes ADD COLUMN actual_target_species TEXT;
ALTER TABLE trip_outcomes ADD COLUMN started_at TEXT;
ALTER TABLE trip_outcomes ADD COLUMN ended_at TEXT;
ALTER TABLE trip_outcomes ADD COLUMN followed_plan TEXT;
ALTER TABLE trip_outcomes ADD COLUMN catch_count INTEGER;
ALTER TABLE trip_outcomes ADD COLUMN satisfaction INTEGER;
ALTER TABLE trip_outcomes ADD COLUMN gear_refs_json TEXT;
ALTER TABLE trip_outcomes ADD COLUMN completed_at TEXT;
ALTER TABLE trip_outcomes ADD COLUMN updated_at TEXT;

CREATE INDEX IF NOT EXISTS idx_trip_outcomes_report_completed
ON trip_outcomes(report_id, completed_at DESC);

CREATE INDEX IF NOT EXISTS idx_trip_outcomes_trip_completed
ON trip_outcomes(trip_id, completed_at DESC);
"""
