from __future__ import annotations

VERSION = "0006_v7_mirror_write_framework"
DESCRIPTION = "JSON-first mirror write operations and diagnostics"

UP_SQL = """
CREATE TABLE IF NOT EXISTS mirror_operations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    operation_id TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('running', 'success', 'failed')),
    source_write_succeeded INTEGER NOT NULL DEFAULT 1,
    mirror_write_succeeded INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 1,
    error_text TEXT,
    details_json TEXT NOT NULL DEFAULT '{}',
    started_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(domain, operation_id)
);

CREATE TABLE IF NOT EXISTS mirror_domain_status (
    domain TEXT PRIMARY KEY,
    status TEXT NOT NULL CHECK(status IN ('healthy', 'degraded', 'unavailable', 'unknown')),
    last_operation_id TEXT,
    last_success_at TEXT,
    last_failure_at TEXT,
    last_error TEXT,
    reconciliation_requested_at TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS mirror_reconciliation_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    operation_id TEXT,
    reason TEXT,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'resolved')),
    requested_at TEXT NOT NULL,
    resolved_at TEXT,
    UNIQUE(domain, operation_id, status)
);

CREATE INDEX IF NOT EXISTS idx_mirror_operations_domain_status
ON mirror_operations(domain, status, completed_at);

CREATE INDEX IF NOT EXISTS idx_mirror_reconciliation_pending
ON mirror_reconciliation_requests(domain, status, requested_at);
"""
