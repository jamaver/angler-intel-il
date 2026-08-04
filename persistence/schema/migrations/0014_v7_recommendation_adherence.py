from __future__ import annotations

VERSION = "0014_v7_recommendation_adherence"
DESCRIPTION = "Recommendation adherence records linked to completed trips"

UP_SQL = """
CREATE TABLE IF NOT EXISTS recommendation_adherence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id TEXT NOT NULL,
    trip_outcome_id INTEGER NOT NULL,
    trip_id TEXT,
    report_id TEXT NOT NULL,
    adherence TEXT NOT NULL,
    trip_occurred INTEGER NOT NULL,
    outcome TEXT NOT NULL,
    catch_count INTEGER,
    satisfaction INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(report_id),
    FOREIGN KEY(recommendation_id) REFERENCES recommendations(id) ON DELETE CASCADE,
    FOREIGN KEY(trip_outcome_id) REFERENCES trip_outcomes(id) ON DELETE CASCADE,
    FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL,
    FOREIGN KEY(report_id) REFERENCES trip_reports(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_recommendation_adherence_recommendation
ON recommendation_adherence(recommendation_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_recommendation_adherence_outcome
ON recommendation_adherence(outcome, updated_at DESC);
"""
