from __future__ import annotations

VERSION = "0012_v7_recommendations_authority"
DESCRIPTION = "Register recommendation and intelligence history authority domain"

UP_SQL = """
INSERT OR IGNORE INTO data_authority(domain, authority, note, updated_at)
VALUES(
  'recommendations',
  'json',
  'Saved report JSON remains authoritative until the explicit V7.3.6 recommendation-history transition.',
  CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_intelligence_snapshots_report_id
ON intelligence_snapshots(report_id);

CREATE INDEX IF NOT EXISTS idx_recommendation_feedback_recommendation_created
ON recommendation_feedback(recommendation_id, created_at DESC);
"""
