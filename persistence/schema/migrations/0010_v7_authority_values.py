from __future__ import annotations

VERSION = "0010_v7_authority_values"
DESCRIPTION = "Permit explicit per-domain SQLite authority states"

UP_SQL = """
CREATE TABLE data_authority_v7_3 (
    domain TEXT PRIMARY KEY,
    authority TEXT NOT NULL CHECK(authority IN ('json', 'sqlite_mirror', 'sqlite')),
    source_path TEXT,
    source_hash TEXT,
    note TEXT,
    updated_at TEXT NOT NULL
);

INSERT INTO data_authority_v7_3(domain, authority, source_path, source_hash, note, updated_at)
SELECT domain, authority, source_path, source_hash, note, updated_at FROM data_authority;

DROP TABLE data_authority;
ALTER TABLE data_authority_v7_3 RENAME TO data_authority;
"""
