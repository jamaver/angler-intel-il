from __future__ import annotations

VERSION = "0001_v7_migration_authority_provenance"
DESCRIPTION = "Migration authority, provenance, and validation tables"

UP_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    checksum TEXT NOT NULL,
    description TEXT NOT NULL,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS migration_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    db_path TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS data_authority (
    domain TEXT PRIMARY KEY,
    authority TEXT NOT NULL CHECK(authority = 'json'),
    source_path TEXT,
    source_hash TEXT,
    note TEXT,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    logical_name TEXT NOT NULL,
    path TEXT NOT NULL,
    file_hash TEXT,
    record_count INTEGER NOT NULL DEFAULT 0,
    source_of_truth TEXT NOT NULL DEFAULT 'json',
    generated_only INTEGER NOT NULL DEFAULT 0,
    last_seen_at TEXT NOT NULL,
    last_imported_at TEXT,
    UNIQUE(domain, path)
);

CREATE TABLE IF NOT EXISTS legacy_record_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL,
    source_path TEXT NOT NULL,
    source_key TEXT NOT NULL,
    normalized_id TEXT,
    payload_hash TEXT,
    source_hash TEXT,
    status TEXT NOT NULL DEFAULT 'mapped',
    notes TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(domain, source_path, source_key)
);

CREATE TABLE IF NOT EXISTS validation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_at TEXT NOT NULL,
    db_path TEXT NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    source_manifest_hash TEXT,
    summary_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS validation_diffs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    validation_run_id INTEGER NOT NULL,
    domain TEXT NOT NULL,
    source_path TEXT,
    record_key TEXT,
    status TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    FOREIGN KEY(validation_run_id) REFERENCES validation_runs(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS app_settings (
    key TEXT PRIMARY KEY,
    value_json TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_source_files_domain ON source_files(domain);
CREATE INDEX IF NOT EXISTS idx_legacy_record_map_domain ON legacy_record_map(domain);
CREATE INDEX IF NOT EXISTS idx_validation_runs_status ON validation_runs(status);
CREATE INDEX IF NOT EXISTS idx_validation_diffs_domain ON validation_diffs(domain);
"""

