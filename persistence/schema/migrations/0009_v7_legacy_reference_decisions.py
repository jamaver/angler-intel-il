from __future__ import annotations

VERSION = "0009_v7_legacy_reference_decisions"
DESCRIPTION = "Operator-reviewed legacy catch reference decisions"

UP_SQL = """
CREATE TABLE IF NOT EXISTS legacy_reference_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    catch_id TEXT NOT NULL,
    relationship TEXT NOT NULL CHECK(relationship IN ('gear', 'waterbody')),
    role TEXT NOT NULL DEFAULT '',
    original_reference TEXT NOT NULL,
    catch_payload_hash TEXT NOT NULL,
    decision TEXT NOT NULL CHECK(decision IN ('accepted_legacy', 'linked')),
    target_id TEXT,
    note TEXT NOT NULL,
    operator_name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(catch_id, relationship, role, original_reference),
    FOREIGN KEY(catch_id) REFERENCES catches(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_legacy_reference_decisions_catch
ON legacy_reference_decisions(catch_id, relationship, role);
"""
