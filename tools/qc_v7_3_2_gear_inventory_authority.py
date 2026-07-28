#!/usr/bin/env python3
"""QC for the V7.3.2 Gear Locker authority contract."""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from persistence.connection import connect
from persistence.gear_inventory_authority import (
    activate_gear_inventory_authority,
    is_gear_inventory_sqlite_authoritative,
    save_gear_inventory_sqlite_authoritative,
)
from persistence.gear_inventory_mirror import mirror_gear_inventory
from persistence.migrations import migrate


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="angler-v7-3-2-qc-") as temp_dir:
        root = Path(temp_dir)
        db = root / "gear.sqlite3"
        source = root / "gear_inventory.json"
        inventory = {
            "version": "fixture",
            "updated_at": "2026-07-27T20:00:00-05:00",
            "items": [{"id": "rod-1", "category": "rod", "brand": "Fixture", "model": "Rod", "status": "owned", "favorite": True, "length_ft": 7.0}],
            "maintenance": [],
            "catalog_cache": [],
        }
        source.write_text(json.dumps(inventory), encoding="utf-8")
        with connect(db) as conn:
            migrate(conn, db_path=str(db))
        assert mirror_gear_inventory(inventory, source, db_path=db).mirror_write_succeeded
        assert activate_gear_inventory_authority(db, source) == inventory
        assert is_gear_inventory_sqlite_authoritative(db)
        changed = dict(inventory)
        changed["items"] = [dict(inventory["items"][0], status="retired", favorite=False)]
        changed["updated_at"] = "2026-07-27T20:01:00-05:00"
        assert save_gear_inventory_sqlite_authoritative(changed, db, source) == changed
        assert json.loads(source.read_text(encoding="utf-8")) == changed
        blocked = mirror_gear_inventory(changed, source, db_path=db)
        assert not blocked.mirror_write_succeeded and "SQLite-authoritative" in (blocked.error or "")
        with connect(db, read_only=True) as conn:
            assert conn.execute("SELECT authority FROM data_authority WHERE domain='gear_inventory'").fetchone()[0] == "sqlite"
            assert conn.execute("SELECT status FROM gear_items WHERE id='rod-1'").fetchone()[0] == "retired"
            assert '"status":"ok"' in conn.execute("SELECT value_json FROM app_settings WHERE key='v7.gear_inventory.compatibility_export'").fetchone()[0]
    print("PASS: V7.3.2 gear inventory authority QC")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
