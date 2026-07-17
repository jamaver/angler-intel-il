from __future__ import annotations

import importlib
import pkgutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from .canonical_json import canonical_dumps
from .connection import connect


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _schema_package() -> str:
    return "persistence.schema.migrations"


@dataclass(slots=True)
class Migration:
    version: str
    description: str
    checksum: str
    sql: str


def _normalize_sql(sql: str) -> str:
    lines = [line.rstrip() for line in sql.strip().splitlines()]
    return "\n".join(lines).strip() + "\n"


def list_migrations() -> list[Migration]:
    package = importlib.import_module(_schema_package())
    migrations: list[Migration] = []
    for module_info in sorted(pkgutil.iter_modules(package.__path__), key=lambda item: item.name):
        if not module_info.name[0].isdigit():
            continue
        module = importlib.import_module(f"{_schema_package()}.{module_info.name}")
        sql = _normalize_sql(getattr(module, "UP_SQL", ""))
        migrations.append(
            Migration(
                version=str(getattr(module, "VERSION", module_info.name)),
                description=str(getattr(module, "DESCRIPTION", module_info.name)),
                checksum=__import__("hashlib").sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )
    return migrations


def migration_checksums() -> dict[str, str]:
    return {migration.version: migration.checksum for migration in list_migrations()}


def ensure_metadata_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
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
        """
    )
    conn.commit()


def _already_applied(conn: sqlite3.Connection, version: str) -> str | None:
    row = conn.execute("SELECT checksum FROM schema_migrations WHERE version = ?", (version,)).fetchone()
    return str(row["checksum"]) if row else None


def apply_migration(
    conn: sqlite3.Connection,
    migration: Migration,
    *,
    mode: str = "apply",
    db_path: str = "",
) -> None:
    current = _already_applied(conn, migration.version)
    if current is not None and current != migration.checksum:
        raise RuntimeError(f"Migration checksum changed for {migration.version}")
    if current is not None:
        return

    with conn:
        conn.executescript(migration.sql)
        conn.execute(
            """
            INSERT INTO schema_migrations(version, checksum, description, applied_at)
            VALUES(?, ?, ?, ?)
            """,
            (migration.version, migration.checksum, migration.description, utc_now()),
        )
        conn.execute(
            """
            INSERT INTO migration_runs(run_at, db_path, mode, status, details_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            (utc_now(), db_path, mode, "ok", canonical_dumps({"version": migration.version})),
        )


def migrate(conn: sqlite3.Connection, *, db_path: str = "") -> list[str]:
    ensure_metadata_schema(conn)
    applied: list[str] = []
    for migration in list_migrations():
        current = _already_applied(conn, migration.version)
        if current is not None and current != migration.checksum:
            raise RuntimeError(f"Migration checksum changed for {migration.version}")
        if current is None:
            apply_migration(conn, migration, db_path=db_path)
            applied.append(migration.version)
    return applied
