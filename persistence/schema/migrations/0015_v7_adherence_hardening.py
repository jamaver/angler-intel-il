from __future__ import annotations

VERSION = "0015_v7_adherence_hardening"
DESCRIPTION = "Trip completion date and validation guardrails"

UP_SQL = """
ALTER TABLE trip_outcomes ADD COLUMN actual_trip_date TEXT;

CREATE TRIGGER IF NOT EXISTS trg_trip_outcomes_validate_insert
BEFORE INSERT ON trip_outcomes
BEGIN
  SELECT CASE WHEN NEW.outcome NOT IN ('completed', 'no_catch', 'did_not_fish') THEN RAISE(ABORT, 'invalid trip outcome') END;
  SELECT CASE WHEN NEW.trip_occurred NOT IN (0, 1) THEN RAISE(ABORT, 'trip_occurred must be 0 or 1') END;
  SELECT CASE WHEN NEW.catch_count IS NOT NULL AND NEW.catch_count < 0 THEN RAISE(ABORT, 'catch_count cannot be negative') END;
  SELECT CASE WHEN NEW.satisfaction IS NOT NULL AND NEW.satisfaction NOT BETWEEN 1 AND 5 THEN RAISE(ABORT, 'satisfaction must be 1 to 5') END;
  SELECT CASE WHEN NEW.followed_plan NOT IN ('exact', 'partial', 'substituted', 'changed_water', 'changed_target', 'unknown', 'did_not_fish') THEN RAISE(ABORT, 'invalid followed_plan') END;
END;

CREATE TRIGGER IF NOT EXISTS trg_trip_outcomes_validate_update
BEFORE UPDATE ON trip_outcomes
BEGIN
  SELECT CASE WHEN NEW.outcome NOT IN ('completed', 'no_catch', 'did_not_fish') THEN RAISE(ABORT, 'invalid trip outcome') END;
  SELECT CASE WHEN NEW.trip_occurred NOT IN (0, 1) THEN RAISE(ABORT, 'trip_occurred must be 0 or 1') END;
  SELECT CASE WHEN NEW.catch_count IS NOT NULL AND NEW.catch_count < 0 THEN RAISE(ABORT, 'catch_count cannot be negative') END;
  SELECT CASE WHEN NEW.satisfaction IS NOT NULL AND NEW.satisfaction NOT BETWEEN 1 AND 5 THEN RAISE(ABORT, 'satisfaction must be 1 to 5') END;
  SELECT CASE WHEN NEW.followed_plan NOT IN ('exact', 'partial', 'substituted', 'changed_water', 'changed_target', 'unknown', 'did_not_fish') THEN RAISE(ABORT, 'invalid followed_plan') END;
END;
"""
