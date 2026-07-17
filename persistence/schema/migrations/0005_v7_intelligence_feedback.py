from __future__ import annotations

VERSION = "0005_v7_intelligence_feedback"
DESCRIPTION = "Intelligence snapshots, recommendations, and feedback tables"

UP_SQL = """
CREATE TABLE IF NOT EXISTS intelligence_snapshots (
    id TEXT PRIMARY KEY,
    trip_id TEXT,
    report_id TEXT,
    zip TEXT,
    target_species TEXT,
    source_path TEXT,
    source_hash TEXT,
    summary_json TEXT NOT NULL,
    legacy_payload_json TEXT NOT NULL,
    created_at TEXT,
    FOREIGN KEY(trip_id) REFERENCES trips(id) ON DELETE SET NULL,
    FOREIGN KEY(report_id) REFERENCES trip_reports(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    intelligence_snapshot_id TEXT,
    target_species TEXT,
    lure_type TEXT,
    lure_label TEXT,
    fit_label TEXT,
    score REAL,
    confidence TEXT,
    reasons_json TEXT NOT NULL,
    caution_json TEXT NOT NULL,
    legacy_payload_json TEXT NOT NULL,
    created_at TEXT,
    updated_at TEXT,
    FOREIGN KEY(intelligence_snapshot_id) REFERENCES intelligence_snapshots(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recommendation_explanations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id TEXT NOT NULL,
    explanation_type TEXT NOT NULL,
    body TEXT NOT NULL,
    source_path TEXT,
    FOREIGN KEY(recommendation_id) REFERENCES recommendations(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id TEXT NOT NULL,
    feedback_type TEXT NOT NULL,
    rating INTEGER,
    notes TEXT,
    created_at TEXT,
    FOREIGN KEY(recommendation_id) REFERENCES recommendations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_recommendations_species ON recommendations(target_species);
CREATE INDEX IF NOT EXISTS idx_recommendations_confidence ON recommendations(confidence);
"""

