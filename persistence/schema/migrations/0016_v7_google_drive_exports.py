from __future__ import annotations

VERSION = "0016_v7_google_drive_exports"
DESCRIPTION = "Durable secondary cloud export queue"

UP_SQL = """
CREATE TABLE IF NOT EXISTS cloud_exports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    provider TEXT NOT NULL,
    object_type TEXT NOT NULL,
    object_id TEXT NOT NULL,
    local_path TEXT NOT NULL,
    remote_path TEXT NOT NULL,
    local_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'uploading', 'ok', 'failed')),
    attempt_count INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    UNIQUE(provider, object_type, object_id, remote_path)
);

CREATE INDEX IF NOT EXISTS idx_cloud_exports_status ON cloud_exports(provider, status, updated_at);
CREATE INDEX IF NOT EXISTS idx_cloud_exports_object ON cloud_exports(provider, object_type, object_id);
"""
