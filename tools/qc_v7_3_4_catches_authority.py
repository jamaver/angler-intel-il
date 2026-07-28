#!/usr/bin/env python3
"""Focused contract QC for V7.3.4 SQLite-authoritative catches."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.catches_authority import activate_catches_authority, is_catches_sqlite_authoritative, save_catches_sqlite_authoritative
from persistence.catches_mirror import mirror_catches
from persistence.connection import connect
from persistence.gear_inventory_mirror import mirror_gear_inventory
from persistence.migrations import migrate


def write(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-4-qc-") as temp_dir:
        root = Path(temp_dir); db = root / "catches.sqlite3"; source = root / "catches.json"; gear = root / "gear.json"
        inventory = {"items": [{"id": "rod-1", "category": "rod", "brand": "QC", "model": "Rod", "display_name": "QC Rod", "status": "owned", "quantity": 1}], "maintenance": [], "catalog_cache": []}
        catches = [{"id": "catch-1", "timestamp": "2026-07-28T08:00:00", "species": "Largemouth Bass", "waterbody": "QC Pond", "gear_refs": {"rod": "rod-1"}, "gear_labels": {"rod": "QC Rod"}}]
        write(gear, inventory); write(source, catches)
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
        assert mirror_gear_inventory(inventory, gear, db_path=db).mirror_write_succeeded
        assert mirror_catches(source, db_path=db).mirror_write_succeeded
        exported = activate_catches_authority(db, source)
        assert exported == catches and is_catches_sqlite_authoritative(db)
        before = hashlib.sha256(source.read_bytes()).hexdigest()
        updated = catches + [{"id": "catch-2", "timestamp": "2026-07-28T10:00:00", "species": "Bluegill", "waterbody": "QC Creek"}]
        save_catches_sqlite_authoritative(updated, db, source, usage_events=[{"catch_id": "catch-1", "gear_item_id": "rod-1"}])
        assert json.loads(source.read_text(encoding="utf-8")) == updated
        assert hashlib.sha256(source.read_bytes()).hexdigest() != before
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT authority FROM data_authority WHERE domain='catches'").fetchone()[0] == "sqlite"
            assert conn.execute("SELECT COUNT(*) FROM catches").fetchone()[0] == 2
            assert conn.execute("SELECT COUNT(*) FROM gear_usage WHERE catch_id='catch-1'").fetchone()[0] == 1
            assert conn.execute("SELECT value_json FROM app_settings WHERE key='v7.catches.compatibility_export'").fetchone()
        blocked = mirror_catches(source, db_path=db, force=True)
        assert not blocked.mirror_write_succeeded and "SQLite-authoritative" in (blocked.error or "")
        save_catches_sqlite_authoritative([], db, source)
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT COUNT(*) FROM catches").fetchone()[0] == 0
    print("PASS: V7.3.4 catch authority QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
