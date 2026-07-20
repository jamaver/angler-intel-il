#!/usr/bin/env python3
"""Focused QC for the V7.1.0 JSON-first mirror-write framework."""
from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence import app_health_v7
from persistence.authority import V7_AUTHORITY
from persistence.connection import connect
from persistence.migrations import migrate
from persistence.mirror import get_mirror_status, mirror_after_json_write


def fail(message: str) -> None:
    raise AssertionError(message)


def setup_db(path: Path) -> None:
    with connect(path) as conn:
        migrate(conn, db_path=str(path))


def set_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO app_settings(key, value_json, updated_at) VALUES(?, ?, '2026-07-20T00:00:00+00:00')",
        (key, value),
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-1-qc-") as temp_dir:
        temp = Path(temp_dir)
        db = temp / "angler_intel.sqlite3"
        setup_db(db)

        # Successful mirror callback and operation-id idempotency.
        calls = {"count": 0}

        def successful_callback(conn: sqlite3.Connection) -> None:
            calls["count"] += 1
            set_setting(conn, "mirror_qc_success", '{"ok":true}')

        first = mirror_after_json_write("target_profile", successful_callback, operation_id="target-profile-qc", db_path=db)
        assert first.source_write_succeeded and first.mirror_write_succeeded and not first.idempotent
        duplicate = mirror_after_json_write("target_profile", successful_callback, operation_id="target-profile-qc", db_path=db)
        assert duplicate.mirror_write_succeeded and duplicate.idempotent
        assert calls["count"] == 1, "successful operation retry ran the mirror callback again"

        # A failed callback must roll back its normalized writes and degrade diagnostics.
        def rollback_callback(conn: sqlite3.Connection) -> None:
            set_setting(conn, "mirror_qc_rolled_back", '{"bad":true}')
            raise RuntimeError("intentional callback failure")

        failed = mirror_after_json_write("gear_inventory", rollback_callback, operation_id="gear-qc-failure", db_path=db)
        assert failed.source_write_succeeded and not failed.mirror_write_succeeded
        assert failed.reconciliation_requested
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT 1 FROM app_settings WHERE key = 'mirror_qc_rolled_back'").fetchone() is None
            row = conn.execute("SELECT status, attempt_count FROM mirror_operations WHERE domain = 'gear_inventory' AND operation_id = 'gear-qc-failure'").fetchone()
            assert row and row["status"] == "failed"
            status = conn.execute("SELECT status, last_error FROM mirror_domain_status WHERE domain = 'gear_inventory'").fetchone()
            assert status and status["status"] == "degraded" and "intentional callback failure" in status["last_error"]
            assert any(row["domain"] == "gear_inventory" and row["status"] == "degraded" for row in get_mirror_status(conn))

        # Malformed payloads are rejected without touching SQLite.
        malformed = mirror_after_json_write("not_a_domain", successful_callback, db_path=db)
        assert not malformed.mirror_write_succeeded and "Unsupported" in (malformed.error or "")
        not_callable = mirror_after_json_write("catches", None, db_path=db)
        assert not not_callable.mirror_write_succeeded and "callable" in (not_callable.error or "")

        # Source failure and missing databases never cause a mirror database to appear.
        skipped = mirror_after_json_write("catches", successful_callback, db_path=db, source_write_succeeded=False)
        assert not skipped.source_write_succeeded and not skipped.mirror_write_succeeded
        missing_db = temp / "missing.sqlite3"
        missing = mirror_after_json_write("catches", successful_callback, db_path=missing_db)
        assert not missing.mirror_write_succeeded and not missing_db.exists()

        # A locked DB must fail safely after JSON has succeeded.
        lock_db = temp / "locked.sqlite3"
        setup_db(lock_db)
        locker = sqlite3.connect(lock_db, timeout=0)
        locker.execute("BEGIN IMMEDIATE")
        try:
            locked = mirror_after_json_write("manual_waters", successful_callback, operation_id="locked-qc", db_path=lock_db, busy_timeout_ms=20)
            assert locked.source_write_succeeded and not locked.mirror_write_succeeded
        finally:
            locker.rollback()
            locker.close()

        # App Health must show the degraded mirror status without initiating writes.
        original_data_dir = app_health_v7.DATA_DIR
        original_backup_dir = app_health_v7.BACKUP_DIR
        try:
            app_health_v7.DATA_DIR = temp
            app_health_v7.BACKUP_DIR = temp / "backups"
            health = app_health_v7.get_v7_health_for_app()
            assert health["available"] and health["mirror_summary"].get("degraded", 0) >= 1
            assert all(row["authority"] == V7_AUTHORITY for row in health["authorities"])
        finally:
            app_health_v7.DATA_DIR = original_data_dir
            app_health_v7.BACKUP_DIR = original_backup_dir

    print("PASS: V7.1.0 mirror-write framework QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
